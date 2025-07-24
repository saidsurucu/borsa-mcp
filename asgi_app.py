"""
ASGI application for Borsa MCP Server

This module provides ASGI/HTTP access to the Borsa MCP server,
allowing it to be deployed as a web service with FastAPI wrapper
for proper middleware support.

Usage:
    uvicorn asgi_app:app --host 0.0.0.0 --port 8000
"""

import os
import logging
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Import the MCP server
from borsa_mcp_server import app as mcp_server

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base URL configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Configure CORS
cors_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Configure JSON encoder for proper Turkish character support
class UTF8JSONResponse(JSONResponse):
    def __init__(self, content=None, status_code=200, headers=None, **kwargs):
        if headers is None:
            headers = {}
        headers["Content-Type"] = "application/json; charset=utf-8"
        super().__init__(content, status_code, headers, **kwargs)
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

# Configure middleware
custom_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Session-ID"],
    ),
]

# MCP server is already imported as mcp_server

# Create MCP Starlette sub-application with root path - mount will add /mcp prefix
mcp_app = mcp_server.http_app(path="/")
logger.info(f"MCP Starlette app created - type: {type(mcp_app)}")

# Create FastAPI wrapper application
app = FastAPI(
    title="Borsa MCP Server",
    description="MCP server for Istanbul Stock Exchange (BIST) and cryptocurrency data",
    version="0.1.0",
    middleware=custom_middleware,
    default_response_class=UTF8JSONResponse,  # Use UTF-8 JSON encoder
    redirect_slashes=False  # Disable to prevent 307 redirects on /mcp endpoint
)

# FastAPI health check endpoint - BEFORE mounting MCP app
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "Borsa MCP Server",
        "version": "0.1.0",
        "tools_count": len(mcp_server._tool_manager._tools) if hasattr(mcp_server, '_tool_manager') else 40
    }

# Add explicit redirect for /mcp to /mcp/ with method preservation
@app.api_route("/mcp", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def redirect_to_slash(request: Request):
    """Redirect /mcp to /mcp/ preserving HTTP method with 308"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/mcp/", status_code=308)

# Debug endpoint to test routing
@app.get("/debug/test")
async def debug_test():
    """Debug endpoint to test if FastAPI routes work"""
    return {"message": "FastAPI routes working", "debug": True}

# FastAPI root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Borsa MCP Server",
        "description": "MCP server for Istanbul Stock Exchange (BIST) and cryptocurrency data",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health",
            "status": "/status"
        },
        "transports": {
            "http": "/mcp"
        },
        "supported_data_sources": [
            "KAP (Public Disclosure Platform)",
            "Yahoo Finance",
            "TEFAS (Turkish Electronic Fund Trading Platform)", 
            "BtcTurk Cryptocurrency Exchange",
            "Coinbase Global Cryptocurrency Exchange",
            "Dovizcom Currency & Commodities",
            "Turkish Economic Calendar"
        ],
        "tools_count": len(mcp_server._tool_manager._tools) if hasattr(mcp_server, '_tool_manager') else 40
    }

# Standard well-known discovery endpoint
@app.get("/.well-known/mcp")
async def well_known_mcp():
    """Standard MCP discovery endpoint"""
    return {
        "mcp_server": {
            "name": "Borsa MCP Server",
            "version": "0.1.0",
            "endpoint": f"{BASE_URL}/mcp",
            "capabilities": ["tools", "resources"],
            "tools_count": len(mcp_server._tool_manager._tools) if hasattr(mcp_server, '_tool_manager') else 40
        }
    }

# MCP Discovery endpoint for ChatGPT integration
@app.get("/mcp/discovery")
async def mcp_discovery():
    """MCP Discovery endpoint for ChatGPT and other MCP clients"""
    return {
        "name": "Borsa MCP Server",
        "description": "MCP server for Istanbul Stock Exchange (BIST) and cryptocurrency data",
        "version": "0.1.0",
        "protocol": "mcp",
        "transport": "http",
        "endpoint": "/mcp",
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": False
        },
        "tools_count": len(mcp_server._tool_manager._tools) if hasattr(mcp_server, '_tool_manager') else 40,
        "contact": {
            "url": BASE_URL
        }
    }

# FastAPI status endpoint
@app.get("/status")
async def status():
    """Status endpoint with detailed information"""
    tools = []
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        for tool in mcp_server._tool_manager._tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.description[:100] + "..." if len(tool.description) > 100 else tool.description
            })
    
    return {
        "status": "operational",
        "tools": tools,
        "total_tools": len(tools),
        "transport": "streamable_http",
        "architecture": "FastAPI wrapper + MCP Starlette sub-app",
        "data_sources": {
            "kap": "758 BIST companies",
            "yahoo_finance": "Historical data and indices",
            "tefas": "836+ Turkish funds",
            "btcturk": "295+ cryptocurrency pairs",
            "coinbase": "500+ global crypto pairs",
            "dovizcom": "28+ currencies and commodities"
        }
    }

# Mount MCP app at /mcp/ with trailing slash
app.mount("/mcp/", mcp_app)

# Set the lifespan context after mounting if available
if hasattr(mcp_app, 'lifespan'):
    app.router.lifespan_context = mcp_app.lifespan

logger.info("MCP app mounted successfully at /mcp/")

# Export for uvicorn
__all__ = ["app"]