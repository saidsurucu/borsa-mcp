"""Live allocation tests through the router. These hit real TEFAS on purpose.

The feature exists because a mocked check would have agreed with the old
"allocation is unavailable" conclusion — the JSON endpoint was there the whole
time under a new name. CLAUDE.md #11: drive the real endpoint before believing
a green suite. borsapy owns the fetching now, so what these verify is that the
integration is actually wired, not just that borsapy works.

Run with:  uv run python -m pytest tests/test_tefas_allocation_live.py -q
Excluded from the default run by the `live` marker.
"""
import asyncio
import time

import pytest

from providers.market_router import MarketRouter

pytestmark = pytest.mark.live


# TEFAS allows roughly 4 requests before returning HTTP 429 for ~45s (measured
# 2026-08-07), so space the tests out. Real tool calls arrive seconds apart;
# a test file firing them back to back is the pathological case.
@pytest.fixture(autouse=True)
def _respect_tefas_rate_limit():
    yield
    time.sleep(12)


def test_portfolio_is_populated():
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data("TPC", include_portfolio=True))

    assert payload["portfolio"] is not None, "the bug this feature fixes"
    assert payload["portfolio_history"] is None, "no window was asked for"
    assert "warnings" not in payload or not any(
        "unavailable" in w for w in payload["warnings"]
    )

    allocation = payload["portfolio"]["allocation"]
    assert allocation, "TPC holds assets; empty would be a false claim"
    total = sum(item["weight"] for item in allocation)
    assert total == pytest.approx(100.0, abs=1.0), f"weights sum to {total}"
    assert all(item["code"] for item in allocation)


def test_history_matrix_when_a_window_is_given():
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data(
        "TPC", include_portfolio=True,
        start_date="2026-07-01", end_date="2026-07-31",
    ))

    history = payload["portfolio_history"]
    assert history, "start_date should scope the allocation too"
    assert len(history) > 15

    dates = [entry["date"] for entry in history]
    assert dates == sorted(dates), "oldest first"
    assert len(dates) == len(set(dates)), "a chunk boundary duplicated a day"

    # Rectangular: every row carries the same columns, or the markdown
    # renderer falls back to dumping JSON into a cell.
    assert len({frozenset(entry) for entry in history}) == 1


def test_pension_fund_resolves_through_the_universe_probe():
    """AAJ is an EMK fund, so the YAT probe has to fall through.

    TEFAS signals "not in this universe" by leaking 'Index 0 out of bounds for
    length 0' rather than an empty list.
    """
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data("AAJ", include_portfolio=True))
    assert payload["portfolio"]["allocation"]


def test_leveraged_fund_keeps_its_negative_repo_leg():
    router = MarketRouter()
    payload = asyncio.run(router.get_fund_data("ABG", include_portfolio=True))
    weights = {
        item["code"]: item["weight"]
        for item in payload["portfolio"]["allocation"]
    }
    assert weights.get("hs", 0) > 100, "leveraged equity position"
    assert weights.get("r", 0) < 0, "the repo leg funding it must survive"


def test_unknown_fund_warns_instead_of_claiming_an_empty_portfolio():
    router = MarketRouter()
    with pytest.raises(Exception):
        # The fund itself does not exist, so the whole call fails — an
        # empty-but-successful payload would read as "exists, holds nothing".
        asyncio.run(router.get_fund_data("ZZZZ", include_portfolio=True))
