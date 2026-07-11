# USD / EUR Inflation Calculator

**Date:** 2026-07-11
**Status:** Approved, not yet implemented
**Scope:** Extend `get_macro_data` so it serves US CPI and Euro-area HICP alongside Turkish TÜFE/ÜFE, including the purchasing-power calculator.

## Goal

Today `get_macro_data` answers "100 TL in 2010 is worth how much today?" using TCMB's official
calculator. The same question for dollars and euros has no answer in this server. This adds it:
US CPI-U and Euro-area HICP, both as a rate series and as a cumulative purchasing-power
calculation.

Explicitly **out of scope**: FX-adjusted Turkish inflation ("dolar bazında TR enflasyonu"), and
multi-region side-by-side comparison in a single call. Both were considered and deferred.

## Data sources

FRED's keyless CSV export is the primary source for both series. Verified live on 2026-07-11:

| Region | Series | Coverage | Note |
|--------|--------|----------|------|
| `us` | `CPIAUCNS` | 1913-01 → 2026-05 | CPI-U, **not** seasonally adjusted. `CPIAUCSL` (the SA variant) is the wrong series for a purchasing-power calculation. |
| `eu` | `CP0000EZ19M086NEST` | 1996-12 → 2026-05 | Euro-area HICP, all items. |

`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>` → `observation_date,<SERIES_ID>`
CSV, missing values encoded as `.`.

FRED's euro series was cross-checked against Eurostat's `prc_hicp_midx` API. The base years differ
(FRED is rebased) but the ratios agree: 2010-01 → 2025-12 is 1.4142 via FRED and 1.4149 via
Eurostat, a 0.05% difference. Since the calculator only ever consumes *ratios*, the differing base
is irrelevant. FRED is also more current — it carried through 2026-05 while Eurostat's public
dissemination stopped at 2025-12.

**Fallbacks** (both keyless, both verified returning 200):
- `us` → BLS public API v1, series `CUUR0000SA0`. Capped at 25 requests/day/IP and returns only the
  last 3 years, so it is a degraded-but-alive path, not an equal substitute.
- `eu` → Eurostat `prc_hicp_midx` (JSON-stat: `geo=EA`, `coicop=CP00`, `unit=I15`).

Two rules keep the fallbacks from producing quietly wrong numbers:

1. **A fallback replaces the whole series; it never merges into one.** FRED's euro series and
   Eurostat's use different base years, so a dict holding months from both would yield ratios that
   are silently garbage. The cache entry records which source produced it.
2. **The BLS fallback only spans ~3 years, and a calculation reaching past that must fail, not
   truncate.** If the requested start month is missing from the fallback series, the provider raises
   and says the source is degraded — computing "$100 in 2010" off a series that begins in 2023 would
   return a confident wrong answer, which is worse than an error.

The fallbacks are deliberate, not speculative. This repository has already been burned by an
upstream feed that died silently — borsapy's economic-calendar endpoint began returning an empty
DataFrame for every query, and the failure was invisible because nothing raised. FRED's CSV export
is a graph-export URL rather than a contract-backed API, so it deserves a second leg to stand on.

## Components

### `providers/fred_cpi_provider.py` (new)

```python
SERIES = {
    "us": ("CPIAUCNS",           "US CPI-U, NSA — BLS via FRED",       1913),
    "eu": ("CP0000EZ19M086NEST", "Euro area HICP — Eurostat via FRED", 1997),
}
```

- `_get_index(region) -> dict[str, float]` — keyed `"YYYY-MM"` → index level. Fetches the CSV, drops
  `.` rows, caches for 6 hours (the underlying data is monthly, so this is generous). On HTTP error
  or an empty parse it tries the region's fallback; if that also yields nothing it raises
  `DataNotAvailableError`. It never returns an empty dict, because an empty-but-successful response
  reads to an LLM as "this exists and has no data" — a much stronger and, here, false claim.
- `get_inflation_data(region, start_date, end_date, limit)` — derives month-over-month % and
  year-over-year % from the index, applies the date filter, then the limit.
- `calculate_inflation(region, start_year, start_month, end_year, end_month, basket_value)` —
  `ratio = index[end] / index[start]`, from which it reports the final basket value, cumulative
  inflation %, average annual inflation (`ratio ** (12 / months) - 1`), and **both index levels it
  used**, so a caller can verify the arithmetic rather than trust it.

Requested months outside the series range raise a `ValueError` that names the available range.

### `providers/market_router.py`

`get_macro_data` gains `region: str = "tr"`.

- `region == "tr"` dispatches to the existing TCMB path, unchanged.
- `region in ("us", "eu")` dispatches to `FredCpiProvider`.
- `inflation_type` (tufe/ufe) is meaningless for US/EU, where only a headline index exists. Passing
  it is not an error; it is ignored and a `warnings` entry says so, matching the existing
  ignored-flag convention in `get_fund_data` and `get_technical_analysis`.

Year bounds are validated per region — TR ≥ 1982, US ≥ 1913, EU ≥ 1997 — because a single global
bound would either lock US callers out of 70 years of history or let EU callers ask for data that
does not exist.

### `models/unified_base.py`

- `MacroDataResult` gains `region: str = "tr"`, `currency: Optional[str]` (TRY/USD/EUR), and
  `warnings: Optional[List[str]]`.
- `InflationCalculation` gains `avg_annual_inflation`, `start_index`, `end_index`, all optional. The
  TR path fills them too, from TCMB's `ilkYilTufe` / `sonYilTufe`, so both regions return the same
  shape.

### `unified_mcp_server.py`

`MacroRegionLiteral = Literal["tr", "us", "eu"]`, exposed as `region` with default `"tr"`. The
`start_year` / `end_year` lower bound drops from 2000 to 1913; the meaningful per-region check lives
in the router. Tool description becomes: Turkish TÜFE/ÜFE, US CPI, or Euro-area HICP inflation data
and cumulative purchasing-power calculation.

Tool count stays at 28.

## Data flow

```
get_macro_data(data_type, region, ...)
  └─ MarketRouter.get_macro_data
       ├─ region=tr  → TcmbProvider          (TCMB calculator API / scraped tables)
       └─ region=us|eu → FredCpiProvider
                           ├─ FRED CSV  (primary)
                           └─ BLS v1 | Eurostat  (fallback)
```

## Error handling

Providers raise; the tool layer converts via `classify_tool_error`. No path returns a successful
response with an empty body. The failure modes that must raise, not degrade:

- FRED and the fallback both unreachable → `DataNotAvailableError`.
- Requested period outside the series → `ValueError` naming the available range.
- Requested period outside a *degraded fallback* series (e.g. BLS's 3-year window) →
  `DataNotAvailableError` stating that the primary source is down and the fallback does not reach
  that far back.
- `start >= end` → `ValueError`.

## Backward compatibility

Every existing call omits `region`, gets `"tr"`, and hits the untouched TCMB path. The added model
fields are optional. No existing response field changes type or disappears.

## Testing

`tests/test_macro_global_inflation.py`:

- **Ratio math** against a fixed fixture, with golden values computed from real data on 2026-07-11:
  US 2010-01 → 2026-05 turns $100 into **$154.66** (cumulative 54.7%); EUR over the same window turns
  €100 into **€144.91** (cumulative 44.9%).
- **Parser**: `.` rows are dropped rather than crashing or becoming 0.0.
- **Validation**: out-of-range year, inverted date range, and unknown region each raise, and the
  message names the valid range.
- **Regression**: `region` omitted still routes to TCMB and returns the pre-existing shape.
- **Live smoke**: each series parses to ≥ 300 points, dates are strictly increasing, and the latest
  observation is within the last 4 months — this is what catches a silently-dead upstream.
