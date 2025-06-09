from abc import ABC, abstractmethod
from app.database_manager import get_db
from pymongo.database import Database
from app.logger_manager import LoggerManager

class BaseService(ABC):
    service_name = "Unnamed Service"

    def __init__(self):
        logger_instance = LoggerManager()
        self.logger = logger_instance.get_logger("Service Runner")

    def get_database(self) -> Database:
        return get_db()

    @abstractmethod
    async def run(self):
        """This method must be implemented by subclasses to define service behavior."""
        pass

    @classmethod
    def get_entrypoint(cls):
        instance = cls()
        return instance.run, cls.service_name