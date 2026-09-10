"""Smoke test: the unified server exposes exactly the expected tool surface."""
import asyncio

from unified_mcp_server import app
from conftest import tools_by_name


def test_server_exposes_23_tools():
    tools = asyncio.run(tools_by_name(app))
    assert len(tools) == 23


def test_compare_assets_is_exposed():
    tools = asyncio.run(tools_by_name(app))
    assert "compare_assets" in tools
