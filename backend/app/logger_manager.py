import logging
import logging.handlers
import logging_loki
import queue
import os
import multiprocessing

DEBUG = os.getenv("DEBUG", "0")

class LoggerManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if LoggerManager._initialized:
            return
        LoggerManager._initialized = True

        self.log_queue = queue.Queue(200)

        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)

        self.log_format = '%(asctime)s - %(name)-30s - WORKER %(process)-3s - %(module)-35s - %(levelname)-7s - %(message)s'
        formatter = logging.Formatter(self.log_format)

        self.file_handler = logging.handlers.TimedRotatingFileHandler(
            filename="/logs/backend.log",
            when="midnight",
            backupCount=10,
            encoding="utf-8",
            delay=True,
        )
        self.file_handler.setFormatter(formatter)

        self.listener = logging.handlers.QueueListener(
            self.log_queue, self.file_handler
        )
        self.listener.start()

        self.handlers = [self.queue_handler]

        if DEBUG == "1":
            loki_handler = logging_loki.LokiHandler(
                url="http://loki:3100/loki/api/v1/push",
                tags={"application": "einkaufsliste_backend", "worker": self.get_pid_of_process()},
                auth=("username", "password"),
                version="1",
            )
            self.handlers.append(loki_handler)

    def get_logger(self, name: str = "Einkaufsliste Backend"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Handler nur einmal hinzufügen
        for handler in self.handlers:
            if handler not in logger.handlers:
                logger.addHandler(handler)

        return logger

    def stop_listener(self):
        self.listener.stop()

    def get_pid_of_process(self) -> int:
        return  os.getpid()
