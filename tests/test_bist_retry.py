"""BIST history must survive a flaky websocket.

borsapy reaches BIST through a TradingView websocket that fails roughly half the time
with `APIError: No data received for BIST:<TICKER>`. Nothing retried anywhere, so a
single transient drop surfaced to the caller as a hard error — and it made this repo's
own test suite unreliable, which is how it was noticed.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from providers.borsapy_provider import BorsapyProvider


def _frame():
    idx = pd.to_datetime(["2026-07-08", "2026-07-09", "2026-07-10"])
    return pd.DataFrame(
        {"Open": [1.0, 1.1, 1.2], "High": [1.3, 1.3, 1.4],
         "Low": [0.9, 1.0, 1.1], "Close": [1.2, 1.2, 1.3],
         "Volume": [10, 11, 12]},
        index=idx,
    )


def test_a_transient_websocket_drop_is_retried():
    calls = {"n": 0}

    def history(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("No data received for BIST:GARAN")
        return _frame()

    ticker = MagicMock()
    ticker.history = history

    provider = BorsapyProvider()
    with patch.object(provider, "_get_ticker", return_value=ticker):
        import asyncio
        result = asyncio.run(provider.get_finansal_veri("GARAN", period="1mo"))

    assert calls["n"] == 3, "should have retried twice before succeeding"
    assert "error" not in result
    assert len(result["data"]) == 3


def test_a_persistent_failure_still_raises_rather_than_retrying_forever():
    calls = {"n": 0}

    def history(**kwargs):
        calls["n"] += 1
        raise RuntimeError("No data received for BIST:GARAN")

    ticker = MagicMock()
    ticker.history = history

    provider = BorsapyProvider()
    with patch.object(provider, "_get_ticker", return_value=ticker):
        import asyncio
        result = asyncio.run(provider.get_finansal_veri("GARAN", period="1mo"))

    assert calls["n"] <= 4, "must not retry indefinitely"
    assert "error" in result, "a genuinely dead upstream must still report failure"
