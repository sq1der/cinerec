import redis.asyncio as aioredis
from app.config import settings

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def cache_get(key: str) -> str | None:
    r = await get_redis()
    return await r.get(key)


async def cache_set(key: str, value: str, ttl: int) -> None:
    r = await get_redis()
    await r.set(key, value, ex=ttl)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def cache_exists(key: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(key))