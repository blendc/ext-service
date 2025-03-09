import os
import logging
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

import peewee as pw
from peewee_migrate import Router
from playhouse.shortcuts import model_to_dict, dict_to_model

from core.settings import settings

logger = logging.getLogger(__name__)

if getattr(settings, 'DB_TYPE', 'sqlite') == 'postgres':
    try:
        from playhouse.pool import PooledPostgresqlDatabase
        db = PooledPostgresqlDatabase(
            settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            max_connections=settings.DB_MAX_CONNECTIONS,
            stale_timeout=settings.DB_STALE_TIMEOUT,
        )
        logger.info("Using PostgreSQL database")
    except ImportError:
        logger.warning("PostgreSQL driver not installed, falling back to SQLite")
        db_path = Path(settings.DB_PATH) if hasattr(settings, 'DB_PATH') else Path('db.sqlite')
        db = pw.SqliteDatabase(db_path)
else:
    db_path = Path(settings.DB_PATH) if hasattr(settings, 'DB_PATH') else Path('db.sqlite')
    db = pw.SqliteDatabase(db_path)
    logger.info(f"Using SQLite database at {db_path}")

router = Router(db, migrate_dir='migrations')


class BaseModel(pw.Model):

    class Meta:
        database = db

    @classmethod
    def get_or_none(cls, *query, **filters):
        try:
            return cls.get(*query, **filters)
        except cls.DoesNotExist:
            return None

    def to_dict(self, exclude=None, only=None, recurse=False, max_depth=1):
        return model_to_dict(
            self,
            exclude=exclude,
            only=only,
            recurse=recurse,
            max_depth=max_depth
        )

    @classmethod
    def from_dict(cls, data, ignore_unknown=False):
        return dict_to_model(cls, data, ignore_unknown=ignore_unknown)


@contextmanager
def database_connection():
    if db.is_closed():
        db.connect()
    try:
        yield
    finally:
        if not db.is_closed():
            db.close()


def db_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with database_connection():
            return func(*args, **kwargs)
    return wrapper


def create_tables(*models):
    with database_connection():
        db.create_tables(models, safe=True)


def drop_tables(*models):
    with database_connection():
        db.drop_tables(models, safe=True, cascade=True)


def run_migrations(fake=False):
    with database_connection():
        router.run(fake=fake)


def create_migration(name, auto=True):
    with database_connection():
        router.create(name, auto=auto)
