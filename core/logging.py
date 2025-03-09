import logging
import json
import sys
import time
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from webob import Request, Response

from core.settings import settings

__all__ = (
    "setup_logging",
    "get_logger",
    "log_request",
    "log_error",
    "log_request_middleware",
)


class JsonFormatter(logging.Formatter):
    def __init__(self, **kwargs):
        self.json_attributes = kwargs
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        for attr, value in record.__dict__.items():
            if attr not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno", "module",
                "msecs", "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread", "threadName"
            ):
                log_data[attr] = value
        
        for attr, value in self.json_attributes.items():
            log_data[attr] = value
        
        return json.dumps(log_data)


def setup_logging(
    level: Optional[str] = None,
    json_format: bool = False,
    sentry_dsn: Optional[str] = None
) -> None:
    log_level = getattr(logging, level or settings.LOG_LEVEL)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if json_format:
        formatter = JsonFormatter(
            app="ext-service",
            environment=settings.ENV
        )
    else:
        formatter = logging.Formatter(settings.LOG_FORMAT)
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    if sentry_dsn or settings.SENTRY_DSN:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,
            event_level=logging.ERROR
        )
        
        sentry_sdk.init(
            dsn=sentry_dsn or settings.SENTRY_DSN,
            environment=settings.ENV,
            integrations=[sentry_logging],
            traces_sample_rate=0.1,
        )
        
        logger = logging.getLogger(__name__)
        logger.info("Sentry integration enabled")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_request(
    req: Request,
    resp: Response,
    duration: float,
    logger: Optional[logging.Logger] = None
) -> None:
    if logger is None:
        logger = logging.getLogger("ext.http")
    
    request_info = {
        "method": req.method,
        "path": req.path,
        "query": req.query_string.decode() if req.query_string else "",
        "remote_addr": req.remote_addr,
        "user_agent": req.user_agent,
    }
    
    response_info = {
        "status": resp.status_code,
        "content_type": resp.content_type,
        "content_length": len(resp.body) if resp.body else 0,
    }
    
    logger.info(
        f"{req.method} {req.path} {resp.status_code} ({duration:.3f}s)",
        extra={
            "request": request_info,
            "response": response_info,
            "duration": duration,
        }
    )


def log_error(
    req: Request,
    error: Exception,
    logger: Optional[logging.Logger] = None
) -> None:
    if logger is None:
        logger = logging.getLogger("ext.http")
    
    request_info = {
        "method": req.method,
        "path": req.path,
        "query": req.query_string.decode() if req.query_string else "",
        "remote_addr": req.remote_addr,
        "user_agent": req.user_agent,
    }
    
    logger.error(
        f"Error processing {req.method} {req.path}: {str(error)}",
        exc_info=True,
        extra={"request": request_info}
    )
    
    if settings.SENTRY_DSN:
        sentry_sdk.capture_exception(error)


def log_request_middleware(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(req: Request, *args, **kwargs) -> Response:
        start_time = time.time()
        
        try:
            response = func(req, *args, **kwargs)
            duration = time.time() - start_time
            log_request(req, response, duration)
            return response
        except Exception as e:
            duration = time.time() - start_time
            log_error(req, e)
            raise
    
    return wrapper 