import asyncio
from app.service_base import BaseService

class TestService(BaseService):
    service_name = "Test Service"

    async def run(self):
        while True:
            self.logger.info(f"[{self.service_name}] Doing some background work...")
            await asyncio.sleep(60)
