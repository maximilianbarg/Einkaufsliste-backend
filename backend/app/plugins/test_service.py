import asyncio
from ..own_logger import get_logger

logger = get_logger()

service_name = "Test Service"

async def run():
    while True:
        logger.info(f"[{service_name}] Doing some background work...")
        await asyncio.sleep(5)
