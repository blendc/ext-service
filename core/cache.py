import json
import logging
import hashlib
import functools
from typing import Any, Optional, Callable, Union, Dict, Tuple

import redis
from webob import Request, Response

from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "cache",
    "cache_response",
    "invalidate_cache",
    "clear_cache",
)

try:
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis cache")
except redis.ConnectionError:
    logger.warning("Could not connect to Redis, caching will be disabled")
    redis_client = None


def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
    key_parts = [prefix]
    
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            try:
                key_parts.append(json.dumps(arg, sort_keys=True))
            except (TypeError, ValueError):
                key_parts.append(str(hash(str(arg))))
    
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        key_parts.append(key)
        
        if isinstance(value, (str, int, float, bool)):
            key_parts.append(str(value))
        else:
            try:
                key_parts.append(json.dumps(value, sort_keys=True))
            except (TypeError, ValueError):
                key_parts.append(str(hash(str(value))))
    
    key_string = ":".join(key_parts)
    return f"cache:{hashlib.md5(key_string.encode()).hexdigest()}"


def cache(prefix: str, timeout: Optional[int] = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not settings.CACHE_ENABLED or redis_client is None:
                return func(*args, **kwargs)
            
            cache_key = _generate_cache_key(prefix, *args, **kwargs)
            cached_value = redis_client.get(cache_key)
            
            if cached_value is not None:
                try:
                    return json.loads(cached_value)
                except json.JSONDecodeError:
                    return cached_value.decode()
            
            result = func(*args, **kwargs)
            
            if result is not None:
                try:
                    redis_client.set(
                        cache_key,
                        json.dumps(result),
                        ex=timeout or settings.CACHE_DEFAULT_TIMEOUT
                    )
                except (TypeError, ValueError):
                    logger.warning(f"Could not cache result for {func.__name__}: not JSON serializable")
            
            return result
        
        return wrapper
    
    return decorator


def _generate_response_cache_key(req: Request, vary_headers: Tuple[str, ...] = ()) -> str:
    key_parts = [req.path_info]
    
    if req.query_string:
        key_parts.append(req.query_string.decode())
    
    for header in vary_headers:
        if header.lower() in req.headers:
            key_parts.append(f"{header}:{req.headers[header]}")
    
    if hasattr(req, "user_id") and req.user_id:
        key_parts.append(f"user:{req.user_id}")
    
    key_string = ":".join(key_parts)
    return f"response:{hashlib.md5(key_string.encode()).hexdigest()}"


def cache_response(timeout: Optional[int] = None, vary_headers: Tuple[str, ...] = ()) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(req: Request, *args, **kwargs) -> Response:
            if not settings.CACHE_ENABLED or redis_client is None:
                return func(req, *args, **kwargs)
            
            if req.method != "GET":
                return func(req, *args, **kwargs)
            
            cache_key = _generate_response_cache_key(req, vary_headers)
            cached_data = redis_client.get(cache_key)
            
            if cached_data is not None:
                try:
                    cached_response = json.loads(cached_data)
                    response = Response(
                        body=cached_response["body"],
                        status=cached_response["status"],
                        content_type=cached_response["content_type"]
                    )
                    
                    for name, value in cached_response["headers"].items():
                        response.headers[name] = value
                    
                    response.headers["X-Cache"] = "HIT"
                    
                    return response
                except (json.JSONDecodeError, KeyError):
                    pass
            
            response = func(req, *args, **kwargs)
            
            try:
                response_data = {
                    "body": response.body.decode() if hasattr(response.body, "decode") else response.body,
                    "status": response.status_code,
                    "content_type": response.content_type,
                    "headers": dict(response.headers)
                }
                
                redis_client.set(
                    cache_key,
                    json.dumps(response_data),
                    ex=timeout or settings.CACHE_DEFAULT_TIMEOUT
                )
                
                response.headers["X-Cache"] = "MISS"
            except (TypeError, ValueError, AttributeError):
                logger.warning("Could not cache response: not JSON serializable")
            
            return response
        
        return wrapper
    
    return decorator


def invalidate_cache(pattern: str) -> int:
    if redis_client is None:
        return 0
    
    keys = redis_client.keys(f"*{pattern}*")
    if not keys:
        return 0
    
    return redis_client.delete(*keys)


def clear_cache() -> int:
    if redis_client is None:
        return 0
    
    keys = redis_client.keys("cache:*") + redis_client.keys("response:*")
    if not keys:
        return 0
    
    return redis_client.delete(*keys) 