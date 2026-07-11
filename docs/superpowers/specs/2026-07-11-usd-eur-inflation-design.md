# USD / EUR Inflation Calculator

**Date:** 2026-07-11
**Status:** Approved after adversarial review (Codex `gpt-5.6-sol`), not yet implemented
**Scope:** Extend `get_macro_data` so it serves US CPI and euro-area HICP alongside Turkish
TÜFE/ÜFE, including the purchasing-power calculator — and fix a live silent-failure bug in the
existing TR path that this work would otherwise inherit.

## Goal

Today `get_macro_data` answers "100 TL in 2010 is worth how much today?" using TCMB's official
calculator. The same question for dollars and euros has no answer in this server. This adds it:
US CPI-U and euro-area HICP, both as a rate series and as a cumulative purchasing-power
calculation.

Explicitly **out of scope**: FX-adjusted Turkish inflation ("dolar bazında TR enflasyonu"), and
multi-region side-by-side comparison in a single call. Both were considered and deferred.

## Prerequisite: the TR path lies when TCMB fails

`TcmbProvider.calculate_inflation()` catches every exception and returns an `EnflasyonHesaplamaSonucu`
with `yeni_sepet_degeri=""` and `error_message` set. `MarketRouter.get_macro_data()` never reads
`error_message`; it checks `hasattr(result, 'yeni_sepet_degeri')`, which the error object satisfies.
The empty string is falsy, so `final_value` falls back to the input basket and the tool returns:

```
calculation: {initial_value: 100.0, final_value: 100.0, cumulative_inflation: 0.0, period_months: 0}
```

Reproduced live on 2026-07-11 by passing an inverted date range. **A failed call reports 0%
inflation as a success.** An LLM reading that tells the user prices did not move. The inflation
series path has the same hole in a milder form: on failure it returns `inflation_data: null` inside
a successful response, which reads as "this exists and has no data".

This must be fixed as part of this work, not after it. The spec below claims providers raise and
the tool layer classifies; leaving the TR path as-is would make that claim false for two of the
four code paths the tool has.

**Fix:** the router inspects `error_message` and empty results, and raises `DataNotAvailableError`.
Errors surface through `classify_tool_error`, per CLAUDE.md #7.

## Data sources

FRED's keyless CSV export is the primary source for both series
(`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>` → `observation_date,<SERIES_ID>`,
missing values encoded as `.`). Verified live on 2026-07-11:

| Region | Series | Coverage | Note |
|--------|--------|----------|------|
| `us` | `CPIAUCNS` | 1913-01 → 2026-05 | CPI-U, **not** seasonally adjusted. `CPIAUCSL` (the SA variant) is the wrong series for a purchasing-power calculation. |
| `eu` | `CP0000EZCCM086NEST` | 1996-01 → 2026-05 | Euro-area HICP, **changing composition** (EA11 → … → EA19 → EA20). |

### Why changing composition, and not EA19

The obvious series, `CP0000EZ19M086NEST`, is titled "Euro Area (19 Countries)". It is still being
updated, which makes it look healthy, but it measures a **frozen** 19-country geography — Croatia
joined the euro in 2023 and is not in it. The drift against canonical EA20 is small but grows
monotonically. Measured against Eurostat's EA20 as reference, for the ratio 2015-01 → 2025-12:

| Series | Ratio | Deviation from EA20 | Latest month |
|---|---|---|---|
| Eurostat EA20 (reference) | 1.31891 | — | 2025-12 |
| **FRED `CP0000EZCCM086NEST`** (chosen) | 1.31887 | **0.003%** | 2026-05 |
| FRED `CP00MI15EA20M086NEST` (fixed EA20) | 1.31887 | 0.003% | 2026-05 |
| FRED `CP0000EZ19M086NEST` (rejected) | 1.31805 | 0.065% | 2026-05 |

Changing composition wins over fixed EA20 because it matches the ordinary meaning of "euro-area
inflation over time" and reaches back to 1996-01 rather than 1999-12.

Base years differ across all of these (FRED rebases), which does not matter: the calculator consumes
only *ratios*. That is exactly why a series must never be assembled from two sources — see below.

**Golden value, recomputed on the corrected series:** €100 (2010-01) → **€145.01** (2026-05),
cumulative 45.0%. The pre-review figure of €144.91 came from the wrong EA19 series.

### Fallbacks

- `us` → BLS public API v1, series `CUUR0000SA0`. Capped at 25 requests/day/IP, returns only the
  last 3 years. A degraded-but-alive path, not an equal substitute.
- `eu` → Eurostat `prc_hicp_midx`, `geo=EA`, `coicop=CP00`, `unit=I15`. Eurostat's `EA` is the
  changing-composition cut, so it measures the same geography as the chosen FRED series — verified,
  the two agree within 0.011% on ratios from 2010-01 to 2015/2020/2023/2025.

Three rules keep the fallbacks from producing quietly wrong numbers:

1. **A fallback replaces the whole series; it never merges into one.** The sources use different base
   years, so a dict holding months from both would yield ratios that are silently garbage. The cache
   entry records which source produced it.
2. **A calculation reaching past a degraded fallback's window must fail, not truncate.** BLS spans
   ~3 years. Computing "$100 in 2010" off a series that begins in 2023 would return a confident wrong
   answer, which is worse than an error.
3. **Fallbacks can be stale, and staleness must be visible.** Eurostat's dissemination API currently
   ends at **2025-12** while FRED carries the same data through 2026-05 — a six-month lag, confirmed
   across both `I15` and `I05` units (it is a publication lag, not a rebasing). A fallback that
   quietly answers with a six-month-old index is the same silent-wrong failure, just relocated.

## Components

### `providers/fred_cpi_provider.py` (new)

```python
SERIES = {
    "us": ("CPIAUCNS",           "US CPI-U, NSA — BLS via FRED",                   1913),
    "eu": ("CP0000EZCCM086NEST", "Euro area HICP, changing composition — "
                                 "Eurostat via FRED",                              1996),
}
```

`_get_index(region) -> IndexSeries` returns the parsed series **plus its provenance**: source name,
first month, last month. Keyed `"YYYY-MM"` → index level. Cached 6 hours behind a per-region
single-flight lock, so a cold start with concurrent requests makes one upstream call rather than N —
which also protects the BLS anonymous quota.

Parsing is validated, not merely attempted. HTTP 200 with a garbage body is the failure mode this
repo keeps meeting, so a series is rejected unless:

- the expected column header for the series id is present;
- there are at least 200 observations, and the first month is within one year of the series' known
  start (so a truncated feed cannot pass as a full one);
- months are unique, parseable, and strictly increasing after sorting;
- every level is finite and positive;
- the latest observation is within a freshness window (~70 days). Outside it, the series is still
  served — CPI genuinely lags — but the response carries a warning naming the last observed month.

If validation fails, the region's fallback is tried. If that also fails validation, the provider
raises `DataNotAvailableError`. It never returns an empty or partial series.

`get_inflation_data(region, start_date, end_date, limit)` derives, per month, `change` =
month-over-month % and `rate` = year-over-year %. These field names are inherited from the TR path;
the spec pins their meaning here because they are otherwise ambiguous.

`calculate_inflation(region, start_year, start_month, end_year, end_month, basket_value)`:

- Both endpoints must be **present exactly** in the series. A missing month raises; the nearest
  available month is never silently substituted.
- No month may be missing *inside* the interval.
- `ratio = index[end] / index[start]` → final basket value, cumulative %, and both index levels, so
  a caller can check the arithmetic instead of trusting it.
- `months` = the count of month-to-month intervals (2010-01 → 2011-01 is 12).
- The annualized figure is named **`annualized_compound_change`**, not "average annual inflation".
  On an NSA index it annualizes seasonal movement along with genuine inflation, so it is emitted
  only for intervals of at least 12 months; shorter intervals get `null` plus a warning. Where the
  start and end calendar months differ, a warning notes that the comparison carries seasonality.
- The response states that endpoints are **monthly averages**, not prices on a given day.

### `providers/market_router.py`

`get_macro_data` gains `region` as a **keyword-only** parameter defaulting to `"tr"`, appended after
the existing parameters. Adding it positionally ahead of `inflation_type` would silently reinterpret
an existing `get_macro_data("inflation", "ufe")` call.

- `region == "tr"` → the TCMB path, now with the swallowed-error fix above.
- `region in ("us", "eu")` → `FredCpiProvider`.
- `inflation_type` defaults to `None` and resolves to `"tufe"` only for `region="tr"`. For US/EU an
  explicitly supplied value is **rejected with an error**, not ignored with a warning: US and EU have
  only a headline index, and a caller who asked for PPI should learn they did not get it. (The
  previous design defaulted it to `"tufe"` and warned on every US/EU call — a warning the caller
  could not avoid, which trains readers to ignore warnings.)

Per-region bounds: TR ≥ 1982, US ≥ 1913, EU ≥ 1996, and no endpoint past the latest observation in
the series. Both the calculator's year params and `start_date` / `end_date` are checked.
`basket_value` must be **> 0**; zero makes a purchasing-power result meaningless.

### `models/unified_base.py`

- `MacroDataResult` gains `region`, `currency` (TRY/USD/EUR), `source`, `series_end` (last observed
  month), and `warnings`. Source and series_end are always populated, so staleness and provenance are
  observable facts rather than assumptions.
- `InflationCalculation` gains `annualized_compound_change`, `start_index`, `end_index`, all optional.
  The TR path fills them from TCMB's `ortalama_yillik_enflasyon`, `ilk_yil_tufe`, `son_yil_tufe`,
  which are **localized strings** and need the existing Turkish-number conversion; the annual figure
  is a percentage while the index fields are levels. TR error objects must raise, not become
  zero-valued calculations.

The markdown renderer already hoists a top-level `warnings` list into `> Not:` lines (verified,
`markdown_renderer.py:60`), and `strip_nulls` drops the new optional fields on paths that do not set
them. Rendered TR output gains `region`/`currency`/`source` lines, so the regression test asserts on
rendered text, not just the router dict.

### `unified_mcp_server.py`

`MacroRegionLiteral = Literal["tr", "us", "eu"]`, exposed as `region`, default `"tr"`. The
`start_year`/`end_year` lower bound drops from 2000 to 1913; the hard-coded `le=2030` upper bound is
replaced by a data-availability check in the router, since a literal year ceiling ages badly. The
tool description states the monthly-average endpoint semantics and that US/EU offer a headline index
only.

Tool count stays at 28.

## Data flow

```
get_macro_data(data_type, *, region, ...)
  └─ MarketRouter.get_macro_data
       ├─ region=tr    → TcmbProvider      (TCMB calculator API / scraped tables)
       │                   └─ error_message set or empty → raise DataNotAvailableError
       └─ region=us|eu → FredCpiProvider
                           ├─ FRED CSV (primary)            ─┐
                           └─ BLS v1 | Eurostat (fallback)  ─┴─ validated, whole-series, provenance
```

## Error handling

Providers raise; the tool layer converts via `classify_tool_error`. No path returns a successful
response with an empty or fabricated body.

- FRED and the fallback both unreachable or failing validation → `DataNotAvailableError`.
- Requested period outside the series → `ValueError` naming the available range.
- Requested period outside a *degraded fallback* series → `DataNotAvailableError` stating the primary
  source is down and the fallback does not reach that far back.
- A month missing at an endpoint or inside the interval → raise. Never substitute a neighbour.
- `start >= end`, or `basket_value <= 0` → `ValueError`.
- TR: TCMB error or empty result → `DataNotAvailableError` (this is the bug fix).

## Data revisions

CPI and HICP histories get revised, and FRED rebases. Two identical requests either side of a cache
expiry can therefore differ slightly. The response's `source` and `series_end` make the vintage
visible; the spec does not attempt to pin a vintage.

Attribution: FRED marks the Eurostat-derived series as European Union copyright and asks that the
source be credited. The euro-area response names Eurostat as the originating source.

## Backward compatibility

Existing calls omit `region`, get `"tr"`, and keep working — with one deliberate behaviour change:
where the TR path previously returned a fake 0% calculation or a null series on failure, it now
raises. That is the point of the fix, and it is called out here so it is not mistaken for a
regression.

`region` is keyword-only, so positional calls are unaffected. Added model fields are optional.

## Testing

`tests/test_macro_global_inflation.py`:

- **Golden ratios**, from real data on 2026-07-11: US 2010-01 → 2026-05 turns $100 into **$154.66**
  (cumulative 54.7%); EUR over the same window turns €100 into **€145.01** (cumulative 45.0%).
- **Parser rejection**, each asserting a raise rather than a quiet pass: HTTP 200 with an HTML error
  body; a renamed/missing column; a series truncated to a handful of rows; duplicate months; a gap
  inside the requested interval; a non-finite or negative level.
- **Freshness**: a series whose last observation is months old is served *with* a warning naming the
  month, not silently.
- **Fallback**: activation on primary failure, provenance reported in the response, and a request
  reaching past the BLS 3-year window raising instead of computing off a truncated series.
- **Fallback equivalence**: FRED and Eurostat overlapping months agree on ratios after normalization
  (not a single hand-picked interval).
- **Endpoints**: a month absent from the series raises rather than snapping to a neighbour.
- **Annualization**: emitted at ≥ 12 months, `null` + warning below that, seasonality warning when
  the start and end calendar months differ.
- **Validation**: out-of-range year per region, inverted range, `basket_value=0`, `inflation_type`
  supplied with `region="us"` — each raises with an actionable message.
- **TR regression**: `region` omitted still routes to TCMB and returns the pre-existing shape,
  asserted on the *rendered markdown* as well as the router dict; and a TCMB failure now raises
  instead of reporting 0%.
- **Live smoke**: each series parses to ≥ 300 points, months strictly increasing, latest observation
  within the freshness window — this is what catches a silently-dead upstream.
