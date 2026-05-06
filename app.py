"""
ASGI application for Borsa MCP Server

This is the production ASGI application that can be run with:
    uvicorn app:app --host 0.0.0.0 --port 8000

The MCP server will be available at:
    http://localhost:8000/mcp/
"""

from starlette.responses import JSONResponse
from unified_mcp_server import app as mcp

# Add health check endpoint to the MCP server
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Dokploy and other monitoring services"""
    return JSONResponse({
        "status": "healthy",
        "service": "Borsa MCP Server",
        "version": "0.9.0"
    })

# Create ASGI app directly from FastMCP server
# This avoids routing issues with nested mounts
app = mcp.http_app()

# Endpoints:
# - /mcp/ - MCP server (Streamable HTTP transport, default FastMCP path)
# - /health - Health check for monitoring
# Run with: uvicorn app:app --host 0.0.0.0 --port 8000
