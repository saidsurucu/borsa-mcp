# Tool Consolidation & Contract Standardization (v1.0.0)

**Date**: 2026-07-12
**Status**: Approved design, revised after adversarial review (Codex `gpt-5.6-sol`)
**Scope**: 28 tools → 22; one parameter contract; a canonical price/return contract;
new `compare_assets` tool

> **Revision note.** The first draft proposed 28 → 18. An adversarial review plus direct
> verification against the code killed five of those merges and surfaced three live bugs
> unrelated to the redesign. Both are recorded below rather than quietly dropped, because the
> reasoning that produced the bad merges ("same source", "same question") is exactly the
> reasoning that will produce the next one.

---

## Problem

Two observed pains:

1. **Context cost** — 28 tool schemas sit in every request's context.
2. **Wrong tool / long call chains** — answering "ASELS mi altın mı?" takes ~6 tool calls plus
   arithmetic the model performs itself, across mismatched date windows.

## What the measurements say

The 28 schemas cost **27,320 characters ≈ 7,600 tokens** — about 4% of a 200k window. The cost
is concentrated, not spread across tool count:

| | chars | share |
|---|---|---|
| `get_evds_data` alone | 4,860 | 18% |
| Largest 6 tools | 12,800 | 47% |
| Smallest 14 tools | ~6,000 | 22% |

Merging tools moves parameters; it does not delete them. EVDS's 4.2k of parameter documentation
still has to live inside whatever tool absorbs it. A 5-mega-tool design could hoist a shared
`symbol`/`market`/`period` block into `$defs` and would land somewhere below 27.3k — **this was
never measured, and the earlier "20-22k" figure was a guess, not a result.** It is not used as a
premise here. What is load-bearing is the qualitative trade: a mega-tool buys a few thousand
tokens at the price of large action-dependent schemas, invalid parameter combinations, and worse
tool selection.

So tool count is not the lever for pain (1) — **schema diet is**. And pain (2) is solved by a
canonical price/return contract plus `compare_assets`, both of which are independent of tool
count.

The consolidation below is therefore justified on **selection-surface clarity**, not token
savings. Every merge must answer "these ask the same question" *and* survive a parity check
against the real code. Five proposed merges did not.

---

## 0. Live bugs (present today, independent of this redesign)

These ship first, on their own, as non-breaking fixes. All three were verified in the code.

| Bug | Evidence | Fix |
|---|---|---|
| **`get_bond_yields(country="US")` returns Turkish yields labelled US.** The schema advertises `TR \| US` and the description says "Country: TR or US", but the handler unconditionally calls `BorsapyBondProvider().get_tahvil_faizleri()`. `country` is merely echoed. | `unified_mcp_server.py:1254` | Restrict the literal to `TR` until a US provider exists. Do not silently mislabel. |
| **Crypto historical data ignores `period`, `start_date`, `end_date` entirely.** The `CRYPTO_TR` / `CRYPTO_GLOBAL` branches call `get_kripto_ohlc(symbol)` / `get_coinbase_ohlc(symbol)` with no date arguments. A requested window is silently discarded. | `providers/market_router.py:485` | Thread the date/period contract into both crypto branches. Until then, reject the params rather than ignoring them. |
| **`downsample_ohlcv` is dead code and has never fired.** It reads `payload["data_points"]`, but the router writes the row list to `"data"` and puts `len(rows)` — an **int** — in `"data_points"`. `isinstance(points, list)` is always False, so the function returns immediately. CLAUDE.md documents an auto-downsample that does not happen; size is actually bounded by a separate resampling path in the router. | `providers/response_shaper.py:77` vs `providers/market_router.py:~535` | Fix the key, or delete the function and correct CLAUDE.md. Do not leave a documented behaviour that does not exist. |

The FX empty-`rates` render bug (section 2.5) also ships in this phase.

---

## 1. Tool map (28 → 22)

### Merges kept

| Tool | Absorbs | Rationale |
|---|---|---|
| `get_quote` | `get_quick_info`, `get_fx_data`(current), `get_crypto_market`(ticker) | All ask "what is it worth now". Equities return P/E, P/B, 52w; FX bid/ask; crypto bid/ask/24h. **Breaking sub-change**: today's FX supports `symbol=None` (all rates) and `category`. A universal symbol-based contract drops both; catalog/category browsing moves to `search_symbol`. This is a real contract change, documented as such — not a transparent absorption. `exchange` stays optional and crypto-only. |
| `get_historical_data` | `get_fx_data`(historical), `get_crypto_market`(ohlc/kline), index history, fund NAV history | **This is not a merge. It is a new canonical history adapter** — see section 3. Crypto branches currently ignore dates, index history does not exist, and TEFAS has no normalized OHLCV path. Treating it as a rename is the single biggest error in the first draft. |
| `get_technical_analysis` | `get_pivot_points` | Pivots are an indicator. |
| `get_corporate_actions` | `get_dividends` | **Kept, but re-scoped as real work.** Today `get_dividends` covers BIST **and US** including splits, while `get_corporate_actions` is BIST-only with a `year` filter and İş Yatırım rights/bonus data. A merge must *normalize* dividends, splits, rights issues and bonus issues across both markets — `get_corporate_actions(symbol, market, year?, action_type?)` — and document which filters apply where. Absorbing without normalizing loses US dividends and all splits. |
| *help folding* | `get_screener_help` → `screen_securities(help=true)`; `get_scanner_help` → `scan_stocks(help=true)`; `get_regulations` → `get_fund_data(data_type="regulations")` | Help becomes scope-aware without unifying the screeners. `help=true` combined with active filters is a validation error, not a silent precedence rule. |

`get_crypto_market` is **narrowed** (not removed) to `orderbook | trades | exchange_info` once
ticker and OHLC move out. What remains is exchange microstructure, which genuinely is crypto-only.

### Merges rejected after review

Each was proposed in the first draft and each fails a parity check against the code.

| Rejected merge | Why it is wrong |
|---|---|
| `get_profile` ← index components | "An index's profile is its constituents" is false. `get_index_data` also returns the index **level, open/high/low, previous close, change and volume** (`market_router.py:2110`). Moving only components silently loses the quote. **Decision:** `get_index_data` stays. Its level may later be exposed via `get_quote(market="index")` and its history via the history adapter, but that is a decomposition to spec and test, not a one-line merge. |
| `get_financial_statements` ← `get_financial_ratios` | Different parameters (`statement_type`/`period`/`last_n` vs `ratio_set`) and different sources — `ratio_set` spans `buffett`, `core_health`, `advanced`, `comprehensive`, each on a different calculation path, and US ratios come from quick info. An `include_ratios: bool` cannot express `ratio_set`. **Decision:** stay separate. |
| `get_analyst_data` ← `get_earnings` | The "same yfinance source" claim is false: BIST earnings fall back to TradingView. An earnings date is not "what analysts think". Merging also doubles latency when only one half is wanted. **Decision:** stay separate. |
| `screen` ← `screen_securities` + `screen_funds` | This *is* the mega-tool problem this design claims to avoid: preset + `security_type` + nested `custom_filters` on one side, `fund_type` + category + fixed return thresholds + a different `sort_by` vocabulary on the other. **Decision:** stay separate; fold only their help into `help=true`. |
| `get_macro_data` ← `get_bond_yields` | `get_macro_data` is already parameter-heavy (an inflation calculator); adding a `data_type="bonds"` mode leaves most parameters irrelevant for that mode. The bond tool is 292 chars. **Decision:** keep it separate and fix its `country` lie (section 0). A tiny honest tool beats another mode on a crowded one. |

### Resulting count

28 − 7 absorbed (`get_quick_info`, `get_fx_data`, `get_pivot_points`, `get_dividends`,
`get_screener_help`, `get_scanner_help`, `get_regulations`) + 1 new (`compare_assets`) = **22**.

---

## 2. Parameter contract

### 2.1 One `market` vocabulary, narrowed per tool

Conceptually one enum: `bist | us | crypto | fx | fund | index`.

Today's `crypto_tr` / `crypto_global` encode an *exchange*, not a market. They collapse to
`market="crypto"` plus `exchange: btcturk | coinbase`, inferred from the symbol suffix
(`BTCTRY` → btcturk, `BTC-USD` → coinbase) and overridable.

**Each tool's JSON Schema is narrowed to the markets it actually supports.** An earlier draft
proposed giving every tool the full enum and rejecting unsupported values at runtime, with the
supported subset stated only in the field description. That deliberately weakens schema
validation to buy a cosmetic uniformity — the model can then emit a call the schema would have
caught. One vocabulary conceptually; a narrow `Literal` per tool in practice.

### 2.2 `symbol` is always `str | list[str]`

Today it appears as four different types (`str`, `Union[str, List[str]]`, `Optional[str]`,
`Optional[Union[str, List[str]]]`). Where a provider cannot parallelize, the server loops. Cap: 10.

`symbol=None`-means-"everything" (today's FX catalog mode) is **removed**; discovery belongs to
`search_symbol`.

### 2.3 One time contract

Every time-series tool accepts **either** `period` **or** `start_date` + `end_date`. Both together
is an error. The same `HistoricalPeriodLiteral` everywhere, plus an explicit `interval` (section 3).

### 2.4 Response skeleton (markdown/TSV preserved)

```
## Meta
symbol: ASELS   market: bist   source: yfinance
as_of: 2026-07-11   interval: 1d   price_basis: close   currency: TRY

## Data
<TSV>

## Warnings
> Not: ...
```

This delivers the requested `metadata / data / source / warnings` separation **without** switching
to JSON. Markdown/TSV output stays.

### 2.5 "No data" vs "tool failed" — and where the fix lives

| State | Behavior |
|---|---|
| Data present | `## Data` populated |
| Legitimately empty (delisted fund, market closed) | `## Data` not emitted; `## Warnings` states why |
| Fetch failed | Provider raises; `classify_tool_error` returns an actionable suggestion |

**The bug:** `markdown_renderer.py:99` renders *every* empty list as `key: Sonuç bulunamadı.`
An FX historical request returns `rates=[]` alongside a populated `historical_data`, so the
renderer announced a failure next to perfectly good data.

**The fix site matters, and the first draft got it wrong.** Globally stripping empty lists in
`response_shaper` would hide real anomalies and contradict the project's own "never return an
empty-but-successful payload" rule (CLAUDE.md #7). Instead:

- **The FX router returns a mode-specific payload** — `rates` for current mode, `historical_data`
  for historical mode, never both. This is the actual root cause.
- **The provider/tool boundary raises** when the field expected for the selected mode is
  unexpectedly empty.
- **The renderer stops translating empty lists into failure language.** It may omit them as a
  presentation fallback, but semantic failure detection does not belong there.
- **`response_shaper` stays semantics-neutral.**

---

## 3. The canonical price/return contract *(the piece the first draft was missing)*

Without this, `compare_assets` produces precise-looking but economically incomparable numbers.
The markdown skeleton is a presentation contract; this is the data contract. It must be specified
and implemented **before** the history adapter, which must land **before** `compare_assets`.

For every market, define and test:

| Dimension | Must be specified per market |
|---|---|
| Native currency | TRY, USD, … |
| Price column | close / adjusted close / NAV |
| Price basis | bid, ask, mid, last, NAV — **gram-altin is a dealer quote with a spread; today's FX OHLC does not say which side it is** |
| Timezone & valuation date | Europe/Istanbul, America/New_York, UTC for crypto |
| Interval / granularity | Coinbase candle limits; intraday crypto vs daily equities |
| Start/end inclusivity | |
| Ordering | Coinbase returns newest-first, BtcTurk oldest-first (CLAUDE.md #6) |
| Stale-price tolerance | max days a suspended/delisted asset may reach back |
| Split adjustment | **always applied** |
| Dividend treatment | how the total-return series is actually constructed |
| Fund NAV lag | TEFAS publication date ≠ valuation date ≠ order cutoff ≠ executable date |
| FX conversion date | aligned to *each asset's actual* observation dates, not the requested dates |
| Empty vs failure | per section 2.5 |

Note this exposes an unresolved implementation question: US history currently ignores its
`adjust` flag, BIST adjustment semantics are provider-specific, and typical "adjusted close"
series bundle split *and* dividend adjustment together. "Splits always adjusted, dividends
optional" is a requirement, not yet a mechanism. **Two endpoints are only sufficient once a
trustworthy split-adjusted or total-return series exists.**

---

## 4. `compare_assets`

### Signature

```python
compare_assets(
    assets:            list[str | AssetRef],      # AssetRef = {"symbol": str, "market": Market}
    start_date:        str,                       # required
    end_date:          str = <today>,
    base_currency:     Literal["TRY", "USD"] = "TRY",
    compare_currency:  Optional[Literal["TRY", "USD"]] = None,
    include_dividends: bool = True,
    initial_amount:    Optional[float] = None,
)
```

`AssetRef` is a real schema member, not prose. The first draft's signature said `list[str]` while
the text allowed dicts — those calls would have failed validation. Bare strings are accepted where
resolution is unique; ambiguous ones (`USD`) require an `AssetRef`. Note that today's
`search_symbol` **requires** `market`, so the assumed cross-market bare-symbol resolver does not
exist and must be built. Resolution precedence is deterministic and non-unique resolution is an
error, never a guess. Every resolution is echoed in `## Meta`.

### Endpoint semantics

The comparison models an **investment simulation**, so the endpoints are asymmetric:

- **start** = the first tradable observation **on or after** `start_date`.
- **end** = the last observation **on or before** `end_date`.

The first draft used last-on-or-before for both. That is an as-of close-to-close comparison, not an
investment: you cannot buy on Saturday at Friday's already-passed close.

A **maximum-staleness rule** bounds both ends. Without it, a suspended or delisted asset silently
reaches for a price far outside the requested window. Exceeding it is a warning, not a silent fill.
For TEFAS, staleness is measured against the valuation date, not the publication date.

### Currency normalization

**Every asset is normalized to TRY first, then converted.**

- Natively TRY-quoted: `usd_price = try_price / USDTRY`
- Natively USD-quoted (Coinbase `BTC-USD`): `try_price = usd_price × USDTRY`, and its **USD return is
  computed directly from native USD prices** — never by dividing a USD price by USDTRY.

The FX observations used for conversion are aligned to **each asset's actual start and end dates**,
not the requested dates.

Listing `USD` as an asset should then yield `return_usd = 0` exactly — a self-check on the output.

### Price basis and honesty about executability

`include_fees` stays out of v1: gold spread, fund entry/exit commissions and BIST brokerage each need
assumptions that vary by user and institution, and a fabricated rate is more misleading than none.

**But silently presenting a reference-price return as realizable performance is not acceptable.**
Spread is not a fee; for gram-altin over a short window it can dominate the return. Therefore:

- every row reports its `price_basis`;
- results are labelled **gross reference-price return**;
- assets with a material spread carry a prominent non-executable-price warning.

A future transaction-cost model should support buy-at-ask / sell-at-bid, not a generic `fee_bps`.

### Other rules

- **Splits always adjusted**, independent of `include_dividends`. A 1:10 split otherwise reads as −90%.
- **`include_dividends` is a no-op for TEFAS funds** (NAV is already total-return). Warned, not swallowed.
- Rows sorted by `base_currency` return, descending.

---

## 5. Compatibility and migration

### A clean v1 surface, but "the consumer is an LLM" was too glib

The first draft argued that since nothing *imports* `get_dividends`, a clean break is free. That
ignores: saved prompts and custom agents naming old tools; client allowlists and tool-specific
approval rules; sessions holding a stale tool list; deterministic workflow products; cached tool
metadata; and **mixed old/new Cloud Run revisions serving split traffic during rollout**.

**Approach:** keep the v1 surface clean — no deprecated alias tools inside it — but **retain v0 at a
separate endpoint/revision** for a short migration window, publish a name mapping, drain old
sessions, and never split traffic across incompatible revisions.

Version surfaces are currently inconsistent (`pyproject.toml` still says `0.8.0`, and README/CLAUDE.md
tool counts disagree). All of them get updated in the same change.

`crypto_tr` / `crypto_global` map silently to `crypto` + `exchange` at the *value* level. Schema cost:
zero.

### Phases — reordered, because the dependency runs the other way

**Phase 0 — Live bug fixes (non-breaking, ships alone).** Section 0's three bugs plus the FX
empty-`rates` root cause. Independent of everything else; no reason to wait.

**Phase 1 — Canonical price/return contract (section 3).** Specified and implemented per market.
Everything else depends on it.

**Phase 2 — Canonical history adapter.** `get_historical_data` serving bist/us/crypto/fx/fund/index
under one contract, with normalized rows, currency, timezone, interval, inclusivity, ordering,
adjustment basis, caps and per-market failure behaviour. This is **new work**, not a merge.

**Phase 3 — Parameter contract + the kept merges (breaking, v1.0.0).** Sections 1 and 2.

**Phase 4 — `compare_assets`.** A thin layer over Phases 1–2.

### Verification

- **Parity test per merge**, in `tests/`: every field the old tool returned must be reachable from the
  corresponding mode of the new tool. The five rejected merges are the evidence that this test must be
  written *before* the merge, not after.
- **`compare_assets`**: hand-computed expected returns over a fixed window, including one natively-USD
  asset and one TEFAS fund spanning a NAV-lag boundary.
- **Deploy check**: CLAUDE.md records a previous audit finding the Cloud Run image running older code
  than `main`. After each phase, verify the tool list and representative calls against
  **`https://borsa.surucu.dev/mcp`**, not just locally.

### Explicitly out of scope

`include_fees` / transaction-cost modelling; full series alignment and charting output; merging EVDS
into another tool; switching to JSON output; measuring a 5-mega-tool variant we have already rejected
on non-token grounds.
