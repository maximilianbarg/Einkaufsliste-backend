from datetime import datetime, timezone
from fastapi import HTTPException, Depends, APIRouter, status, Query
from bson import ObjectId
import json
from pymongo.collection import Collection, InsertOneResult
from typing import Dict, Optional
from redis import Redis

from ..logger_manager import LoggerManager
from ..connection_manager import ConnectionManager
from ..authentication.models import User
from ..authentication.auth_methods import get_current_active_user
from ..database_manager import get_redis
from ..collections.collection_filter import parse_filter_string
from ..collections.helper_methods import get_collection_by_id, get_collection_info, update_modified_status_of_collection, add_item_event

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
    dependencies=[Depends(get_current_active_user)],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

cache_time = 300

# Manager-Instanz erstellen
sockets = ConnectionManager()

# Logging
logger_instance = LoggerManager()
logger = logger_instance.get_logger("Collections")


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
    distinct: Optional[str] = Query(
        None,
        description="distinct Feld wie 'id' oder 'unique_item_name'"
    ),
    current_user: User = Depends(get_current_active_user),
    redis_client: Redis = Depends(get_redis)
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

    if distinct:
        items = items.distinct(distinct)

    data = await items.to_list(length=None)

    # ObjectId in String umwandeln
    for item in data:
        item["id"] = str(item["_id"])
        del item["_id"]

    data_json = {"name": collection_name, "data": data}

    # 3. Daten in Redis cachen
    await redis_client.set(redis_key, json.dumps(data_json), ex=cache_time)

    logger.info(f"collection {collection_id} retreaved")
    return {"source": "db"} | data_json

@router.get("/{collection_id}/changes")
async def get_changes(
    collection_id: str,
    filter: Optional[str] = Query(
        None,
        description="Filter-String wie 'timestamp>2025-05-10T13:35:39.877988Z,timestamp<=2025-05-09T13:35:39.877988Z'"
    ),
    sort: Optional[str] = Query(
        None,
        description="Sort-String wie 'price=asc' oder 'name=desc,price=asc'"
    ),
    distinct: Optional[str] = Query(
        None,
        description="distinct Feld wie 'id' oder 'unique_item_name'"
    ),
    current_user: User = Depends(get_current_active_user),
    ):

    collection_events_key = f"{collection_id}_events"
    # get collection
    collection: Collection = await get_collection_by_id(collection_events_key)
    collection_name = (await get_collection_info(collection_id))["collection_name"]

    # get items
    mongo_filter = parse_filter_string(filter)
    items = collection.find(mongo_filter)

    if sort:
        items = items.sort(parse_filter_string(sort))

    if distinct:
        items = items.distinct(distinct)

    data = await items.to_list(length=None)

    # ObjectId in String umwandeln
    for item in data:
        item["item"]["id"] = str(item["_id"])
        del item["_id"]
        del item["item"]["_id"]

    data_json = {"name": collection_name, "data": data}

    logger.info(f"collection {collection_id} changes retreaved")
    return {"source": "db"} | data_json

# MongoDB: Einzelnes Item erstellen
@router.post("/{collection_id}/item")
async def create_item(collection_id: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # get collection
    collection: Collection = await get_collection_by_id(collection_id)
    # Insert the item into the collection
    result: InsertOneResult = await collection.insert_one(item)

    # add item event
    await add_item_event(collection_id, "created", item)

    # update modified date
    await update_modified_status_of_collection(collection_id)

    item_id = str(result.inserted_id)

    # Das aktualisierte Item abrufen
    created_item = await collection.find_one({"_id": ObjectId(item_id)})

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if created_item:
        created_item["id"] = str(created_item["_id"])  # ObjectId in String umwandeln
        del created_item["_id"]

    logger.info(f"item in collection {collection_id} created")

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

    # add item event
    await add_item_event(collection_id, "edited", updated_item)

    # update modified date
    await update_modified_status_of_collection(collection_id)

    # Sicherstellen, dass das Item JSON-serialisierbar ist (z. B. ObjectId in String umwandeln)
    if updated_item:
        updated_item["id"] = str(updated_item["_id"])  # ObjectId in String umwandeln
        del updated_item["_id"]

    logger.info(f"item in collection {collection_id} updated")

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "edited", "item": updates}))

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

    # add item event
    await add_item_event(collection_id, "removed", {"_id": ObjectId(item_id)})

    # update modified date
    await update_modified_status_of_collection(collection_id)

    logger.info(f"item in collection {collection_id} deleted")

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "removed", "id": f"{item_id}"}))

    return {"message": "Item deleted", "id": item_id}
