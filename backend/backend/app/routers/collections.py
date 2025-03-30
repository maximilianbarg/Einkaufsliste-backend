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
from ..dependencies import user, get_current_active_user

router = APIRouter(
    prefix="/private",
    tags=["private"],
    dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}},
)

User = user.User

# Umgebungsvariablen abrufen
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "my_database")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = mongo_client[os.getenv("MONGO_DATABASE", "my_database")]

# Redis-Client einrichten
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)


# MongoDB: Tabelle dynamisch erstellen
@router.post("/create/{collection_name}")
def create_table(collection_name: str, current_user: User = Depends(get_current_active_user)):
    if collection_name in db.list_collection_names():
        raise HTTPException(status_code=400, detail="Collection already exists")
    db.create_collection(collection_name)
    return {"message": f"Collection '{collection_name}' created successfully"}

# MongoDB-Methoden aktualisieren
@router.get("/{collection_name}/items")
async def get_items(collection_name: str, current_user: User = Depends(get_current_active_user)):
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{collection_name}"
    cached_data = redis_client.get(redis_key)
    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "redis", "data": json.loads(cached_data)}

    # 2. Wenn nicht in Redis, in MongoDB nachsehen
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = db[collection_name]
    data = list(collection.find())

    # ObjectId in String umwandeln
    for item in data:
        item["_id"] = str(item["_id"])

    # 3. Daten in Redis cachen
    redis_client.set(redis_key, json.dumps(data), ex=3600)  # 1 Stunde Cache-Lebensdauer

    return {"source": "mongodb", "data": data}

# MongoDB: Einzelnes Item erstellen
@router.post("/{collection_name}/item")
def create_item(collection_name: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # Check if the collection exists
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Insert the item into the collection
    collection = db[collection_name]
    result = collection.insert_one(item)
    
    # Publish a WebSocket notification
    redis_client.publish("realtime", f"Created item with ID {result.inserted_id} in {collection_name}")
    
    # Return the inserted item's ID
    return {"message": "Item created", "item_id": str(result.inserted_id)}

# MongoDB: Einzelnes Item bearbeiten
@router.put("/{collection_name}/item/{item_id}")
def update_item(collection_name: str, item_id: str, updates: Dict, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    collection = db[collection_name]
    result = collection.update_one({"_id": ObjectId(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Updated item with ID {item_id} in {collection_name}")
    return {"message": "Item updated"}


# MongoDB: Einzelnes Item löschen
@router.delete("/{collection_name}/item/{item_id}")
def delete_item(collection_name: str, item_id: str, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    collection = db[collection_name]
    result = collection.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted item with ID {item_id} from {collection_name}")
    return {"message": "Item deleted"}


# MongoDB: Ganze Tabelle löschen
@router.delete("/{collection_name}")
def delete_table(collection_name: str, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    db.drop_collection(collection_name)
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted collection {collection_name}")
    return {"message": f"Collection '{collection_name}' deleted successfully"}
