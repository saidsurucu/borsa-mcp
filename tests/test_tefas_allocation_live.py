"""Live TEFAS allocation tests. These hit the real endpoint on purpose.

The whole feature exists because a mocked check would have agreed with the old
"allocation is unavailable" conclusion — the JSON endpoint was there the whole
time under a new name. CLAUDE.md #11: drive the real endpoint before believing
a green suite.

Run with:  uv run python -m pytest tests/test_tefas_allocation_live.py -q
Excluded from the default run by the `live` marker.
"""
import asyncio
import time

import pytest

from providers.market_router import MarketRouter
from providers.tefas_allocation import AllocationUnavailable, fetch_allocation

pytestmark = pytest.mark.live

# TEFAS allows roughly 4 requests before returning HTTP 429 for ~45s (measured
# 2026-08-07). The provider's own 1.5s spacing is sized for real tool calls,
# which arrive seconds apart; a test file firing them back to back is the
# pathological case, so space the tests themselves out.
@pytest.fixture(autouse=True)
def _respect_tefas_rate_limit():
    yield
    time.sleep(12)


def test_snapshot_returns_a_real_breakdown():
    result = asyncio.run(fetch_allocation("TPC"))
    assert result["fund_type"] == "YAT"
    assert len(result["rows"]) == 1

    allocation = result["rows"][0]["allocation"]
    assert allocation, "TPC holds assets; an empty list would be a false claim"
    total = sum(a["weight"] for a in allocation)
    assert total == pytest.approx(100.0, abs=1.0), f"weights sum to {total}"


def test_every_returned_code_is_known_or_explicitly_unlabeled():
    result = asyncio.run(fetch_allocation("TPC"))
    for item in result["rows"][0]["allocation"]:
        assert item["label"] is not None or item["code"] in result["unlabeled"]


def test_history_spans_more_than_one_month_via_chunking():
    """A single call for this window is rejected by TEFAS ('1 ayı aşamaz').

    Getting rows back at all proves the chunking works, not just that the
    endpoint answered.
    """
    result = asyncio.run(
        fetch_allocation("TPC", start_date="2026-06-08", end_date="2026-08-07")
    )
    dates = [row["date"] for row in result["rows"]]
    assert len(dates) > 30, f"expected two months of trading days, got {len(dates)}"
    assert dates == sorted(dates), "rows must be oldest-first"
    assert len(dates) == len(set(dates)), "chunk boundaries duplicated a day"
    assert dates[0] >= "2026-06-08" and dates[-1] <= "2026-08-07"


def test_window_beyond_the_rate_limit_is_refused_up_front():
    """Failing fast beats spending minutes bouncing off HTTP 429."""
    with pytest.raises(ValueError, match="narrower window"):
        asyncio.run(
            fetch_allocation("TPC", start_date="2025-01-01", end_date="2026-08-07")
        )


def test_unknown_fund_raises_rather_than_returning_empty():
    with pytest.raises(AllocationUnavailable):
        asyncio.run(fetch_allocation("ZZZZ"))


def test_pension_fund_type_is_probed():
    """AAJ is an EMK (pension) fund, so the YAT probe has to fall through.

    TEFAS signals "not in this universe" by leaking 'Index 0 out of bounds for
    length 0' rather than returning an empty list. Reading that as a hard error
    made the probe abort on the first candidate instead of trying EMK.
    """
    result = asyncio.run(fetch_allocation("AAJ"))
    assert result["fund_type"] == "EMK"
    assert result["rows"][0]["allocation"]


# --- through the router, the way the tool calls it --------------------------

def test_router_populates_portfolio():
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data("TPC", include_portfolio=True))
    assert payload["portfolio"] is not None, "the bug this feature fixes"
    assert payload["portfolio"]["allocation"]
    assert payload["portfolio_history"] is None, "no window asked for"


def test_router_adds_history_when_a_window_is_given():
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data(
        "TPC", include_portfolio=True,
        start_date="2026-07-01", end_date="2026-07-31",
    ))
    assert payload["portfolio_history"], "start_date should scope the allocation too"
    assert len(payload["portfolio_history"]) > 15
    # portfolio stays the newest row in the window
    assert payload["portfolio"] == payload["portfolio_history"][-1]
