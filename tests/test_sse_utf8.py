import httpx
import pytest

from app import app


@pytest.mark.asyncio
async def test_sse_response_declares_utf8_charset():
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/mcp",
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
            )

    response.raise_for_status()
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert "get_bond_yields" in response.text
