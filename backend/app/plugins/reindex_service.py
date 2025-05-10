from datetime import time
from app.service_scheduled import ScheduledService
import asyncio

class DailyCleanupService(ScheduledService):
    service_name = "Daily Reindex Service"
    run_time = time(hour=21, minute=33)

    async def run_scheduled_task(self):
        db = self.get_database()
        self.logger.info(f"[{self.service_name}] Performing daily Reindex...")
        
        collections = await db.list_collection_names()
        #events_collections = [name for name in collections if re.search(r'events$', name)]

        for collectionId in collections:
            self.logger.info(f"Reindex collection: {collectionId}")
            await db.command('reIndex', collectionId)

        self.logger.info(f"[{self.service_name}] Reindex complete.")
