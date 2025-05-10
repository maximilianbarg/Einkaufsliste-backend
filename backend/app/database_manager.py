from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.database import Database
from redis.asyncio import Redis, ConnectionPool
import os

from .logger_manager import LoggerManager

class DatabaseManager:
    db: Database
    redis_client: Redis
    mongo_client: AsyncIOMotorClient

    _instance = None
    _initialized = False

    max_connections = 20

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        else:
            self._initialized = True

    async def init(self):
            logger_instance = LoggerManager()
            self.logger = logger_instance.get_logger()

            self.logger.info("Connect to Database...")
            # Umgebungsvariablen abrufen
            self.redis_host = os.getenv("REDIS_HOST", "localhost")
            self.mongo_uri = os.getenv("MONGO_URI", "MONGO_URI")
            self.mongo_db = os.getenv("MONGO_DATABASE", "my_database")

            self.redis_client = Redis(
                host=self.redis_host,
                port=6379,
                decode_responses=True,
                max_connections=self.max_connections,
            )

            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                maxPoolSize=self.max_connections,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
            )

            self.db: Database = self.mongo_client[self.mongo_db]

    async def shutdown(self):
        self.logger.info("Closing DB connections...")
        self.mongo_client.close()
        await self.redis_client.close()

databaseManager = DatabaseManager()

def get_db() -> Database:
    return databaseManager.db

def get_redis() -> Redis:
    return databaseManager.redis_client