import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, Callable, Union

import jwt
from webob import Request, Response, exc

from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "create_token",
    "verify_token",
    "require_auth",
    "optional_auth",
    "require_roles",
)


def create_token(user_id: Union[str, int], roles: Optional[list] = None, **extra_claims) -> str:
    now = int(time.time())
    expiration = now + settings.JWT_EXPIRATION
    
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expiration,
        **extra_claims
    }
    
    if roles:
        payload["roles"] = roles
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token")
        raise exc.HTTPUnauthorized(json={"error": "Token expired"})
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise exc.HTTPUnauthorized(json={"error": "Invalid token"})


def extract_token_from_request(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.params.get("token")


def require_auth(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(req: Request, *args, **kwargs) -> Response:
        token = extract_token_from_request(req)
        if not token:
            raise exc.HTTPUnauthorized(json={"error": "Authentication required"})
        
        payload = verify_token(token)
        req.user = payload
        req.user_id = payload.get("sub")
        
        return func(req, *args, **kwargs)
    
    return wrapper


def optional_auth(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(req: Request, *args, **kwargs) -> Response:
        token = extract_token_from_request(req)
        if token:
            try:
                payload = verify_token(token)
                req.user = payload
                req.user_id = payload.get("sub")
            except exc.HTTPUnauthorized:
                req.user = None
                req.user_id = None
        else:
            req.user = None
            req.user_id = None
        
        return func(req, *args, **kwargs)
    
    return wrapper


def require_roles(roles: list) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @require_auth
        def wrapper(req: Request, *args, **kwargs) -> Response:
            user_roles = req.user.get("roles", [])
            
            if not any(role in user_roles for role in roles):
                raise exc.HTTPForbidden(json={"error": "Insufficient permissions"})
            
            return func(req, *args, **kwargs)
        
        return wrapper
    
    return decorator 