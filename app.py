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
# This avoids routing issues with nested mounts.
#
# stateless_http=True: every request is self-contained; no per-client transport
# object is kept server-side. The stateful default keeps a transport (task group,
# memory streams, buffers) per `initialize` until the client sends DELETE /mcp —
# which claude.ai and most clients never do. Measured on the live container:
# ~11.5k sessions opened / ~750 closed per day, ~1-1.3 GB/day growth, and two
# OOM-kills at 10.8 GB RSS (2026-08-27, 2026-09-07). Nothing here needs a session:
# no progress, sampling, subscriptions or elicitation — plain request/response tools.
app = mcp.http_app(stateless_http=True)

# Endpoints:
# - /mcp/ - MCP server (Streamable HTTP transport, default FastMCP path)
# - /health - Health check for monitoring
# Run with: uvicorn app:app --host 0.0.0.0 --port 8000
