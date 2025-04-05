import os
from pymongo import MongoClient
import redis

class DbClient:
    def __init__(self):
        # Umgebungsvariablen abrufen
        self.mongo_uri = os.getenv("MONGO_URI", "MONGO_URI")
        self.mongo_db = os.getenv("MONGO_DATABASE", "my_database")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_client = redis.Redis(host=self.redis_host, port=6379, decode_responses=True)

        self.mongo_client = MongoClient(os.getenv("MONGO_URI", "MONGO_URI"))
        self.db = self.mongo_client[os.getenv("MONGO_DATABASE", "my_database")]

    