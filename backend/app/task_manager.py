import asyncio
from asyncio import Task
from typing import Any

class TaskManager:

    def create_task(self, task: Any) -> Task:
        return asyncio.create_task(self.safe_task_wrapper(task))

    async def safe_task_wrapper(self, task: Any) -> Task:
        try:
            return await task
        except Exception as e:
            self.logger.error(f"Task failed: {e}")