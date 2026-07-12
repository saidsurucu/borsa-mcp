"""The shared httpx client must survive an event-loop change.

`BorsaApiClient` is constructed at import time (market_router is a module-level
singleton), and it built its `httpx.AsyncClient` right there in __init__. httpx binds a
connection pool to the loop it is first used on, so once that loop closes, every
subsequent request dies with `RuntimeError: Event loop is closed`.

That much would be a test-only nuisance — production runs one long-lived loop. What made
it a real bug is what the error became: the exchange providers catch their own
exceptions and return an empty result carrying `error_message`, and the callers only
checked whether the data was empty. So "the connection is dead" reached the model as
"BTCTRY has no quote" — which reads as "this pair does not trade". A transport failure
had turned into a false statement about the market.
"""
import asyncio

import pytest

from borsa_client import BorsaApiClient


def test_the_http_client_survives_a_closed_event_loop():
    """Two separate asyncio.run() calls: the second gets a fresh loop."""
    client = BorsaApiClient()

    async def fetch():
        result = await client.get_kripto_ticker(pair_symbol="BTCTRY")
        return result

    first = asyncio.run(fetch())     # binds the pool to loop #1, which then closes
    second = asyncio.run(fetch())    # loop #2 — used to raise "Event loop is closed"

    assert first.ticker_data, "first call should have worked"
    assert second.ticker_data, (
        "the second call died with the loop: "
        f"{getattr(second, 'error_message', None)}"
    )


def test_a_transport_failure_is_not_reported_as_a_missing_quote():
    """The masking bug. get_crypto_market discarded the provider's error_message, so a
    dead connection was indistinguishable from a pair that does not trade."""
    from models.unified_base import DataType, ExchangeType
    from providers.market_router import MarketRouter

    router = MarketRouter()

    async def broken_ticker(pair_symbol=None, **kwargs):
        from models.btcturk_models import KriptoTickerSonucu
        return KriptoTickerSonucu(
            ticker_data=[], total_pairs=0,
            error_message="Event loop is closed",
        )

    from unittest.mock import AsyncMock, MagicMock
    client = MagicMock()
    client.get_kripto_ticker = AsyncMock(side_effect=broken_ticker)
    router._client = client

    from models.unified_base import MarketType
    with pytest.raises(Exception) as exc:
        asyncio.run(router.get_quote("BTCTRY", MarketType.CRYPTO_TR))

    msg = str(exc.value)
    assert "Event loop is closed" in msg, (
        f"the transport failure must reach the caller, not be recast as 'no quote': {msg}"
    )
