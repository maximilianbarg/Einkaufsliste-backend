import asyncio
from app.service_base import BaseService

class TestService(BaseService):
    service_name = "Test Service"

    async def run(self):
        print(f"✅ {self.service_name} STARTED")
        self.logger.info(f"✅ {self.service_name} STARTED")
        
        while True:
            self.get_database()
            self.logger.info(f"[{self.service_name}] Doing some background work...")
            await asyncio.sleep(60)
