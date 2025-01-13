from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
import redis
import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Annotated
from .routers import user


SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 Setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Passwort-Kontext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Benutzerdatenbank simuliert
fake_users_db = {
    "user1": {
        "username": "user1",
        "full_name": "User One",
        "email": "user1@example.com",
        "hashed_password": pwd_context.hash("password1"),
        "disabled": False,
    }
}

router = APIRouter()

# Modelle
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserInDB(user.User):
    hashed_password: str

# Passwort-Hash überprüfen
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Benutzer abrufen
def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

# Authentifizierung überprüfen
def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
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
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=401,
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
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: user.User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Geschützter Endpunkt
@router.get("/users/me", response_model=user.User)
async def read_users_me(current_user: user.User = Depends(get_current_active_user)):
    return current_user

# Authentifizierung: Token-Endpunkt
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
