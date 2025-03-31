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
import bson
from datetime import datetime, timedelta, timezone
from typing import Collection, List, Dict, Optional, Annotated
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
    # get user id
    user_id = current_user.username
    #create collection id
    collection_id = str(bson.ObjectId())

    # check if collection already exists
    get_collection_in_db(collection_name, user_id, should_exist=False)

    # Collection erstellen
    db.create_collection(collection_id)

    # Den Benutzer zur `users_collections`-Tabelle hinzufügen
    db.users_collections.update_one(
        {"collection_name": collection_name},
        {
            "$set": {
                "id": collection_id,  # Collection-ID speichern
                "owner": user_id  # Besitzer speichern
            },
            "$addToSet": {"users": user_id}  # Benutzer nur hinzufügen, falls noch nicht vorhanden
        },
        upsert=True  # Erstellt den Eintrag, falls er noch nicht existiert
    )

    return {"message": f"Collection '{collection_name}' created successfully", "collection_id": str(collection_id)}


@router.get("/{collection_id}/items")
async def get_items(collection_id: str, current_user: User = Depends(get_current_active_user)):
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{collection_id}"
    cached_data = redis_client.get(redis_key)

    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "redis"} | json.loads(cached_data)
    
    # get collection
    collection = get_collection_by_id(collection_id)

    collection_name = get_collection_info(collection_id)["collection_name"]
    
    # get items
    data = list(collection.find())

    # ObjectId in String umwandeln
    for item in data:
        item["_id"] = str(item["_id"])

    collection_json = {"name": collection_name, "data": data}

    # 3. Daten in Redis cachen
    redis_client.set(redis_key, json.dumps(collection_json), ex=3600)  # 1 Stunde Cache-Lebensdauer

    return {"source": "mongodb"} | collection_json

@router.get("/list")
async def get_collections(current_user: User = Depends(get_current_active_user)):
    # get user id
    user_id = current_user.username
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{user_id}"
    cached_data = None #redis_client.get(redis_key)

    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "redis"} | json.loads(cached_data)
    
    # get collection
    collections = db.users_collections.find() #{"users": user_id}
    
    # get items
    data = list(collections)

    # ObjectId in String umwandeln
    for item in data:
        del item["_id"]

    collection_json = {"data": data}

    # 3. Daten in Redis cachen
    redis_client.set(redis_key, json.dumps(collection_json), ex=3600)  # 1 Stunde Cache-Lebensdauer

    return {"source": "mongodb"} | collection_json

# MongoDB: Einzelnes Item erstellen
@router.post("/{collection_id}/item")
def create_item(collection_id: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = get_collection_by_id(collection_id)
    
    # Insert the item into the collection
    result = collection.insert_one(item)

    #remove cached item
    redis_key = f"collection_cache:{collection_id}"
    redis_client.delete(redis_key)

    # Publish a WebSocket notification
    redis_client.publish("realtime", f"Created item with ID {result.inserted_id} in {collection_id}")
    
    # Return the inserted item's ID
    return {"message": "Item created", "item_id": str(result.inserted_id)}

# MongoDB: Einzelnes Item bearbeiten
@router.put("/{collection_id}/item/{item_id}")
def update_item(collection_id: str, item_id: str, updates: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = get_collection_by_id(collection_id)
    # update item
    result = collection.update_one({"_id": ObjectId(item_id)}, {"$set": updates})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    #remove cached item
    redis_key = f"collection_cache:{collection_id}"
    redis_client.delete(redis_key)

    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Updated item with ID {item_id} in {collection_id}")

    return {"message": "Item updated"}


# MongoDB: Einzelnes Item löschen
@router.delete("/{collection_id}/item/{item_id}")
def delete_item(collection_id: str, item_id: str, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = get_collection_by_id(collection_id)
    # delete item
    result = collection.delete_one({"_id": ObjectId(item_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    #remove cached item
    redis_key = f"collection_cache:{collection_id}"
    redis_client.delete(redis_key)

    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted item with ID {item_id} from {collection_id}")

    return {"message": "Item deleted"}


# MongoDB: Ganze Tabelle löschen
@router.delete("/{collection_id}")
def delete_table(collection_id: str, current_user: User = Depends(get_current_active_user)):
   
    # delete from users list
    db.users_collections.find_one_and_delete(
        {"id": collection_id}
    )
    
    # delete list
    db.drop_collection(collection_id)

    #remove cached item
    redis_key = f"collection_cache:{collection_id}"
    redis_client.delete(redis_key)

    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted collection {collection_id}")

    return {"message": f"Collection '{collection_id}' deleted successfully"}


## helper methods
def get_collection_by_id(collection_id: str) -> Collection:
    return db[collection_id]

def get_collection_in_db(collection_name: str, user_id: str, should_exist: bool = True) -> Collection:
    collection_id = get_collection_id(collection_name, user_id, should_exist)

    return db[collection_id] if collection_id else None

def get_collection_info(collection_id) -> Dict:
    return db.users_collections.find_one({"id": collection_id})

def get_collection_id(collection_name, user_id, should_exist: bool = True):
    collection = db.users_collections.find_one(
        {"collection_name": collection_name, "users": user_id}
    )

    if not collection and should_exist:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if collection and not should_exist:
        raise HTTPException(status_code=400, detail="Collection already exists for this user")
    
    return collection["id"] if collection else None