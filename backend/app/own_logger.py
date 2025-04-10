
import logging
import sys


def get_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Handler hinzufügen, falls noch keiner da ist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger