import asyncio
from asyncio import Task
from typing import Any
from .logger_manager import LoggerManager

loggermanager = LoggerManager()

logger = loggermanager.get_logger("Task Manager")

class TaskManager:

    def create_task(self, task: Any) -> Task:
        return asyncio.create_task(self.safe_task_wrapper(task))

    async def safe_task_wrapper(self, task: Any) -> Task:
        try:
            return await task
        except Exception as e:
            logger.error(f"Task failed: {e}")