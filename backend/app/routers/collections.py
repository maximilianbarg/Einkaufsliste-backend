from fastapi import HTTPException, Depends, APIRouter
from bson import ObjectId
import json
import bson
from typing import Collection, Dict

from ..connection_manager import ConnectionManager
from ..dependencies import user, get_current_active_user
from ..dbclient import DbClient

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}},
)

cache_time = 300

User = user.User

# get db and redis
db_client = DbClient()
db = db_client.db
redis_client = db_client.redis_client

# Manager-Instanz erstellen
sockets = ConnectionManager()


## collection methods -------------------------------------------------------------------------

@router.get("/list")
def get_collections(current_user: User = Depends(get_current_active_user)):   
    # get collection
    collections = db.users_collections.find() #{"users": user_id}
    
    # get items
    data = list(collections)

    # ObjectId in String umwandeln
    for item in data:
        del item["_id"]

    collection_json = {"data": data}
    
    return {"source": "db"} | collection_json

# MongoDB: Tabelle dynamisch erstellen
@router.post("/create/{collection_name}")
def create_table(collection_name: str, current_user: User = Depends(get_current_active_user)):
    # get user id
    user_id = current_user.username
    #create collection id
    collection_id = str(bson.ObjectId())

    # check if collection already exists
    get_collection_in_db(collection_name, user_id)

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

    return {"message": f"Collection '{collection_id}' deleted successfully"}


## item methods -------------------------------------------------------------------------

@router.get("/{collection_id}/items")
def get_items(collection_id: str, current_user: User = Depends(get_current_active_user)):
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{collection_id}"
    cached_data = redis_client.get(redis_key)
    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "cache"} | json.loads(cached_data)
    
    # get collection
    collection = get_collection_by_id(collection_id)
    collection_name = get_collection_info(collection_id)["collection_name"]
    
    # get items
    data = list(collection.find())

    # ObjectId in String umwandeln
    for item in data:
        item["_id"] = str(item["_id"])

    data_json = {"name": collection_name, "data": data}

    # 3. Daten in Redis cachen
    redis_client.set(redis_key, json.dumps(data_json), ex=cache_time)

    return {"source": "db"} | data_json

# MongoDB: Einzelnes Item erstellen
@router.post("/{collection_id}/item")
def create_item(collection_id: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = get_collection_by_id(collection_id)
    
    # Insert the item into the collection
    result = collection.insert_one(item)

    item_id = str(result.inserted_id)

    # Das aktualisierte Item abrufen
    created_item = collection.find_one({"_id": ObjectId(item_id)})

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if created_item:
        created_item["_id"] = str(created_item["_id"])  # ObjectId in String umwandeln

    # Publish a WebSocket notification
    sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "created", "item": created_item}))
    
    # Return the inserted item's ID
    return {"message": "Item created", "item_id": item_id}

# MongoDB: Einzelnes Item bearbeiten
@router.put("/{collection_id}/item/{item_id}")
def update_item(collection_id: str, item_id: str, updates: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = get_collection_by_id(collection_id)
    # update item
    result = collection.update_one({"_id": ObjectId(item_id)}, {"$set": updates})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    # Das aktualisierte Item abrufen
    updated_item = collection.find_one({"_id": ObjectId(item_id)})

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if updated_item:
        updated_item["_id"] = str(updated_item["_id"])  # ObjectId in String umwandeln

    # Publish a WebSocket notification
    sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "edited", "item": updated_item}))

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

    # Publish a WebSocket notification
    sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "removed", "item_id": f"{item_id}"}))

    return {"message": "Item deleted"}


## helper methods -------------------------------------------------------------------------

def get_collection_by_id(collection_id: str) -> Collection:
    return db[collection_id]

def get_collection_info(collection_id) -> Dict:
    return db.users_collections.find_one({"id": collection_id})

def get_collection_in_db(collection_name: str, user_id: str) -> Collection:
    collection_id = get_collection_id(collection_name, user_id, False)
    return db[collection_id] if collection_id else None

def get_collection_id(collection_name, user_id, should_exist: bool = True):
    collection = db.users_collections.find_one(
        {"collection_name": collection_name, "users": user_id}
    )

    if not collection and should_exist:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if collection and not should_exist:
        raise HTTPException(status_code=400, detail="Collection already exists for this user")
    
    return collection["id"] if collection else None