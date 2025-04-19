import os
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager

from .dbclient import DbClient
from .routers import collections, websockets
from .dependencies import router
from .service_loader import load_services
from .own_logger import get_logger, log_format
#import debugpy
import multiprocessing
import logging


# Setze uvloop als Event-Loop-Policy
import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = get_logger()
DEBUG = os.getenv("DEBUG", 0)

def is_master_process() -> bool:
    """Funktion, um zu prüfen, ob wir im Master-Prozess sind"""
    return os.getpid() == multiprocessing.get_start_method()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connect to Database...")
    db_client = DbClient()

    if is_master_process():
        logger.info("Starting background services...")
        await load_services()

    yield
    db_client.shutdown()

# FastAPI-Anwendung erstellen
app = FastAPI(lifespan=lifespan)

instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=[".*admin.*", "/metrics"],
    )

# Prometheus metrics
logger.info("Starting Prometheus metrics...")
instrumentator.instrument(app).expose(app)

app.debug = True if(DEBUG == 1) else False

app.include_router(router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------

#@app.middleware("http")
async def log_structured_requests(request: Request, call_next):
    logger.info({
        "event": "request",
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "client": request.client.host
    })
    response = await call_next(request)
    logger.info({
        "event": "response",
        "status_code": response.status_code
    })
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("fastapi")
    response = await call_next(request)
    logger.info(f"{request.method} {response.status_code} - {request.url}")
    return response

# Root-Endpunkt
@app.get("/")
async def root():
    return {"message": "Einkaufsliste Backend is running!"}

