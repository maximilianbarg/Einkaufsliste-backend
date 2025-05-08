import importlib
import os
import asyncio
from app.logger_manager import LoggerManager
from app.service_base import BaseService
from app.database_manager import DatabaseManager

logger_instance = LoggerManager()
logger = logger_instance.get_logger("Service Loader")

database_manager = DatabaseManager()

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "plugins")

async def load_services():
    await database_manager.init()
    
    logger.info("Starting background services...")

    tasks = []

    for file in os.listdir(PLUGIN_FOLDER):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = file[:-3]
            module_path = f"app.plugins.{module_name}"

            try:
                mod = importlib.import_module(module_path)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseService) and attr is not BaseService:
                        instance = attr()
                        task = asyncio.create_task(instance.run())
                        logger.info(f"Started service: {instance.service_name}")
                        tasks.append(task)
            except Exception as e:
                logger.info(f"Failed to load {module_name}: {e}")

    # keep services alive
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(load_services())