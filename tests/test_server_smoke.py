"""Smoke test: the unified server exposes exactly the expected tool surface."""
import asyncio

from unified_mcp_server import app


def test_server_exposes_28_tools():
    tools = asyncio.run(app.get_tools())
    assert len(tools) == 28
