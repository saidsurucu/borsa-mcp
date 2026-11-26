"""Warn that İş Yatırım's year-end figures may be inflation-indexed.

For non-bank BIST companies the İş Yatırım statement API returned FY2025 and FY2024
columns multiplied by Turkish CPI factors (THYAO FY2025 revenue 1,187.8 bn TRY against
955.5 bn reported), while interim columns were untouched. Its P/E and EV multiples
were consistent with the inflated figures. Numbers are passed through unchanged; the
caller has to be told.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from models.unified_base import MarketType, PeriodType, RatioSetType, StatementType
from providers.borsapy_provider import BorsapyProvider
from providers.market_router import MarketRouter

MARKER = "endekslen"


def _router(**client_methods):
    router = MarketRouter()
    client = MagicMock()
    for name, value in client_methods.items():
        setattr(client, name, AsyncMock(return_value=value))
    router._client = client
    return router


def _notes(response):
    """Every warning that mentions indexing, wherever the envelope carries it."""
    found = list(response.get("warnings") or [])
    found += (response.get("metadata") or {}).get("warnings") or []
    return sorted({w for w in found if MARKER in w})


# --- provider: which results carry the risk --------------------------------------

def _provider(monkeypatch, bank):
    def get_income_stmt(quarterly, financial_group=None, **kwargs):
        if bank and financial_group is None:
            raise ValueError("no XI_29 table for a bank")
        return pd.DataFrame({"2025Q4": [1.0]}, index=pd.Index(["Satış Gelirleri"], name="Item"))

    provider = BorsapyProvider()
    monkeypatch.setattr(
        provider, "_get_ticker", lambda code: SimpleNamespace(get_income_stmt=get_income_stmt)
    )
    return provider


def test_industrial_statements_are_flagged(monkeypatch):
    res = asyncio.run(_provider(monkeypatch, bank=False).get_kar_zarar("THYAO", "quarterly"))

    assert res["yil_sonu_endeks_riski"] is True


def test_bank_statements_are_not_flagged(monkeypatch):
    res = asyncio.run(_provider(monkeypatch, bank=True).get_kar_zarar("GARAN", "quarterly"))

    assert res["tablo"]
    assert res["yil_sonu_endeks_riski"] is False


# --- statements --------------------------------------------------------------------

def _statements(periods, flagged=True, symbols="THYAO"):
    table = {"tablo": [{"Kalem": "Satış Gelirleri", **{p: 1.0 for p in periods}}]}
    if flagged:
        table["yil_sonu_endeks_riski"] = True
    router = _router(get_kar_zarar=table)
    return asyncio.run(router.get_financial_statements(
        symbols, MarketType.BIST, StatementType.INCOME, PeriodType.QUARTERLY
    ))


def test_quarterly_statements_name_the_affected_year_end_columns():
    (note,) = _notes(_statements(["2026Q2", "2025Q4", "2025Q3", "2024Q4", "2023Q4"]))

    assert "2025Q4, 2024Q4" in note
    assert "2026Q2" not in note and "2023Q4" not in note


def test_annual_columns_are_year_end_columns():
    (note,) = _notes(_statements(["2025", "2024", "2023"]))

    assert "2025, 2024" in note


def test_interim_only_statements_carry_no_warning():
    assert _notes(_statements(["2026Q2", "2026Q1", "2025Q3"])) == []


def test_unflagged_statements_carry_no_warning():
    # Banks, and the Yahoo fallback, which is not indexed.
    assert _notes(_statements(["2025Q4"], flagged=False)) == []


def test_each_symbol_is_named_once_in_a_batch():
    table = {"tablo": [{"Kalem": "x", "2025Q4": 1.0}], "yil_sonu_endeks_riski": True}
    router = _router(get_bilanco=table, get_kar_zarar=table, get_nakit_akisi=table)

    res = asyncio.run(router.get_financial_statements(
        ["THYAO", "PGSUS"], MarketType.BIST, StatementType.ALL, PeriodType.QUARTERLY
    ))

    notes = _notes(res)
    assert [n.split(":")[0] for n in notes] == ["PGSUS", "THYAO"]


# --- ratio responses -------------------------------------------------------------

def _ratios(valuation, yahoo_pe=None):
    router = _router(get_finansal_oranlar=valuation)
    router._client.yfinance_provider.get_hizli_bilgi = AsyncMock(return_value={
        "bilgiler": SimpleNamespace(pe_ratio=yahoo_pe, last_price=100.0)
    })
    return asyncio.run(router.get_financial_ratios("THYAO", MarketType.BIST, RatioSetType.VALUATION))


def test_valuation_ratios_are_flagged():
    assert _notes(_ratios({"fk_orani": 2.9, "pd_dd": 0.4, "fd_favok": 5.9, "fd_satislar": 0.95}))


def test_price_to_book_alone_is_not_flagged():
    assert _notes(_ratios({"pd_dd": 0.4})) == []


def test_a_pe_taken_from_yahoo_is_not_flagged():
    assert _notes(_ratios({"pd_dd": 0.4}, yahoo_pe=3.5)) == []


def _quote(pe):
    router = _router(get_hizli_bilgi={"hizli_bilgi": SimpleNamespace(symbol="THYAO", pe_ratio=pe)})
    return asyncio.run(router.get_quote("THYAO", MarketType.BIST))


def test_quote_with_a_pe_is_flagged():
    assert _notes(_quote(2.9))


def test_quote_without_a_pe_is_not_flagged():
    assert _notes(_quote(None)) == []


def test_us_quote_is_not_flagged():
    router = _router(get_us_quick_info={"bilgiler": SimpleNamespace(symbol="AAPL", pe_ratio=30.0)})

    assert _notes(asyncio.run(router.get_quote("AAPL", MarketType.US))) == []


def _sector_router():
    router = _router()
    router._bist_sector_peers = AsyncMock(return_value=(["PGSUS"], "XUHIZ"))
    router._fetch_bist_metrics = AsyncMock(return_value={
        "THYAO": {"pe_ratio": 2.9, "pb_ratio": 0.4},
        "PGSUS": {"pe_ratio": 30.0, "pb_ratio": 0.6},
    })
    return router


def test_sector_comparison_is_flagged():
    res = asyncio.run(_sector_router().get_sector_comparison("THYAO", MarketType.BIST))

    assert len(_notes(res)) == 1


def test_sector_comparison_batch_keeps_the_warning():
    res = asyncio.run(
        _sector_router().get_sector_comparison_multi(["THYAO", "PGSUS"], MarketType.BIST)
    )

    assert len(_notes(res)) == 1


def _profile_router():
    return _router(get_sirket_bilgileri_yfinance={
        "bilgiler": SimpleNamespace(symbol="THYAO", trailingPE=2.9)
    })


def test_profile_with_a_pe_is_flagged():
    res = asyncio.run(_profile_router().get_profile("THYAO", MarketType.BIST))

    assert _notes(res)


def test_profile_batch_is_flagged():
    res = asyncio.run(_profile_router().get_profile(["THYAO", "PGSUS"], MarketType.BIST))

    assert len(_notes(res)) == 1


def test_screener_results_with_a_pe_are_flagged():
    router = _router(screen_bist_stocks={"results": [{"ticker": "THYAO", "pe_ratio": 2.9}]})

    assert _notes(asyncio.run(router.screen_securities(MarketType.BIST)))
