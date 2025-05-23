from fastapi import HTTPException, Depends, APIRouter, status
from pymongo import ASCENDING
from pymongo.collection import Collection
from typing import Dict
from datetime import datetime, timezone

from ..logger_manager import LoggerManager
from ..database_manager import get_db, get_redis

# Logging
logger_instance = LoggerManager()
logger = logger_instance.get_logger("Collections")


async def get_collection_by_id(collection_id: str) -> Collection:
    collection = get_db()[collection_id]

    if collection is None:
        logger.warning(f"Collection {collection_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    return collection

async def get_collection_info(collection_id) -> Dict:
    collection_info = await get_db().users_collections.find_one({"id": collection_id})

    if collection_info is None:
        logger.warning(f"Collection info {collection_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    return collection_info

async def get_collection_in_db(collection_name: str, user_id: str) -> Collection:
    collection_id = await get_collection_id(collection_name, user_id, False)
    return get_db()[collection_id] if collection_id else None

async def get_collection_id(collection_name, user_id, should_exist: bool = True):
    collection = await get_db().users_collections.find_one(
        {"collection_name": collection_name, "users": user_id}
    )

    if collection is None and should_exist:
        logger.warning(f"Collection {collection_name} not found for user {user_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if collection and not should_exist:
        logger.warning(f"Collection {collection_name} already exists for user {user_id}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection already exists for this user")

    return collection["id"] if collection else None

async def create_collection(collection_id: str, index: str | None):
    db = get_db()
    # Collection erstellen
    await db.create_collection(collection_id)

    if(index):
        await db[collection_id].create_index([(index, ASCENDING)])

    # Collection für events erstellen
    events_collection_id = f"{collection_id}_events"
    await db.create_collection(events_collection_id)
    await db[events_collection_id].create_index([("timestamp", ASCENDING)])

async def delete_collection(collectionId: str):
    db = get_db()
    await db.drop_collection(collectionId)
        # delete events list
    await db.drop_collection(f"{collectionId}_events")

async def update_modified_status_of_collection(collection_id):
    key_pattern = f"collection_cache:{collection_id}*"
    redis = get_redis()

    keys = await redis.keys(key_pattern)
    if keys:
        await redis.delete(*keys)

    await get_db().users_collections.update_one(
        {"id": collection_id},
        {"$set": {"last_modified": datetime.now().isoformat()}}
    )
    logger.info(f"Collection info from {collection_id} updated")


async def add_item_event(collection_id: str, event: str, item: Dict):
    # get collection events
    collection_events: Collection = await get_collection_by_id(f"{collection_id}_events")
    # Insert the item into the collection
    await collection_events.insert_one(
        {
            "event": event,
            "item": item,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        }
    )
    logger.debug(f"item event added to {collection_id}")