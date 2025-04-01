from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter
from typing import List, Dict
from ..dependencies import user, get_current_active_user

router = APIRouter(
    prefix="/sockets",
    tags=["sockets"],
    dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}},
)

User = user.User

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


@router.websocket("/connect")
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
@router.post("/broadcast")
async def broadcast_message(message: str):
    await manager.broadcast(message)
    return {"message": "Broadcast sent to all connected users."}


# Beispiel-Endpunkt: Nachricht an eine Gruppe senden
@router.post("/group/{group_name}")
async def send_to_group(group_name: str, message: str):
    await manager.send_to_group(group_name, message)
    return {"message": f"Message sent to group {group_name}."}


# Beispiel-Endpunkt: Benutzer zu einer Gruppe hinzufügen
@router.post("/group/{group_name}/add/{user_id}")
async def add_user_to_group(group_name: str, user_id: str):
    manager.add_user_to_group(user_id, group_name)
    return {"message": f"User {user_id} added to group {group_name}."}


# Beispiel-Endpunkt: Benutzer aus einer Gruppe entfernen
@router.post("/group/{group_name}/remove/{user_id}")
async def remove_user_from_group(group_name: str, user_id: str):
    manager.remove_user_from_group(user_id, group_name)
    return {"message": f"User {user_id} removed from group {group_name}."}


# Beispiel-Endpunkt: Alle Mitglieder einer Gruppe abrufen
@router.get("/group/{group_name}/members")
async def get_group_members(group_name: str):
    members = manager.get_group_members(group_name)
    return {"members": members}