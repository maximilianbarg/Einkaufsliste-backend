import asyncio
from app.service_base import BaseService
from pymongo.database import Database
from pymongo import ASCENDING, errors
from typing import Callable, List

class Migration:
    def __init__(self, name: str, function: Callable):
        self.name = name
        self.function = function

class MigrationService(BaseService):
    service_name = "Migration Service"

    # Migrationen registrieren
    

    async def run(self):        
        self.logger.info(f"[{self.service_name}] apply migrations...")
        db = self.get_database()

        # inital index
        try:
            await db.migrations.create_index("name", unique=True)
        except Exception as e:
            i=0

        # all other migrations
        migrations = [            
            Migration("add_user_name_index", lambda: db.users.create_index([("username", ASCENDING)], unique=True)),
            Migration("add_users_in_collection_index", lambda: db.users_collections.create_index([("users", ASCENDING)])),
        ]

        await self.apply_migrations(db, migrations)
        
        
    async def apply_migrations(self, db: Database, migrations: List[Migration]):
        for migration in migrations:
            try:
                if await db.migrations.find_one({"name": migration.name}):
                    self.logger.info(f"[{self.service_name}] migration skipped (already completed): {migration.name}")
                    continue

                self.logger.info(f"[{self.service_name}] start migration: {migration.name}")
                await migration.function()
                await db.migrations.insert_one({"name": migration.name})
                self.logger.info(f"[{self.service_name}] migration completed: {migration.name}")
            except Exception as e:
                self.logger.error(f"[{self.service_name}] error in migration '{migration.name}': {e}")
                break
