import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

import pytest
from webob import Request, Response
from webob.dec import wsgify

from core.db import db, database_connection, create_tables, drop_tables
from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "TestClient",
    "setup_test_database",
    "teardown_test_database",
    "create_test_tables",
    "drop_test_tables",
    "with_test_database",
)


class TestClient:

    def __init__(self, app):
        self.app = app
    
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        content_type: Optional[str] = None,
    ) -> Response:
        req = Request.blank(path)
        req.method = method.upper()
        
        if params:
            req.params = params
        
        if headers:
            for name, value in headers.items():
                req.headers[name] = value
        
        if json_data is not None:
            req.body = json.dumps(json_data).encode()
            req.content_type = "application/json"
        
        if data is not None:
            if isinstance(data, str):
                req.body = data.encode()
            else:
                req.body = data
            
            if content_type:
                req.content_type = content_type
        
        return req.get_response(self.app)
    
    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return self.request("GET", path, params=params, headers=headers)
    
    def post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        content_type: Optional[str] = None,
    ) -> Response:
        return self.request(
            "POST",
            path,
            params=params,
            headers=headers,
            json_data=json_data,
            data=data,
            content_type=content_type,
        )
    
    def put(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        content_type: Optional[str] = None,
    ) -> Response:
        return self.request(
            "PUT",
            path,
            params=params,
            headers=headers,
            json_data=json_data,
            data=data,
            content_type=content_type,
        )
    
    def patch(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        content_type: Optional[str] = None,
    ) -> Response:
        return self.request(
            "PATCH",
            path,
            params=params,
            headers=headers,
            json_data=json_data,
            data=data,
            content_type=content_type,
        )
    
    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return self.request("DELETE", path, params=params, headers=headers)
    
    def options(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return self.request("OPTIONS", path, params=params, headers=headers)
    
    def head(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        return self.request("HEAD", path, params=params, headers=headers)


def setup_test_database():
    test_db_name = f"test_{settings.DB_NAME}"
    
    original_db_name = settings.DB_NAME
    
    settings.DB_NAME = test_db_name
    
    with database_connection():
        db.execute_sql(f"CREATE DATABASE {test_db_name}")
    
    return original_db_name


def teardown_test_database(original_db_name: str):
    test_db_name = settings.DB_NAME
    
    if not db.is_closed():
        db.close()
    
    settings.DB_NAME = original_db_name
    with database_connection():
        db.execute_sql(f"DROP DATABASE IF EXISTS {test_db_name}")


def create_test_tables(*models):
    with database_connection():
        db.create_tables(models, safe=True)


def drop_test_tables(*models):
    with database_connection():
        db.drop_tables(models, safe=True, cascade=True)


def with_test_database(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        original_db_name = setup_test_database()
        
        try:
            return func(*args, **kwargs)
        finally:
            teardown_test_database(original_db_name)
    
    return wrapper


@pytest.fixture
def test_client(app):
    return TestClient(app)


@pytest.fixture
def test_database():
    original_db_name = setup_test_database()
    
    yield
    
    teardown_test_database(original_db_name)


@pytest.fixture
def auth_token(user_id: str = "test_user", roles: Optional[List[str]] = None):
    from core.auth import create_token
    
    return create_token(user_id, roles=roles or ["user"]) 