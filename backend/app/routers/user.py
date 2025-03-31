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

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    