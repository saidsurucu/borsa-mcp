"""Tests for the BIST P/E (F/K) yfinance fallback in MarketRouter.

İş Yatırım/borsapy frequently omits trailingPE for BIST names (e.g. ASELS),
which then gets null-stripped from the response and looks like missing data.
The router backfills F/K from yfinance's consolidated trailing P/E.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from providers.market_router import MarketRouter
from models.unified_base import MarketType, RatioSetType


def _build_router(fk_orani, yf_pe):
    """MarketRouter with a mocked client: İş Yatırım ratios + yfinance fast info."""
    router = MarketRouter()
    client = MagicMock()
    client.get_finansal_oranlar = AsyncMock(return_value={
        "kapanis_fiyati": 374.0,
        "fk_orani": fk_orani,   # None simulates the missing-P/E case
        "pd_dd": 6.0,
        "fd_favok": 31.5,
        "fd_satislar": 8.55,
    })
    client.yfinance_provider = MagicMock()
    client.yfinance_provider.get_hizli_bilgi = AsyncMock(return_value={
        "bilgiler": SimpleNamespace(pe_ratio=yf_pe, last_price=374.0)
    })
    router._client = client
    return router


def test_pe_backfilled_from_yfinance_when_isyatirim_missing():
    router = _build_router(fk_orani=None, yf_pe=52.42)
    res = asyncio.run(router.get_financial_ratios("ASELS", MarketType.BIST, RatioSetType.VALUATION))

    valuation = res["valuation"]
    assert valuation["pe_ratio"] == 52.42, "F/K should be backfilled from yfinance"
    # Other İş Yatırım ratios remain untouched.
    assert valuation["pb_ratio"] == 6.0
    assert valuation["ev_ebitda"] == 31.5
    warnings = res["metadata"]["warnings"]
    assert any("Yahoo Finance" in w for w in warnings)
    router._client.yfinance_provider.get_hizli_bilgi.assert_awaited_once()


def test_isyatirim_pe_preferred_when_present():
    router = _build_router(fk_orani=12.3, yf_pe=99.9)
    res = asyncio.run(router.get_financial_ratios("GARAN", MarketType.BIST, RatioSetType.VALUATION))

    assert res["valuation"]["pe_ratio"] == 12.3, "İş Yatırım P/E should be kept when available"
    # yfinance fallback must not be invoked when İş Yatırım already supplied F/K.
    router._client.yfinance_provider.get_hizli_bilgi.assert_not_awaited()


def test_pe_absent_when_both_sources_missing():
    router = _build_router(fk_orani=None, yf_pe=None)
    res = asyncio.run(router.get_financial_ratios("ASELS", MarketType.BIST, RatioSetType.VALUATION))

    # No fabricated value: pe_ratio stays None and is later null-stripped.
    assert res["valuation"]["pe_ratio"] is None
