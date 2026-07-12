"""Smoke test: the unified server exposes exactly the expected tool surface."""
import asyncio

from unified_mcp_server import app


def test_server_exposes_23_tools():
    tools = asyncio.run(app.get_tools())
    assert len(tools) == 23


def test_compare_assets_is_exposed():
    tools = asyncio.run(app.get_tools())
    assert "compare_assets" in tools
