from __future__ import annotations 
import asyncio
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectionManager, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        # Speichert WebSocket-Verbindungen mit einer Benutzer-ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Speichert Benutzer-IDs, die zu Gruppen gehören
        self.channels: Dict[str, List[str]] = {}  # Gruppenname -> Liste von Benutzer-IDs

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
    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)
        else:
            print(f"User {user_id} is not connected.")

    # Broadcast an alle Verbindungen senden
    async def send_to_broadcast(self, user_id: str, message: str):
        for connection in self.active_connections.values():
            if connection.user == user_id:
                continue
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(connection)

    # Nachricht an eine Gruppe von Benutzern senden
    async def send_to_channel(self, user_id: str, channel_name: str, message: str):
        # Hole alle Benutzer-IDs in der Gruppe
        channel_user_ids = self.channels.get(channel_name, [])
        for channel_user_id in channel_user_ids:
            if channel_user_id == user_id:
                continue
            else:
                await self.send_to_user(channel_user_id, message)

    # Benutzer zu einer Gruppe hinzufügen
    def add_user_to_channel(self, user_id: str, channel_name: str):
        if channel_name not in self.channels:
            self.channels[channel_name] = []
        if user_id not in self.channels[channel_name]:
            self.channels[channel_name].append(user_id)

    # Benutzer aus einer Gruppe entfernen
    def remove_user_from_channel(self, user_id: str, group_name: str):
        if group_name in self.channels and user_id in self.channels[group_name]:
            self.channels[group_name].remove(user_id)

    # Alle Mitglieder einer Gruppe entfernen
    def remove_all_users_from_channel(self, channel_name: str):
        if channel_name in self.channels:
            del self.channels[channel_name]

    # Liste aller Gruppen eines Benutzers
    def get_subscribed_channels_of_user(self, user_id: str):
        return [channel_name for channel_name, members in self.channels.items() if user_id in members]

    # Alle Benutzer einer Gruppe abrufen
    def get_users_of_channel(self, channel_name: str):
        return self.channels.get(channel_name, [])

