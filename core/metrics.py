import time
import logging
import functools
from typing import Callable, Dict, List, Optional, Union, Any

from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server
from webob import Request, Response

from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "setup_metrics",
    "track_request_time",
    "increment_counter",
    "set_gauge",
    "observe_histogram",
    "observe_summary",
    "metrics_middleware",
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf"))
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
    ["method"]
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total number of HTTP errors",
    ["method", "endpoint", "error_type"]
)

DB_QUERY_LATENCY = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf"))
)

CACHE_HIT_COUNT = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["cache_type"]
)

CACHE_MISS_COUNT = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["cache_type"]
)

RATE_LIMIT_HIT_COUNT = Counter(
    "rate_limit_hits_total",
    "Total number of rate limit hits",
    ["endpoint"]
)


def setup_metrics(port: Optional[int] = None) -> None:
    metrics_port = port or getattr(settings, "METRICS_PORT", 8000)
    
    try:
        start_http_server(metrics_port)
        logger.info(f"Metrics server started on port {metrics_port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {str(e)}")


def track_request_time(
    method: str,
    endpoint: str,
    duration: float,
    status: int
) -> None:
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def increment_counter(
    counter: Counter,
    value: float = 1,
    **labels
) -> None:
    counter.labels(**labels).inc(value)


def set_gauge(
    gauge: Gauge,
    value: float,
    **labels
) -> None:
    gauge.labels(**labels).set(value)


def observe_histogram(
    histogram: Histogram,
    value: float,
    **labels
) -> None:
    histogram.labels(**labels).observe(value)


def observe_summary(
    summary: Summary,
    value: float,
    **labels
) -> None:
    summary.labels(**labels).observe(value)


def metrics_middleware(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(req: Request, *args, **kwargs) -> Response:
        method = req.method
        endpoint = req.path_info
        
        ACTIVE_REQUESTS.labels(method=method).inc()
        
        start_time = time.time()
        
        try:
            response = func(req, *args, **kwargs)
            duration = time.time() - start_time
            
            track_request_time(
                method=method,
                endpoint=endpoint,
                duration=duration,
                status=response.status_code
            )
            
            return response
        except Exception as e:
            duration = time.time() - start_time
            
            ERROR_COUNT.labels(
                method=method,
                endpoint=endpoint,
                error_type=type(e).__name__
            ).inc()
            
            track_request_time(
                method=method,
                endpoint=endpoint,
                duration=duration,
                status=500
            )
            
            raise
        finally:
            ACTIVE_REQUESTS.labels(method=method).dec()
    
    return wrapper


def track_db_query(query_type: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                DB_QUERY_LATENCY.labels(query_type=query_type).observe(duration)
        
        return wrapper
    
    return decorator


def track_cache(cache_type: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            if result is not None:
                CACHE_HIT_COUNT.labels(cache_type=cache_type).inc()
            else:
                CACHE_MISS_COUNT.labels(cache_type=cache_type).inc()
            
            return result
        
        return wrapper
    
    return decorator 