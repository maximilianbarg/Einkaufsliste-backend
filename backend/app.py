from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
import redis
import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Annotated


# Umgebungsvariablen abrufen
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "my_database")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# MongoDB-Client einrichten
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DATABASE]

# Redis-Client einrichten
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# Passwort-Kontext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FastAPI-Anwendung erstellen
app = FastAPI()

# Benutzerdatenbank simuliert
fake_users_db = {
    "user1": {
        "username": "user1",
        "full_name": "User One",
        "email": "user1@example.com",
        "hashed_password": pwd_context.hash("password1"),
        "disabled": False,
    }
}

# Modelle
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

# Passwort-Hash überprüfen
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Benutzer abrufen
def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

# Authentifizierung überprüfen
def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# JWT-Token erstellen
def create_access_token(data: dict, expires_delta: Optional[int] = None):
    to_encode = data.copy()
    if expires_delta:
        to_encode.update({"exp": expires_delta})
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Benutzerinformationen aus Token extrahieren
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Authentifizierung: Token-Endpunkt
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Geschützter Endpunkt
@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

class ConnectionManager:
    def __init__(self):
        # Speichert WebSocket-Verbindungen mit einer Benutzer-ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Speichert Benutzer-IDs, die zu Gruppen gehören
        self.groups: Dict[str, List[str]] = {}  # Gruppenname -> Liste von Benutzer-IDs

    # Verbindungsaufbau mit Benutzer-ID
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    # Trennung der Verbindung
    def disconnect(self, websocket: WebSocket):
        # Entfernt die Verbindung basierend auf der WebSocket-Instanz
        user_id = next((uid for uid, conn in self.active_connections.items() if conn == websocket), None)
        if user_id:
            del self.active_connections[user_id]

    # Nachricht an eine spezifische Verbindung senden
    async def send_message(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)
        else:
            print(f"User {user_id} is not connected.")

    # Broadcast an alle Verbindungen senden
    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(connection)

    # Nachricht an eine Gruppe von Benutzern senden
    async def send_to_group(self, group_name: str, message: str):
        # Hole alle Benutzer-IDs in der Gruppe
        user_ids = self.groups.get(group_name, [])
        for user_id in user_ids:
            await self.send_message(user_id, message)

    # Benutzer zu einer Gruppe hinzufügen
    def add_user_to_group(self, user_id: str, group_name: str):
        if group_name not in self.groups:
            self.groups[group_name] = []
        if user_id not in self.groups[group_name]:
            self.groups[group_name].append(user_id)

    # Benutzer aus einer Gruppe entfernen
    def remove_user_from_group(self, user_id: str, group_name: str):
        if group_name in self.groups and user_id in self.groups[group_name]:
            self.groups[group_name].remove(user_id)

    # Alle Mitglieder einer Gruppe entfernen
    def remove_all_users_from_group(self, group_name: str):
        if group_name in self.groups:
            del self.groups[group_name]

    # Liste aller Gruppen eines Benutzers
    def get_user_groups(self, user_id: str):
        return [group_name for group_name, members in self.groups.items() if user_id in members]

    # Alle Benutzer einer Gruppe abrufen
    def get_group_members(self, group_name: str):
        return self.groups.get(group_name, [])


# Manager-Instanz erstellen
manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: User = Depends(get_current_active_user)):
    # Verbindungsaufbau mit Benutzer-ID
    await manager.connect(websocket, current_user.id)

    # Optional: Benutzer zu einer Gruppe hinzufügen (z.B. "example_group")
    manager.add_user_to_group(current_user.id, "example_group")

    try:
        while True:
            data = await websocket.receive_text()
            # Beispiel: Nachricht an eine Gruppe senden
            await manager.send_to_group("example_group", f"Message from {current_user.username}: {data}")
    except WebSocketDisconnect:
        # Entfernen des Benutzers aus der Gruppe und Trennen der Verbindung
        manager.remove_user_from_group(current_user.id, "example_group")
        manager.disconnect(websocket)


# Beispiel-Endpunkt: Nachricht an alle Benutzer senden (Broadcast)
@app.post("/broadcast")
async def broadcast_message(message: str):
    await manager.broadcast(message)
    return {"message": "Broadcast sent to all connected users."}


# Beispiel-Endpunkt: Nachricht an eine Gruppe senden
@app.post("/group/{group_name}")
async def send_to_group(group_name: str, message: str):
    await manager.send_to_group(group_name, message)
    return {"message": f"Message sent to group {group_name}."}


# Beispiel-Endpunkt: Benutzer zu einer Gruppe hinzufügen
@app.post("/group/{group_name}/add/{user_id}")
async def add_user_to_group(group_name: str, user_id: str):
    manager.add_user_to_group(user_id, group_name)
    return {"message": f"User {user_id} added to group {group_name}."}


# Beispiel-Endpunkt: Benutzer aus einer Gruppe entfernen
@app.post("/group/{group_name}/remove/{user_id}")
async def remove_user_from_group(group_name: str, user_id: str):
    manager.remove_user_from_group(user_id, group_name)
    return {"message": f"User {user_id} removed from group {group_name}."}


# Beispiel-Endpunkt: Alle Mitglieder einer Gruppe abrufen
@app.get("/group/{group_name}/members")
async def get_group_members(group_name: str):
    members = manager.get_group_members(group_name)
    return {"members": members}

#-------------------------------------------------------------------------------------------------------------------

# Root-Endpunkt
@app.get("/")
def root():
    return {"message": "Python Backend with Realtime and Dynamic Collections is running!"}


# MongoDB: Tabelle dynamisch erstellen
@app.post("/mongo/{collection_name}")
def create_table(collection_name: str, current_user: User = Depends(get_current_active_user)):
    if collection_name in db.list_collection_names():
        raise HTTPException(status_code=400, detail="Collection already exists")
    db.create_collection(collection_name)
    return {"message": f"Collection '{collection_name}' created successfully"}

# MongoDB-Methoden aktualisieren
@app.get("/mongo/{collection_name}/items")
async def get_items(collection_name: str, current_user: User = Depends(get_current_active_user)):
    # 1. In Redis nachsehen
    redis_key = f"collection_cache:{collection_name}"
    cached_data = redis_client.get(redis_key)
    if cached_data:
        # Daten aus Redis zurückgeben
        return {"source": "redis", "data": json.loads(cached_data)}

    # 2. Wenn nicht in Redis, in MongoDB nachsehen
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = db[collection_name]
    data = list(collection.find())

    # ObjectId in String umwandeln
    for item in data:
        item["_id"] = str(item["_id"])

    # 3. Daten in Redis cachen
    redis_client.set(redis_key, json.dumps(data), ex=3600)  # 1 Stunde Cache-Lebensdauer

    return {"source": "mongodb", "data": data}

# MongoDB: Einzelnes Item erstellen
@app.post("/mongo/{collection_name}/item")
def create_item(collection_name: str, item: Dict, current_user: User = Depends(get_current_active_user)):
    # Check if the collection exists
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Insert the item into the collection
    collection = db[collection_name]
    result = collection.insert_one(item)
    
    # Publish a WebSocket notification
    redis_client.publish("realtime", f"Created item with ID {result.inserted_id} in {collection_name}")
    
    # Return the inserted item's ID
    return {"message": "Item created", "item_id": str(result.inserted_id)}

# MongoDB: Einzelnes Item bearbeiten
@app.put("/mongo/{collection_name}/item/{item_id}")
def update_item(collection_name: str, item_id: str, updates: Dict, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    collection = db[collection_name]
    result = collection.update_one({"_id": ObjectId(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Updated item with ID {item_id} in {collection_name}")
    return {"message": "Item updated"}


# MongoDB: Einzelnes Item löschen
@app.delete("/mongo/{collection_name}/item/{item_id}")
def delete_item(collection_name: str, item_id: str, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    collection = db[collection_name]
    result = collection.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted item with ID {item_id} from {collection_name}")
    return {"message": "Item deleted"}


# MongoDB: Ganze Tabelle löschen
@app.delete("/mongo/{collection_name}")
def delete_table(collection_name: str, current_user: User = Depends(get_current_active_user)):
    if collection_name not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    db.drop_collection(collection_name)
    # Benachrichtigung über WebSocket
    redis_client.publish("realtime", f"Deleted collection {collection_name}")
    return {"message": f"Collection '{collection_name}' deleted successfully"}
