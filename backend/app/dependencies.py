import bson
from fastapi import HTTPException, Depends, APIRouter, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from .routers import user
from .dbclient import DbClient

SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ADMIN_KEY = os.getenv("ADMIN_KEY", "1234")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# get db and redis
db_client = DbClient()
db = db_client.db
redis_client = db_client.redis_client

# OAuth2 Setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Passwort-Kontext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    tags=["user"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

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
def get_user(username: str):
    user_dict = db["users"].find_one({"username": username})
    if user_dict:
        return UserInDB(**user_dict)
    return None

# **Benutzer in `users`-Collection speichern**
def create_user(username: str, fullname: str, email: str, password: str, admin_key: str):
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin key wrong")

    user = UserInDB(
        username=username,
        full_name=fullname,
        email=email,
        hashed_password=pwd_context.hash(password),
        disabled=False
    )
    
    db["users"].insert_one(user.model_dump())
    return user

# **Benutzer aus `users`-Collection löschen**
def delete_user_in_db(username: str):
    result = db["users"].delete_one({"username": username})

    collections_to_delete = db.users_collections.find({"owner": username})

    # delete owned collections
    for col in list(collections_to_delete):
        db.drop_collection(col["id"])

    db.users_collections.delete_many({"owner": username})

    # delete user from collection list
    db.users_collections.update_many(
        {"users": username},  # Alle Dokumente finden, in denen der Benutzer existiert
        {"$pull": {"users": username}}  # Benutzer aus der `users`-Liste entfernen
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

# Authentifizierung überprüfen
def authenticate_user(username: str, password: str):
    user = get_user(username)
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
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: user.User = Depends(get_current_user)) -> UserInDB:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

## endpoints

# Geschützter Endpunkt
@router.get("/user/me", response_model=user.User)
async def read_users_me(current_user: user.User = Depends(get_current_active_user)):
    return current_user

# Neuen Nutzer anlegen
@router.post("/user/sign_up", response_model=Token)
async def sign_up_for_access_token(username: str, fullname: str, email: str, password: str, admin_key: str):
    user = get_user(username)
    if user == None:
        user = create_user(username, fullname, email, password, admin_key)
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Nutzer entfernen
@router.post("/user/delete")
async def delete_user(username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    delete_user_in_db(username)
    return {"message": "user deleted"}

# Authentifizierung: Token-Endpunkt
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}