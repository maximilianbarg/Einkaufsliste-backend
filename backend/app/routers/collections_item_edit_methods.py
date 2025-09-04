from datetime import datetime, timezone
from fastapi import HTTPException, Depends, APIRouter, status, Query
from bson import ObjectId
import json

from pymongo import ReturnDocument
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
    updated_item = await collection.find_one_and_update({"_id": ObjectId(item_id)}, {"$set": updates}, return_document=ReturnDocument.AFTER)

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
    deleted_item = await collection.find_one_and_delete({"_id": ObjectId(item_id)})

    if deleted_item is None:
        logger.warning(f"item {item_id} not in collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # add item event
    await add_item_event(collection_id, "removed", deleted_item)

    # update modified date
    await update_modified_status_of_collection(collection_id)

    logger.info(f"item in collection {collection_id} deleted")

    # Publish a WebSocket notification
    await sockets.send_to_channel(f"{current_user.username}", f"{collection_id}", json.dumps({"event": "removed", "id": f"{item_id}"}))

    return {"message": "Item deleted", "id": item_id}
