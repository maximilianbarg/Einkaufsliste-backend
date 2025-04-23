import bson
from fastapi import HTTPException, Depends, APIRouter, status, Form, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

from .logger_manager import LoggerManager
from .routers import user
from app.dbclient import DbClient
from pymongo.database import Database

SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ADMIN_KEY = os.getenv("ADMIN_KEY", "1234")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# get db and redis
db_client = DbClient()

def get_db():
    return db_client.db

def get_redis():
    return db_client.redis_client

# OAuth2 Setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Passwort-Kontext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    tags=["user"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

logger_instance = LoggerManager()
logger = logger_instance.get_logger()

## classes

# Modelle
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserInDB(user.User):
    hashed_password: str

## helper methods

# Passwort-Hash überprüfen
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# **Benutzer aus `users`-Collection abrufen**
async def get_user(username: str):
    user_dict = await get_db()["users"].find_one({"username": username})
    if user_dict:
        return UserInDB(**user_dict)
    return None

# **Benutzer in `users`-Collection speichern**
async def create_user(username: str, fullname: str, email: str, password: str, admin_key: str):
    if admin_key != ADMIN_KEY:
        logger.warning(f"admin key {admin_key} wrong")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin key wrong")

    user = UserInDB(
        username=username,
        full_name=fullname,
        email=email,
        hashed_password=pwd_context.hash(password),
        disabled=False
    )

    await get_db()["users"].insert_one(user.model_dump())
    return user

# **Benutzer aus `users`-Collection löschen**
async def delete_user_in_db(username: str):
    db = get_db()
    result = await db["users"].delete_one({"username": username})

    collections_to_delete = db.users_collections.find({"owner": username})

    # delete owned collections
    async for col in collections_to_delete:
        await db.drop_collection(col["id"])

    await db.users_collections.delete_many({"owner": username})

    # delete user from collection list
    await db.users_collections.update_many(
        {"users": username},  # Alle Dokumente finden, in denen der Benutzer existiert
        {"$pull": {"users": username}}  # Benutzer aus der `users`-Liste entfernen
    )

    if result.deleted_count == 0:
        logger.warning(f"user {username} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

# Authentifizierung überprüfen
async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# JWT-Token erstellen
def create_access_token(data: dict, expires_delta: Optional[int] = None):
    to_encode = data.copy()
    if expires_delta:
        to_encode.update({"exp": expires_delta})
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Benutzerinformationen aus Token extrahieren
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    return await extract_token(token)

async def extract_token(token: str) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        logger.warning(f"Could not validate credentials")
        raise credentials_exception
    
    user = await get_user(username=token_data.username)
    if user is None:
        logger.warning(f"Could not validate credentials")
        raise credentials_exception
    return user

async def get_current_active_user(current_user: user.User = Depends(get_current_user)) -> UserInDB:
    if current_user.disabled:
        logger.warning(f"user {current_user.username} disabled. Tried to login")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

## endpoints

# Geschützter Endpunkt
@router.get("/user/all")
async def read_users_me(current_user: user.User = Depends(get_current_active_user), db: Database = Depends(get_db)):
    users = []

    async for user in db["users"].find():
        del user["_id"]
        del user["disabled"]
        del user["hashed_password"]
        users.append(user)

    return users

@router.get("/user/me", response_model=user.User)
async def read_users_me(current_user: user.User = Depends(get_current_active_user)):
    return current_user

# Neuen Nutzer anlegen
@router.post("/user/sign_up", response_model=Token)
async def sign_up_for_access_token(username: str = Form(...), fullname: str = Form(...), email: str = Form(...), password: str = Form(...), admin_key: str = Form(...)):
    user = await get_user(username)
    if user == None:
        user = await create_user(username, fullname, email, password, admin_key)
    else:
        logger.warning(f"username {username} already exists")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )
    
    logger.info(f"user {username} created")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Nutzer entfernen
@router.post("/user/delete")
async def delete_user(background_tasks: BackgroundTasks, username: str = Form(...), password: str = Form(...)):
    user = await authenticate_user(username, password)
    if not user:
        logger.warning(f"user {username} could not be deleted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    background_tasks.add_task(delete_user_in_db, username)

    logger.info(f"user {username} deleted")
    return {"message": "user deleted"}

# Authentifizierung: Token-Endpunkt
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"wrong password for user {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}