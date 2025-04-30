from __future__ import annotations
import asyncio
from typing import List, Dict
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio.client import PubSub

from .logger_manager import LoggerManager
from .database_manager import DatabaseManager
from .redis_stream_manager import RedisStreamManager
from .task_manager import TaskManager


class ConnectionManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConnectionManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    async def init(self, database_manager: DatabaseManager):
        logger_instance = LoggerManager()
        self.logger = logger_instance.get_logger("Connection Manager")
        self.active_connections: Dict[str, WebSocket] = {}
        self.channels: Dict[str, List[str]] = {}
        self.subscription_ready: Dict[str, asyncio.Event] = {}
        self.subscriber_tasks: Dict[str, asyncio.Task] = {}
        self.taskManager = TaskManager()

        self.database_manager = database_manager
        self.redis_stream_manager = RedisStreamManager(database_manager.redis_client)


    # ------------------- connection -------------------

    async def connect(self, websocket: WebSocket, user_id: str, channel_name: str):
        await websocket.accept()

        connection_id = f"{channel_name}_{user_id}"

        self.active_connections[connection_id] = websocket
        self.logger.debug(f"[Connection Manager] connect websocket for user {user_id}")

        channels = await self.redis_stream_manager.get_channels_of_user(user_id)

        for channel_name in channels:
            if channel_name not in self.channels:
                self.channels[channel_name] = []

            if not user_id in self.channels[channel_name]:
                self.logger.debug(f"websocket subscribe to {channel_name}")
                self.channels[channel_name].append(user_id)
                await self.create_redis_stream_listener(user_id, channel_name)

    def disconnect(self, websocket: WebSocket):
        connection_id = next((uid for uid, conn in self.active_connections.items() if conn == websocket), None)

        self.logger.debug(f"[Connection Manager] disconnect websocket from user {connection_id}")
        if connection_id:
            del self.active_connections[connection_id]


    # ------------------- channel management -------------------

    async def add_user_to_channel(self, user_id: str, channel_name: str):
        await self.redis_stream_manager.add_user_to_channel(channel_name, user_id)

    def remove_user_from_channel(self, user_id: str, channel_name: str):
        self.taskManager.create_task(self.redis_stream_manager.remove_user_from_channel(channel_name, user_id))

        if channel_name in self.channels and user_id in self.channels[channel_name]:
            self.logger.debug(f"websocket unsubscribe user {user_id} from channel {channel_name}")
            self.channels[channel_name].remove(user_id)

            self.logger.debug(f"[REDIS GROUP] channel user count {len(self.channels[channel_name])}")
            if len(self.channels[channel_name]) == 0:
                self.logger.debug(f"websocket redis remove group {channel_name}")
                self.taskManager.create_task(self.unsubscribe(channel_name))

    def remove_all_users_from_channel(self, channel_name: str):
        if channel_name in self.channels:
            del self.channels[channel_name]

    def get_subscribed_channels_of_user(self, user_id: str) -> List[str]:
        return [channel_name for channel_name, members in self.channels.items() if user_id in members]

    async def get_users_of_channel(self, channel_name: str):
        return await self.redis_stream_manager.get_users_in_channel(channel_name)


    # ------------------- send -------------------

    async def send_to_user(self, connection_id: str, message: str) -> bool:
        websocket = self.active_connections.get(connection_id)
        if websocket:
            self.logger.debug(f"websocket message sent to user {connection_id}")
            await websocket.send_text(message)
            return True
        else:
            self.logger.warning(f"user {connection_id} is not connected. wrong socket manager.")
            return False

    async def send_to_broadcast(self, user_id: str, message: str):
        for connection in self.active_connections.values():
            if connection.user == user_id:
                continue

            await connection.send_text(message)

    async def send_to_channel(self, user_id: str, channel_name: str, message):
        redis_channel_user_ids = await self.redis_stream_manager.get_users_in_channel(channel_name)

        self.logger.debug(f"Websocket Manager: redis_channel_user_ids:       {redis_channel_user_ids}")
        self.logger.debug(f"Websocket Manager: redis_channel_user_ids count: {len(redis_channel_user_ids)}")

        if len(redis_channel_user_ids) == 0:
            self.logger.info(f"Websocket Manager: no one in redis stream channel. skip message...")
            return

        for redis_channel_user_id in redis_channel_user_ids:
            self.logger.info(f"Websocket Manager: send message to redis stream channel {channel_name}")
            await self.redis_stream_manager.add_message(
                    stream_key=f"{channel_name}_{redis_channel_user_id}",
                    group_name=channel_name,
                    user_id=user_id,
                    data=message
                )


    # ------------------- redis stream -------------------

    async def create_redis_stream_listener(self, user_id, channel_name):
        key = f"{channel_name}_{user_id}"

        self.logger.debug("websocket create listener called")

        task = self.taskManager.create_task(
                self.redis_stream_manager.listen_to_stream(
                    stream_key=key,
                    group=channel_name,
                    consumer=f"consumer_{user_id}",
                    on_message=self.handle_stream_message,
                )
            )

        self.subscriber_tasks[channel_name] = task

    async def handle_stream_message(self, msg_id: str, msg_data: Dict):
        try:
            channel = msg_data.get("channel")
            sender = msg_data.get("sender")
            data = msg_data.get("data")

            if channel and sender and data:
                self.logger.debug(f"received stream message from user {sender} for channel {channel}")
                await self.send_to_websocket_channel(sender, channel, data, msg_id)

        except Exception as e:
                self.logger.error(f"Error in handle_stream_message: {e}")
                await asyncio.sleep(0.3)

    async def send_to_websocket_channel(self, user_id: str, channel_name: str, message: str, msg_id: str):
        self.logger.info(f"Websocket: send message to users")
        message_sent = []

        channel_user_ids = self.channels.get(channel_name, [])
        redis_channel_user_ids = await self.redis_stream_manager.get_users_in_channel(channel_name)
        self.logger.debug(f"Websocket: channel_user_ids:       {channel_user_ids}")
        self.logger.debug(f"Websocket: redis_channel_user_ids: {redis_channel_user_ids}")
        self.logger.debug(f"Websocket: BEFORE SEND TO USER | message_sent: {message_sent}")

        for channel_user_id in channel_user_ids:
            if channel_user_id != user_id:
                connection_id = f"{channel_name}_{channel_user_id}"
                temp = await self.send_to_user(connection_id, message)

                if temp:
                    self.logger.info(f"Websocket: message in redis acknowledged")
                    await self.redis_stream_manager.ack_message(f"{channel_name}_{channel_user_id}", channel_name, msg_id)
                    await self.redis_stream_manager.delete_message(f"{channel_name}_{channel_user_id}", msg_id)
                else:
                    self.remove_user_from_channel(channel_user_id, channel_name)

                message_sent.append(temp)

        self.logger.debug(f"Websocket: AFTER SEND TO USER | message_sent: {message_sent}")

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

            await self.redis_stream_manager.delete_group(channel_name, "websocket_group")
