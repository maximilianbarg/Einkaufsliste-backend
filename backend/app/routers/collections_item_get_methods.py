from datetime import datetime, timezone
from fastapi import HTTPException, Depends, APIRouter, status, Query
from bson import ObjectId
import json

from pymongo import ReturnDocument
from pymongo.collection import Collection, InsertOneResult
from typing import Dict, Optional
from redis import Redis
from itertools import groupby
from operator import itemgetter

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
    history: bool = Query(
        True,
        description="true oder false für alle Änderungen oder nur die wichtigsten pro item"
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
        item["item"]["id"] = str(item["item"]["_id"])
        del item["_id"]
        del item["item"]["_id"]

    logger.info(f"data={data}")

    if not history:
        items_events_grouped = group_and_sort_changes(data)
        data = remove_not_important_changes(items_events_grouped)
        logger.info(f"filtered={data}")


    data_json = {"name": collection_name, "data": data}

    logger.info(f"collection {collection_id} changes retreaved")
    return {"source": "db"} | data_json


def remove_not_important_changes(items_events_grouped) -> list[Dict]:
    data = []
    for collection_id, item_events in items_events_grouped.items():
        created = None
        edited = None
        removed = None

        for item_event in item_events:
            match item_event["event"]:
                case "created":
                    created = item_event
                case "edited":
                    edited = item_event
                case "removed":
                    removed = item_event
                case _:  # default case
                    raise ValueError(f"unknown event: {item_event['event']}")

        if created is not None and edited is not None and removed is None:
            data.append(created)
            data.append(edited)

        elif created is not None and edited is None and removed is None:
            data.append(created)

        elif created is None and edited is not None and removed is None:
            data.append(edited)

        elif created is None and removed is not None:
            data.append(removed)

    return data


def group_and_sort_changes(items: list[Dict]) -> Dict:
    items_sorted = sorted(items, key=lambda x: (x["item"]["id"], x["timestamp"]))

    return {
        _id: list(group)
        for _id, group in groupby(items_sorted, key=lambda x: (x["item"]["id"]))
    }