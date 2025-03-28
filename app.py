import logging
import os
import sys
from datetime import datetime

import peewee as pw

from ext import JSONResponseRouter
# from core.auth import require_auth, require_roles, create_token
from core.cache import cache_response
from core.db import BaseModel, db_connection, create_tables
from core.docs import document_route, api_docs
from core.http import response_ok, response_created, response_no_content
from core.logging import setup_logging
from core.metrics import metrics_middleware, setup_metrics
from core.rate_limit import rate_limit
from core.serializer import BaseSchema
from core.settings import settings
from core.validate import verify

from marshmallow import fields

setup_logging()

logger = logging.getLogger(__name__)

router = JSONResponseRouter()


class User(BaseModel):
    username = pw.CharField(max_length=100, unique=True)
    email = pw.CharField(max_length=100, unique=True)
    password_hash = pw.CharField(max_length=100)
    is_active = pw.BooleanField(default=True)
    created_at = pw.DateTimeField(default=datetime.now)
    updated_at = pw.DateTimeField(default=datetime.now)


class Task(BaseModel):
    title = pw.CharField(max_length=100)
    description = pw.TextField(null=True)
    is_completed = pw.BooleanField(default=False)
    user = pw.ForeignKeyField(User, backref="tasks")
    created_at = pw.DateTimeField(default=datetime.now)
    updated_at = pw.DateTimeField(default=datetime.now)


class UserSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    username = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(load_only=True, required=True)
    is_active = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class TaskSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    title = fields.String(required=True)
    description = fields.String(allow_none=True)
    is_completed = fields.Boolean()
    user_id = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


user_schema = {
    "username": {"type": "string", "required": True, "minlength": 3, "maxlength": 50},
    "email": {"type": "string", "required": True, "regex": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"},
    "password": {"type": "string", "required": True, "minlength": 8},
}

task_schema = {
    "title": {"type": "string", "required": True, "minlength": 1, "maxlength": 100},
    "description": {"type": "string", "nullable": True},
    "is_completed": {"type": "boolean", "default": False},
}

login_schema = {
    "username": {"type": "string", "required": True},
    "password": {"type": "string", "required": True},
}


@router.get("/")
@metrics_middleware
@document_route(
    summary="API root",
    description="API",
    tags=["system"],
    response_schema={
        "content_type": "application/json",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "description": {"type": "string"},
            },
        },
    },
    status_codes={
        200: "Success",
    },
)
def index(req):
    return response_ok({
        "name": "Sample API",
        "version": "1.0.0",
        "description": "Sample API ext-service",
    })


@router.get("/docs")
@metrics_middleware
@document_route(
    summary="API documentation",
    description="HTML for the API",
    tags=["system"],
    status_codes={
        200: "Success",
    },
)
def docs(req):
    return api_docs.serve_documentation(req)


@router.get("/openapi.json")
@metrics_middleware
@document_route(
    summary="openAPI specification",
    description="API",
    tags=["system"],
    status_codes={
        200: "Success",
    },
)
def openapi(req):
    return api_docs.serve_openapi_spec(req)


@router.post("/users")
@metrics_middleware
@rate_limit(limit=10, period=60, key_prefix="register")
@verify(user_schema)
@document_route(
    summary="Register",
    description="a new user",
    tags=["users"],
    request_schema={
        "content_type": "application/json",
        "schema": user_schema,
    },
    response_schema={
        "content_type": "application/json",
        "schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "username": {"type": "string"},
                "email": {"type": "string"},
                "is_active": {"type": "boolean"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        },
    },
    status_codes={
        201: "User created",
        400: "Invalid request",
        409: "Username or email already exists",
    },
)
@db_connection
def register_user(req):
    data = req.data
    
    if User.get_or_none(User.username == data.username):
        return response_ok({"error": "Username already exists"}, status=409)
    
    if User.get_or_none(User.email == data.email):
        return response_ok({"error": "Email already exists"}, status=409)
    
    user = User.create(
        username=data.username,
        email=data.email,
        password_hash=data.password,
    )
    
    return response_created(UserSchema.serialize_one(user))


@router.post("/auth/login")
@metrics_middleware
@rate_limit(limit=5, period=60, key_prefix="login")
@verify(login_schema)
@document_route(
    summary="Login",
    description="with username and password",
    tags=["auth"],
    request_schema={
        "content_type": "application/json",
        "schema": login_schema,
    },
    response_schema={
        "content_type": "application/json",
        "schema": {
            "type": "object",
            "properties": {
                "token": {"type": "string"},
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
        },
    },
    status_codes={
        200: "Login successful",
        400: "Invalid request",
        401: "Invalid credentials",
    },
)

@db_connection
def create_task(req):
    data = req.data
    
    user_id = req.user_id
    
    task = Task.create(
        title=data.title,
        description=data.description,
        is_completed=data.is_completed,
        user_id=user_id,
    )
    
    return response_created(TaskSchema.serialize_one(task))


@db_connection
def get_task(req, task_id):
    user_id = req.user_id
    
    task = Task.get_or_none(Task.id == task_id, Task.user_id == user_id)
    
    if not task:
        return response_ok({"error": "Task not found"}, status=404)
    
    return response_ok(TaskSchema.serialize_one(task))


@db_connection
def get_all_users(req):
    users = User.select()
    
    return response_ok(UserSchema.serialize_many(users))


# def create_admin_user():
#     with db_connection():
#         admin = User.get_or_none(User.username == "admin")
#
#         if not admin:
#             User.create(
#                 username="admin",
#                 email="admin@example.com",
#                 password_hash="admin123",
#             )
#             logger.info("Admin user created")


def init_db():
    create_tables(User, Task)

#     create_admin_user()


def main():
    """Run the application."""
    print("Starting ext-service application...")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")

    # Set up metrics
    print("Setting up metrics...")
    metrics_port = settings.METRICS_PORT
    setup_metrics(port=metrics_port)
    print("Metrics setup complete!")
    
    # Run server
    from wsgiref.simple_server import make_server
    
    host = settings.HOST
    port = settings.PORT
    
    print(f"Starting server at http://{host}:{port}")
    print(f"API documentation available at http://{host}:{port}/docs")
    print(f"Metrics available at http://{host}:{metrics_port}")
    print(f"RPC endpoint available at http://{host}:{port}/rpc")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        server = make_server(host, port, router.app)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nError starting server: {e}")
        raise


if __name__ == "__main__":
    main() 