"""Buffett value analysis: currency, trailing-year cash flow and assumption disclosure.

Yahoo quotes THYAO in TRY but publishes its statements in USD. The analysis used to
divide those USD figures by a million, label them "Milyon TL" and compare them with a
lira share price, reporting an intrinsic value ~50x too small.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from models.unified_base import MarketType, RatioSetType
from providers.buffett_analyzer_provider import BuffettAnalyzerProvider
from providers.market_router import MarketRouter
from providers.yfinance_provider import YahooFinanceProvider

M = 1_000_000
QUARTERS = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"]


def _row(name, values, periods=QUARTERS):
    return {"Kalem": name, **{p: v for p, v in zip(periods, values)}}


class FakeYahoo:
    """Statement source with the latest four quarters summing to round numbers.

    TTM: net income 100, D&A 20, capex -32, working-capital cash effect +6 (millions),
    so owner earnings are 94. The fifth quarter is large on purpose: it must be ignored.
    """

    def __init__(self, financial_currency="TRY", currency="TRY", fx=None,
                 periods=QUARTERS, net_income=None, working_capital=True):
        self.info = {
            "currency": currency,
            "financialCurrency": financial_currency,
            "marketCap": 10_000 * M,
            "currentPrice": 100.0,
            "sharesOutstanding": 100 * M,
            "returnOnEquity": 0.15,
        }
        ni = net_income or [10 * M, 20 * M, 30 * M, 40 * M, 1000 * M]
        self.income = [_row("Net Income", ni, periods)]
        self.cashflow = [
            _row("Depreciation And Amortization", [5 * M] * 4 + [500 * M], periods),
            _row("Capital Expenditure", [-8 * M] * 4 + [-800 * M], periods),
        ]
        if working_capital:
            self.cashflow.append(_row(
                "Change In Working Capital", [1 * M, -2 * M, 3 * M, 4 * M, 900 * M], periods
            ))
        self.get_fx_rate = AsyncMock(return_value=fx)

    async def get_kar_zarar(self, *args, **kwargs):
        return {"tablo": self.income}

    async def get_nakit_akisi(self, *args, **kwargs):
        return {"tablo": self.cashflow}

    async def get_bilanco(self, *args, **kwargs):
        return {"tablo": []}

    async def get_sirket_bilgileri(self, *args, **kwargs):
        return {}

    def _get_ticker(self, *args, **kwargs):
        return SimpleNamespace(info=self.info)


def _analyze(yahoo):
    provider = BuffettAnalyzerProvider(yfinance_provider=yahoo)
    return asyncio.run(provider.calculate_buffett_value_analysis("TEST"))


def test_owner_earnings_sum_the_last_four_quarters():
    res = _analyze(FakeYahoo())

    assert res["owner_earnings"]["owner_earnings"] == 94
    assert res["oe_yield"]["oe_annual"] == 94
    assert res["dcf_fisher"]["parameters"]["oe_annual"] == 94


def test_working_capital_inflow_raises_owner_earnings():
    res = _analyze(FakeYahoo())

    # Yahoo's +6 is cash coming in; the formula subtracts the *increase* in working capital.
    assert res["owner_earnings"]["working_capital_change"] == -6


def test_usd_statements_are_converted_to_the_lira_quote_currency():
    yahoo = FakeYahoo(financial_currency="USD", fx=50.0)

    res = _analyze(yahoo)

    yahoo.get_fx_rate.assert_awaited_once_with("USD", "TRY")
    assert res["owner_earnings"]["owner_earnings"] == 94 * 50
    assert res["oe_yield"]["oe_yield"] == pytest.approx(94 * 50 / 10_000)
    assert any("USD" in w and "50" in w for w in res["warnings"])


def test_matching_currencies_need_no_exchange_rate():
    yahoo = FakeYahoo()

    _analyze(yahoo)

    yahoo.get_fx_rate.assert_not_awaited()


def test_missing_exchange_rate_is_an_error_not_a_number():
    res = _analyze(FakeYahoo(financial_currency="USD", fx=None))

    assert "USD" in res["error"] and "TRY" in res["error"]
    assert "dcf_fisher" not in res
    assert "buffett_score" not in res


def test_unknown_statement_currency_is_an_error():
    res = _analyze(FakeYahoo(financial_currency=None))

    assert res["error"]
    assert "dcf_fisher" not in res


def test_fewer_than_four_complete_quarters_is_an_error():
    nan = float("nan")
    res = _analyze(FakeYahoo(net_income=[10 * M, nan, 30 * M, nan, 50 * M]))

    assert "4" in res["error"]
    assert "dcf_fisher" not in res


def test_four_quarters_spanning_more_than_a_year_is_an_error():
    gapped = ["2026-09-30", "2026-06-30", "2025-06-30", "2024-12-31", "2024-09-30"]
    res = _analyze(FakeYahoo(periods=gapped))

    assert res["error"]
    assert "dcf_fisher" not in res


def test_absent_working_capital_row_is_disclosed():
    res = _analyze(FakeYahoo(working_capital=False))

    assert res["owner_earnings"]["owner_earnings"] == 88
    assert any("İşletme sermayesi" in w for w in res["warnings"])


def test_default_discount_rate_is_disclosed():
    # No bond provider: the DCF falls back to a hard-coded 30%.
    res = _analyze(FakeYahoo())

    assert any("Varsayılan" in w and "tahvil faizi" in w and "30" in w for w in res["warnings"])


def test_profitable_company_with_negative_owner_earnings_is_not_called_loss_making():
    yahoo = FakeYahoo()
    # Net income stays +100; capex alone drives owner earnings below zero.
    yahoo.cashflow[1] = _row("Capital Expenditure", [-200 * M] * 4)

    res = _analyze(yahoo)

    assert res["buffett_score"] == "AVOID"
    assert "zarar" not in res["error"]
    assert "zarar" not in res["data_quality_notes"]


def test_router_surfaces_buffett_errors_as_warnings():
    router = MarketRouter()
    client = MagicMock()
    client.calculate_buffett_value_analysis = AsyncMock(
        return_value={"error": "USD/TRY kuru alınamadı"}
    )
    router._client = client

    res = asyncio.run(router.get_financial_ratios("THYAO", MarketType.BIST, RatioSetType.BUFFETT))

    assert any("USD/TRY kuru alınamadı" in w for w in res["warnings"])


def _fake_fx_ticker(monkeypatch, history):
    requested = []

    def ticker(symbol):
        requested.append(symbol)
        return SimpleNamespace(history=lambda **kwargs: history)

    monkeypatch.setattr("providers.yfinance_provider.yf.Ticker", ticker)
    return requested


def test_fx_rate_is_the_latest_close_of_the_pair(monkeypatch):
    requested = _fake_fx_ticker(monkeypatch, pd.DataFrame({"Close": [49.0, 50.5]}))

    rate = asyncio.run(YahooFinanceProvider().get_fx_rate("USD", "TRY"))

    assert rate == 50.5
    assert requested == ["USDTRY=X"]


def test_fx_rate_is_none_when_yahoo_has_no_data(monkeypatch):
    _fake_fx_ticker(monkeypatch, pd.DataFrame())

    assert asyncio.run(YahooFinanceProvider().get_fx_rate("USD", "TRY")) is None
