from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter, status
from ..dependencies import user, extract_token, get_current_active_user
from ..connection_manager import ConnectionManager

router = APIRouter(
    prefix="/sockets",
    tags=["sockets"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

User = user.User

# Manager-Instanz erstellen
manager = ConnectionManager()


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket):

    authorization = websocket.headers.get("Authorization")
    token = authorization.split(" ")[1]
    current_user: User = await extract_token(token)

    user_id = current_user.username

    # Verbindungsaufbau mit Benutzer-ID
    await manager.connect(websocket, user_id)

    try:
        while True:
            await websocket.receive_text() # nur dafür da, damit der websocket erhalten bleibt
    except WebSocketDisconnect:
        channels = manager.get_subscribed_channels_of_user(user_id)

        for channel in channels:
            # Entfernen des Benutzers aus der Gruppe und Trennen der Verbindung
            manager.remove_user_from_channel(user_id, channel)

        manager.disconnect(websocket)


# Beispiel-Endpunkt: Nachricht an alle Benutzer senden (Broadcast)
@router.post("/broadcast")
async def broadcast_message(message: str, current_user: User = Depends(get_current_active_user)):
    await manager.send_to_broadcast(current_user.username, message)
    return {"message": "Broadcast sent to all connected users."}


# Beispiel-Endpunkt: Nachricht an eine Gruppe senden
@router.post("/channel/{channel_name}")
async def send_to_channel(channel_name: str, message: str, current_user: User = Depends(get_current_active_user)):
    await manager.send_to_channel(current_user.username, channel_name, message)
    return {"message": f"Message sent to group {channel_name}."}


# Beispiel-Endpunkt: Benutzer zu einer Gruppe hinzufügen
@router.post("/channel/{channel_name}/subscribe")
async def add_user_to_channel(channel_name: str, current_user: User = Depends(get_current_active_user)):
    await manager.add_user_to_channel(current_user.username, channel_name)
    return {"message": f"User {current_user.username} added to group {channel_name}."}


# Beispiel-Endpunkt: Benutzer aus einer Gruppe entfernen
@router.post("/channel/{channel_name}/unsubscribe")
async def remove_user_from_channel(channel_name: str, current_user: User = Depends(get_current_active_user)):
    manager.remove_user_from_channel(current_user.username, channel_name)
    return {"message": f"User {current_user.username} removed from group {channel_name}."}


# Beispiel-Endpunkt: Alle Mitglieder einer Gruppe abrufen
@router.get("/channel/{channel_name}/members")
async def get_channel_members(channel_name: str, current_user: User = Depends(get_current_active_user)):
    members = manager.get_users_of_channel(channel_name)
    return {"members": members}