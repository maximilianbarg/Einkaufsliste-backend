from fastapi import HTTPException, Depends, APIRouter, status, Query
from bson import ObjectId
import json
import bson
from pymongo.database import Database
from pymongo.collection import Collection, InsertOneResult
from typing import Dict, Optional
from datetime import datetime, timezone

from ..logger_manager import LoggerManager
from ..connection_manager import ConnectionManager
from ..dependencies import user, get_current_active_user
from ..dbclient import DbClient
from ..collection_filter import parse_filter_string

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    dependencies=[Depends(get_current_active_user)],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

cache_time = 300

User = user.User

# get db and redis
db_client = DbClient()
db: Database = db_client.db
redis_client = db_client.redis_client

# Manager-Instanz erstellen
sockets = ConnectionManager()

# Logging
logger_instance = LoggerManager()
logger = logger_instance.get_logger()


## user collections -------------------------------------------------------------------------

@router.get("/list")
async def get_collections(current_user: User = Depends(get_current_active_user)):
    # get collection
    collections = db.users_collections.find({"users": current_user.username})

    # get items
    data = await collections.to_list(length=None)

    # Entfernen von _id aus jedem Element
    for item in data:
        del item["_id"]

    collection_json = {"data": data}

    return {"source": "db"} | collection_json


## collection methods -------------------------------------------------------------------------

# MongoDB: Tabelle dynamisch erstellen
@router.post("/create/{collection_name}/{purpose}")
async def create_table(collection_name: str, purpose: str, current_user: User = Depends(get_current_active_user)):
    # get user id
    user_id = current_user.username
    #create collection id
    collection_id = str(bson.ObjectId())

    # check if collection already exists
    await get_collection_in_db(collection_name, user_id)

    # Collection erstellen
    await db.create_collection(collection_id)

    # Den Benutzer zur `users_collections`-Tabelle hinzufügen
    await db.users_collections.update_one(
        {"collection_name": collection_name},
        {
            "$set": {
                "id": collection_id,  # Collection-ID speichern
                "owner": user_id,  # Besitzer speichern
                "last_modified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),  # datum speichern
                "purpose": purpose
            },
            "$addToSet": {"users": user_id}  # Benutzer nur hinzufügen, falls noch nicht vorhanden
        },
        upsert=True  # Erstellt den Eintrag, falls er noch nicht existiert
    )

    return {"message": f"Collection '{collection_name}' created successfully", "id": str(collection_id)}

# MongoDB: Ganze Tabelle löschen
@router.delete("/{collection_id}")
async def delete_table(collection_id: str, current_user: User = Depends(get_current_active_user)):

    # delete from users list
    await db.users_collections.find_one_and_delete(
        {"id": collection_id}
    )

    # delete list
    await db.drop_collection(collection_id)

    #remove cached item
    redis_key = f"collection_cache:{collection_id}_no_filter"
    await redis_client.delete(redis_key)

    return {"message": f"Collection deleted successfully",  "id": collection_id}

@router.get("/{collection_id}/info")
async def get_items(collection_id: str, current_user: User = Depends(get_current_active_user)):
    collection_info = await get_collection_info(collection_id)

    del collection_info["_id"]

    return {"source": "db", "data": collection_info}

# MongoDB: Tabelle teilen
@router.patch("/{collection_id}/users/add/{user_id}")
async def share_collection(collection_id: str, user_id: str, current_user: User = Depends(get_current_active_user)):

    # add user to list
    result = await db.users_collections.update_one(
        {"id": collection_id, "owner": current_user.username},
        {"$addToSet": {"users": user_id}}
    )

    if result.matched_count == 0:
        logger.warning(f"user {user_id} not added from collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not owner of collection")

    return {"message": f"Collection shared with user '{user_id}'",  "id": collection_id}

# MongoDB: Tabelle teilen
@router.patch("/{collection_id}/users/remove/{user_id}")
async def unshare_collection(collection_id: str, user_id: str, current_user: User = Depends(get_current_active_user)):

    # add user to list
    result = await db.users_collections.update_one(
        {"id": collection_id, "owner": current_user.username},
        {"$pull": {"users": user_id}}
    )

    if result.matched_count == 0:
        logger.warning(f"user {user_id} not removed from collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": f"User '{user_id}' removed from collection", "id": collection_id}


## item methods -------------------------------------------------------------------------

@router.get("/{collection_id}/items")
async def get_items(
    collection_id: str,
    filter: Optional[str] = Query(
        None,
        description="Filter-String wie 'price>2,price<7,name:Apfel'"
    ),
    sort: Optional[str] = Query(
        None,
        description="Sort-String wie 'price=asc' oder 'name=desc,price=asc'"
    ),
    skip: Optional[str] = Query(
        None,
        description="Skip-String wie '10'"
    ),
    limit: Optional[str] = Query(
        None,
        description="Limit-String wie '50'"
    ),
    current_user: User = Depends(get_current_active_user)
    ):
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{collection_id}:{filter or ''}:{sort or ''}:{skip or ''}:{limit or ''}"
    cached_data = await redis_client.get(redis_key)
    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "cache"} | json.loads(cached_data)

    # get collection
    collection: Collection = await get_collection_by_id(collection_id)
    collection_name = (await get_collection_info(collection_id))["collection_name"]

    # get items
    mongo_filter = parse_filter_string(filter)
    items = collection.find(mongo_filter)

    if sort:
        items = items.sort(parse_filter_string(sort))

    if limit:
        items = items.limit(int(limit))

    if skip:
        items = items.skip(int(skip))

    data = await items.to_list(length=None)

    # ObjectId in String umwandeln
    for item in data:
        item["id"] = str(item["_id"])
        del item["_id"]

    data_json = {"name": collection_name, "data": data}

    # 3. Daten in Redis cachen
    await redis_client.set(redis_key, json.dumps(data_json), ex=cache_time)

    return {"source": "db"} | data_json

# MongoDB: Einzelnes Item erstellen
@router.post("/{collection_id}/item")
async def create_item(collection_id: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection: Collection = await get_collection_by_id(collection_id)

    # Insert the item into the collection
    result: InsertOneResult = await collection.insert_one(item)

    # update modified date
    await update_modified_status_of_collection(collection_id)

    item_id = str(result.inserted_id)

    # Das aktualisierte Item abrufen
    created_item = await collection.find_one({"_id": ObjectId(item_id)})

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if created_item:
        created_item["id"] = str(created_item["_id"])  # ObjectId in String umwandeln
        del created_item["_id"]

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "created", "item": created_item}))

    # Return the inserted item's ID
    return {"message": "Item created", "id": item_id}


# MongoDB: Einzelnes Item bearbeiten
@router.put("/{collection_id}/item/{item_id}")
async def update_item(collection_id: str, item_id: str, updates: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = await get_collection_by_id(collection_id)
    # update item
    updated_item = await collection.find_one_and_update({"_id": ObjectId(item_id)}, {"$set": updates})

    if updated_item is None:
        logger.warning(f"item {item_id} not in collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # update modified date
    await update_modified_status_of_collection(collection_id)

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if updated_item:
        updated_item["id"] = str(updated_item["_id"])  # ObjectId in String umwandeln
        del updated_item["_id"]

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "edited", "item": updated_item}))

    return {"message": "Item updated", "id": item_id}


# MongoDB: Einzelnes Item löschen
@router.delete("/{collection_id}/item/{item_id}")
async def delete_item(collection_id: str, item_id: str, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection = await get_collection_by_id(collection_id)
    # delete item
    result = await collection.delete_one({"_id": ObjectId(item_id)})

    if result.deleted_count == 0:
        logger.warning(f"item {item_id} not in collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # update modified date
    await update_modified_status_of_collection(collection_id)

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "removed", "id": f"{item_id}"}))

    return {"message": "Item deleted", "id": item_id}


## helper methods -------------------------------------------------------------------------

async def get_collection_by_id(collection_id: str) -> Collection:
    collection = db[collection_id]

    if collection is None:
        logger.warning(f"Collection {collection_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    
    return collection

async def get_collection_info(collection_id) -> Dict:
    collection_info = await db.users_collections.find_one({"id": collection_id})

    if collection_info is None:
        logger.warning(f"Collection info {collection_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    
    return collection_info

async def get_collection_in_db(collection_name: str, user_id: str) -> Collection:
    collection_id = await get_collection_id(collection_name, user_id, False)
    return db[collection_id] if collection_id else None

async def get_collection_id(collection_name, user_id, should_exist: bool = True):
    collection = await db.users_collections.find_one(
        {"collection_name": collection_name, "users": user_id}
    )

    if collection is None and should_exist:
        logger.warning(f"Collection {collection_name} not found for user {user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if collection and not should_exist:
        logger.warning(f"Collection {collection_name} already exists for user {user_id}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection already exists for this user")

    return collection["id"] if collection else None

async def update_modified_status_of_collection(collection_id):
    redis_key = f"collection_cache:{collection_id}"
    await redis_client.delete(redis_key)

    await db.users_collections.update_one(
        {"id": collection_id},
        {"$set": {"last_modified": datetime.now().isoformat()}}
    )
    logger.info(f"Collection info from {collection_id} updated")