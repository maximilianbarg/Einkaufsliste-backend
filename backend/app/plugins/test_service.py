import asyncio
from ..logger_manager import LoggerManager

logger_instance = LoggerManager()
logger = logger_instance.get_logger()

service_name = "Test Service"

async def run():
    while True:
        logger.info(f"[{service_name}] Doing some background work...")
        await asyncio.sleep(60)
