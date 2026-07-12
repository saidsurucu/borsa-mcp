"""Cross-asset return comparison — the arithmetic, with no I/O in it.

Answering "ASELS mi altın mı?" used to take six tool calls, plus currency conversion
the model performed itself, across windows that did not line up. Every one of those
steps is a place to be quietly wrong.

The rules that matter, each pinned by a test in tests/test_compare_assets.py:

* **The window is asymmetric.** Start is the first bar ON OR AFTER the requested date —
  you cannot buy on a Saturday at Friday's already-passed close. End is the last bar on
  or before.
* **Every asset is normalized to TRY first.** A natively USD-quoted asset (Coinbase
  BTC-USD) must NOT have its USD price divided by USDTRY; that reports a 50% loss on an
  asset that never moved.
* **The FX rate is read on the day the asset actually traded**, not on the day that was
  requested. A fund's endpoints sit a trading day earlier than a stock's, so the two
  convert at different rates.
* **Returns are PRICE returns, dividends excluded** (design doc §3.3, Decision A). Funds
  are the one asymmetry — NAV accrues its holdings' dividends — and they say so.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from providers.canonical_series import Bar, CanonicalSeries


@dataclass
class AssetWindow:
    """One asset's canonical series, ready to be priced at two endpoints."""
    series: CanonicalSeries


def _to_try(bar: Bar, currency: str, fx_rate: float) -> float:
    """A bar's close in lira.

    A TRY-quoted asset is already there. A USD-quoted one is multiplied by USDTRY —
    never divided, which is the mistake that turns a flat BTC-USD into a 50% loss.
    """
    if currency == "TRY":
        return bar.close
    if currency == "USD":
        return bar.close * fx_rate
    raise ValueError(f"cannot convert {currency} to TRY")


def _to_usd(bar: Bar, currency: str, fx_rate: float) -> float:
    """A bar's close in dollars.

    A natively USD asset is returned as-is: its dollar return is computed from dollar
    prices, not round-tripped through lira.
    """
    if currency == "USD":
        return bar.close
    if currency == "TRY":
        return bar.close / fx_rate
    raise ValueError(f"cannot convert {currency} to USD")


def compute_comparison(
    assets: List[AssetWindow],
    usdtry: CanonicalSeries,
    start_date: str,
    end_date: str,
    initial_amount: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Price every asset at both endpoints and express the move in TRY and USD.

    `usdtry` is the FX series used for conversion. It is read at each asset's OWN
    endpoint dates, which is why it is passed whole rather than as two scalars.
    """
    rows: List[Dict[str, Any]] = []

    for item in assets:
        s = item.series
        meta = s.meta

        start_bar = s.first_on_or_after(start_date)
        end_bar = s.last_on_or_before(end_date)

        # The rate on the day this asset actually traded — not on the day requested.
        # A fund exits a trading day before a stock does, and the lira can move in
        # between.
        fx_start = usdtry.last_on_or_before(start_bar.date).close
        fx_end = usdtry.last_on_or_before(end_bar.date).close

        try_start = _to_try(start_bar, meta.currency, fx_start)
        try_end = _to_try(end_bar, meta.currency, fx_end)
        usd_start = _to_usd(start_bar, meta.currency, fx_start)
        usd_end = _to_usd(end_bar, meta.currency, fx_end)

        row: Dict[str, Any] = {
            "asset": meta.symbol,
            "market": meta.market,
            "currency": meta.currency,
            "price_basis": meta.price_basis,
            "start_date": start_bar.date,
            "end_date": end_bar.date,
            "start_price": start_bar.close,
            "end_price": end_bar.close,
            "return_try": try_end / try_start - 1,
            "return_usd": usd_end / usd_start - 1,
            "warnings": list(meta.warnings),
        }

        if initial_amount is not None:
            row["end_value_try"] = initial_amount * (1 + row["return_try"])
            # The dollar value of the same opening stake, grown at the dollar return.
            row["end_value_usd"] = (initial_amount / fx_start) * (1 + row["return_usd"])

        rows.append(row)

    rows.sort(key=lambda r: r["return_try"], reverse=True)
    return rows
