
import json
import logging
import sys
import os
from fastapi.logger import logger
import logging_loki
from logging.handlers import RotatingFileHandler

class StructuredLogger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
        if extra is None:
            extra = {}
        extra['app_name'] = 'Einkaufsliste Backend'
        super()._log(level, json.dumps(msg) if isinstance(msg, dict) else msg, args, exc_info, extra, stack_info)


#logging.setLoggerClass(StructuredLogger)

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def get_logger():
    if not logger.handlers:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler()
            ]
        ) 

        formatter = logging.Formatter(log_format)
        rotation_handler = RotatingFileHandler('/logs/backend.log', maxBytes=240 * 1000, backupCount=18)
        rotation_handler.setFormatter(formatter)
        loki_handler = logging_loki.LokiHandler(
            url="http://loki:3100/loki/api/v1/push", 
            tags={"application": "einkaufsliste_backend"},
            auth=("username", "password"),
            version="1",
        )
        logger.addHandler(loki_handler)
        logger.addHandler(rotation_handler)

    return logger
