"""Client Redis partagé (cache, limitation de débit, puis files de tâches)."""

from redis.asyncio import Redis

from app.config import get_settings

redis_client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
