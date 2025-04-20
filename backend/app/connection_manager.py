from __future__ import annotations 
import asyncio
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio.client import PubSub

from .logger_manager import LoggerManager
from .dbclient import DbClient


class ConnectionManager:
    _instance = None
    divider = "|"
    db_client = DbClient()
    synchronizer: PubSub = db_client.synchronizer
    redis_client_pub_sub = db_client.redis_client_pub_sub
    subscriber_tasks: Dict[str, asyncio.Task] = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectionManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        logger_instance = LoggerManager()
        self.logger = logger_instance.get_logger()
        self.active_connections: Dict[str, WebSocket] = {}
        self.channels: Dict[str, List[str]] = {}
        self.subscription_ready: Dict[str, asyncio.Event] = {}  # 🔧 NEU

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.logger.info(f"User {user_id} connected.")

    def disconnect(self, websocket: WebSocket):
        user_id = next((uid for uid, conn in self.active_connections.items() if conn == websocket), None)
        if user_id:
            del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            self.logger.debug(f"send event to user {user_id}")
            await websocket.send_text(message)
        else:
            self.logger.warning(f"user {user_id} is not connected.")

    async def send_to_broadcast(self, user_id: str, message: str):
        for connection in self.active_connections.values():
            if connection.user == user_id:
                continue
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(connection)

    async def send_to_channel(self, user_id: str, channel_name: str, message: str, send_to_broadcast: bool = True):
        if send_to_broadcast:
            self.logger.debug(f"send event to redis {channel_name}")
            await self.redis_client_pub_sub.publish(
                channel=channel_name, 
                message=message
            )
        
        channel_user_ids = self.channels.get(channel_name, [])
        for channel_user_id in channel_user_ids:
            if channel_user_id == user_id:
                continue
            await self.send_to_user(channel_user_id, message)

    async def add_user_to_channel(self, user_id: str, channel_name: str):
        if channel_name not in self.channels:
            self.channels[channel_name] = []

        already_in_channel = user_id in self.channels[channel_name]
        if not already_in_channel:
            self.logger.debug(f"websocket subscribe to {channel_name}")
            self.channels[channel_name].append(user_id)

            key = f"{channel_name}|{user_id}"
            self.subscription_ready[key] = asyncio.Event()  # 🔧 Event vorbereiten

            task = asyncio.create_task(self.listen_for_redis_messages(channel_name, user_id))
            self.subscriber_tasks[channel_name] = task

            await self.wait_for_subscription_ready(channel_name)
    
    async def wait_for_subscription_ready(self, channel_name: str):
        event = self.subscription_ready.get(channel_name)
        if event:
            await event.wait()
            del self.subscription_ready[channel_name]


    def remove_user_from_channel(self, user_id: str, channel_name: str):
        if channel_name in self.channels and user_id in self.channels[channel_name]:
            self.logger.debug(f"websocket unsubscribe user {user_id} from channel {channel_name}")
            self.channels[channel_name].remove(user_id)
            self.logger.debug(f"websocket redis unsubscribe from {channel_name}")
            asyncio.create_task(self.unsubscribe(channel_name))

    async def unsubscribe(self, channel_name: str):
        await self.synchronizer.unsubscribe(channel_name)
        task = self.subscriber_tasks.get(channel_name)
        if task:
            self.logger.debug(f"cancelling subscription task {channel_name}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"subscription task {channel_name} cancelled")
            del self.subscriber_tasks[channel_name]

    def remove_all_users_from_channel(self, channel_name: str):
        if channel_name in self.channels:
            del self.channels[channel_name]

    def get_subscribed_channels_of_user(self, user_id: str) -> List[str]:
        return [channel_name for channel_name, members in self.channels.items() if user_id in members]

    def get_users_of_channel(self, channel_name: str):
        return self.channels.get(channel_name, [])

    async def listen_for_redis_messages(self, channel_name: str, user_id: str):  # 🔧 Parameter erweitert
        key = f"{channel_name}|{user_id}"
        self.logger.debug(f"websocket redis subscribe to {channel_name}")
        
        await self.synchronizer.subscribe(channel_name)

        self.subscription_ready[key].set()  # 🔧 Subscriber ist jetzt bereit

        async for message in self.redis_client_pub_sub.listen():
            if message and message["type"] == "message":
                channel = message["channel"]
                data = message["data"]
                self.logger.debug(f"websocket redis send message to channel {channel}")
                await self.send_to_channel("BROADCAST", channel, data, send_to_broadcast=False)
