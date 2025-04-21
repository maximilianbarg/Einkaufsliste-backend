from typing import Dict, Callable
import asyncio
from redis.asyncio import Redis
from .logger_manager import LoggerManager


class RedisStreamManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        loggermanager = LoggerManager()
        self.logger = loggermanager.get_logger("RedisStreamManager")

    async def listen_to_stream(
        self,
        stream_key: str,
        group: str,
        consumer: str,
        on_message: Callable[[str, Dict], asyncio.Future],
        block: int = 5000,
        count: int = 10
    ):
        await self.create_group(stream_key, group)

        while True:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=group,
                    consumername=consumer,
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
                await asyncio.sleep(1)

    async def create_group(self, stream_key, group):
        try:
            await self.redis.xgroup_create(name=stream_key, groupname=group, id="$", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                self.logger.debug(f"Group {group} for stream {stream_key} already exists.")
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

        send_data = {"channel": stream_key, "sender": user_id, "data": data}

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