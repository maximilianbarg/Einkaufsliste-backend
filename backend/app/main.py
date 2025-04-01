from fastapi import FastAPI
from .routers import collections, websockets
from .dependencies import router


# FastAPI-Anwendung erstellen
app = FastAPI()

app.include_router(router)
app.include_router(collections.router)
app.include_router(websockets.router)

#-------------------------------------------------------------------------------------------------------------------

# Root-Endpunkt
@app.get("/")
def root():
    return {"message": "Einkaufsliste Backend is running!"}
