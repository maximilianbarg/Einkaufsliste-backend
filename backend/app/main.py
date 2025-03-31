from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Annotated
from .routers import user, collections, websockets, shared_collections
from .dependencies import user, router, get_current_active_user

User = user.User

# FastAPI-Anwendung erstellen
app = FastAPI()

app.include_router(router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------

# Root-Endpunkt
@app.get("/")
def root():
    return {"message": "Einkaufsliste Backend is running!"}
