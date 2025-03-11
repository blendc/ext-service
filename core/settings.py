import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

ENV = os.getenv("ENV", "development")

config_file = BASE_DIR / f"config/{ENV}.yaml"
config: Dict[str, Any] = {}

if config_file.exists():
    with open(config_file, "r") as f:
        config = yaml.safe_load(f) or {}


class FlexibleDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class Settings(FlexibleDict):

    def __init__(self):
        super().__init__()
        
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
        self.ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
        
        self.DB_TYPE = os.getenv("DB_TYPE", "sqlite")
        self.DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "db.sqlite"))
        self.DB_NAME = os.getenv("DB_NAME", "ext_service")
        self.DB_USER = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = int(os.getenv("DB_PORT", "5432"))
        self.DB_MAX_CONNECTIONS = int(os.getenv("DB_MAX_CONNECTIONS", "10"))
        self.DB_STALE_TIMEOUT = int(os.getenv("DB_STALE_TIMEOUT", "300"))
        
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        self.JWT_SECRET = os.getenv("JWT_SECRET", self.SECRET_KEY)
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRATION = int(os.getenv("JWT_EXPIRATION", "3600"))
        
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        self.RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
        self.RATE_LIMIT_DEFAULT = int(os.getenv("RATE_LIMIT_DEFAULT", "100"))
        
        self.CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300"))
        
        self.SENTRY_DSN = os.getenv("SENTRY_DSN", "")
        
        self.RPC_TIMEOUT = float(os.getenv("RPC_TIMEOUT", "10.0"))
        self.RPC_MAX_RETRIES = int(os.getenv("RPC_MAX_RETRIES", "3"))
        self.RPC_RETRY_DELAY = float(os.getenv("RPC_RETRY_DELAY", "0.5"))
        self.SERVICE_NAME = os.getenv("SERVICE_NAME", "ext-service")

        self.USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8000")
        self.TASK_SERVICE_URL = os.getenv("TASK_SERVICE_URL", "http://localhost:8001")
        
        for key, value in config.items():
            self[key.upper()] = value
    
    def get_nested(self, key: str, default: Optional[Any] = None) -> Any:
        keys = key.split(".")
        value = self
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)