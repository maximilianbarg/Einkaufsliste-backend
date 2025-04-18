from typing import Optional
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.database import Database
from redis import Redis
import os

class DbClient:
    db: Database
    redis_client: Redis
    
    def __init__(self):
        # Umgebungsvariablen abrufen
        self.mongo_uri = os.getenv("MONGO_URI", "MONGO_URI")
        self.mongo_db = os.getenv("MONGO_DATABASE", "my_database")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_client: Redis = Redis(host=self.redis_host, port=6379, decode_responses=True)

        self.mongo_client = AsyncIOMotorClient(os.getenv("MONGO_URI", "MONGO_URI"))
        self.db: Database = self.mongo_client[os.getenv("MONGO_DATABASE", "my_database")]

    