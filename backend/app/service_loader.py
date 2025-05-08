import importlib
import os
import asyncio
from app.logger_manager import LoggerManager

logger_instance = LoggerManager()
logger = logger_instance.get_logger("Service Loader")

PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "plugins")

async def load_services():
    logger.info("Starting background services...")

    tasks = []

    for file in os.listdir(PLUGIN_FOLDER):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = file[:-3]
            module_path = f"app.plugins.{module_name}"

            try:
                mod = importlib.import_module(module_path)
                task = asyncio.create_task(mod.run())
                logger.info(f"Started service: {mod.service_name}")
                tasks.append(task)
            except Exception as e:
                logger.info(f"Failed to load {module_name}: {e}")

    # keep services alive
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(load_services())