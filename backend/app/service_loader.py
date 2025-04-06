import importlib
import os
import asyncio
from .own_logger import get_logger

logger = get_logger()
PLUGIN_FOLDER = os.path.join(os.path.dirname(__file__), "plugins")

async def load_services():
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

    return tasks
