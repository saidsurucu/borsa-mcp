# Canonical Price Series Layer (Phase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one normalization layer that turns any (symbol, market) into a `CanonicalSeries` whose currency, price basis, adjustment, date convention and row order are declared and correct — so that a later `compare_assets` can put a BIST stock, gram gold, a dollar and a TEFAS fund in the same table without producing nonsense.

**Architecture:** A new pure module `providers/canonical_series.py` holds the value objects, the per-asset specification registry, and a `to_canonical()` adapter that takes a raw `MarketRouter` payload and returns a normalized, ascending, fully-declared series. It reads existing router output rather than replacing it, so nothing downstream breaks. Provider-level fixes (FX asset resolution, US adjustment mode, fund valuation date, Coinbase window cap) are made where the wrong data originates.

**Tech Stack:** Python 3.12, pytest, pydantic (already in use), yfinance 1.1.0, borsapy 0.10.2. No new dependencies.

## Global Constraints

- **Decision A (spec §3.3): v1 computes a PRICE return.** Splits adjusted in every market; dividends adjusted in none. Never silently produce a total-return series.
- **All LLM-visible descriptions are English.** Turkish only in Turkish-domain data values.
- **Never return an empty-but-successful payload.** Providers raise; the tool layer converts via `classify_tool_error` (CLAUDE.md #7).
- **A declared field must be true.** If the code cannot establish currency / basis / adjustment for an asset, it raises — it does not guess a default.
- Existing tool signatures and markdown/TSV output stay unchanged in this phase. This layer is additive.
- Run the full suite with `uv run python -m pytest tests/ -q --ignore=tests/adhoc` before every commit.
- **Verify against live providers, not only mocks.** Phase 0 shipped two bugs that every mocked test approved (CLAUDE.md #11).

---

## File Structure

| File | Responsibility |
|---|---|
| `providers/canonical_series.py` | **Create.** Value objects (`Bar`, `SeriesMeta`, `CanonicalSeries`), the `FX_ASSET_SPECS` registry, `normalize_date()`, `to_canonical()`. Pure — no network. |
| `tests/test_canonical_series.py` | **Create.** Unit tests for the above. |
| `tests/test_canonical_series_live.py` | **Create.** Live tests against real providers, one per market. |
| `providers/borsapy_fx_provider.py` | **Modify.** Fix the `ons` currency lie and the `XPT-USD` mis-mapping; expose one resolution path. |
| `providers/market_router.py` | **Modify.** FX symbol resolution, ascending crypto order, float volume, Coinbase 350-cap error, fund valuation date. |
| `providers/yfinance_provider.py` | **Modify.** Take `auto_adjust` and pass it to `ticker.history()`. |
| `borsa_client.py` | **Modify.** Thread `adjust` through `get_us_stock_data`. |

---

### Task 1: Value objects and the date normalizer

The four markets emit four different date formats (spec §3.1). Everything downstream depends on one convention: a plain `YYYY-MM-DD` string meaning that market's session date.

**Files:**
- Create: `providers/canonical_series.py`
- Create: `tests/test_canonical_series.py`

**Interfaces:**
- Produces: `Bar`, `SeriesMeta`, `CanonicalSeries`, `normalize_date(value) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_canonical_series.py
"""Canonical series layer — one price contract across six markets."""
import pytest

from providers.canonical_series import Bar, SeriesMeta, CanonicalSeries, normalize_date


# The four formats the six markets actually emit today (spec §3.1).
@pytest.mark.parametrize("raw,expected", [
    ("2026-06-01T00:00:00", "2026-06-01"),          # BIST: naive, T00:00 is an artifact
    ("2024-06-10T00:00:00-04:00", "2024-06-10"),    # US: tz-aware New York
    ("2026-07-11", "2026-07-11"),                   # FX: already date-only
    ("2026-07-10", "2026-07-10"),                   # Fund: already date-only
])
def test_normalize_date_handles_every_market_format(raw, expected):
    assert normalize_date(raw) == expected


def test_normalize_date_keeps_the_utc_calendar_day_for_crypto():
    # Crypto candles are UTC-midnight stamped. The UTC day IS the session day;
    # converting to Istanbul would roll it forward and pick the wrong bar at a
    # window boundary.
    from datetime import datetime, timezone
    dt = datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert normalize_date(dt) == "2026-07-12"


def test_normalize_date_rejects_junk_rather_than_guessing():
    with pytest.raises(ValueError):
        normalize_date("not a date")


def test_canonical_series_is_always_ascending():
    # Coinbase returns descending; the layer must not care what came in.
    bars = [Bar(date="2026-07-03", close=3.0), Bar(date="2026-07-01", close=1.0)]
    s = CanonicalSeries(meta=_meta(), bars=bars)
    assert [b.date for b in s.bars] == ["2026-07-01", "2026-07-03"]


def test_canonical_series_rejects_an_undeclared_currency():
    with pytest.raises(ValueError):
        SeriesMeta(symbol="X", market="fx", currency="", price_basis="last",
                   adjustment="none", source="s")


def _meta():
    return SeriesMeta(symbol="BTC-USD", market="crypto", currency="USD",
                      price_basis="last", adjustment="n/a", source="coinbase")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'providers.canonical_series'`

- [ ] **Step 3: Write minimal implementation**

```python
# providers/canonical_series.py
"""One price contract across BIST, US, crypto, FX and TEFAS funds.

Every field this module declares is true or it raises. The six markets disagree on
currency, price basis, adjustment, date format and row order (see the design doc,
§3.1 — every cell there was measured against live data). Downstream code — above
all compare_assets — must not have to know which market it is holding.
"""
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from typing import Any, List, Optional

# What a price actually is, per market.
PriceBasis = str   # "last" | "ask" | "nav"
Adjustment = str   # "split" | "none" | "n/a"


def normalize_date(value: Any) -> str:
    """Reduce any market's date to a plain YYYY-MM-DD session date.

    BIST emits "2026-06-01T00:00:00" (naive; the T00:00 is an artifact of a
    round-trip, not a real timestamp — the date is the Istanbul session date).
    US emits "2024-06-10T00:00:00-04:00" (tz-aware New York). FX and funds emit
    date-only. Crypto emits a UTC-midnight datetime, and the UTC day IS the
    session day — converting it to Istanbul would roll it forward and pick the
    wrong bar at a window boundary.

    In every case the calendar date as written is the session date, so the
    correct normalization is to take it and drop the time — never to convert
    the timezone.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, _date):
        return value.isoformat()

    text = str(value).strip()
    head = text[:10]
    try:
        datetime.strptime(head, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"unparseable date: {value!r}") from exc
    return head


@dataclass(frozen=True)
class Bar:
    date: str                     # YYYY-MM-DD, session date
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None   # float: 6.779 BTC is not 6


@dataclass(frozen=True)
class SeriesMeta:
    symbol: str
    market: str
    currency: str          # "TRY" | "USD" — declared, never assumed
    price_basis: PriceBasis
    adjustment: Adjustment
    source: str
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        for name in ("currency", "price_basis", "adjustment", "source"):
            if not getattr(self, name):
                raise ValueError(
                    f"SeriesMeta.{name} must be declared; guessing a default is how "
                    "a TRY series ends up labelled USD"
                )


@dataclass(frozen=True)
class CanonicalSeries:
    meta: SeriesMeta
    bars: List[Bar]

    def __post_init__(self):
        object.__setattr__(self, "bars", sorted(self.bars, key=lambda b: b.date))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_canonical_series.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add providers/canonical_series.py tests/test_canonical_series.py
git commit -m "feat(canonical): value objects and one date convention across six markets"
```

---

### Task 2: Endpoint selection with a staleness bound

`compare_assets` models an investment: you cannot buy on Saturday at Friday's already-passed close. Start and end are therefore asymmetric (spec §4).

**Files:**
- Modify: `providers/canonical_series.py`
- Modify: `tests/test_canonical_series.py`

**Interfaces:**
- Consumes: `CanonicalSeries`, `Bar` (Task 1)
- Produces: `CanonicalSeries.first_on_or_after(date, max_staleness_days) -> Bar`, `CanonicalSeries.last_on_or_before(date, max_staleness_days) -> Bar`, `StalePriceError`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_canonical_series.py
from providers.canonical_series import StalePriceError


def _series(dates):
    return CanonicalSeries(
        meta=_meta(),
        bars=[Bar(date=d, close=float(i + 1)) for i, d in enumerate(dates)],
    )


def test_start_is_the_first_bar_on_or_after_the_requested_date():
    # 2026-07-04 is a Saturday. An investor buying "from 2026-07-04" gets Monday's
    # open session, not Friday's close, which has already happened.
    s = _series(["2026-07-03", "2026-07-06", "2026-07-07"])
    assert s.first_on_or_after("2026-07-04").date == "2026-07-06"


def test_end_is_the_last_bar_on_or_before_the_requested_date():
    s = _series(["2026-07-03", "2026-07-06", "2026-07-07"])
    assert s.last_on_or_before("2026-07-05").date == "2026-07-03"


def test_exact_hits_are_used_as_is():
    s = _series(["2026-07-03", "2026-07-06"])
    assert s.first_on_or_after("2026-07-03").date == "2026-07-03"
    assert s.last_on_or_before("2026-07-06").date == "2026-07-06"


def test_a_suspended_asset_cannot_silently_reach_outside_the_window():
    # Without a staleness bound, a delisted stock happily answers with a price from
    # months earlier and the return looks perfectly reasonable.
    s = _series(["2026-01-05"])
    with pytest.raises(StalePriceError):
        s.last_on_or_before("2026-07-10", max_staleness_days=7)


def test_staleness_within_the_bound_is_allowed():
    s = _series(["2026-07-08"])
    assert s.last_on_or_before("2026-07-10", max_staleness_days=7).date == "2026-07-08"


def test_no_bar_at_all_raises():
    s = _series(["2026-07-03"])
    with pytest.raises(StalePriceError):
        s.first_on_or_after("2026-07-10")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series.py -q -k "on_or or stale or suspended"`
Expected: FAIL — `ImportError: cannot import name 'StalePriceError'`

- [ ] **Step 3: Write minimal implementation**

```python
# providers/canonical_series.py — add near the top
from datetime import timedelta

DEFAULT_MAX_STALENESS_DAYS = 10   # a long weekend plus a national holiday run


class StalePriceError(Exception):
    """No observation close enough to the requested date to be usable."""


# ...and add these methods to CanonicalSeries:

    def first_on_or_after(
        self, target: str, max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS
    ) -> Bar:
        """The first tradable bar at or after `target`.

        This is the START of an investment window: you cannot buy on a Saturday at
        Friday's already-passed close.
        """
        for bar in self.bars:                      # ascending
            if bar.date >= target:
                self._check_gap(bar.date, target, max_staleness_days)
                return bar
        raise StalePriceError(
            f"{self.meta.symbol}: no observation on or after {target}"
        )

    def last_on_or_before(
        self, target: str, max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS
    ) -> Bar:
        """The last bar at or before `target` — the END of an investment window."""
        for bar in reversed(self.bars):
            if bar.date <= target:
                self._check_gap(bar.date, target, max_staleness_days)
                return bar
        raise StalePriceError(
            f"{self.meta.symbol}: no observation on or before {target}"
        )

    @staticmethod
    def _check_gap(found: str, target: str, max_days: int) -> None:
        gap = abs(
            (datetime.strptime(found, "%Y-%m-%d") - datetime.strptime(target, "%Y-%m-%d")).days
        )
        if gap > max_days:
            raise StalePriceError(
                f"nearest observation is {found}, {gap} days from {target} "
                f"(limit {max_days}). The asset is likely suspended or delisted; "
                "using it would silently price the window from outside it."
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_canonical_series.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add providers/canonical_series.py tests/test_canonical_series.py
git commit -m "feat(canonical): asymmetric window endpoints with a staleness bound"
```

---

### Task 3: Fix the FX asset registry — `ons` and `XPT-USD`

Two live bugs (spec §0b). `ons` maps to `ons-altin`, which is an ounce of gold priced **in lira** (~106,463 TRY), but the code labels it USD because of `birim = "TRY" if asset in ["gram-altin", "gumus"] else "USD"` (`providers/borsapy_fx_provider.py:146`). And `XPT-USD` maps to `gram-platin` — platinum per **gram in TRY** — which is not the same asset as platinum per **ounce in USD**. `get_fx_data` applies this mapping; `get_historical_data` does not, so the same symbol returns 2,477 TRY from one tool and 1,637 USD from the other.

**Files:**
- Modify: `providers/canonical_series.py`
- Modify: `providers/borsapy_fx_provider.py:29-51` (`ASSET_MAPPING`), `:140-153` (the `birim` logic)
- Modify: `tests/test_canonical_series.py`

**Interfaces:**
- Produces: `FX_ASSET_SPECS: dict[str, FxAssetSpec]`, `resolve_fx_asset(symbol) -> FxAssetSpec`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_canonical_series.py
from providers.canonical_series import resolve_fx_asset, FX_ASSET_SPECS


def test_ons_is_a_lira_series_and_must_say_so():
    # ons -> ons-altin is an ounce of gold priced IN LIRA (~106,463 TRY). The old
    # code labelled it USD, a 26x error against the real USD ounce (~4,120).
    spec = resolve_fx_asset("ons")
    assert spec.currency == "TRY"
    assert spec.provider_symbol == "ons-altin"


def test_xpt_usd_is_not_gram_platin():
    # XPT-USD is platinum per OUNCE in USD. gram-platin is platinum per GRAM in TRY.
    # They are different assets; mapping one onto the other made get_fx_data and
    # get_historical_data return 2,477 TRY and 1,637 USD for the same symbol.
    spec = resolve_fx_asset("XPT-USD")
    assert spec.provider_symbol == "XPT-USD"
    assert spec.currency == "USD"

    gram = resolve_fx_asset("gram-platin")
    assert gram.provider_symbol == "gram-platin"
    assert gram.currency == "TRY"


@pytest.mark.parametrize("symbol,currency", [
    ("gram-altin", "TRY"), ("USD", "TRY"), ("EUR", "TRY"),
    ("gram-gumus", "TRY"), ("gram-platin", "TRY"),
    ("BRENT", "USD"), ("XAG-USD", "USD"), ("XPD-USD", "USD"), ("ons", "TRY"),
])
def test_every_fx_asset_declares_its_true_currency(symbol, currency):
    assert resolve_fx_asset(symbol).currency == currency


def test_every_fx_asset_declares_its_price_basis():
    # canlidoviz's OHLC close is the satış/ask side of the Serbest Piyasa quote —
    # measured against the live page: close 6225.546 == BAYİ SATIŞ 6225.55, while
    # BAYİ ALIŞ 6224.70 appears nowhere in the OHLC.
    for spec in FX_ASSET_SPECS.values():
        assert spec.price_basis == "ask"


def test_an_unknown_fx_asset_raises_rather_than_defaulting_to_usd():
    with pytest.raises(ValueError):
        resolve_fx_asset("DOGECOIN-MOON")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series.py -q -k "fx or ons or xpt"`
Expected: FAIL — `ImportError: cannot import name 'resolve_fx_asset'`

- [ ] **Step 3: Write minimal implementation**

```python
# providers/canonical_series.py — add

@dataclass(frozen=True)
class FxAssetSpec:
    """What an FX/commodity symbol really is.

    The old ASSET_MAPPING conflated naming differences with asset differences:
    XPT-USD (platinum per ounce, USD) was mapped onto gram-platin (platinum per
    gram, TRY). They are separate assets and both are now addressable.
    """
    provider_symbol: str
    currency: str
    price_basis: PriceBasis = "ask"


# canlidoviz item semantics, verified live 2026-07-12.
FX_ASSET_SPECS = {
    # TRY-quoted: how many lira for one unit
    "USD":         FxAssetSpec("USD", "TRY"),
    "EUR":         FxAssetSpec("EUR", "TRY"),
    "GBP":         FxAssetSpec("GBP", "TRY"),
    "JPY":         FxAssetSpec("JPY", "TRY"),
    "CHF":         FxAssetSpec("CHF", "TRY"),
    "CAD":         FxAssetSpec("CAD", "TRY"),
    "AUD":         FxAssetSpec("AUD", "TRY"),
    "gram-altin":  FxAssetSpec("gram-altin", "TRY"),
    "gram-gumus":  FxAssetSpec("gram-gumus", "TRY"),
    "gram-platin": FxAssetSpec("gram-platin", "TRY"),
    # ons-altin is an OUNCE OF GOLD PRICED IN LIRA (~106,463 TRY), not in USD.
    "ons":         FxAssetSpec("ons-altin", "TRY"),
    "ons-altin":   FxAssetSpec("ons-altin", "TRY"),
    # USD-quoted
    "BRENT":       FxAssetSpec("BRENT", "USD"),
    "XAG-USD":     FxAssetSpec("XAG-USD", "USD"),
    "XPD-USD":     FxAssetSpec("XPD-USD", "USD"),
    "XPT-USD":     FxAssetSpec("XPT-USD", "USD"),
}

# Backwards-compatible aliases for names the old mapping used.
_FX_ALIASES = {"gumus": "gram-gumus"}


def resolve_fx_asset(symbol: str) -> FxAssetSpec:
    key = _FX_ALIASES.get(symbol, symbol)
    spec = FX_ASSET_SPECS.get(key)
    if spec is None:
        raise ValueError(
            f"unknown FX asset {symbol!r}. Defaulting its currency is how 'ons' "
            f"became a lira series labelled USD. Known: {sorted(FX_ASSET_SPECS)}"
        )
    return spec
```

Then make `providers/borsapy_fx_provider.py` the single consumer of this registry. Replace `ASSET_MAPPING` lookups with `resolve_fx_asset(asset).provider_symbol`, and replace every `birim = ...` branch (lines 143, 146, 149, 152) with:

```python
from providers.canonical_series import resolve_fx_asset
...
birim = resolve_fx_asset(asset).currency
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_canonical_series.py -q && uv run python -m pytest tests/ -q --ignore=tests/adhoc`
Expected: PASS, and the full suite still green.

- [ ] **Step 5: Verify live — the two tools must now agree**

```bash
uv run python - <<'PY'
import asyncio
from fastmcp import Client
from unified_mcp_server import app

async def main():
    async with Client(app) as c:
        for sym in ["XPT-USD", "gram-platin", "ons", "gram-altin"]:
            a = await c.call_tool("get_fx_data", {"symbol": sym, "data_type": "current"})
            b = await c.call_tool("get_historical_data", {"symbol": sym, "market": "fx", "period": "5d"})
            print(sym, "current:", a.content[0].text[:80].replace("\n", " "))
            print(sym, "hist   :", b.content[0].text[:80].replace("\n", " "))
asyncio.run(main())
PY
```

Expected: `XPT-USD` returns the **same** asset and currency from both tools. `ons` returns a TRY value from both, and no longer errors on the historical path.

- [ ] **Step 6: Commit**

```bash
git add providers/canonical_series.py providers/borsapy_fx_provider.py tests/test_canonical_series.py
git commit -m "fix(fx): ons is a lira series, XPT-USD is not gram-platin

resolve_fx_asset is now the single source of truth for an FX symbol's provider
name, currency and price basis. Previously ASSET_MAPPING conflated naming
differences with asset differences (XPT-USD -> gram-platin: ounce-USD mapped onto
gram-TRY), and the currency was inferred by a hardcoded membership test that
labelled ons-altin — an ounce of gold priced in lira — as USD."
```

---

### Task 4: US must return split-adjusted, dividend-unadjusted closes

Per Decision A. Today `adjust` is accepted and ignored: `YFinanceProvider.get_finansal_veri` calls `ticker.history()` with no `auto_adjust`, and yfinance 1.1.0 defaults it to `True`, so US closes are fully adjusted (splits **and** dividends) while BIST's default is raw. Setting `auto_adjust=False` gives Yahoo's `Close`, which is split-adjusted but not dividend-adjusted — matching the BIST `adjust=True` series.

**Files:**
- Modify: `providers/yfinance_provider.py:190,211` (the two `ticker.history()` calls)
- Modify: `borsa_client.py:1237-1243` (`get_us_stock_data`)
- Modify: `providers/market_router.py:465-470` (US branch)
- Create: `tests/test_canonical_series_live.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `YFinanceProvider.get_finansal_veri(..., auto_adjust: bool = False)`; `BorsaApiClient.get_us_stock_data(..., auto_adjust: bool = False)`.

- [ ] **Step 1: Write the failing test**

This one must be live: the whole bug is that the mock accepted whatever we sent (CLAUDE.md #11).

```python
# tests/test_canonical_series_live.py
"""Live price-contract tests. These hit real providers on purpose.

Phase 0 shipped two bugs that every mocked test approved. A price contract that is
only verified against fixtures is not verified.
"""
import asyncio
import pytest

from providers.market_router import MarketRouter
from models.unified_base import MarketType

pytestmark = pytest.mark.live


def _closes(payload):
    return {row["date"][:10]: row["close"] for row in payload["data"]}


def test_us_close_is_split_adjusted():
    # NVDA did a 10:1 split on 2024-06-10. A raw, unadjusted series would show a
    # ~90% cliff across it. Yahoo's `Close` (auto_adjust=False) is split-adjusted.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "NVDA", MarketType.US, start_date="2024-06-05", end_date="2024-06-14"))
    c = _closes(payload)
    before, after = c["2024-06-07"], c["2024-06-10"]
    assert 0.5 < after / before < 2.0, (
        f"a ~10x cliff means splits are NOT adjusted: {before} -> {after}"
    )


def test_us_close_is_NOT_dividend_adjusted():
    # KO went ex-dividend on 2024-06-14 ($0.485 on a ~$62.99 close, ~0.77%).
    # A dividend-adjusted series absorbs the drop and prints roughly FLAT across the
    # ex-date; a price series shows the drop. Decision A wants the price series.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "KO", MarketType.US, start_date="2024-06-10", end_date="2024-06-18"))
    c = _closes(payload)
    move = c["2024-06-14"] / c["2024-06-13"] - 1
    assert move < -0.002, (
        f"ex-dividend move was {move:.4%}; a dividend-adjusted series prints ~+0.07% "
        "here, which is the fully-adjusted close we are trying to stop returning"
    )


def test_bist_close_is_split_adjusted_by_default():
    # BIMAS did a 100% bonus issue (bedelsiz) on 2026-05-14. At the old default
    # (adjust=False) the series went 813.00 -> 414.00 and a window spanning it
    # reported -49% for a company that only split.
    router = MarketRouter()
    payload = asyncio.run(router.get_historical_data(
        "BIMAS", MarketType.BIST, start_date="2026-05-08", end_date="2026-05-20"))
    c = _closes(payload)
    before, after = c["2026-05-13"], c["2026-05-14"]
    assert 0.8 < after / before < 1.25, (
        f"bonus-issue cliff still present: {before} -> {after}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series_live.py -q -p no:cacheprovider`
Expected: `test_us_close_is_NOT_dividend_adjusted` FAILS (the current series is dividend-adjusted, so the ex-date prints ~+0.07%). `test_bist_close_is_split_adjusted_by_default` FAILS (the cliff is present at the current default). `test_us_close_is_split_adjusted` passes already.

Register the marker so the suite does not warn — add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["live: hits real providers; excluded from the default run"]
```

- [ ] **Step 3: Write the implementation**

`providers/yfinance_provider.py` — add the parameter and forward it (both call sites, lines ~190 and ~211):

```python
    async def get_finansal_veri(self, ticker_kodu, period=None, start_date=None,
                                end_date=None, market="bist", auto_adjust: bool = False):
        ...
            if start_date or end_date:
                hist_df = ticker.history(start=start_date, end=end_date,
                                         auto_adjust=auto_adjust)
        ...
                hist_df = ticker.history(period=period_value, auto_adjust=auto_adjust)
```

`borsa_client.py` — thread it through:

```python
    async def get_us_stock_data(self, ticker_kodu, period=None, start_date=None,
                                end_date=None, auto_adjust: bool = False):
        return await self.yfinance_provider.get_finansal_veri(
            ticker_kodu, period=period, start_date=start_date, end_date=end_date,
            market="us", auto_adjust=auto_adjust,
        )
```

`providers/market_router.py` — the US branch passes it, and BIST now defaults to adjusted:

```python
        # Decision A (design §3.3): splits adjusted everywhere, dividends nowhere.
        # BIST: adjust=True gives the split-adjusted TradingView frame.
        # US: auto_adjust=False gives Yahoo's `Close`, which is split-adjusted but
        # NOT dividend-adjusted — the same basis as BIST's adjusted frame. The
        # default (auto_adjust=True) bundles dividends in and is not comparable.
```

In the BIST branch (`market_router.py:440`) change `adjust=adjust` to `adjust=True` **only** when the caller did not explicitly ask otherwise — keep the parameter, flip its default at the tool boundary (`unified_mcp_server.py:~408`) from `False` to `True`, and correct the description, which currently claims "False = real trading prices (default)" and is wrong in both directions.

In the US branch (`market_router.py:465-470`):

```python
            result = await self._client.get_us_stock_data(
                symbol, period=period or "1mo",
                start_date=start_date, end_date=end_date,
                auto_adjust=False,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_canonical_series_live.py -q -p no:cacheprovider`
Expected: PASS (3 passed)

Then: `uv run python -m pytest tests/ -q --ignore=tests/adhoc -m "not live"`
Expected: the full suite still green.

- [ ] **Step 5: Commit**

```bash
git add providers/yfinance_provider.py borsa_client.py providers/market_router.py \
        unified_mcp_server.py tests/test_canonical_series_live.py pyproject.toml
git commit -m "fix(prices): one adjustment basis — splits everywhere, dividends nowhere

BIST returned raw prices (a 100% bonus issue took BIMAS 813.00 -> 414.00, so any
window spanning it reported -49%) while US returned a fully split- AND
dividend-adjusted series. Directly incomparable. US's adjust flag was accepted and
ignored, and its description claimed the opposite of what it did."
```

---

### Task 5: Crypto — ascending order, real volume, and an honest window-cap error

Three live bugs (spec §0b). Coinbase returns rows descending while every other market ascends, and the router does not normalize — so `data[-1]` is the newest bar on BtcTurk and the *oldest* on Coinbase. `int(dp.volume)` turns 6.779 BTC into `6`. And Coinbase's hard 350-candle cap makes a 1-year daily request fail with "no data" when the truth is "window too wide".

**Files:**
- Modify: `providers/market_router.py:485-528` (both crypto branches)
- Modify: `tests/test_phase0_live_bugs.py`

**Interfaces:**
- Consumes: `MarketRouter._resolve_window` (exists), `CanonicalSeries` (Task 1) is not needed here — this fixes the raw payload at source.
- Produces: `COINBASE_MAX_CANDLES = 350`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_phase0_live_bugs.py

def test_coinbase_rows_come_back_ascending_like_every_other_market():
    """Coinbase answers newest-first; BtcTurk oldest-first. The router must not
    pass that inconsistency on — data[-1] silently means different things."""
    async def ohlc(product_id, start=None, end=None, granularity="ONE_DAY"):
        return SimpleNamespace(candles=[      # newest-first, as Coinbase really does
            SimpleNamespace(start=d, open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
            for d in ("2026-07-10", "2026-07-08", "2026-07-06")
        ])

    router = MarketRouter()
    client = MagicMock()
    client.get_coinbase_ohlc = AsyncMock(side_effect=ohlc)
    router._client = client

    res = asyncio.run(router.get_historical_data(
        "BTC-USD", MarketType.CRYPTO_GLOBAL,
        start_date="2026-07-01", end_date="2026-07-10"))

    dates = [r["date"][:10] for r in res["data"]]
    assert dates == sorted(dates), f"rows are not ascending: {dates}"


def test_crypto_volume_is_not_truncated_to_int():
    """int(6.779) == 6. Fractional volume is the norm in crypto."""
    async def ohlc(pair, from_time=None, to_time=None):
        return SimpleNamespace(ohlc_data=[
            SimpleNamespace(time="2026-07-05", open=1.0, high=2.0,
                            low=0.5, close=1.5, volume=6.779)
        ])

    router = MarketRouter()
    client = MagicMock()
    client.get_kripto_ohlc = AsyncMock(side_effect=ohlc)
    router._client = client

    res = asyncio.run(router.get_historical_data(
        "BTCTRY", MarketType.CRYPTO_TR,
        start_date="2026-07-01", end_date="2026-07-10"))

    assert res["data"][0]["volume"] == pytest.approx(6.779)


def test_coinbase_window_over_the_candle_cap_says_so():
    """Coinbase hard-caps at 350 candles. A 1y daily request is 365 and gets an
    HTTP 400, which the provider swallows into an empty list — so the tool used to
    report "no data" when the truth was "window too wide"."""
    router = MarketRouter()
    router._client = MagicMock()

    with pytest.raises(Exception) as exc:
        asyncio.run(router.get_historical_data(
            "BTC-USD", MarketType.CRYPTO_GLOBAL, period="1y"))

    msg = str(exc.value).lower()
    assert "350" in msg or "too wide" in msg or "candle" in msg, (
        f"the error must name the real cause, not 'no data': {exc.value}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_phase0_live_bugs.py -q -k "ascending or truncated or candle_cap"`
Expected: 3 FAIL — descending order preserved; volume is `6`; error says "No historical data".

- [ ] **Step 3: Write the implementation**

In `providers/market_router.py`, above the class:

```python
# Coinbase's Advanced Trade API rejects any request for more than 350 candles,
# whatever the granularity. Verified live: 350 -> OK, 351 -> HTTP 400.
COINBASE_MAX_CANDLES = 350
```

In the `CRYPTO_GLOBAL` branch, before calling the client:

```python
            win_start, win_end = self._resolve_window(period, start_date, end_date)
            if win_start and win_end:
                span = (win_end - win_start).days
                if span > COINBASE_MAX_CANDLES:
                    raise ValueError(
                        f"Coinbase serves at most {COINBASE_MAX_CANDLES} candles per "
                        f"request; {span} days of daily bars were requested. Narrow the "
                        f"window, or use market='crypto_tr' (BtcTurk), which has no cap."
                    )
```

In both crypto branches, replace `"volume": int(dp.volume) if dp.volume else None` with:

```python
                        "volume": float(dp.volume) if dp.volume is not None else None,
```

And after the `CRYPTO_GLOBAL` rows are built (Coinbase answers newest-first):

```python
            # Coinbase returns candles newest-first; every other market here is
            # ascending. Normalize rather than propagate the inconsistency —
            # data[-1] must mean the same thing in every market (CLAUDE.md #6).
            data_points.sort(key=lambda row: str(row["date"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_phase0_live_bugs.py -q`
Expected: PASS

- [ ] **Step 5: Verify live**

```bash
uv run python - <<'PY'
import asyncio
from providers.market_router import MarketRouter
from models.unified_base import MarketType
r = MarketRouter()
p = asyncio.run(r.get_historical_data("BTC-USD", MarketType.CRYPTO_GLOBAL,
                                      start_date="2026-07-01", end_date="2026-07-10"))
d = [x["date"][:10] for x in p["data"]]
print("ascending:", d == sorted(d), d[:3], "...")
try:
    asyncio.run(r.get_historical_data("BTC-USD", MarketType.CRYPTO_GLOBAL, period="1y"))
except Exception as e:
    print("1y error:", e)
PY
```

Expected: `ascending: True`, and the 1y error names the 350-candle cap.

- [ ] **Step 6: Commit**

```bash
git add providers/market_router.py tests/test_phase0_live_bugs.py
git commit -m "fix(crypto): ascending rows, float volume, honest window-cap error"
```

---

### Task 6: Funds — expose the NAV series and its true valuation date

Measured (spec §3.2): regressing TI2's daily NAV returns against XU100 gives correlation **0.014 at lag 0 and 0.938 at lag 1**. The NAV stamped date D is marked to the close of **D−1**. TEFAS's `tarih` is the *publication* date and is the only date the data carries. A fund's `[A, B]` window is therefore economically `[A−1, B−1]`, and `compare_assets` must align on the valuation date, not the published one.

Also: `get_fund_data` calls `fund.history()` but only emits 7 rows of `recent_prices` — there is no path for a full NAV series today.

**Files:**
- Modify: `providers/market_router.py` — add `get_fund_price_series()`
- Modify: `providers/canonical_series.py` — fund branch of `to_canonical()`
- Modify: `tests/test_canonical_series.py`

**Interfaces:**
- Consumes: `CanonicalSeries`, `SeriesMeta`, `Bar`, `normalize_date` (Task 1)
- Produces: `MarketRouter.get_fund_price_series(symbol, start_date, end_date) -> dict` with keys `symbol, currency, source, data` (rows: `{published_date, valuation_date, close}`)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_canonical_series.py
from providers.canonical_series import fund_valuation_date


def test_fund_valuation_date_is_the_previous_trading_day():
    # NAV published on Friday 2026-07-10 is marked to Thursday 2026-07-09's close.
    assert fund_valuation_date("2026-07-10") == "2026-07-09"


def test_fund_valuation_date_skips_the_weekend():
    # NAV published Monday 2026-07-06 is marked to Friday 2026-07-03, not Sunday.
    assert fund_valuation_date("2026-07-06") == "2026-07-03"


def test_fund_series_is_keyed_on_the_valuation_date_not_the_publication_date():
    # This is the whole point: a fund's [A,B] is economically [A-1,B-1]. Comparing a
    # fund's published dates against a stock's session dates silently offsets the
    # windows by one trading day.
    from providers.canonical_series import to_canonical

    raw = {
        "symbol": "TI2",
        "currency": "TRY",
        "source": "tefas",
        "data": [
            {"published_date": "2026-07-09", "close": 10.0},
            {"published_date": "2026-07-10", "close": 11.0},
        ],
    }
    series = to_canonical(raw, market="fund")

    assert [b.date for b in series.bars] == ["2026-07-08", "2026-07-09"]
    assert series.meta.price_basis == "nav"
    assert series.meta.currency == "TRY"
    assert any("valuation date" in w.lower() for w in series.meta.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series.py -q -k "fund or valuation"`
Expected: FAIL — `ImportError: cannot import name 'fund_valuation_date'`

- [ ] **Step 3: Write the implementation**

```python
# providers/canonical_series.py — add

def fund_valuation_date(published_date: str) -> str:
    """The date a TEFAS NAV is actually marked to: the previous TRADING day.

    Measured, not assumed: regressing TI2's daily NAV returns against XU100 gives
    correlation 0.014 at lag 0 and 0.938 at lag 1 (confirmed on AFA). TEFAS's
    `tarih` is the publication date, and it is the only date the data exposes.

    Weekends are skipped. Turkish public holidays are NOT modelled — on a holiday
    boundary this can name a non-trading day, which shifts the endpoint by a day at
    most. Callers select bars by "on or before" / "on or after", so a date that is
    not a real session simply resolves to the neighbouring one.
    """
    d = datetime.strptime(published_date, "%Y-%m-%d") - timedelta(days=1)
    while d.weekday() >= 5:          # 5 = Saturday, 6 = Sunday
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


FUND_LAG_WARNING = (
    "Fund rows are keyed on their valuation date (the previous trading day), not "
    "TEFAS's publication date. A fund's freshest NAV always trails the freshest "
    "stock close by one trading day."
)
FUND_TOTAL_RETURN_WARNING = (
    "Fund NAV accrues its holdings' dividends, so a fund is a total return while "
    "the stocks beside it are a price return (dividends excluded)."
)
```

Add the fund branch to `to_canonical()` (see Task 7 for the dispatcher), and add `MarketRouter.get_fund_price_series`:

```python
    async def get_fund_price_series(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """A fund's full NAV series. `get_fund_data` only ever emitted 7 rows.

        TEFAS is close-only: there is no OHLC and no volume. The v2 API accepts only
        fixed period buckets (5 years is the maximum); arbitrary windows are served
        by fetching the smallest covering bucket and filtering client-side, which
        borsapy already does.
        """
        import borsapy as bp

        fund = bp.Fund(symbol.upper())
        hist = await asyncio.get_running_loop().run_in_executor(
            None, lambda: fund.history(start=start_date, end=end_date)
        )
        if hist is None or len(hist) == 0:
            raise DataNotAvailableError(
                f"No NAV history for fund '{symbol}' between "
                f"{start_date or 'start'} and {end_date or 'now'}"
            )

        rows = [
            {"published_date": idx.strftime("%Y-%m-%d"), "close": float(row["Price"])}
            for idx, row in hist.iterrows()
        ]
        return {
            "symbol": symbol.upper(),
            "currency": "TRY",
            "source": "tefas",
            "data": rows,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_canonical_series.py -q`
Expected: PASS

- [ ] **Step 5: Verify live against a real fund**

```bash
uv run python - <<'PY'
import asyncio
from providers.market_router import MarketRouter
from providers.canonical_series import to_canonical
raw = asyncio.run(MarketRouter().get_fund_price_series("TI2", "2026-06-01", "2026-07-11"))
s = to_canonical(raw, market="fund")
print("currency:", s.meta.currency, "basis:", s.meta.price_basis)
print("first/last valuation dates:", s.bars[0].date, s.bars[-1].date)
print("warnings:", s.meta.warnings)
PY
```

Expected: TRY / nav, ascending valuation dates each one trading day before the published date, and both fund warnings present.

- [ ] **Step 6: Commit**

```bash
git add providers/market_router.py providers/canonical_series.py tests/test_canonical_series.py
git commit -m "feat(funds): full NAV series keyed on the valuation date (D-1), measured by lag regression"
```

---

### Task 7: The `to_canonical()` dispatcher — one series for every market

Ties Tasks 1–6 together. This is the function `compare_assets` will call, and the only place that knows the six markets differ.

**Files:**
- Modify: `providers/canonical_series.py`
- Modify: `tests/test_canonical_series.py`
- Modify: `tests/test_canonical_series_live.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `to_canonical(raw: dict, market: str) -> CanonicalSeries`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_canonical_series.py
from providers.canonical_series import to_canonical


def test_bist_series_declares_try_last_split():
    raw = {"symbol": "ASELS", "metadata": {"source": "borsapy"},
           "data": [{"date": "2026-07-10T00:00:00", "close": 129.0}]}
    s = to_canonical(raw, market="bist")
    assert (s.meta.currency, s.meta.price_basis, s.meta.adjustment) == ("TRY", "last", "split")
    assert s.bars[0].date == "2026-07-10"


def test_us_series_declares_usd_last_split():
    raw = {"symbol": "AAPL", "metadata": {"source": "yfinance"},
           "data": [{"date": "2026-07-10T00:00:00-04:00", "close": 230.0}]}
    s = to_canonical(raw, market="us")
    assert (s.meta.currency, s.meta.price_basis, s.meta.adjustment) == ("USD", "last", "split")
    assert s.bars[0].date == "2026-07-10"


def test_crypto_currency_comes_from_the_pair_not_a_default():
    # BTCTRY at 3,005,375 and BTC-USD at 64,034 arrive in identically-shaped
    # payloads today. The quote currency must be derived, not assumed.
    tr = to_canonical({"symbol": "BTCTRY", "metadata": {"source": "btcturk"},
                       "data": [{"date": "2026-07-10", "close": 3005375.0}]},
                      market="crypto_tr")
    gl = to_canonical({"symbol": "BTC-USD", "metadata": {"source": "coinbase"},
                       "data": [{"date": "2026-07-10", "close": 64034.0}]},
                      market="crypto_global")
    assert tr.meta.currency == "TRY"
    assert gl.meta.currency == "USD"
    assert tr.meta.adjustment == "n/a" and gl.meta.adjustment == "n/a"


def test_fx_currency_and_basis_come_from_the_registry():
    s = to_canonical({"symbol": "gram-altin", "metadata": {"source": "borsapy"},
                      "data": [{"date": "2026-07-10", "close": 6225.55}]}, market="fx")
    assert (s.meta.currency, s.meta.price_basis) == ("TRY", "ask")

    brent = to_canonical({"symbol": "BRENT", "metadata": {"source": "borsapy"},
                          "data": [{"date": "2026-07-10", "close": 76.02}]}, market="fx")
    assert brent.meta.currency == "USD"


def test_an_unknown_market_raises():
    with pytest.raises(ValueError):
        to_canonical({"symbol": "X", "data": []}, market="martian_exchange")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_canonical_series.py -q -k "declares or crypto_currency or registry or unknown_market"`
Expected: FAIL — `ImportError: cannot import name 'to_canonical'`

- [ ] **Step 3: Write the implementation**

```python
# providers/canonical_series.py — add

# What each market's close actually is, after Task 4/5/6. Every value here is
# measured (design doc §3.1), not assumed.
_MARKET_CONTRACT = {
    "bist":          {"currency": "TRY", "price_basis": "last", "adjustment": "split"},
    "us":            {"currency": "USD", "price_basis": "last", "adjustment": "split"},
    "crypto_tr":     {"currency": None,  "price_basis": "last", "adjustment": "n/a"},
    "crypto_global": {"currency": None,  "price_basis": "last", "adjustment": "n/a"},
    "fx":            {"currency": None,  "price_basis": None,   "adjustment": "n/a"},
    "fund":          {"currency": "TRY", "price_basis": "nav",  "adjustment": "n/a"},
}

# Every BtcTurk pair is quoted in one of these two; Coinbase uses a dash.
_BTCTURK_QUOTES = ("TRY", "USDT")


def _crypto_quote_currency(symbol: str, market: str) -> str:
    if market == "crypto_global":
        if "-" not in symbol:
            raise ValueError(f"cannot derive quote currency from {symbol!r}")
        return symbol.rsplit("-", 1)[1].upper()
    up = symbol.upper()
    for quote in _BTCTURK_QUOTES:
        if up.endswith(quote):
            return "TRY" if quote == "TRY" else "USD"
    raise ValueError(
        f"cannot derive quote currency from BtcTurk pair {symbol!r}; "
        "labelling it by default is how a 3,005,375 TRY close passes for USD"
    )


def to_canonical(raw: dict, market: str) -> CanonicalSeries:
    """Normalize a raw router payload into the one contract.

    `raw` is what MarketRouter.get_historical_data / get_fund_price_series return.
    """
    contract = _MARKET_CONTRACT.get(market)
    if contract is None:
        raise ValueError(
            f"unknown market {market!r}; known: {sorted(_MARKET_CONTRACT)}"
        )

    symbol = raw.get("symbol", "")
    source = raw.get("source") or (raw.get("metadata") or {}).get("source") or "unknown"
    warnings: List[str] = []

    currency = contract["currency"]
    price_basis = contract["price_basis"]

    if market in ("crypto_tr", "crypto_global"):
        currency = _crypto_quote_currency(symbol, market)
    elif market == "fx":
        spec = resolve_fx_asset(symbol)
        currency, price_basis = spec.currency, spec.price_basis
    elif market == "fund":
        currency = raw.get("currency") or "TRY"
        warnings.append(FUND_LAG_WARNING)
        warnings.append(FUND_TOTAL_RETURN_WARNING)

    bars = []
    for row in raw.get("data", []):
        if market == "fund":
            bar_date = fund_valuation_date(normalize_date(row["published_date"]))
        else:
            bar_date = normalize_date(row["date"])
        bars.append(Bar(
            date=bar_date,
            close=float(row["close"]),
            open=row.get("open"),
            high=row.get("high"),
            low=row.get("low"),
            volume=row.get("volume"),
        ))

    if not bars:
        raise ValueError(f"{symbol}: no bars to normalize")

    return CanonicalSeries(
        meta=SeriesMeta(
            symbol=symbol, market=market, currency=currency,
            price_basis=price_basis, adjustment=contract["adjustment"],
            source=source, warnings=warnings,
        ),
        bars=bars,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_canonical_series.py -q && uv run python -m pytest tests/ -q --ignore=tests/adhoc -m "not live"`
Expected: PASS, full suite green.

- [ ] **Step 5: Add the live cross-market test**

```python
# append to tests/test_canonical_series_live.py
from providers.canonical_series import to_canonical


@pytest.mark.parametrize("symbol,market,currency,basis", [
    ("ASELS",      "bist",          "TRY", "last"),
    ("AAPL",       "us",            "USD", "last"),
    ("BTCTRY",     "crypto_tr",     "TRY", "last"),
    ("BTC-USD",    "crypto_global", "USD", "last"),
    ("gram-altin", "fx",            "TRY", "ask"),
    ("BRENT",      "fx",            "USD", "ask"),
])
def test_every_market_yields_a_fully_declared_ascending_series(symbol, market, currency, basis):
    router = MarketRouter()
    raw = asyncio.run(router.get_historical_data(
        symbol, MarketType(market), start_date="2026-07-01", end_date="2026-07-10"))
    s = to_canonical(raw, market=market)

    assert s.meta.currency == currency
    assert s.meta.price_basis == basis
    dates = [b.date for b in s.bars]
    assert dates == sorted(dates), f"not ascending: {dates}"
    assert all(len(d) == 10 for d in dates), f"date format leaked through: {dates}"
    assert dates[0] >= "2026-07-01" and dates[-1] <= "2026-07-10"
```

Run: `uv run python -m pytest tests/test_canonical_series_live.py -q -p no:cacheprovider`
Expected: PASS (9 passed)

- [ ] **Step 6: Commit**

```bash
git add providers/canonical_series.py tests/test_canonical_series.py tests/test_canonical_series_live.py
git commit -m "feat(canonical): to_canonical() — one declared series for all six markets"
```

---

### Task 8: Document the contract and close the loop

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-07-12-tool-consolidation-design.md`

- [ ] **Step 1: Add the contract table to CLAUDE.md**

Under a new `## Canonical Price Contract` heading, paste the measured table from spec §3.1, then state Decision A in two sentences: splits adjusted everywhere, dividends nowhere, results are a price return. Note that `providers/canonical_series.py` is the only place allowed to decide an asset's currency, basis or adjustment.

- [ ] **Step 2: Add the new gotcha to CLAUDE.md "Common Issues"**

```markdown
### 13. Two markets can both be "right" and still be incomparable
BIST returned raw prices while US returned a split- and dividend-adjusted series. Each was
internally consistent; putting them in one table was nonsense. BIMAS's 100% bonus issue took the
BIST series 813.00 -> 414.00, so any window spanning 2026-05-14 reported -49% for a company that
only split. Before comparing two series, ask what each price *is* — not whether each is correct.
`providers/canonical_series.py` is now the single answer to that question.
```

- [ ] **Step 3: Mark the resolved rows in the spec's §0b table**

Change the "Fixed by" column to "Fixed in" with the commit for each row this plan closed: `ons`, `XPT-USD`, `gumus`/`ons` history, US `adjust`, Coinbase ordering, Coinbase cap, crypto volume, crypto currency, BIST flaky un-adjust (moot under Decision A — `adjust=True` never calls `_unadjust_prices`).

- [ ] **Step 4: Run the full suite one last time**

Run: `uv run python -m pytest tests/ -q --ignore=tests/adhoc -m "not live"`
Then: `uv run python -m pytest tests/ -q --ignore=tests/adhoc -m live`
Expected: both green.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: record the canonical price contract and Decision A"
```

---

## Self-Review

**Spec coverage (§3.4 checklist):**

| §3.4 requirement | Task |
|---|---|
| rows sorted ascending, always | 1 (`CanonicalSeries.__post_init__`), 5 (Coinbase at source) |
| `date` as plain `YYYY-MM-DD`, one convention | 1 (`normalize_date`) |
| funds: published **and** derived valuation date | 6 (`fund_valuation_date`) |
| declared `currency`, correct per asset | 3 (FX registry), 7 (crypto from pair, BIST/US/fund from contract) |
| declared `price_basis` | 3, 7 |
| declared `adjustment`, actually applied | 4 (splits everywhere, dividends nowhere) |
| BIST un-adjust failure detected | 4 — **moot**: Decision A always requests `adjust=True`, which never enters `_unadjust_prices`. Recorded in Task 8 Step 3 rather than defended against. |
| explicit stale-price tolerance | 2 (`StalePriceError`, `DEFAULT_MAX_STALENESS_DAYS`) |
| provider window caps surfaced as their real cause | 5 (`COINBASE_MAX_CANDLES`) |

**Deferred to Phase 2/3, not lost** (tracked in spec §0b): US silent resampling with no `bar_interval`/warning and its future-dated bars (Phase 2, history adapter); `guncel_deger` mislabelled `sell` (Phase 3, `get_quote`); `get_fund_data` dropping the order cutoff and valor fields (Phase 3). The flaky TradingView websocket is a reliability problem, not a contract one, and is tracked separately.

**Type consistency:** `to_canonical(raw, market)` takes `market` as a `str` matching `MarketType.value` (`"bist"`, `"crypto_tr"`, …), not the enum — the live test passes `MarketType(market)` to the router but the plain string to `to_canonical`. `Bar.volume` is `Optional[float]` everywhere (Task 5 stops the `int()` truncation that would otherwise contradict it). `fund_valuation_date` takes and returns `YYYY-MM-DD` strings, matching `normalize_date`'s output.
