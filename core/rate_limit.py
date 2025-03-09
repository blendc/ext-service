import time
import logging
from functools import wraps
from typing import Callable, Optional, Union, Dict, Any

import redis
from webob import Request, Response, exc

from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "rate_limit",
    "get_rate_limit_remaining",
    "reset_rate_limit",
)

try:
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis for rate limiting")
except redis.ConnectionError:
    logger.warning("Could not connect to Redis, rate limiting will be disabled")
    redis_client = None


def _get_client_identifier(req: Request) -> str:
    if hasattr(req, "user_id") and req.user_id:
        return f"user:{req.user_id}"
    
    forwarded_for = req.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = req.remote_addr or "unknown"
    
    return f"ip:{client_ip}"


def _get_rate_limit_key(req: Request, key_prefix: str) -> str:
    client_id = _get_client_identifier(req)
    return f"ratelimit:{key_prefix}:{client_id}"


def get_rate_limit_remaining(req: Request, key_prefix: str) -> Dict[str, Any]:
    if not settings.RATE_LIMIT_ENABLED or redis_client is None:
        return {
            "limit": -1,
            "remaining": -1,
            "reset": -1,
        }
    
    rate_key = _get_rate_limit_key(req, key_prefix)
    
    pipe = redis_client.pipeline()
    pipe.get(rate_key)
    pipe.ttl(rate_key)
    count_bytes, ttl = pipe.execute()
    
    limit = settings.RATE_LIMIT_DEFAULT
    
    count = int(count_bytes) if count_bytes else 0
    remaining = max(0, limit - count)
    
    reset = int(time.time() + ttl) if ttl > 0 else int(time.time() + 60)
    
    return {
        "limit": limit,
        "remaining": remaining,
        "reset": reset,
    }


def reset_rate_limit(req: Request, key_prefix: str) -> bool:
    if not settings.RATE_LIMIT_ENABLED or redis_client is None:
        return False
    
    rate_key = _get_rate_limit_key(req, key_prefix)
    return bool(redis_client.delete(rate_key))


def rate_limit(
    limit: Optional[int] = None,
    period: int = 60,
    key_prefix: str = "default"
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(req: Request, *args, **kwargs) -> Response:
            if not settings.RATE_LIMIT_ENABLED or redis_client is None:
                return func(req, *args, **kwargs)
            
            rate_key = _get_rate_limit_key(req, key_prefix)
            
            rate_limit_value = limit or settings.RATE_LIMIT_DEFAULT
            
            count = redis_client.get(rate_key)
            current = int(count) if count else 0
            
            if current >= rate_limit_value:
                ttl = redis_client.ttl(rate_key)
                reset_time = int(time.time() + ttl) if ttl > 0 else int(time.time() + period)
                
                response = exc.HTTPTooManyRequests(
                    json={"error": "Rate limit exceeded"},
                    content_type="application/json"
                )
                
                response.headers["X-RateLimit-Limit"] = str(rate_limit_value)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(reset_time)
                response.headers["Retry-After"] = str(ttl if ttl > 0 else period)
                
                return response
            
            pipe = redis_client.pipeline()
            pipe.incr(rate_key)
            
            if current == 0:
                pipe.expire(rate_key, period)
            
            pipe.execute()
            
            response = func(req, *args, **kwargs)
            
            remaining = max(0, rate_limit_value - (current + 1))
            ttl = redis_client.ttl(rate_key)
            reset_time = int(time.time() + ttl) if ttl > 0 else int(time.time() + period)
            
            response.headers["X-RateLimit-Limit"] = str(rate_limit_value)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            
            return response
        
        return wrapper
    
    return decorator 