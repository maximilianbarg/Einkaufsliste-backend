from __future__ import annotations 
import asyncio
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio.client import PubSub

from .logger_manager import LoggerManager
from .dbclient import DbClient
from .redis_manager import RedisStreamManager


class ConnectionManager:
    _instance = None
    divider = "|"
    db_client = DbClient()
    redis_stream_manager = RedisStreamManager(db_client.redis_client)
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

    # ------------------- connection -------------------

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.logger.info(f"User {user_id} connected.")

    def disconnect(self, websocket: WebSocket):
        user_id = next((uid for uid, conn in self.active_connections.items() if conn == websocket), None)
        if user_id:
            del self.active_connections[user_id]

    # ------------------- send -------------------

    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            self.logger.debug(f"message sent to user {user_id}")
            await websocket.send_text(message)
        else:
            self.logger.warning(f"user {user_id} is not connected. trying different socket manager.")

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
            await self.redis_stream_manager.add_message(
                stream_key=channel_name,
                group_name="websocket_group",
                user_id=user_id,
                data=message
            )
        
        channel_user_ids = self.channels.get(channel_name, [])

        for channel_user_id in channel_user_ids:
            if channel_user_id != user_id and self.active_connections[channel_user_id] != None:
                await self.send_to_user(channel_user_id, message)


    # ------------------- channel management -------------------

    async def add_user_to_channel(self, user_id: str, channel_name: str):
        if channel_name not in self.channels:
            self.channels[channel_name] = []

        if not user_id in self.channels[channel_name]:
            self.logger.debug(f"websocket subscribe to {channel_name}")
            self.channels[channel_name].append(user_id)
            await self.create_redis_stream_listener(user_id, channel_name)

    def remove_user_from_channel(self, user_id: str, channel_name: str):
        if channel_name in self.channels and user_id in self.channels[channel_name]:
            self.logger.debug(f"websocket unsubscribe user {user_id} from channel {channel_name}")
            self.channels[channel_name].remove(user_id)
            self.logger.debug(f"websocket redis unsubscribe from {channel_name}")
            asyncio.create_task(self.unsubscribe(channel_name))

    def remove_all_users_from_channel(self, channel_name: str):
        if channel_name in self.channels:
            del self.channels[channel_name]

    def get_subscribed_channels_of_user(self, user_id: str) -> List[str]:
        return [channel_name for channel_name, members in self.channels.items() if user_id in members]

    def get_users_of_channel(self, channel_name: str):
        return self.channels.get(channel_name, [])

    # ------------------- redis stream -------------------

    async def create_redis_stream_listener(self, user_id, channel_name):
        key = f"{channel_name}|{user_id}"
        self.subscription_ready[key] = asyncio.Event()

        task = asyncio.create_task(
                self.redis_stream_manager.listen_to_stream(
                    stream_key=channel_name,
                    group="websocket_group",
                    consumer=f"consumer_{user_id}",
                    on_message=self.handle_stream_message
                )
            )
        self.subscriber_tasks[channel_name] = task

        await self.wait_for_subscription_ready(channel_name)
    
    async def handle_stream_message(self, msg_id: str, msg_data: Dict):
        channel = msg_data.get("channel")
        sender = msg_data.get("sender")
        data = msg_data.get("data")

        if channel and sender and data:
            self.logger.debug(f"received stream message from user {sender} for channel {channel}")
            await self.send_to_channel(sender, channel, data, send_to_broadcast=False)

            # ACK und DEL message
            await self.redis_stream_manager.ack_message(channel, "websocket_group", msg_id)
            await self.redis_stream_manager.delete_message(channel, msg_id)


    async def wait_for_subscription_ready(self, channel_name: str):
        event = self.subscription_ready.get(channel_name)
        if event:
            await event.wait()
            del self.subscription_ready[channel_name]


    async def unsubscribe(self, channel_name: str):
        task = self.subscriber_tasks.get(channel_name)
        if task:
            self.logger.debug(f"cancelling subscription task {channel_name}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"subscription task {channel_name} cancelled")
            del self.subscriber_tasks[channel_name]