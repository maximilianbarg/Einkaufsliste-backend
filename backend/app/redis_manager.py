from typing import Dict, Callable, List
import asyncio
from redis.asyncio import Redis
from .logger_manager import LoggerManager
from multiprocessing import current_process

class RedisStreamManager:
    groups: Dict[str, str] = {}

    def __init__(self, redis: Redis):
        self.redis = redis
        loggermanager = LoggerManager()
        self.logger = loggermanager.get_logger("Redis Stream Manager")

    async def listen_to_stream(
        self,
        stream_key: str,
        group: str,
        consumer: str,
        on_message: Callable[[str, Dict], asyncio.Future],
        block: int = 500,
        count: int = 10
    ):
        await self.create_group(stream_key, group)
        self.logger.debug(f"start listening for messages in channel {stream_key}")

        while True:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=group,
                    consumername=f"{consumer}_{current_process().pid}",
                    streams={stream_key: '>'},
                    count=count,
                    block=block
                )

                for _, entries in messages:
                    for msg_id, msg_data in entries:
                        await on_message(msg_id, msg_data)

            except asyncio.CancelledError:
                self.logger.info(f"Stream listener for {stream_key} cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in stream listener {stream_key}: {e}")
                await asyncio.sleep(0.3)

    async def create_group(self, stream_key, group):
        try:
            exists = await self.redis.exists(stream_key)
            if not exists:
                await self.redis.xgroup_create(name=stream_key, groupname=group, id="$", mkstream=True)
            self.groups[stream_key] = group
        except Exception as e:
            if "BUSYGROUP" in str(e):
                self.logger.debug(f"Group {group} for stream {stream_key} already exists.")
            else:
                raise
    
    async def delete_group(self, stream_key, group):
        try:
            await self.redis.xgroup_destroy(name=stream_key, groupname=group)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                self.logger.debug(f"Group {group} for stream {stream_key} already destroyed.")
            else:
                raise

    async def add_message(
    self,
    stream_key: str,
    data: Dict[str, str],
    group_name: str,
    user_id: str,
    maxlen: int = None
) -> str:
        await self.create_group(stream_key, group_name)
        self.logger.debug(f"add redis message to channel {stream_key}")

        send_data = {"channel": group_name, "sender": user_id, "data": data}

        # Nachricht zum Stream hinzufügen
        if maxlen:
            msg_id = await self.redis.xadd(stream_key, send_data, maxlen=maxlen)
        else:
            msg_id = await self.redis.xadd(stream_key, send_data)

        return msg_id

    async def ack_message(self, channel: str, group: str, msg_id: str):
        await self.redis.xack(channel, group, msg_id)

    async def delete_message(self, channel: str, msg_id: str):
        await self.redis.xdel(channel, msg_id)

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    # ------------------- channel -------------------

    async def get_users_in_channel(self, channel_name: str, user_id: str) -> List[str]:
        return await self.redis.smembers(f"channel:{channel_name}")

    async def get_users_in_sub_channel(self, channel_name: str, user_id: str) -> List[str]:
        return await self.redis.smembers(f"channel:{channel_name}_{user_id}")
    
    async def get_channels_of_user(self, user_id: str) -> List[str]:
        return await self.redis.smembers(f"user:{user_id}:channels")

    async def add_user_to_channel(self, channel_name: str, user_id: str):
        self.logger.debug(f"add_user_to_channel {channel_name}_{user_id}")
        await self.redis.sadd(f"channel:{channel_name}", user_id)
        await self.redis.sadd(f"channel:{channel_name}_{user_id}", user_id)
        await self.redis.sadd(f"user:{user_id}:channels", channel_name)

    async def remove_user_from_channel(self, channel_name: str, user_id: str):
        self.logger.debug(f"remove_user_from_channel {channel_name}_{user_id}")
        await self.redis.srem(f"channel:{channel_name}_{user_id}", user_id)
        await self.redis.srem(f"user:{user_id}:channels", channel_name)

