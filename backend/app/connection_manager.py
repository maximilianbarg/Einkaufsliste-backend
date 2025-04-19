from __future__ import annotations 
import asyncio
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect
from .own_logger import get_logger
from .dbclient import DbClient



class ConnectionManager:
    logger = get_logger()
    _instance = None
    db_client = DbClient()
    redis_pub_sub = db_client.redis_pub_sub

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
        # Initialisierung
        self.initialized = False

    async def initialize(self):
        if not self.initialized:
            # Redis-Nachrichten-Listener im Hintergrund starten
            asyncio.create_task(self.listen_for_redis_messages())
            self.initialized = True

    # Verbindungsaufbau mit Benutzer-ID
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        # Benutzer auch zu einem Redis-Kanal hinzufügen
        await self.add_user_to_channel(user_id, f"channel_{user_id}")
        await self.initialize()
        self.logger.info(f"User {user_id} connected.")

    # Trennung der Verbindung
    def disconnect(self, websocket: WebSocket):
        # Entfernt die Verbindung basierend auf der WebSocket-Instanz
        user_id = next((uid for uid, conn in self.active_connections.items() if conn == websocket), None)
        if user_id:
            del self.active_connections[user_id]
            # Entfernen aus Redis-Kanal
            self.remove_user_from_channel(user_id, f"channel_{user_id}")

    # Nachricht an eine spezifische Verbindung senden
    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)
        else:
            self.logger.warning(f"user {user_id} is not connected.")

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
        self.logger.info(f"send event to channel {channel_name}")
        channel_user_ids = self.channels.get(channel_name, [])
        for channel_user_id in channel_user_ids:
            if channel_user_id == user_id:
                continue
            else:
                await self.send_to_user(channel_user_id, message)

    # Benutzer zu einer Gruppe hinzufügen
    async def add_user_to_channel(self, user_id: str, channel_name: str):
        if channel_name not in self.channels:
            self.channels[channel_name] = []
        if user_id not in self.channels[channel_name]:
            self.channels[channel_name].append(user_id)
        # Redis Channel abonnieren
        await self.redis_pub_sub.subscribe(channel_name)

    # Benutzer aus einer Gruppe entfernen
    def remove_user_from_channel(self, user_id: str, channel_name: str):
        if channel_name in self.channels and user_id in self.channels[channel_name]:
            self.channels[channel_name].remove(user_id)
        # Redis Channel abmelden
        asyncio.create_task(self.redis_pub_sub.unsubscribe(channel_name))

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
    
    # Redis-Nachrichten empfangen und an WebSockets weiterleiten
    async def listen_for_redis_messages(self):
        # Diese Funktion wird ständig im Hintergrund laufen, um Nachrichten von Redis zu erhalten.
        while True:
            message = await self.redis_pub_sub.get_message(ignore_subscribe_messages=True)
            if message:
                channel = message.get("channel", "")
                data = message.get("data", "")
                # Alle Nachrichten von Redis an die WebSocket-Verbindungen weiterleiten
                self.logger.info(f"Received message on channel {channel}: {data}")
                if channel and data:
                    # Entsprechend der Benutzer-ID das richtige WebSocket finden und Nachricht senden
                    user_id = channel.split("_")[-1]  # Kanalname basiert auf Benutzer-ID
                    await self.send_to_user(user_id, data)

