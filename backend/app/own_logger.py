
import logging
import sys
import os
from fastapi.logger import logger
import logging_loki


log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEBUG = os.getenv("Debug", 0)
debug = True if(DEBUG == 1) else False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("/backend.log"),
        logging.StreamHandler()
    ]
)

if(debug):
    handler = logging_loki.LokiHandler(
        url="http://loki:3100/loki/api/v1/push", 
        tags={"application": "einkaufsliste_backend"},
        auth=("username", "password"),
        version="1",
    )
    logger.addHandler(handler)

def get_logger():
    logger.setLevel(logging.INFO)

    # Handler hinzufügen, falls noch keiner da ist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger