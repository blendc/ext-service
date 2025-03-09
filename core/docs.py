import inspect
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from webob import Request, Response

from core.settings import settings

logger = logging.getLogger(__name__)

__all__ = (
    "APIDocumentation",
    "document_route",
    "generate_openapi_spec",
)


class APIDocumentation:
    def __init__(self):
        self.routes = []
        self.tags = set()
        self.schemas = {}
    
    def add_route(
        self,
        path: str,
        method: str,
        summary: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        request_schema: Optional[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        status_codes: Optional[Dict[int, str]] = None,
        deprecated: bool = False,
        security: Optional[List[Dict[str, List[str]]]] = None,
    ) -> None:
        if tags:
            self.tags.update(tags)
        
        route_doc = {
            "path": path,
            "method": method.upper(),
            "summary": summary,
            "description": description or summary,
            "tags": tags or [],
            "request_schema": request_schema,
            "response_schema": response_schema,
            "status_codes": status_codes or {},
            "deprecated": deprecated,
            "security": security or [],
        }
        
        self.routes.append(route_doc)
        
        if request_schema and "schema" in request_schema:
            schema_name = request_schema.get("schema_name", f"Request{len(self.schemas)}")
            self.schemas[schema_name] = request_schema["schema"]
        
        if response_schema and "schema" in response_schema:
            schema_name = response_schema.get("schema_name", f"Response{len(self.schemas)}")
            self.schemas[schema_name] = response_schema["schema"]
    
    def add_schema(self, name: str, schema: Dict[str, Any]) -> None:
        self.schemas[name] = schema
    
    def add_tag(self, name: str, description: Optional[str] = None) -> None:
        self.tags.add((name, description))
    
    def generate_html(self) -> str:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>API Documentation</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1, h2, h3, h4 {
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                }
                h1 { font-size: 2.5em; }
                h2 { font-size: 2em; }
                h3 { font-size: 1.5em; }
                h4 { font-size: 1.2em; }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                }
                th, td {
                    text-align: left;
                    padding: 12px;
                    border-bottom: 1px solid #ddd;
                }
                th {
                    background-color: #f2f2f2;
                }
                code {
                    background-color: #f5f5f5;
                    padding: 2px 5px;
                    border-radius: 3px;
                    font-family: monospace;
                }
                pre {
                    background-color: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                }
                .method {
                    display: inline-block;
                    padding: 5px 10px;
                    border-radius: 5px;
                    color: white;
                    font-weight: bold;
                    min-width: 80px;
                    text-align: center;
                }
                .get { background-color: #61affe; }
                .post { background-color: #49cc90; }
                .put { background-color: #fca130; }
                .delete { background-color: #f93e3e; }
                .patch { background-color: #50e3c2; }
                .head { background-color: #9012fe; }
                .options { background-color: #0d5aa7; }
                .deprecated {
                    text-decoration: line-through;
                    opacity: 0.7;
                }
                .tag {
                    display: inline-block;
                    background-color: #e8f4f8;
                    padding: 2px 8px;
                    border-radius: 3px;
                    margin-right: 5px;
                    font-size: 0.9em;
                }
                .endpoint {
                    margin-bottom: 2em;
                    padding: 1em;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
                .endpoint:hover {
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                .status-code {
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 3px;
                    margin-right: 5px;
                    font-size: 0.9em;
                }
                .status-2xx { background-color: #e8f5e9; }
                .status-3xx { background-color: #e3f2fd; }
                .status-4xx { background-color: #fff3e0; }
                .status-5xx { background-color: #ffebee; }
            </style>
        </head>
        <body>
            <h1>API Documentation</h1>
        """
        
        if self.tags:
            html += "<h2>Tags</h2><ul>"
            for tag in sorted(self.tags):
                if isinstance(tag, tuple):
                    name, description = tag
                    html += f"<li><strong>{name}</strong>: {description or ''}</li>"
                else:
                    html += f"<li><strong>{tag}</strong></li>"
            html += "</ul>"
        
        routes_by_tag = {}
        for route in self.routes:
            for tag in route["tags"] or ["default"]:
                if tag not in routes_by_tag:
                    routes_by_tag[tag] = []
                routes_by_tag[tag].append(route)
        
        for tag, routes in sorted(routes_by_tag.items()):
            html += f"<h2>{tag}</h2>"
            
            for route in sorted(routes, key=lambda r: r["path"]):
                method_class = route["method"].lower()
                deprecated_class = " deprecated" if route["deprecated"] else ""
                
                html += f"""
                <div class="endpoint{deprecated_class}">
                    <h3>
                        <span class="method {method_class}">{route["method"]}</span>
                        <code>{route["path"]}</code>
                    </h3>
                    <p>{route["summary"]}</p>
                """
                
                if route["description"] and route["description"] != route["summary"]:
                    html += f"<p>{route['description']}</p>"
                
                if route["tags"]:
                    html += "<p>"
                    for tag in route["tags"]:
                        html += f'<span class="tag">{tag}</span>'
                    html += "</p>"
                
                if route["request_schema"]:
                    html += "<h4>Request</h4>"
                    if "content_type" in route["request_schema"]:
                        html += f"<p>Content-Type: <code>{route['request_schema']['content_type']}</code></p>"
                    if "schema" in route["request_schema"]:
                        html += "<pre><code>" + json.dumps(route["request_schema"]["schema"], indent=2) + "</code></pre>"
                
                if route["response_schema"]:
                    html += "<h4>Response</h4>"
                    if "content_type" in route["response_schema"]:
                        html += f"<p>Content-Type: <code>{route['response_schema']['content_type']}</code></p>"
                    if "schema" in route["response_schema"]:
                        html += "<pre><code>" + json.dumps(route["response_schema"]["schema"], indent=2) + "</code></pre>"
                
                if route["status_codes"]:
                    html += "<h4>Status Codes</h4><ul>"
                    for code, description in sorted(route["status_codes"].items()):
                        status_class = f"status-{str(code)[0]}xx"
                        html += f'<li><span class="status-code {status_class}">{code}</span> {description}</li>'
                    html += "</ul>"
                
                if route["security"]:
                    html += "<h4>Security</h4><ul>"
                    for security in route["security"]:
                        for scheme, scopes in security.items():
                            html += f"<li><strong>{scheme}</strong>"
                            if scopes:
                                html += ": " + ", ".join(scopes)
                            html += "</li>"
                    html += "</ul>"
                
                html += "</div>"
        
        if self.schemas:
            html += "<h2>Schemas</h2>"
            for name, schema in sorted(self.schemas.items()):
                html += f"<h3>{name}</h3>"
                html += "<pre><code>" + json.dumps(schema, indent=2) + "</code></pre>"
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def generate_openapi_spec(self, info: Dict[str, Any]) -> Dict[str, Any]:
        paths = {}
        components = {
            "schemas": self.schemas,
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        }
        
        for route in self.routes:
            path = route["path"]
            method = route["method"].lower()
            
            path_for_openapi = re.sub(r"{([^}]+)}", r"{\1}", path)
            
            if path_for_openapi not in paths:
                paths[path_for_openapi] = {}
            
            operation = {
                "summary": route["summary"],
                "description": route["description"],
                "tags": route["tags"],
                "deprecated": route["deprecated"],
                "responses": {}
            }
            
            if route["request_schema"]:
                operation["requestBody"] = {
                    "content": {
                        route["request_schema"].get("content_type", "application/json"): {
                            "schema": route["request_schema"].get("schema", {})
                        }
                    },
                    "required": True
                }
            
            for code, description in route["status_codes"].items():
                response = {
                    "description": description
                }
                
                if code == 200 and route["response_schema"]:
                    response["content"] = {
                        route["response_schema"].get("content_type", "application/json"): {
                            "schema": route["response_schema"].get("schema", {})
                        }
                    }
                
                operation["responses"][str(code)] = response
            
            if not operation["responses"]:
                operation["responses"]["200"] = {
                    "description": "Successful operation"
                }
            
            if route["security"]:
                operation["security"] = route["security"]
            
            paths[path_for_openapi][method] = operation
        
        openapi_spec = {
            "openapi": "3.0.0",
            "info": info,
            "paths": paths,
            "components": components,
            "tags": [{"name": tag[0], "description": tag[1]} if isinstance(tag, tuple) else {"name": tag} for tag in sorted(self.tags)]
        }
        
        return openapi_spec
    
    def serve_documentation(self, req: Request) -> Response:
        html = self.generate_html()
        return Response(
            body=html,
            content_type="text/html"
        )
    
    def serve_openapi_spec(self, req: Request) -> Response:
        info = {
            "title": getattr(settings, "API_TITLE", "API Documentation"),
            "version": getattr(settings, "API_VERSION", "1.0.0"),
            "description": getattr(settings, "API_DESCRIPTION", "")
        }
        
        openapi_spec = self.generate_openapi_spec(info)
        
        return Response(
            body=json.dumps(openapi_spec, indent=2),
            content_type="application/json"
        )


api_docs = APIDocumentation()


def document_route(
    summary: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    request_schema: Optional[Dict[str, Any]] = None,
    response_schema: Optional[Dict[str, Any]] = None,
    status_codes: Optional[Dict[int, str]] = None,
    deprecated: bool = False,
    security: Optional[List[Dict[str, List[str]]]] = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        path = getattr(func, "_route_path", "/")
        method = getattr(func, "_route_method", "GET")
        
        api_docs.add_route(
            path=path,
            method=method,
            summary=summary,
            description=description,
            tags=tags,
            request_schema=request_schema,
            response_schema=response_schema,
            status_codes=status_codes,
            deprecated=deprecated,
            security=security,
        )
        
        return func
    
    return decorator


def generate_openapi_spec(info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if info is None:
        info = {
            "title": getattr(settings, "API_TITLE", "API Documentation"),
            "version": getattr(settings, "API_VERSION", "1.0.0"),
            "description": getattr(settings, "API_DESCRIPTION", "")
        }
    
    return api_docs.generate_openapi_spec(info) 