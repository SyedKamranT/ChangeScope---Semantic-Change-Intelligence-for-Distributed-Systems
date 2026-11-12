"""Production-grade rate limiting with Redis sliding-window and in-memory fallback."""

import time
import uuid
from collections import defaultdict

from packages.shared.config import settings
from packages.shared.errors import ChangeScopeBaseError
from packages.shared.logger import logger


class RateLimitExceededError(ChangeScopeBaseError):
    """Raised when request volume exceeds tenant or IP rate limits."""

    status_code = 429
    error_type = "https://changescope.io/errors/rate-limit-exceeded"
    title = "Rate Limit Exceeded"

    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__(f"Rate limit exceeded. Please retry after {retry_after_seconds} seconds.")
        self.retry_after_seconds = retry_after_seconds


class InMemoryRateLimiter:
    """Sliding-window rate limiter operating in process memory."""

    def __init__(self, default_limit: int = 120, window_seconds: int = 60) -> None:
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int | None = None) -> tuple[bool, int]:
        """Evaluates whether the key is permitted to make a request.

        Returns: (is_allowed, retry_after_seconds).
        """
        now = time.time()
        max_reqs = limit or self.default_limit
        cutoff = now - self.window_seconds

        # Prune outdated timestamps
        timestamps = [t for t in self._history[key] if t > cutoff]
        self._history[key] = timestamps

        if len(timestamps) >= max_reqs:
            oldest = timestamps[0]
            retry_after = max(1, int(oldest + self.window_seconds - now))
            return False, retry_after

        self._history[key].append(now)
        return True, 0

    def reset(self, key: str | None = None) -> None:
        """Clears history for testing or manual administrative reset."""
        if key:
            self._history.pop(key, None)
        else:
            self._history.clear()


class RateLimiter:
    """Unified rate limiter with Redis coordination and automatic in-memory fallback."""

    def __init__(self) -> None:
        self._in_memory = InMemoryRateLimiter()

    async def check_rate_limit(
        self,
        key: str,
        limit: int = 120,
        window_seconds: int = 60,
    ) -> None:
        """Asserts rate limit for the given key (e.g. tenant_id or client_ip).

        Raises RateLimitExceededError if limit is breached.
        """
        # 1. Attempt Redis Sliding Window (if available and not running in isolated test mode)
        if settings.ENVIRONMENT != "test":
            try:
                import redis.asyncio as aioredis

                r = aioredis.from_url(settings.REDIS_URL, socket_timeout=0.5, socket_connect_timeout=0.5)
                now = time.time()
                redis_key = f"ratelimit:{key}"
                member = f"{now}:{uuid.uuid4().hex}"

                pipe = r.pipeline()
                pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
                pipe.zadd(redis_key, {member: now})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, window_seconds + 5)
                results = await pipe.execute()
                await r.aclose()

                current_count = results[2]
                if current_count > limit:
                    logger.warning("rate_limit_exceeded_redis", key=key, count=current_count, limit=limit)
                    raise RateLimitExceededError(retry_after_seconds=window_seconds)
                return
            except RateLimitExceededError:
                raise
            except Exception as exc:
                # Redis is offline or failed: Fallback seamlessly to in-memory limiter
                logger.debug("redis_rate_limit_fallback_in_memory", error=str(exc))

        # 2. In-Memory Limiter Fallback
        allowed, retry_after = self._in_memory.is_allowed(key, limit=limit)
        if not allowed:
            logger.warning("rate_limit_exceeded_in_memory", key=key, limit=limit)
            raise RateLimitExceededError(retry_after_seconds=retry_after)


rate_limiter = RateLimiter()
