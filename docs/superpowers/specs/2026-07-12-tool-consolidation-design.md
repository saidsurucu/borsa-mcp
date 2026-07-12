# Tool Consolidation & Contract Standardization (v1.0.0)

**Date**: 2026-07-12
**Status**: Approved design, not yet implemented
**Scope**: 28 tools → 18 tools; single parameter contract; new `compare_assets` tool

---

## Problem

Two observed pains, in the user's words:

1. **Context cost** — 28 tool schemas sit in every request's context.
2. **Wrong tool / long call chains** — answering "ASELS mi altın mı?" takes ~6 tool calls
   plus arithmetic the model performs itself, across mismatched date windows.

## What the measurements say

The 28 schemas cost **27,320 characters ≈ 7,600 tokens** — about 4% of a 200k window.
The cost is concentrated, not spread across tool count:

| | chars | share |
|---|---|---|
| `get_evds_data` alone | 4,860 | 18% |
| Largest 6 tools | 12,800 | 47% |
| Smallest 14 tools | ~6,000 | 22% |

**Merging tools does not delete parameters.** EVDS's 4.2k of parameter documentation
still has to live inside whatever tool absorbs it. A 28→5 mega-tool redesign was estimated
at ~20-22k chars — a ~1,500-2,000 token saving, about 1% of context — while introducing a
new error surface (per-mode parameter matrices) that the model must navigate without the
recoverable feedback of a named tool list.

So tool count is not the lever for pain (1). Schema diet is. And pain (2) is solved by a
consistent contract plus `compare_assets`, both of which are independent of tool count.

The consolidation below is therefore justified on **selection-surface clarity**, not on
token savings. Every merge answers "these ask the same question"; none exist to hit a number.

---

## 1. Tool map (28 → 18)

### Price data (4)

| Tool | Absorbs | Rationale |
|---|---|---|
| `get_quote` | `get_quick_info`, `get_fx_data`(current), `get_crypto_market`(ticker) | All ask "what is it worth now". Equities return P/E, P/B, 52w; FX returns bid/ask; crypto returns bid/ask/24h. Same skeleton. Multi-symbol in every market. |
| `get_historical_data` | `get_fx_data`(historical), `get_crypto_market`(ohlc, kline), index history | All OHLCV. `compare_assets` sits directly on top of this. |
| `get_technical_analysis` | `get_pivot_points` | Pivots are an indicator. Separate tool was a historical accident. |
| `get_crypto_market` | *(narrowed to `orderbook`, `trades`, `exchange_info`)* | Ticker and OHLC move out; what remains is exchange microstructure, which genuinely is crypto-only. |

### Company research (5)

| Tool | Absorbs | Rationale |
|---|---|---|
| `get_profile` | `get_index_data` (components, via `market="index"`) | An index's "profile" is its constituents. |
| `get_financial_statements` | `get_financial_ratios` (via `include_ratios`) | Same İş Yatırım source, same period parameters. |
| `get_analyst_data` | `get_earnings` | Both are "what does the street think / when do results land": ratings, price targets, EPS estimates, earnings calendar. Same yfinance source, same multi-ticker semantics. |
| `get_corporate_actions` | `get_dividends` | Both are "what did the company distribute or issue". BIST corporate actions already carry dividend history. |
| `get_news` | — | |

### Screening (3)

| Tool | Absorbs | Rationale |
|---|---|---|
| `screen` | `screen_securities`, `screen_funds`, `get_screener_help` | `market: bist \| us \| fund`. The filter vocabulary already varied by market; `help=true` returns the presets and filters **for that market**, so help becomes scope-aware instead of a separate tool. |
| `scan_stocks` | `get_scanner_help` (via `help=true`) | |
| `get_sector_comparison` | — | Symbol-anchored; not a screen. |

### Macro (3)

| Tool | Absorbs | Rationale |
|---|---|---|
| `get_macro_data` | `get_bond_yields` (via `data_type="bonds"`) | The bond schema is 292 chars; it does not earn a tool slot. |
| `get_evds_data` | — *(schema diet: 4,860 → target ~2,000 chars)* | Stays separate: different source, key-gated, very large. |
| `get_economic_calendar` | — | |

### Other (3)

| Tool | Absorbs |
|---|---|
| `search_symbol` | — (entry point) |
| `get_fund_data` | `get_regulations` (via `data_type="regulations"`) |
| `compare_assets` | **NEW** |

**Estimated schema cost after consolidation + EVDS diet: ~5,000 tokens** (from ~7,600).

### Merges flagged as debatable

- **`get_analyst_data` + `get_earnings`** — is a price target the same tool as an earnings
  date? Judged yes (both are forward-looking street consensus from one source). Split if it
  reads as forced in practice.
- **`screen` carrying three filter vocabularies** (BIST presets, yfscreen filters, TEFAS
  categories). `help=true` keeps it navigable, but this is where the schema can bloat.
  Watch its character count.

---

## 2. Standard contract

Binds all 18 tools.

### 2.1 One `market` vocabulary

`bist | us | crypto | fx | fund | index`

Today's `crypto_tr` / `crypto_global` encode an *exchange*, not a market. They collapse to
`market="crypto"` plus `exchange: btcturk | coinbase`, inferred from the symbol suffix
(`BTCTRY` → btcturk, `BTC-USD` → coinbase) and overridable.

The `Literal["bist","us"]` that appears in eleven tools today is replaced by the single enum.
Tools that support only a subset keep the **same enum type** and declare the subset in the
field's `description` ("bist, us only"), rather than defining a narrower `Literal`. Passing an
unsupported market is rejected at runtime with an actionable error. This way there is exactly
one market vocabulary to learn, and the supported subset is still stated where the model reads
it.

### 2.2 `symbol` is always `str | list[str]`

Today it appears as four different types (`str`, `Union[str, List[str]]`, `Optional[str]`,
`Optional[Union[str, List[str]]]`). Where a provider cannot parallelize, the server loops.
From the model's side there is no difference. Cap: 10 symbols.

### 2.3 One time contract

Every time-series tool accepts **either** `period` **or** `start_date` + `end_date`.
Supplying both is an error. The same `HistoricalPeriodLiteral` is used everywhere. Exceptions
like `get_fx_data` having no `period` disappear.

### 2.4 Response skeleton (markdown/TSV preserved)

```
## Meta
symbol: ASELS   market: bist   source: yfinance
as_of: 2026-07-11   bar_interval: 1d

## Data
<TSV>

## Warnings
> Not: ...
```

This delivers the requested `metadata / data / source / warnings` separation **without**
switching to JSON. Markdown/TSV output stays.

### 2.5 "No data" vs "tool failed"

| State | Behavior |
|---|---|
| Data present | `## Data` populated |
| Legitimately empty (delisted fund, market closed) | `## Data` section **is not emitted at all**; `## Warnings` states why |
| Fetch failed | Provider raises; `classify_tool_error` returns an actionable suggestion |

**Bug this kills**: `providers/markdown_renderer.py:103` currently renders *every* empty list
as `key: Sonuç bulunamadı.` A historical-data request leaves `rates` legitimately empty, and
the renderer announced that emptiness as a failure — while the historical data rendered fine
right below it. New rule: an empty list is not emitted. If a field being empty is genuinely
anomalous, a warning says so.

`response_shaper` strips nulls today but not empty lists. That is the fix site.

---

## 3. `compare_assets`

### Signature

```python
compare_assets(
    assets:            list[str],                 # ["ASELS", "gram-altin", "USD", "TPC"]
    start_date:        str,                       # required
    end_date:          str = <today>,
    base_currency:     Literal["TRY", "USD"] = "TRY",
    compare_currency:  Optional[Literal["TRY", "USD"]] = None,
    include_dividends: bool = True,
    initial_amount:    Optional[float] = None,    # if given, value columns are returned too
)
```

### Symbol resolution

Bare strings are accepted and resolved with `search_symbol`'s logic. An explicit
`{"symbol": "X", "market": "bist"}` form disambiguates. **Every resolution is echoed in
`## Meta`** so the model cannot silently compare the wrong instrument.

### Return calculation

No full series alignment. A period return needs two endpoints, so for each asset take the
**last observation on or before `start_date`** and the last on or before `end_date`. This
handles BIST being closed on weekends while crypto trades 24/7, with no special-casing.
The actual dates used are reported **per asset** — if one reads from July 9 and another from
July 10, that is visible, not hidden.

USD return is derived from the TRY series; no separate USD series is fetched:

```
return_usd = (P_end / USDTRY_end) / (P_start / USDTRY_start) - 1
```

Side benefit: list `USD` as an asset and its `return_usd` is 0 by definition — the output
carries its own sanity check.

### Three deliberate decisions

- **Splits are always adjusted**, independent of `include_dividends`. Otherwise a 1:10 split
  reads as a -90% return. Dividends are optional; splits are not.
- **`include_dividends` is a no-op for TEFAS funds** — fund NAV is already total-return.
  This is not swallowed silently; it emits a warning.
- **`include_fees` is out of scope for v1.** Gold buy/sell spread, fund entry/exit
  commissions, BIST brokerage — each needs assumptions that vary by user and institution.
  A fabricated commission rate is more misleading than no commission at all. If genuinely
  needed, v2 adds an explicit `fee_bps`.

### Output

```
## Meta
window: 2026-01-02 → 2026-07-10
base_currency: TRY   compare_currency: USD
fx_series: USDTRY (borsapy)
initial_amount: 100000 TRY   include_dividends: true

## Data
asset       market  start_date  end_date    start_price  end_price  return_try  return_usd  end_value_try  end_value_usd
ASELS       bist    2026-01-02  2026-07-10  ...          ...        0.6073      0.4702      160730         3417
gram-altin  fx      2026-01-02  2026-07-09  ...          ...        ...         ...         ...            ...
USD         fx      2026-01-02  2026-07-10  ...          ...        ...         0.0000     ...            ...

## Warnings
> Not: gram-altin için 2026-07-10 kapanışı yok; 2026-07-09 kullanıldı.
```

Rows are sorted by `base_currency` return, descending.

---

## 4. Compatibility, migration, verification

### No backward compatibility — deliberately

This server's consumer is an LLM, not code. Nothing imports `get_dividends`; the model
re-reads the tool list each session. Keeping ten deprecated shim tools would leave their
schemas in context and **cancel the entire context saving** — defeating one of the two
motivating pains. So: clean break, version `1.0.0`.

The one exception is at the *value* level: `crypto_tr` / `crypto_global` map silently to
`crypto` + `exchange` for a transition period. Schema cost: zero. Runtime cost: a few lines.

### Three phases, each independently deployable

**Phase 1 — Contract + renderer (non-breaking).** Single `market` enum, `str|list` symbol
everywhere, one time contract, `## Meta / ## Data / ## Warnings` skeleton, empty-list render
fix, EVDS schema diet. Tool count stays at 28. The gram-altın bug dies here and part of the
schema cost drops here — so the benefit banks even if the merges slip.

**Phase 2 — Merges (breaking, v1.0.0).** The 28 → 18 map from section 1.

**Phase 3 — `compare_assets`.** Depends on Phase 2: `get_historical_data` must serve
fx/crypto/fund under one signature; `compare_assets` is a thin layer on top.

### Verification

- **Parity test per merge**, in `tests/`: every field the old tool returned must be reachable
  from the corresponding mode of the new tool.
- **`compare_assets`**: hand-computed expected returns over a fixed window.
- **Deploy check**: CLAUDE.md records that a previous audit found the Cloud Run image running
  older code than `main`. After each phase, verify against
  **`https://borsa.surucu.dev/mcp`**, not just locally.

### Explicitly out of scope

`include_fees`; full series alignment / charting output; merging EVDS into another tool;
switching to JSON output.
