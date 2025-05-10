from typing import Optional
from fastapi import HTTPException, Depends, APIRouter, status, Query
import bson
from pymongo import ASCENDING
from pymongo.database import Database
from datetime import datetime, timezone
from redis import Redis

from ..logger_manager import LoggerManager
from ..connection_manager import ConnectionManager
from ..authentication.models import User
from ..authentication.auth_methods import get_current_active_user
from ..database_manager import get_db, get_redis
from ..collections.helper_methods import get_collection_in_db, get_collection_info, create_collection, delete_collection


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


## user collections -------------------------------------------------------------------------

@router.get("/list")
async def get_collections(current_user: User = Depends(get_current_active_user), db: Database = Depends(get_db)):
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
async def create_table(
    collection_name: str, 
    purpose: str,
    index: Optional[str] = Query(
        None,
        description="index like 'price' oder 'last_modified' for faster get items"
    ),
    current_user: User = Depends(get_current_active_user), 
    db: Database = Depends(get_db)
    ):
    # get user id
    user_id = current_user.username
    #create collection id
    collection_id = str(bson.ObjectId())

    # check if collection already exists
    await get_collection_in_db(collection_name, user_id)

    # Collection erstellen
    await create_collection(collection_id, index)

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

    logger.info(f"collection {collection_id} created")
    return {"message": f"Collection '{collection_name}' created successfully", "id": str(collection_id)}


# MongoDB: Ganze Tabelle löschen
@router.delete("/{collection_id}")
async def delete_table(
    collection_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Database = Depends(get_db),
    redis_client: Redis = Depends(get_redis)
    ):

    # delete from users list
    await db.users_collections.find_one_and_delete(
        {"id": collection_id}
    )

    # delete collection
    await delete_collection(collection_id)

    #remove cached item
    redis_key = f"collection_cache:{collection_id}_no_filter"
    await redis_client.delete(redis_key)

    logger.info(f"collection {collection_id} deleted")
    return {"message": f"Collection deleted successfully",  "id": collection_id}

@router.get("/{collection_id}/info")
async def get_items(collection_id: str, current_user: User = Depends(get_current_active_user)):
    collection_info = await get_collection_info(collection_id)

    del collection_info["_id"]

    logger.info(f"collection info {collection_id} retreaved")
    return {"source": "db", "data": collection_info}

@router.patch("/{collection_id}/rename/{collection_name}")
async def rename_collection(
    collection_id: str,
    collection_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Database = Depends(get_db)
    ):

    # add user to list
    result = await db.users_collections.update_one(
        {"id": collection_id, "owner": current_user.username},
        {"$set": {"collection_name": collection_name}}
    )

    if result.matched_count == 0:
        logger.warning(f"collection {collection_id} could not be renamed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not owner of collection")

    return {"message": f"Collection renamed to '{collection_name}'",  "id": collection_id}

# MongoDB: Tabelle teilen
@router.patch("/{collection_id}/users/add/{user_id}")
async def share_collection(
    collection_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Database = Depends(get_db)
    ):

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
async def unshare_collection(
    collection_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Database = Depends(get_db)
    ):

    # add user to list
    result = await db.users_collections.update_one(
        {"id": collection_id, "owner": current_user.username},
        {"$pull": {"users": user_id}}
    )

    if result.matched_count == 0:
        logger.warning(f"user {user_id} not removed from collection {collection_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": f"User '{user_id}' removed from collection", "id": collection_id}