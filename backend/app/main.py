from fastapi import FastAPI
from .routers import collections, websockets
from .dependencies import router
from contextlib import asynccontextmanager
from .service_loader import load_services
from .own_logger import get_logger

logger = get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting background services...")
    await load_services()

    yield

# FastAPI-Anwendung erstellen
app = FastAPI(lifespan=lifespan)

app.include_router(router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------


# Root-Endpunkt
@app.get("/")
def root():
    return {"message": "Einkaufsliste Backend is running!"}