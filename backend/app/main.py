import os
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager

from .database_manager import DatabaseManager
from .routers import collections, websockets, authentication
from .service_loader import load_services
from .logger_manager import LoggerManager
from .connection_manager import ConnectionManager

from multiprocessing import parent_process
import logging


# Setze uvloop als Event-Loop-Policy
import asyncio
import uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger_instance = LoggerManager()
logger = logger_instance.get_logger()

database_manager = DatabaseManager()
connectionManager = ConnectionManager()

DEBUG = os.getenv("DEBUG", "0")

def is_master_process() -> bool:
    """Funktion, um zu prüfen, ob wir im Master-Prozess sind"""
    return parent_process() is None

@asynccontextmanager
async def lifespan(app: FastAPI):
    master = is_master_process()
    
    if not master:
        await database_manager.init()
        await connectionManager.init(database_manager)
    
    if master:
        logger.info("Starting background services...")
        await load_services()

    yield
    await database_manager.shutdown()

# FastAPI-Anwendung erstellen
app = FastAPI(lifespan=lifespan)

instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=[".*admin.*", "/metrics"],
    )

if DEBUG == "1":
    # Prometheus metrics
    logger.info("Starting Prometheus metrics...")
    instrumentator.instrument(app).expose(app)

app.debug = True if(DEBUG == "1") else False

app.include_router(authentication.router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("fastapi")
    response = await call_next(request)
    logger.debug(f"{request.method} {response.status_code} - {request.url}")
    return response

# Root-Endpunkt
@app.get("/")
async def root():
    return {"message": "Einkaufsliste Backend is running!"}

