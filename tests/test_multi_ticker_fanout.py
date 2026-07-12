"""Multi-ticker fan-out tests for MarketRouter batch tools.

get_dividends/get_earnings/get_financial_statements/get_corporate_actions
advertise "Batch support up to 10" but historically only processed
symbol_list[0], silently dropping the rest with successful_count=1.
These tests pin the get_analyst_data-style fan-out contract:
multi input → {"tickers", "data", "successful_count", "failed_count", "warnings"}
and single input keeps the flat legacy shape.
"""
import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from providers.market_router import MarketRouter
from models.unified_base import MarketType, StatementType, PeriodType


def _router_with_client(**async_methods):
    router = MarketRouter()
    client = MagicMock()
    for name, side in async_methods.items():
        setattr(client, name, AsyncMock(side_effect=side))
    router._client = client
    return router


# --- get_dividends ---

def _dividends_payload(ticker):
    return {
        "toplam_temettu_12ay": 5.0,
        "temettuler": [SimpleNamespace(tarih=date(2026, 4, 7), miktar=5.0)],
        "bolunmeler": [],
    }


def test_dividends_multi_returns_all_symbols():
    router = _router_with_client(get_temettu_ve_aksiyonlar_yfinance=_dividends_payload)
    res = asyncio.run(router.get_dividends(["GARAN", "ISCTR", "AKBNK", "TSKB"], MarketType.BIST))

    assert res["tickers"] == ["GARAN", "ISCTR", "AKBNK", "TSKB"]
    assert res["successful_count"] == 4
    assert res["failed_count"] == 0
    assert [d["symbol"] for d in res["data"]] == ["GARAN", "ISCTR", "AKBNK", "TSKB"]
    assert all(d["annual_dividend"] == 5.0 for d in res["data"])
    assert res["metadata"]["successful_count"] == 4
    assert res["metadata"]["failed_count"] == 0


def test_dividends_multi_partial_failure():
    def payload(ticker):
        if ticker.startswith("ISCTR"):
            raise RuntimeError("boom")
        return _dividends_payload(ticker)

    router = _router_with_client(get_temettu_ve_aksiyonlar_yfinance=payload)
    res = asyncio.run(router.get_dividends(["GARAN", "ISCTR"], MarketType.BIST))

    assert res["successful_count"] == 1
    assert res["failed_count"] == 1
    assert any("ISCTR" in w for w in res["warnings"])
    assert [d["symbol"] for d in res["data"]] == ["GARAN"]


def test_dividends_single_keeps_flat_shape():
    router = _router_with_client(get_temettu_ve_aksiyonlar_yfinance=_dividends_payload)
    res = asyncio.run(router.get_dividends("GARAN", MarketType.BIST))

    assert res["symbol"] == "GARAN"
    assert res["annual_dividend"] == 5.0
    assert "data" not in res


# --- get_earnings ---

def _earnings_payload(ticker):
    return {
        "kazanc_takvimi": SimpleNamespace(gelecek_kazanc_tarihi=date(2026, 8, 1)),
        "kazanc_tarihleri": [
            SimpleNamespace(tarih=date(2026, 5, 1), eps_tahmini=1.0,
                            rapor_edilen_eps=1.2, surpriz_yuzdesi=20.0)
        ],
        "buyume_verileri": None,
    }


def test_earnings_multi_returns_all_symbols():
    router = _router_with_client(get_kazanc_takvimi_yfinance=_earnings_payload)
    res = asyncio.run(router.get_earnings(["GARAN", "AKBNK"], MarketType.BIST))

    assert res["tickers"] == ["GARAN", "AKBNK"]
    assert res["successful_count"] == 2
    assert [d["symbol"] for d in res["data"]] == ["GARAN", "AKBNK"]
    assert all(d["next_earnings_date"] == "2026-08-01" for d in res["data"])


def test_earnings_single_keeps_flat_shape():
    router = _router_with_client(get_kazanc_takvimi_yfinance=_earnings_payload)
    res = asyncio.run(router.get_earnings("GARAN", MarketType.BIST))

    assert res["symbol"] == "GARAN"
    assert res["next_earnings_date"] == "2026-08-01"
    assert "data" not in res


# --- get_financial_statements ---

def _statements_payload(symbol, period_str, last_n=None):
    return {"tablo": [{"Kalem": "Toplam Varlıklar", "2025/12": 100.0, "2024/12": 90.0}]}


def test_financial_statements_multi_returns_all_symbols():
    router = _router_with_client(get_bilanco=_statements_payload)
    res = asyncio.run(router.get_financial_statements(
        ["GARAN", "AKBNK"], MarketType.BIST, StatementType.BALANCE, PeriodType.ANNUAL))

    assert res["tickers"] == ["GARAN", "AKBNK"]
    assert res["successful_count"] == 2
    symbols = [d["symbol"] for d in res["data"]]
    assert symbols == ["GARAN", "AKBNK"]
    for d in res["data"]:
        assert d["statements"][0]["statement_type"] == "balance"
        assert d["statements"][0]["data"]["Toplam Varlıklar"] == [100.0, 90.0]


def test_financial_statements_single_keeps_flat_shape():
    router = _router_with_client(get_bilanco=_statements_payload)
    res = asyncio.run(router.get_financial_statements(
        "GARAN", MarketType.BIST, StatementType.BALANCE, PeriodType.ANNUAL))

    assert "statements" in res
    assert res["statements"][0]["symbol"] == "GARAN"
    assert "data" not in res


# --- get_corporate_actions ---

def _capital_payload(symbol, yil=0):
    return {"sermaye_artirimlari": [{
        "tarih": "2025-06-01", "tip_kodu": "02", "tip": "Bedelsiz",
        "tip_en": "Bonus Issue", "bedelli_oran": None, "bedelli_tutar": None,
        "bedelsiz_ic_kaynak_oran": 100.0, "bedelsiz_temettu_oran": None,
        "onceki_sermaye": 100.0, "sonraki_sermaye": 200.0,
    }]}


def _isyatirim_temettu_payload(symbol, yil=0):
    return {"temettuler": [{"tarih": "2026-04-07", "toplam_tutar": 1000.0, "brut_oran": 50.0}]}


def _corporate_actions_router():
    # get_corporate_actions absorbed get_dividends, so it now also pulls the yfinance
    # per-share dividends and splits. Two sources, two shapes, deliberately named
    # apart: `dividends` are lira per share, `dividend_rates` are percent of nominal.
    return _router_with_client(
        get_sermaye_artirimlari=_capital_payload,
        get_isyatirim_temettu=_isyatirim_temettu_payload,
        get_temettu_ve_aksiyonlar_yfinance=_dividends_payload,
    )


def test_corporate_actions_multi_returns_all_symbols():
    router = _corporate_actions_router()
    res = asyncio.run(router.get_corporate_actions(["GARAN", "AKBNK"], MarketType.BIST))

    assert res["tickers"] == ["GARAN", "AKBNK"]
    assert res["successful_count"] == 2
    assert [d["symbol"] for d in res["data"]] == ["GARAN", "AKBNK"]
    for d in res["data"]:
        assert d["capital_increases"][0]["type_code"] == "02"
        assert d["dividend_rates"][0]["gross_rate_percent"] == 50.0
        # The absorbed get_dividends data must survive the merge.
        assert d["dividends"][0]["amount"] == 5.0
        assert d["annual_dividend"] == 5.0


def test_corporate_actions_single_keeps_flat_shape():
    router = _corporate_actions_router()
    res = asyncio.run(router.get_corporate_actions("GARAN", MarketType.BIST))

    assert res["symbol"] == "GARAN"
    assert res["capital_increases"][0]["type_code"] == "02"
    assert res["dividends"][0]["amount"] == 5.0
    assert "data" not in res
