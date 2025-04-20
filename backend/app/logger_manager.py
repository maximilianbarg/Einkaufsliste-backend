from fastapi.logger import logger
import logging_loki
import logging
import logging.handlers
import queue
import os

DEBUG = os.getenv("DEBUG", 0)

class LoggerManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.log_queue = queue.Queue(200)

        # Handler, der Lognachrichten in die Queue legt
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)

        self.log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Format für die Logs
        formatter = logging.Formatter(self.log_format)

        # Zielhandler mit Rotation
        self.file_handler = logging.handlers.TimedRotatingFileHandler(
            filename="/logs/backend.log",
            when="midnight",
            backupCount=10,
            encoding="utf-8",
            delay=True,
        )
        self.file_handler.setFormatter(formatter)

        # Listener im Hintergrund
        self.listener = logging.handlers.QueueListener(
            self.log_queue, self.file_handler
        )
        self.listener.start()

        # Konfiguriere Logger
        self.logger = logging.getLogger("Einkaufsliste Backend")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.queue_handler)
        
        if(DEBUG == 1):
            loki_handler = logging_loki.LokiHandler(
                url="http://loki:3100/loki/api/v1/push", 
                tags={"application": "einkaufsliste_backend"},
                auth=("username", "password"),
                version="1",
            )
            self.logger.addHandler(loki_handler)

    def get_logger(self):
        return self.logger

    def stop_listener(self):
        self.listener.stop()
