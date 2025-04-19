from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.database import Database
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
import os

from .own_logger import get_logger

logger = get_logger()

class DbClient:
    db: Database
    redis_client: Redis
    redis_pub_sub: PubSub
    mongo_client: AsyncIOMotorClient
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            logger.info("Connect to Database...")
            # Umgebungsvariablen abrufen
            self.redis_host = os.getenv("REDIS_HOST", "localhost")
            self.mongo_uri = os.getenv("MONGO_URI", "MONGO_URI")
            self.mongo_db = os.getenv("MONGO_DATABASE", "my_database")

            self.redis_client = Redis(
                host=self.redis_host,
                port=6379,
                decode_responses=True,
                max_connections=6,
            )

            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                maxPoolSize=6,
                minPoolSize=2,
                serverSelectionTimeoutMS=5000,
            )

            self.db: Database = self.mongo_client[self.mongo_db]

            self.redis_pub_sub = self.redis_client.pubsub()

            self.initialized = True

    def shutdown(self):
        logger.info("Closing DB connections...")
        self.mongo_client.close()
        self.redis_client.close()

    