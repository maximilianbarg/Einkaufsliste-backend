from fastapi import HTTPException, Depends, APIRouter, status
from pymongo.collection import Collection
from typing import Dict
from datetime import datetime

from ..logger_manager import LoggerManager
from ..connection_manager import ConnectionManager
from ..authentication.models import User
from ..authentication.auth_methods import get_current_active_user
from ..database_manager import get_db, get_redis

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

async def update_modified_status_of_collection(collection_id):
    redis_key = f"collection_cache:{collection_id}"
    await get_redis().delete(redis_key)

    await get_db().users_collections.update_one(
        {"id": collection_id},
        {"$set": {"last_modified": datetime.now().isoformat()}}
    )
    logger.info(f"Collection info from {collection_id} updated")