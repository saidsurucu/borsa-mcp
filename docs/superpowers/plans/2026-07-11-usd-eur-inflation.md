# USD / EUR Inflation Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `get_macro_data` with a `region` parameter so it serves US CPI and euro-area HICP purchasing-power calculations alongside Turkish TÜFE/ÜFE — and fix the live bug where a failed TCMB call is reported as 0% inflation.

**Architecture:** A new `FredCpiProvider` fetches monthly price indices from FRED's keyless CSV export, validates them (a HTTP 200 with a garbage body is the failure mode this repo keeps meeting), and computes ratios. `MarketRouter.get_macro_data` gains a keyword-only `region` that dispatches to either the existing TCMB path or the new provider. Tool count stays at 28.

**Tech Stack:** Python 3.11+, httpx (async), pytest, Pydantic v2, FastMCP.

**Spec:** `docs/superpowers/specs/2026-07-11-usd-eur-inflation-design.md`

## Global Constraints

- **Never return an empty-but-successful payload.** Providers raise; the tool layer converts via `classify_tool_error`. An empty response reads to an LLM as "this exists and has no data" — a stronger and usually false claim than "the fetch failed". (CLAUDE.md #7)
- **Never trust an upstream that degrades quietly.** Validate the shape of what comes back; do not accept any non-empty parse. (CLAUDE.md #5)
- **All LLM-visible descriptions are written in English**, even though the domain is Turkish.
- `DataNotAvailableError` is imported from `borsapy.exceptions`.
- Series identifiers, verified live on 2026-07-11:
  - US: `CPIAUCNS` (CPI-U, **not** seasonally adjusted), starts 1913-01.
  - EU: `CP0000EZCCM086NEST` (euro-area HICP, **changing composition**), starts 1996-01.
  - The EA19 series `CP0000EZ19M086NEST` is **wrong** — a frozen 19-country geography that drifts from EA20. Do not use it.
- Golden values for tests (real data, 2026-07-11): $100 (2010-01) → **$154.66** at 2026-05 (54.7%); €100 (2010-01) → **€145.01** at 2026-05 (45.0%).
- Run tests with `uv run python -m pytest tests/ -q --ignore=tests/adhoc`.
- `pyproject.toml` sets `asyncio_mode = "auto"`, so an `async def test_*` runs without any marker. The `@pytest.mark.asyncio` decorators shown below are harmless but redundant; drop them to match the existing tests.

---

### Task 1: Stop the TR path reporting 0% inflation on failure

`TcmbProvider.calculate_inflation()` catches every exception and returns a result object with `yeni_sepet_degeri=""` and `error_message` set. `MarketRouter.get_macro_data()` never reads `error_message`; it checks `hasattr(result, 'yeni_sepet_degeri')`, which the error object satisfies. The empty string is falsy, so `final_value` falls back to the input basket and the tool returns a successful-looking `cumulative_inflation: 0.0`. The inflation-series path has the same hole in a milder form: on failure it returns `inflation_data: null` inside a successful response.

This task is a prerequisite: the rest of the plan claims providers raise, and that must be true for every path the tool has, not just the new ones.

**Files:**
- Modify: `providers/market_router.py:2495-2565` (`get_macro_data`)
- Test: `tests/test_macro_tr_errors.py` (create)

**Interfaces:**
- Consumes: `self._client.get_turkiye_enflasyon(...)`, `self._client.calculate_inflation(...)` — both return objects that may carry `error_message`.
- Produces: `MarketRouter.get_macro_data` now raises `DataNotAvailableError` instead of fabricating a zero result. Task 5 builds on this signature.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_macro_tr_errors.py
import pytest
from borsapy.exceptions import DataNotAvailableError
from providers.market_router import MarketRouter


@pytest.mark.asyncio
async def test_calculate_raises_instead_of_reporting_zero_inflation():
    """An inverted range makes TcmbProvider return an error object. The router
    must raise, not report a 0% calculation as a success."""
    router = MarketRouter()

    with pytest.raises(DataNotAvailableError):
        await router.get_macro_data(
            data_type="calculate",
            start_year=2024, start_month=6,
            end_year=2020, end_month=1,   # inverted on purpose
            basket_value=100.0,
        )


@pytest.mark.asyncio
async def test_calculate_never_returns_zero_cumulative_on_error():
    """Regression guard for the exact shape the bug produced."""
    router = MarketRouter()

    try:
        result = await router.get_macro_data(
            data_type="calculate",
            start_year=2024, start_month=6,
            end_year=2020, end_month=1,
            basket_value=100.0,
        )
    except DataNotAvailableError:
        return  # correct behaviour

    calc = result.get("calculation") or {}
    pytest.fail(
        f"Router returned a successful payload for a failed call: {calc}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_macro_tr_errors.py -q`
Expected: FAIL — `DID NOT RAISE`, and the second test fails with the fabricated `{'cumulative_inflation': 0.0, ...}` payload.

- [ ] **Step 3: Make the router inspect error_message and empty results**

In `providers/market_router.py`, add the import at the top of the file (next to the other provider imports):

```python
from borsapy.exceptions import DataNotAvailableError
```

Then rewrite the two branches inside `get_macro_data`. Replace the `if data_type == "inflation":` block body with:

```python
        if data_type == "inflation":
            result = await self._client.get_turkiye_enflasyon(
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )

            # TcmbProvider swallows exceptions and returns an error-bearing object.
            # Surfacing it as a successful empty response would tell the caller
            # "TÜFE exists and has no data", which is false.
            if result is None or getattr(result, "error_message", None):
                raise DataNotAvailableError(
                    f"TCMB inflation data unavailable: "
                    f"{getattr(result, 'error_message', 'no response')}"
                )
            if not getattr(result, "data", None):
                raise DataNotAvailableError(
                    "TCMB returned no inflation rows for the requested range."
                )

            inflation_data = []
            for d in result.data:
                inflation_data.append({
                    "date": d.tarih,
                    "rate": d.yillik_enflasyon or 0.0,
                    "change": d.aylik_enflasyon,
                    "cumulative": None
                })
```

Replace the `elif data_type == "calculate":` block body with:

```python
        elif data_type == "calculate":
            if not all([start_year, start_month, end_year, end_month]):
                raise ValueError(
                    "calculate mode requires start_year, start_month, end_year "
                    "and end_month."
                )
            if basket_value <= 0:
                raise ValueError("basket_value must be greater than 0.")

            result = await self._client.calculate_inflation(
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value
            )

            # The error object still has a `yeni_sepet_degeri` attribute (empty
            # string), so a hasattr check passes and the falsy value silently
            # becomes "prices did not move". Check the error field instead.
            if result is None or getattr(result, "error_message", None):
                raise DataNotAvailableError(
                    f"TCMB inflation calculation failed: "
                    f"{getattr(result, 'error_message', 'no response')}"
                )
            if not result.yeni_sepet_degeri:
                raise DataNotAvailableError(
                    "TCMB returned an empty calculation for the requested period."
                )

            def tr_to_float(s: str) -> float:
                if not s:
                    return 0.0
                return float(s.replace('.', '').replace(',', '.'))

            final_value = tr_to_float(result.yeni_sepet_degeri)
            total_change = tr_to_float(result.toplam_degisim)
            cumulative = (total_change / basket_value) * 100
            period_months = result.toplam_yil * 12 + result.toplam_ay

            calculation = {
                "start_period": f"{start_year}-{start_month:02d}",
                "end_period": f"{end_year}-{end_month:02d}",
                "initial_value": basket_value,
                "final_value": final_value,
                "cumulative_inflation": cumulative,
                "period_months": period_months,
                "start_index": tr_to_float(result.ilk_yil_tufe) or None,
                "end_index": tr_to_float(result.son_yil_tufe) or None,
                "annualized_compound_change": tr_to_float(
                    result.ortalama_yillik_enflasyon
                ) or None,
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_macro_tr_errors.py -q`
Expected: PASS (2 passed)

Then confirm the happy path still works:

Run: `uv run python -c "
import asyncio
from providers.market_router import MarketRouter
r = MarketRouter()
out = asyncio.run(r.get_macro_data(data_type='calculate', start_year=2020, start_month=1, end_year=2024, end_month=12, basket_value=100.0))
print(out['calculation'])
"`
Expected: a real calculation with `cumulative_inflation` far above 0 and non-null `start_index` / `end_index`.

- [ ] **Step 5: Run the full suite for regressions**

Run: `uv run python -m pytest tests/ -q --ignore=tests/adhoc`
Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add tests/test_macro_tr_errors.py providers/market_router.py
git commit -m "fix(macro): raise instead of reporting 0% inflation when TCMB fails

TcmbProvider swallows exceptions into an error-bearing result object whose
yeni_sepet_degeri is an empty string. The router checked hasattr, which the
error object satisfies, and the falsy value made final_value fall back to the
input basket -- so a failed call returned cumulative_inflation: 0.0 as a
success. An LLM reading that tells the user prices did not move."
```

---

### Task 2: `FredCpiProvider` — validated series fetch

**Files:**
- Create: `providers/fred_cpi_provider.py`
- Test: `tests/test_fred_cpi_provider.py` (create)

**Interfaces:**
- Produces, relied on by Tasks 3–5:
  - `IndexSeries` dataclass: `region: str`, `source: str`, `values: Dict[str, float]` (`"YYYY-MM"` → level), `degraded: bool`, and properties `first_month: str`, `last_month: str`.
  - `parse_fred_csv(text: str, series_id: str) -> Dict[str, float]` — raises `ValueError` on a malformed body.
  - `validate_series(values: Dict[str, float], expected_start_year: int, min_observations: int = 200) -> None` — raises `ValueError`.
  - `FredCpiProvider.get_index_series(region: str) -> IndexSeries`.
  - `FredCpiProvider.SERIES: Dict[str, SeriesSpec]` where `SeriesSpec` has `series_id`, `label`, `start_year`, `currency`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fred_cpi_provider.py
import pytest

from providers.fred_cpi_provider import (
    IndexSeries,
    FredCpiProvider,
    parse_fred_csv,
    validate_series,
)

GOOD_CSV = "observation_date,CPIAUCNS\n2010-01-01,216.687\n2010-02-01,216.741\n"


def test_parse_fred_csv_reads_months_and_levels():
    assert parse_fred_csv(GOOD_CSV, "CPIAUCNS") == {
        "2010-01": 216.687,
        "2010-02": 216.741,
    }


def test_parse_fred_csv_drops_missing_value_rows():
    csv = "observation_date,CPIAUCNS\n2010-01-01,216.687\n2010-02-01,.\n"
    assert parse_fred_csv(csv, "CPIAUCNS") == {"2010-01": 216.687}


def test_parse_fred_csv_rejects_html_error_body():
    """FRED answering 200 with an HTML error page must not parse to {}."""
    with pytest.raises(ValueError, match="column"):
        parse_fred_csv("<html><body>Service unavailable</body></html>", "CPIAUCNS")


def test_parse_fred_csv_rejects_renamed_column():
    """yfinance renamed a column and a .get() default hid it for months. Fail loudly."""
    csv = "observation_date,CPI_ALL_ITEMS\n2010-01-01,216.687\n"
    with pytest.raises(ValueError, match="column"):
        parse_fred_csv(csv, "CPIAUCNS")


def test_validate_series_rejects_truncated_feed():
    values = {f"2020-{m:02d}": 100.0 + m for m in range(1, 13)}
    with pytest.raises(ValueError, match="observations"):
        validate_series(values, expected_start_year=1913)


def test_validate_series_rejects_late_start():
    """A feed that begins decades after the series really starts is truncated."""
    values = {f"{y}-01": 100.0 for y in range(1990, 2026)}
    values.update({f"{y}-06": 101.0 for y in range(1990, 2026)})
    values.update({f"{y}-{m:02d}": 100.0 for y in range(1990, 2026) for m in range(2, 6)})
    with pytest.raises(ValueError, match="starts at"):
        validate_series(values, expected_start_year=1913, min_observations=10)


def test_validate_series_rejects_nonpositive_level():
    values = {f"1913-{m:02d}": 9.8 for m in range(1, 13)}
    values.update({f"{y}-{m:02d}": 100.0 for y in range(1914, 1935) for m in range(1, 13)})
    values["1920-06"] = -1.0
    with pytest.raises(ValueError, match="positive"):
        validate_series(values, expected_start_year=1913, min_observations=10)


def test_index_series_exposes_bounds():
    s = IndexSeries(
        region="us",
        source="FRED (CPIAUCNS)",
        values={"2010-01": 100.0, "2010-02": 101.0},
    )
    assert s.first_month == "2010-01"
    assert s.last_month == "2010-02"
    assert s.degraded is False


def test_series_spec_uses_changing_composition_euro_series():
    """EA19 is a frozen geography that drifts from EA20. Guard the choice."""
    assert FredCpiProvider.SERIES["eu"].series_id == "CP0000EZCCM086NEST"
    assert FredCpiProvider.SERIES["us"].series_id == "CPIAUCNS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_fred_cpi_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'providers.fred_cpi_provider'`

- [ ] **Step 3: Write the provider**

```python
# providers/fred_cpi_provider.py
"""
FRED CPI Provider — monthly consumer price indices for the US and the euro area.

Sourced from FRED's keyless CSV export. Two things this module refuses to do,
both learned the hard way in this repo (CLAUDE.md #5, #7):

  * accept any non-empty parse. An upstream that answers HTTP 200 with an HTML
    error page, a renamed column, or a truncated feed must fail loudly.
  * merge two sources into one series. FRED and the fallbacks use different base
    years; a series assembled from both yields ratios that are silently garbage.
"""

import asyncio
import csv
import io
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional

import httpx
from borsapy.exceptions import DataNotAvailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    label: str
    start_year: int
    currency: str


@dataclass
class IndexSeries:
    """A monthly price index plus where it came from.

    `source` and `degraded` are not decoration: a caller must be able to see that
    an answer came from a fallback, and how fresh it is, rather than assume it.
    """
    region: str
    source: str
    values: Dict[str, float]          # "YYYY-MM" -> index level
    degraded: bool = False
    warnings: list = field(default_factory=list)

    @property
    def first_month(self) -> str:
        return min(self.values)

    @property
    def last_month(self) -> str:
        return max(self.values)


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

MIN_OBSERVATIONS = 200
FRESHNESS_DAYS = 70
CACHE_TTL_SECONDS = 6 * 3600


def parse_fred_csv(text: str, series_id: str) -> Dict[str, float]:
    """Parse FRED's `observation_date,<SERIES_ID>` CSV. Raise on anything else."""
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []

    if "observation_date" not in fieldnames or series_id not in fieldnames:
        raise ValueError(
            f"FRED response for {series_id} lacks the expected column: got "
            f"{fieldnames or 'no header'}. The endpoint may have changed or "
            f"returned an error page."
        )

    values: Dict[str, float] = {}
    for row in reader:
        raw = (row.get(series_id) or "").strip()
        if raw in ("", "."):          # FRED encodes a missing observation as '.'
            continue
        observation = (row.get("observation_date") or "").strip()
        if len(observation) < 7:
            continue
        values[observation[:7]] = float(raw)

    return values


def validate_series(
    values: Dict[str, float],
    expected_start_year: int,
    min_observations: int = MIN_OBSERVATIONS,
) -> None:
    """Reject a series that parsed but cannot be what we asked for."""
    if len(values) < min_observations:
        raise ValueError(
            f"Series has only {len(values)} observations, expected at least "
            f"{min_observations}. The feed looks truncated."
        )

    first_year = int(min(values)[:4])
    if first_year > expected_start_year + 1:
        raise ValueError(
            f"Series starts at {min(values)} but should start near "
            f"{expected_start_year}. The feed looks truncated."
        )

    for month, level in values.items():
        if not (level > 0) or level != level or level in (float("inf"), float("-inf")):
            raise ValueError(
                f"Series has a non-positive or non-finite level at {month}: {level}"
            )


def months_between(start: str, end: str) -> int:
    """Count month-to-month intervals. 2010-01 -> 2011-01 is 12."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    return (ey - sy) * 12 + (em - sm)


class FredCpiProvider:
    """US CPI-U and euro-area HICP, with validated parsing and provenance."""

    SERIES: Dict[str, SeriesSpec] = {
        "us": SeriesSpec(
            series_id="CPIAUCNS",
            label="US CPI-U, not seasonally adjusted (BLS via FRED)",
            start_year=1913,
            currency="USD",
        ),
        # Changing composition (EA11 -> ... -> EA19 -> EA20). NOT CP0000EZ19M086NEST,
        # which is frozen at 19 countries, excludes Croatia, and drifts from EA20.
        "eu": SeriesSpec(
            series_id="CP0000EZCCM086NEST",
            label="Euro area HICP, changing composition (Eurostat via FRED)",
            start_year=1996,
            currency="EUR",
        ),
    }

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, tuple] = {}          # region -> (fetched_at, IndexSeries)
        self._locks: Dict[str, asyncio.Lock] = {}   # region -> single-flight lock

    def _lock(self, region: str) -> asyncio.Lock:
        if region not in self._locks:
            self._locks[region] = asyncio.Lock()
        return self._locks[region]

    async def get_index_series(self, region: str, today: Optional[date] = None) -> IndexSeries:
        if region not in self.SERIES:
            raise ValueError(
                f"Unknown region '{region}'. Supported: {sorted(self.SERIES)}."
            )

        # Single-flight: a cold start with concurrent callers makes one upstream
        # call, not N. This also protects the anonymous BLS quota (25/day/IP).
        async with self._lock(region):
            cached = self._cache.get(region)
            if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
                return cached[1]

            series = await self._fetch_primary(region)
            if series is None:
                series = await self._fetch_fallback(region)
            if series is None:
                raise DataNotAvailableError(
                    f"Could not fetch a valid {region.upper()} price index from "
                    f"FRED or its fallback."
                )

            self._annotate_freshness(series, today or date.today())
            self._cache[region] = (time.time(), series)
            return series

    async def _fetch_primary(self, region: str) -> Optional[IndexSeries]:
        spec = self.SERIES[region]
        try:
            response = await self._client.get(
                FRED_CSV_URL.format(series_id=spec.series_id)
            )
            response.raise_for_status()
            values = parse_fred_csv(response.text, spec.series_id)
            validate_series(values, expected_start_year=spec.start_year)
        except Exception as e:
            logger.warning(f"FRED primary fetch failed for {region}: {e}")
            return None

        return IndexSeries(
            region=region,
            source=f"FRED ({spec.series_id})",
            values=values,
        )

    async def _fetch_fallback(self, region: str) -> Optional[IndexSeries]:
        # Implemented in Task 4. Until then there is no second leg.
        return None

    def _annotate_freshness(self, series: IndexSeries, today: date) -> None:
        """Staleness must be an observable fact, not an assumption."""
        last = series.last_month
        last_day = date(int(last[:4]), int(last[5:7]), 1)
        age_days = (today - last_day).days
        if age_days > FRESHNESS_DAYS:
            series.warnings.append(
                f"Latest available observation is {last} ({age_days} days old). "
                f"The source may be lagging or stale."
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_fred_cpi_provider.py -q`
Expected: PASS (9 passed)

- [ ] **Step 5: Confirm both series fetch and validate against the real endpoint**

Run: `uv run python -c "
import asyncio
from providers.fred_cpi_provider import FredCpiProvider
async def main():
    p = FredCpiProvider()
    for region in ('us', 'eu'):
        s = await p.get_index_series(region)
        print(region, s.source, s.first_month, '->', s.last_month, len(s.values), 'points', s.warnings)
asyncio.run(main())
"`
Expected: `us FRED (CPIAUCNS) 1913-01 -> 2026-05 …` and `eu FRED (CP0000EZCCM086NEST) 1996-01 -> 2026-05 …`, no freshness warning.

- [ ] **Step 6: Commit**

```bash
git add providers/fred_cpi_provider.py tests/test_fred_cpi_provider.py
git commit -m "feat(macro): add FredCpiProvider with validated series parsing

Fetches US CPI-U (CPIAUCNS) and euro-area HICP (CP0000EZCCM086NEST, changing
composition) from FRED's keyless CSV export. Rejects an HTML error body, a
renamed column, a truncated feed, and non-positive levels rather than accepting
any non-empty parse."
```

---

### Task 3: Inflation series and the purchasing-power calculation

**Files:**
- Modify: `providers/fred_cpi_provider.py`
- Test: `tests/test_fred_cpi_calculation.py` (create)

**Interfaces:**
- Consumes from Task 2: `IndexSeries`, `FredCpiProvider.get_index_series`, `months_between`.
- Produces, relied on by Task 5:
  - `FredCpiProvider.get_inflation_data(region, start_date=None, end_date=None, limit=None) -> dict` returning `{"region", "currency", "source", "series_end", "inflation_data": [{"date", "rate", "change", "cumulative"}], "warnings"}`. `rate` is year-over-year %, `change` is month-over-month %.
  - `FredCpiProvider.calculate_inflation(region, start_year, start_month, end_year, end_month, basket_value) -> dict` returning `{"region", "currency", "source", "series_end", "calculation": {...}, "warnings"}` where `calculation` has `start_period`, `end_period`, `initial_value`, `final_value`, `cumulative_inflation`, `period_months`, `start_index`, `end_index`, `annualized_compound_change`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fred_cpi_calculation.py
import pytest

from providers.fred_cpi_provider import FredCpiProvider, IndexSeries


def _series(values, region="us", source="test", degraded=False):
    return IndexSeries(region=region, source=source, values=values, degraded=degraded)


@pytest.fixture
def provider_with(monkeypatch):
    def _make(values, region="us", degraded=False):
        p = FredCpiProvider()

        async def fake_get_index_series(r, today=None):
            return _series(values, region=r, degraded=degraded)

        monkeypatch.setattr(p, "get_index_series", fake_get_index_series)
        return p
    return _make


# 12 months of 1%-per-month compounding, plus the endpoint.
FLAT = {f"2020-{m:02d}": 100.0 * (1.01 ** (m - 1)) for m in range(1, 13)}
FLAT["2021-01"] = 100.0 * (1.01 ** 12)


@pytest.mark.asyncio
async def test_calculate_uses_the_index_ratio(provider_with):
    p = provider_with({"2010-01": 200.0, "2020-01": 300.0, **FLAT})
    out = await p.calculate_inflation("us", 2010, 1, 2020, 1, basket_value=100.0)
    calc = out["calculation"]

    assert calc["final_value"] == pytest.approx(150.0)
    assert calc["cumulative_inflation"] == pytest.approx(50.0)
    assert calc["start_index"] == 200.0
    assert calc["end_index"] == 300.0
    assert calc["period_months"] == 120


@pytest.mark.asyncio
async def test_annualized_change_emitted_for_a_full_year(provider_with):
    p = provider_with(FLAT)
    out = await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)
    calc = out["calculation"]

    assert calc["period_months"] == 12
    # 1% compounded monthly for 12 months ~= 12.68% annualized
    assert calc["annualized_compound_change"] == pytest.approx(12.68, abs=0.01)


@pytest.mark.asyncio
async def test_annualized_change_suppressed_below_twelve_months(provider_with):
    """Annualizing an NSA index over 3 months annualizes seasonality too."""
    p = provider_with(FLAT)
    out = await p.calculate_inflation("us", 2020, 1, 2020, 4, basket_value=100.0)

    assert out["calculation"]["annualized_compound_change"] is None
    assert any("12 months" in w for w in out["warnings"])


@pytest.mark.asyncio
async def test_seasonality_warning_when_calendar_months_differ(provider_with):
    p = provider_with({**FLAT, "2022-06": 130.0})
    out = await p.calculate_inflation("us", 2020, 1, 2022, 6, basket_value=100.0)

    assert any("seasonal" in w.lower() for w in out["warnings"])


@pytest.mark.asyncio
async def test_missing_endpoint_raises_instead_of_snapping_to_a_neighbour(provider_with):
    p = provider_with(FLAT)
    with pytest.raises(ValueError, match="not available"):
        await p.calculate_inflation("us", 1975, 3, 2020, 12, basket_value=100.0)


@pytest.mark.asyncio
async def test_gap_inside_the_interval_raises(provider_with):
    values = {"2020-01": 100.0, "2020-02": 101.0, "2021-01": 110.0}  # Mar-Dec missing
    p = provider_with(values)
    with pytest.raises(ValueError, match="missing"):
        await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=100.0)


@pytest.mark.asyncio
async def test_inverted_range_raises(provider_with):
    p = provider_with(FLAT)
    with pytest.raises(ValueError, match="before"):
        await p.calculate_inflation("us", 2021, 1, 2020, 1, basket_value=100.0)


@pytest.mark.asyncio
async def test_nonpositive_basket_raises(provider_with):
    p = provider_with(FLAT)
    with pytest.raises(ValueError, match="greater than 0"):
        await p.calculate_inflation("us", 2020, 1, 2021, 1, basket_value=0.0)


@pytest.mark.asyncio
async def test_inflation_data_reports_yoy_as_rate_and_mom_as_change(provider_with):
    values = {f"2020-{m:02d}": 100.0 for m in range(1, 13)}
    values["2020-12"] = 110.0
    values["2021-12"] = 121.0
    values["2021-01"] = 110.0
    p = provider_with(values)

    out = await p.get_inflation_data("us")
    by_month = {d["date"]: d for d in out["inflation_data"]}

    assert by_month["2021-12"]["rate"] == pytest.approx(10.0)   # YoY vs 2020-12
    assert by_month["2020-12"]["change"] == pytest.approx(10.0)  # MoM vs 2020-11


@pytest.mark.asyncio
async def test_degraded_source_is_reported(provider_with):
    p = provider_with({"2010-01": 200.0, "2020-01": 300.0, **FLAT}, degraded=True)
    out = await p.calculate_inflation("us", 2010, 1, 2020, 1, basket_value=100.0)

    assert any("fallback" in w.lower() or "degraded" in w.lower() for w in out["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_fred_cpi_calculation.py -q`
Expected: FAIL — `AttributeError: 'FredCpiProvider' object has no attribute 'calculate_inflation'`

- [ ] **Step 3: Implement the two methods**

Append to `providers/fred_cpi_provider.py`, inside `FredCpiProvider`:

```python
    def _envelope(self, series: IndexSeries) -> dict:
        spec = self.SERIES[series.region]
        warnings = list(series.warnings)
        if series.degraded:
            warnings.append(
                f"Served from a fallback source ({series.source}); the primary "
                f"source (FRED) was unavailable."
            )
        return {
            "region": series.region,
            "currency": spec.currency,
            "source": series.source,
            "series_end": series.last_month,
            "warnings": warnings,
        }

    async def get_inflation_data(
        self,
        region: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """`rate` is year-over-year %, `change` is month-over-month %."""
        series = await self.get_index_series(region)
        values = series.values
        months = sorted(values)

        rows = []
        for i, month in enumerate(months):
            prev_month = months[i - 1] if i > 0 else None
            change = None
            if prev_month and months_between(prev_month, month) == 1:
                change = (values[month] / values[prev_month] - 1) * 100

            year_ago = f"{int(month[:4]) - 1}-{month[5:7]}"
            rate = None
            if year_ago in values:
                rate = (values[month] / values[year_ago] - 1) * 100

            if start_date and month < start_date[:7]:
                continue
            if end_date and month > end_date[:7]:
                continue

            rows.append({
                "date": month,
                "rate": rate,
                "change": change,
                "cumulative": None,
            })

        if limit:
            rows = rows[-limit:]

        out = self._envelope(series)
        out["inflation_data"] = rows
        return out

    async def calculate_inflation(
        self,
        region: str,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        basket_value: float = 100.0,
    ) -> dict:
        if basket_value <= 0:
            raise ValueError("basket_value must be greater than 0.")

        start = f"{start_year}-{start_month:02d}"
        end = f"{end_year}-{end_month:02d}"
        if months_between(start, end) <= 0:
            raise ValueError(f"Start period {start} must be before end period {end}.")

        series = await self.get_index_series(region)
        values = series.values

        # Never substitute a neighbouring month: a caller asking about 1975-03 and
        # silently getting 1996-01 back would be told a confident wrong number.
        for period in (start, end):
            if period not in values:
                raise ValueError(
                    f"{period} is not available in the {region.upper()} series "
                    f"({series.first_month} to {series.last_month})."
                )

        span = months_between(start, end)
        for i in range(span + 1):
            y, m = divmod((start_year * 12 + start_month - 1) + i, 12)
            month = f"{y}-{m + 1:02d}"
            if month not in values:
                raise ValueError(
                    f"The {region.upper()} series is missing {month}, inside the "
                    f"requested interval {start} to {end}."
                )

        out = self._envelope(series)
        warnings = out["warnings"]

        ratio = values[end] / values[start]

        annualized = None
        if span >= 12:
            annualized = (ratio ** (12 / span) - 1) * 100
        else:
            warnings.append(
                "annualized_compound_change is reported only for intervals of at "
                "least 12 months; on a non-seasonally-adjusted index a shorter "
                "interval would annualize seasonal movement as if it were inflation."
            )

        if start_month != end_month:
            warnings.append(
                f"Start ({start}) and end ({end}) fall in different calendar months. "
                f"These indices are not seasonally adjusted, so the comparison "
                f"carries a seasonal component."
            )

        warnings.append(
            "Index values are monthly averages, not prices on a specific day."
        )

        out["calculation"] = {
            "start_period": start,
            "end_period": end,
            "initial_value": basket_value,
            "final_value": basket_value * ratio,
            "cumulative_inflation": (ratio - 1) * 100,
            "period_months": span,
            "start_index": values[start],
            "end_index": values[end],
            "annualized_compound_change": annualized,
        }
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_fred_cpi_calculation.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Verify the golden values against live data**

Run: `uv run python -c "
import asyncio
from providers.fred_cpi_provider import FredCpiProvider
async def main():
    p = FredCpiProvider()
    for region, label in (('us', '\$'), ('eu', '€')):
        s = await p.get_index_series(region)
        end_y, end_m = int(s.last_month[:4]), int(s.last_month[5:7])
        out = await p.calculate_inflation(region, 2010, 1, end_y, end_m, 100.0)
        c = out['calculation']
        print(f\"{label}100 (2010-01) -> {label}{c['final_value']:.2f} at {c['end_period']} ({c['cumulative_inflation']:.1f}%)\")
asyncio.run(main())
"`
Expected: `$100 (2010-01) -> $154.66 at 2026-05 (54.7%)` and `€100 (2010-01) -> €145.01 at 2026-05 (45.0%)`. If the euro figure comes out as 144.91, the wrong (EA19) series is wired up.

- [ ] **Step 6: Commit**

```bash
git add providers/fred_cpi_provider.py tests/test_fred_cpi_calculation.py
git commit -m "feat(macro): compute US/EU inflation series and purchasing power

Endpoints must be present exactly -- a missing month raises rather than snapping
to a neighbour, and a gap inside the interval raises. The annualized figure is
gated to intervals of at least 12 months, because annualizing a non-seasonally-
adjusted index annualizes seasonality along with inflation."
```

---

### Task 4: Fallback sources, with staleness made visible

**Files:**
- Modify: `providers/fred_cpi_provider.py` (`_fetch_fallback`)
- Test: `tests/test_fred_cpi_fallback.py` (create)

**Interfaces:**
- Consumes from Task 2: `IndexSeries`, `validate_series`, `MIN_OBSERVATIONS`.
- Produces: a working `_fetch_fallback(region) -> Optional[IndexSeries]` returning `degraded=True` series. Task 5 needs no new names.

Facts verified live on 2026-07-11, which the tests encode:
- BLS v1 (`https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0`) returns roughly the last 3 years and is capped at 25 requests/day/IP.
- Eurostat (`prc_hicp_midx`, `geo=EA` — the changing-composition cut, matching the FRED series to within 0.011%) currently ends at **2025-12**, six months behind FRED.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fred_cpi_fallback.py
import pytest

from providers.fred_cpi_provider import (
    FredCpiProvider,
    parse_bls_json,
    parse_eurostat_json,
)

BLS_JSON = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {"series": [{"data": [
        {"year": "2026", "period": "M05", "value": "335.123"},
        {"year": "2026", "period": "M04", "value": "333.020"},
    ]}]},
}

EUROSTAT_JSON = {
    "value": {"0": 129.33, "1": 129.56},
    "dimension": {"time": {"category": {"index": {"2025-11": 0, "2025-12": 1}}}},
}


def test_parse_bls_json_reads_months():
    assert parse_bls_json(BLS_JSON) == {"2026-05": 335.123, "2026-04": 333.020}


def test_parse_bls_json_rejects_a_failed_request():
    with pytest.raises(ValueError, match="BLS"):
        parse_bls_json({"status": "REQUEST_NOT_PROCESSED", "Results": {}})


def test_parse_eurostat_json_reads_months():
    assert parse_eurostat_json(EUROSTAT_JSON) == {"2025-11": 129.33, "2025-12": 129.56}


def test_parse_eurostat_json_rejects_empty_value_block():
    """Eurostat answering 200 with no observations must not parse to {}."""
    with pytest.raises(ValueError, match="Eurostat"):
        parse_eurostat_json({"value": {}, "dimension": {"time": {"category": {"index": {}}}}})


@pytest.mark.asyncio
async def test_calculation_past_the_bls_window_raises(monkeypatch):
    """BLS spans ~3 years. Computing '$100 in 2010' off it would be a confident
    wrong answer, so it must raise rather than compute off a truncated series."""
    p = FredCpiProvider()

    async def no_primary(region):
        return None

    async def bls_only(region):
        from providers.fred_cpi_provider import IndexSeries
        values = {f"{y}-{m:02d}": 300.0 + m for y in (2024, 2025, 2026) for m in range(1, 13)}
        return IndexSeries(
            region=region,
            source="BLS v1 (CUUR0000SA0)",
            values=values,
            degraded=True,
        )

    monkeypatch.setattr(p, "_fetch_primary", no_primary)
    monkeypatch.setattr(p, "_fetch_fallback", bls_only)

    with pytest.raises(ValueError, match="not available"):
        await p.calculate_inflation("us", 2010, 1, 2026, 5, basket_value=100.0)


@pytest.mark.asyncio
async def test_stale_fallback_is_served_with_a_warning_not_silently(monkeypatch):
    """Eurostat currently lags FRED by six months. A quiet six-month-old answer
    is the same silent-wrong failure, just relocated."""
    from datetime import date
    from providers.fred_cpi_provider import IndexSeries

    p = FredCpiProvider()

    async def no_primary(region):
        return None

    async def stale_eurostat(region):
        values = {f"{y}-{m:02d}": 100.0 + m for y in range(2000, 2026) for m in range(1, 13)}
        return IndexSeries(
            region=region,
            source="Eurostat (prc_hicp_midx, geo=EA)",
            values=values,   # ends 2025-12
            degraded=True,
        )

    monkeypatch.setattr(p, "_fetch_primary", no_primary)
    monkeypatch.setattr(p, "_fetch_fallback", stale_eurostat)

    series = await p.get_index_series("eu", today=date(2026, 7, 11))

    assert series.degraded is True
    assert any("2025-12" in w for w in series.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_fred_cpi_fallback.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_bls_json'`

- [ ] **Step 3: Implement the fallbacks**

Add to `providers/fred_cpi_provider.py`, at module level:

```python
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0"
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_midx?format=JSON&geo=EA&coicop=CP00&unit=I15"
)

# A fallback replaces the whole series; it is never merged with the primary. The
# sources use different base years, so a dict holding months from both would
# yield ratios that are silently garbage.
FALLBACK_SOURCES = {
    "us": ("BLS v1 (CUUR0000SA0)", BLS_URL),
    "eu": ("Eurostat (prc_hicp_midx, geo=EA)", EUROSTAT_URL),
}

# BLS returns ~3 years, far short of the primary series, so a validated fallback
# cannot be held to the primary's minimum.
FALLBACK_MIN_OBSERVATIONS = 24


def parse_bls_json(payload: dict) -> Dict[str, float]:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(
            f"BLS request did not succeed: {payload.get('status')} "
            f"{payload.get('message')}"
        )
    try:
        rows = payload["Results"]["series"][0]["data"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"BLS response has an unexpected shape: {e}")

    values: Dict[str, float] = {}
    for row in rows:
        period = row.get("period", "")
        if not period.startswith("M") or period == "M13":  # M13 is an annual average
            continue
        values[f"{row['year']}-{period[1:]}"] = float(row["value"])

    if not values:
        raise ValueError("BLS returned no monthly observations.")
    return values


def parse_eurostat_json(payload: dict) -> Dict[str, float]:
    try:
        index = payload["dimension"]["time"]["category"]["index"]
        value = payload["value"]
    except KeyError as e:
        raise ValueError(f"Eurostat response has an unexpected shape: {e}")

    values = {
        month: float(value[str(i)])
        for month, i in index.items()
        if str(i) in value
    }
    if not values:
        raise ValueError("Eurostat returned no observations.")
    return values
```

Then replace the `_fetch_fallback` stub with:

```python
    async def _fetch_fallback(self, region: str) -> Optional[IndexSeries]:
        label, url = FALLBACK_SOURCES[region]
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            payload = response.json()
            values = (
                parse_bls_json(payload) if region == "us"
                else parse_eurostat_json(payload)
            )
            validate_series(
                values,
                expected_start_year=int(min(values)[:4]),   # a fallback may start late
                min_observations=FALLBACK_MIN_OBSERVATIONS,
            )
        except Exception as e:
            logger.warning(f"Fallback fetch failed for {region} ({label}): {e}")
            return None

        logger.warning(
            f"Serving {region.upper()} from the fallback source {label}; "
            f"FRED was unavailable."
        )
        return IndexSeries(
            region=region,
            source=label,
            values=values,
            degraded=True,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_fred_cpi_fallback.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Verify both fallbacks against the real endpoints**

Run: `uv run python -c "
import asyncio
from providers.fred_cpi_provider import FredCpiProvider
async def main():
    p = FredCpiProvider()
    for region in ('us', 'eu'):
        s = await p._fetch_fallback(region)
        print(region, s.source, s.first_month, '->', s.last_month, len(s.values), 'points, degraded =', s.degraded)
asyncio.run(main())
"`
Expected: US from BLS (~3 years of months), EU from Eurostat ending around 2025-12 — both `degraded = True`.

- [ ] **Step 6: Commit**

```bash
git add providers/fred_cpi_provider.py tests/test_fred_cpi_fallback.py
git commit -m "feat(macro): add BLS and Eurostat fallbacks with visible staleness

A fallback replaces the whole series and never merges with the primary -- the
sources use different base years, so a mixed series would yield silently wrong
ratios. Eurostat currently lags FRED by six months, so the response says which
source answered and how old its last observation is."
```

---

### Task 5: Route `region` through `MarketRouter`

**Files:**
- Modify: `providers/market_router.py` (`get_macro_data`)
- Modify: `models/unified_base.py:910-937` (`InflationCalculation`, `MacroDataResult`)
- Test: `tests/test_macro_region_routing.py` (create)

**Interfaces:**
- Consumes from Tasks 2–4: `FredCpiProvider.get_inflation_data`, `FredCpiProvider.calculate_inflation`.
- Consumes from Task 1: the raising TR path.
- Produces, relied on by Task 6: `MarketRouter.get_macro_data(..., *, region: str = "tr")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_macro_region_routing.py
import inspect

import pytest

from providers.market_router import MarketRouter


def test_region_is_keyword_only():
    """A positional `region` would silently reinterpret an existing
    get_macro_data("inflation", "ufe") call as region="ufe"."""
    sig = inspect.signature(MarketRouter.get_macro_data)
    assert sig.parameters["region"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["region"].default == "tr"


@pytest.mark.asyncio
async def test_us_calculate_returns_currency_and_provenance():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="calculate", region="us",
        start_year=2010, start_month=1, end_year=2020, end_month=1,
        basket_value=100.0,
    )

    assert out["region"] == "us"
    assert out["currency"] == "USD"
    assert "FRED" in out["source"]
    assert out["series_end"] >= "2026-01"
    assert out["calculation"]["cumulative_inflation"] > 15


@pytest.mark.asyncio
async def test_eu_inflation_series_is_served():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="inflation", region="eu", limit=12,
    )

    assert out["currency"] == "EUR"
    assert len(out["inflation_data"]) == 12
    assert out["inflation_data"][-1]["rate"] is not None


@pytest.mark.asyncio
async def test_inflation_type_is_rejected_for_us_not_silently_ignored():
    """US/EU have only a headline index. A caller who asked for PPI should learn
    they did not get it, rather than receive CPI with a warning they cannot avoid."""
    router = MarketRouter()
    with pytest.raises(ValueError, match="inflation_type"):
        await router.get_macro_data(
            data_type="inflation", region="us", inflation_type="ufe",
        )


@pytest.mark.asyncio
async def test_year_before_the_series_start_raises_for_eu():
    router = MarketRouter()
    with pytest.raises(ValueError, match="1996"):
        await router.get_macro_data(
            data_type="calculate", region="eu",
            start_year=1980, start_month=1, end_year=2020, end_month=1,
            basket_value=100.0,
        )


@pytest.mark.asyncio
async def test_tr_remains_the_default_and_keeps_its_shape():
    router = MarketRouter()
    out = await router.get_macro_data(
        data_type="calculate",
        start_year=2020, start_month=1, end_year=2024, end_month=12,
        basket_value=100.0,
    )

    assert out["data_type"] == "calculate"
    assert out["inflation_type"] is None
    assert out["calculation"]["cumulative_inflation"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_macro_region_routing.py -q`
Expected: FAIL — `KeyError: 'region'` in the signature test, `TypeError: got an unexpected keyword argument 'region'` in the rest.

- [ ] **Step 3: Extend the models**

In `models/unified_base.py`, replace `InflationCalculation` and `MacroDataResult` (lines 920-937) with:

```python
class InflationCalculation(BaseModel):
    """Inflation calculation result."""
    start_period: str
    end_period: str
    initial_value: float
    final_value: float
    cumulative_inflation: float
    period_months: int
    start_index: Optional[float] = None
    end_index: Optional[float] = None
    # Named for what it is: on a non-seasonally-adjusted index, annualizing a
    # short interval annualizes seasonality along with inflation. Emitted only
    # for intervals of at least 12 months.
    annualized_compound_change: Optional[float] = None


class MacroDataResult(BaseModel):
    """Result of macro data query."""
    metadata: UnifiedMetadata
    data_type: str  # inflation, calculate
    region: str = "tr"  # tr, us, eu
    currency: Optional[str] = None  # TRY, USD, EUR
    source: Optional[str] = None  # which upstream actually answered
    series_end: Optional[str] = None  # last observed month, YYYY-MM
    inflation_type: Optional[str] = None  # tufe, ufe (TR only)
    inflation_data: Optional[List[InflationData]] = None
    calculation: Optional[InflationCalculation] = None
    warnings: Optional[List[str]] = None
```

- [ ] **Step 4: Route the region in `MarketRouter.get_macro_data`**

Change the signature (note `*` before `region`) and add the dispatch. The TR body is the one from Task 1; only the wrapper changes:

```python
    async def get_macro_data(
        self,
        data_type: str,  # inflation, calculate
        inflation_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        basket_value: float = 100.0,
        limit: Optional[int] = None,
        *,
        region: str = "tr",
    ) -> Dict[str, Any]:
        """Get macro inflation data for Turkey, the US, or the euro area.

        `region` is keyword-only on purpose: adding it positionally would
        reinterpret an existing get_macro_data("inflation", "ufe") call.
        """
        if region not in ("tr", "us", "eu"):
            raise ValueError(
                f"Unknown region '{region}'. Supported: tr, us, eu."
            )

        if region in ("us", "eu"):
            return await self._get_macro_data_global(
                region=region,
                data_type=data_type,
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value,
                limit=limit,
            )

        return await self._get_macro_data_tr(
            data_type=data_type,
            inflation_type=inflation_type or "tufe",
            start_date=start_date,
            end_date=end_date,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            basket_value=basket_value,
            limit=limit,
        )
```

Move the existing TR body (as fixed in Task 1) into `_get_macro_data_tr`, keeping its return statement but setting the new fields:

```python
    async def _get_macro_data_tr(
        self,
        data_type: str,
        inflation_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
        start_year: Optional[int],
        start_month: Optional[int],
        end_year: Optional[int],
        end_month: Optional[int],
        basket_value: float,
        limit: Optional[int],
    ) -> Dict[str, Any]:
        # ... the body from Task 1, unchanged, producing `inflation_data` / `calculation` ...

        return {
            "metadata": self._create_metadata(MarketType.FX, [data_type], "tcmb"),
            "data_type": data_type,
            "region": "tr",
            "currency": "TRY",
            "source": "TCMB",
            "inflation_type": inflation_type if data_type == "inflation" else None,
            "inflation_data": inflation_data,
            "calculation": calculation,
        }
```

Add the global path:

```python
    async def _get_macro_data_global(
        self,
        region: str,
        data_type: str,
        inflation_type: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        start_year: Optional[int],
        start_month: Optional[int],
        end_year: Optional[int],
        end_month: Optional[int],
        basket_value: float,
        limit: Optional[int],
    ) -> Dict[str, Any]:
        from providers.fred_cpi_provider import FredCpiProvider

        if not hasattr(self, "_fred_provider"):
            self._fred_provider = FredCpiProvider()
        p = self._fred_provider

        # Rejected, not ignored: US/EU publish only a headline index, and a caller
        # who asked for PPI should learn they did not get it.
        if inflation_type is not None:
            raise ValueError(
                f"inflation_type is not supported for region='{region}': only a "
                f"headline consumer price index is published "
                f"({'CPI-U' if region == 'us' else 'HICP'}). Omit the parameter, "
                f"or use region='tr' for the TÜFE/ÜFE distinction."
            )

        spec = FredCpiProvider.SERIES[region]
        for year in (start_year, end_year):
            if year is not None and year < spec.start_year:
                raise ValueError(
                    f"The {region.upper()} series starts in {spec.start_year}; "
                    f"{year} is before it."
                )

        if data_type == "inflation":
            payload = await p.get_inflation_data(
                region=region,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            payload["calculation"] = None
        elif data_type == "calculate":
            if not all([start_year, start_month, end_year, end_month]):
                raise ValueError(
                    "calculate mode requires start_year, start_month, end_year "
                    "and end_month."
                )
            payload = await p.calculate_inflation(
                region=region,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value,
            )
            payload["inflation_data"] = None
        else:
            raise ValueError(
                f"Unknown data_type '{data_type}'. Supported: inflation, calculate."
            )

        payload["metadata"] = self._create_metadata(
            MarketType.FX, [data_type], payload["source"]
        )
        payload["data_type"] = data_type
        payload["inflation_type"] = None
        return payload
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_macro_region_routing.py tests/test_macro_tr_errors.py -q`
Expected: PASS (8 passed)

- [ ] **Step 6: Commit**

```bash
git add providers/market_router.py models/unified_base.py tests/test_macro_region_routing.py
git commit -m "feat(macro): route get_macro_data by region (tr/us/eu)

region is keyword-only: adding it positionally would reinterpret an existing
get_macro_data(\"inflation\", \"ufe\") call as region=\"ufe\". inflation_type is
rejected for us/eu rather than ignored with a warning the caller cannot avoid."
```

---

### Task 6: Expose `region` on the tool, and document it

**Files:**
- Modify: `unified_mcp_server.py:1643-1740` (`get_macro_data`)
- Modify: `CLAUDE.md` (the `get_macro_data` row and the Data Sources section)
- Test: `tests/test_macro_tool_surface.py` (create)

**Interfaces:**
- Consumes from Task 5: `MarketRouter.get_macro_data(..., *, region="tr")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_macro_tool_surface.py
import pytest
from fastmcp import Client

from unified_mcp_server import app


@pytest.mark.asyncio
async def test_us_calculation_renders_with_currency_and_source():
    async with Client(app) as client:
        result = await client.call_tool("get_macro_data", {
            "data_type": "calculate",
            "region": "us",
            "start_year": 2010, "start_month": 1,
            "end_year": 2020, "end_month": 1,
            "basket_value": 100.0,
        })

    text = result[0].text
    assert "USD" in text
    assert "FRED" in text
    assert "cumulative_inflation" in text


@pytest.mark.asyncio
async def test_tr_default_still_works_without_region():
    async with Client(app) as client:
        result = await client.call_tool("get_macro_data", {
            "data_type": "calculate",
            "start_year": 2020, "start_month": 1,
            "end_year": 2024, "end_month": 12,
        })

    assert "TRY" in result[0].text


@pytest.mark.asyncio
async def test_failed_tr_call_surfaces_an_error_not_zero_percent():
    """End-to-end guard for the bug fixed in Task 1."""
    async with Client(app) as client:
        with pytest.raises(Exception) as exc:
            await client.call_tool("get_macro_data", {
                "data_type": "calculate",
                "start_year": 2024, "start_month": 6,
                "end_year": 2020, "end_month": 1,
            })

    assert "0.0" not in str(exc.value) or "failed" in str(exc.value).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_macro_tool_surface.py -q`
Expected: FAIL — the tool rejects the unknown `region` argument.

- [ ] **Step 3: Add the parameter to the tool**

In `unified_mcp_server.py`, next to `MacroDataTypeLiteral`, add:

```python
MacroRegionLiteral = Literal["tr", "us", "eu"]
```

Update the tool decorator description:

```python
@app.tool(
    name="get_macro_data",
    title="Macro Inflation Data",
    description=(
        "Inflation data and cumulative purchasing-power calculation for Turkey "
        "(TÜFE/ÜFE), the US (CPI-U), or the euro area (HICP)."
    ),
    tags={"macro", "inflation"},
    output_schema=None,
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
```

Add the `region` parameter after `data_type`, change `inflation_type`'s default to `None`, and relax the year bounds:

```python
    region: Annotated[MacroRegionLiteral, Field(
        description=(
            "Region: 'tr' (TÜFE/ÜFE, TRY), 'us' (CPI-U, USD), 'eu' (HICP, EUR). "
            "US and EU publish a headline index only, so inflation_type does not "
            "apply there."
        ),
        default="tr",
        examples=["tr", "us", "eu"]
    )] = "tr",
    inflation_type: Annotated[Optional[InflationTypeLiteral], Field(
        description=(
            "TR only: tufe (CPI) or ufe (PPI). Defaults to tufe for region='tr'; "
            "supplying it with region='us'/'eu' is an error."
        ),
        default=None
    )] = None,
```

and, on `start_year` / `end_year`, replace `ge=2000, le=2030` with `ge=1913` (the US series starts in 1913; the per-region floor and the "not past the latest observation" ceiling are enforced in the router, since a hard-coded year ceiling ages badly).

Update the docstring's examples:

```python
    """
    Get macro economic inflation data.

    Modes:
    1. inflation: historical rates (TR: TÜFE/ÜFE, US: CPI-U, EU: HICP)
    2. calculate: cumulative inflation and purchasing power between two months

    Index values are monthly averages, not prices on a specific day.

    Examples:
    - get_macro_data("inflation") → Latest TÜFE rates
    - get_macro_data("inflation", inflation_type="ufe", limit=24) → Last 24 months ÜFE
    - get_macro_data("calculate", start_year=2020, start_month=1, end_year=2024, end_month=12)
    - get_macro_data("calculate", region="us", start_year=2010, start_month=1,
                     end_year=2026, end_month=5) → $100 in 2010-01 is $154.66 in 2026-05
    - get_macro_data("inflation", region="eu", limit=12) → Last 12 months euro-area HICP
    """
```

and pass it through:

```python
        return shape(await market_router.get_macro_data(
            data_type=data_type,
            inflation_type=inflation_type,
            start_date=start_date,
            end_date=end_date,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            basket_value=basket_value,
            limit=limit,
            region=region,
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_macro_tool_surface.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the whole suite and confirm the tool count is still 28**

Run: `uv run python -m pytest tests/ -q --ignore=tests/adhoc`
Expected: all pass.

Run: `uv run python -c "
import asyncio
from unified_mcp_server import app
tools = asyncio.run(app.get_tools())
print(len(tools), 'tools')
"`
Expected: `28 tools`

- [ ] **Step 6: Update CLAUDE.md**

In the FX & Macro tools table, replace the `get_macro_data` row with:

```markdown
| `get_macro_data` | Inflation data + purchasing-power calculator. `region`: tr (TÜFE/ÜFE), us (CPI-U), eu (HICP) |
```

Add to the Data Sources section, after the World Bank entry:

```markdown
### FRED (US CPI, Euro-area HICP)
- **Endpoint**: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>` — keyless CSV export
- **US**: `CPIAUCNS` (CPI-U, **not** seasonally adjusted; `CPIAUCSL` is the SA variant and is the wrong series for a purchasing-power calculation), 1913→present
- **EU**: `CP0000EZCCM086NEST` (HICP, **changing composition**: EA11 → … → EA19 → EA20), 1996→present
  - ⚠️ **Not `CP0000EZ19M086NEST`.** That series is titled "Euro Area (19 Countries)" and is still
    updated — which makes it look healthy — but it measures a frozen geography that excludes Croatia
    (euro member since 2023). It drifts from canonical EA20 monotonically: 0.004% in 2020, 0.065% by
    end-2025. The changing-composition series tracks EA20 to 0.003%.
- **Fallbacks**: US → BLS public API v1 (`CUUR0000SA0`, ~3 years only, 25 req/day/IP);
  EU → Eurostat `prc_hicp_midx` (`geo=EA`, the changing-composition cut).
  - ⚠️ **Eurostat lags.** Its dissemination API ended at 2025-12 while FRED carried the same data
    through 2026-05. A fallback that quietly answers with a six-month-old index is a silent-wrong
    failure, so responses always carry `source` and `series_end`.
- **Attribution**: FRED marks the Eurostat-derived series as EU copyright; the euro-area response
  names Eurostat as the originating source.
```

Add to "Common Issues and Solutions", after #7:

```markdown
### 8. A frozen upstream series can look perfectly healthy
`CP0000EZ19M086NEST` is still updated every month, so every liveness check passes — but it measures
euro-area-19, a geography that stopped being the euro area in 2023. Freshness is not correctness.
When a series name encodes a *composition* (EA19, EA20, EU27), verify that the composition is the one
you mean, not just that the data is recent.
```

- [ ] **Step 7: Commit**

```bash
git add unified_mcp_server.py CLAUDE.md tests/test_macro_tool_surface.py
git commit -m "feat(macro): expose region on get_macro_data for USD/EUR inflation

get_macro_data now answers 'what is \$100 from 2010 worth today' for the US and
the euro area, not just Turkey. Tool count stays at 28."
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| TR swallowed-error bug (0% on failure) | 1 |
| `CPIAUCNS` / `CP0000EZCCM086NEST` series choice | 2 |
| Validated parsing (HTML body, renamed column, truncation, non-finite) | 2 |
| Provenance (`source`, `series_end`) and freshness window | 2, 5 |
| Single-flight cache protecting the BLS quota | 2 |
| `rate` = YoY, `change` = MoM | 3 |
| Exact endpoints, no neighbour substitution, no gaps | 3 |
| `annualized_compound_change` gated to ≥ 12 months + seasonality warning | 3 |
| Monthly-average semantics stated in the response | 3 |
| Whole-series fallback, never merged | 4 |
| Degraded fallback must raise rather than truncate | 4 |
| Stale fallback surfaced, not hidden | 4 |
| `region` keyword-only; per-region year bounds; `basket_value > 0` | 1, 5 |
| `inflation_type` rejected for us/eu | 5 |
| Model fields; TR fills `start_index`/`end_index`/annualized | 1, 5 |
| Tool surface, `le=2030` removed, docs | 6 |
| Attribution for Eurostat via FRED | 6 (CLAUDE.md) |
| Golden values $154.66 / €145.01 | 3 (step 5) |
| Live smoke: ≥300 points, increasing months, fresh | 2 (step 5), 6 |

No gaps.

**Type consistency:** `IndexSeries`, `SeriesSpec`, `parse_fred_csv`, `validate_series`, `months_between`, `parse_bls_json`, `parse_eurostat_json`, `get_index_series`, `get_inflation_data`, `calculate_inflation`, `_envelope`, `_fetch_primary`, `_fetch_fallback` are named identically everywhere they appear. `annualized_compound_change` is used consistently (never "average annual inflation") in the provider, the model, and the router.
