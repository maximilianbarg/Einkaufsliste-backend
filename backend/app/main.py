import os
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


from .routers import collections, websockets
from .dependencies import router
from contextlib import asynccontextmanager
from .service_loader import load_services
from .own_logger import get_logger
import debugpy


# Setze uvloop als Event-Loop-Policy
import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = get_logger()

debugpy.listen(("0.0.0.0", 5678))  # Höre auf allen Netzwerkschnittstellen
logger.info("Waiting for debugger attach...")
debugpy.wait_for_client()  # Wartet, bis der Debugger verbunden ist

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background services...")
    await load_services()

    yield

# FastAPI-Anwendung erstellen
app = FastAPI(lifespan=lifespan)

# Prometheus metrics
logger.info("Starting Prometheus metrics...")
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=[".*admin.*", "/metrics"],
)
instrumentator.instrument(app).expose(app)

DEBUG = os.getenv("Debug", 0)
app.debug = True if(DEBUG == 1) else False

app.include_router(router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------


# Root-Endpunkt
@app.get("/")
async def root():
    return {"message": "Einkaufsliste Backend is running!"}