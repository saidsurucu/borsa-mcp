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

**Status: all of the above are fixed and merged** (`a5bd011`), verified live against BtcTurk,
Coinbase, BIST, US and FX.

### 0b. Further live bugs, found while measuring the price contract (section 3)

Surveying what the six markets actually return turned up more of the same class. Listed with
where they get fixed, so none is silently dropped.

| Bug | Status |
|---|---|
| **`XPT-USD` resolves to two different assets.** `get_fx_data` applies `ASSET_MAPPING` → gram-platin, **2,477 TRY**. `get_historical_data` passes the symbol raw → platinum ounce, **1,637 USD**. Same name, different asset, different currency. | ✅ **Fixed.** `resolve_fx_asset` is the one resolution path; both tools now return 1637.97. |
| **`ons` is a TRY series labelled USD.** `birim = "TRY" if asset in ["gram-altin","gumus"] else "USD"`, but `ons` maps to `ons-altin` = ounce-of-gold-**in-lira** (106,463 TRY vs the real USD ounce at 4,120). | ✅ **Fixed.** Currency comes from the registry, including `referans_para_birimi`, which was hardcoded TRY even for BRENT. |
| **`gumus` / `ons` have no historical path at all** — `ASSET_MAPPING` is not applied in `get_historical_data`. | ✅ **Fixed.** |
| **US `adjust` is accepted and ignored**, and the description is wrong in both directions. | ✅ **Fixed.** `auto_adjust=False`; verified on KO's ex-dividend (−0.699% where the adjusted series printed +0.07%). |
| **BIST default is raw**, so a bonus issue reads as a −49% return. | ✅ **Fixed.** `adjust=True` is the default; BIMAS now prints +1.8% across 2026-05-14. |
| **Coinbase rows come back descending** while every other market ascends. | ✅ **Fixed.** Normalized to ascending at source. |
| **Coinbase caps at 350 candles**, and the failure reported as "no data". | ✅ **Fixed.** Names the cap and points at BtcTurk, which has none. |
| **Crypto volume is truncated to int** — 6.779 BTC becomes `6`. | ✅ **Fixed.** |
| **FX current mode is empty-but-successful** — `gram-platin` and `ons` shipped `successful_count: 1` with no data. Only visible once the renderer stopped printing "Sonuç bulunamadı." for an empty list. | ✅ **Fixed** (found during Phase 1). Raises; a partial batch keeps good rows and warns. |
| **BIST's un-adjust is flaky**, so `adjust=False` can silently return adjusted data (§3.2). | ✅ **Moot.** Decision A always requests `adjust=True`, which never enters `_unadjust_prices`. Still true for anyone who passes `adjust=False` explicitly. |
| **US resampling is silent.** `raw_count` is only set in the BIST branch, so `bar_interval` and the "these are NOT daily candles" warning never fire for US. `KO` at `period=1y` returns **13 monthly bars** presented as the raw series. | ⏳ Phase 2 (history adapter) |
| **Resampled bars are stamped in the future** — that query's last row is dated `2026-07-31`, three weeks ahead of today. | ⏳ Phase 2 |
| **`guncel_deger` is a stale daily close (up to 2 days old) mislabelled `sell`.** borsapy's `get_current` just returns the last row of a 5-day history; there is no live quote and no `buy`/`sell` in the source. | ⏳ Phase 3 (`get_quote`) |
| `get_fund_data` drops the order cutoff and settlement valor fields it already receives, and its `price` carries no date. | ⏳ Phase 3 |
| **The TradingView websocket behind BIST fails roughly half the time with no retry anywhere.** A single failure surfaces as a hard error. | ⏳ Separate — reliability, not contract |

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

The markdown skeleton is a presentation contract; this is the data contract. It must be
implemented **before** the history adapter, which must land **before** `compare_assets`.

### 3.1 What the six markets actually do — measured, not assumed

Every cell below was verified against live data, not inferred from code.

| | **BIST** | **US** | **Crypto TR** | **Crypto Global** | **FX** | **Fund** |
|---|---|---|---|---|---|---|
| Native currency | TRY | USD | TRY | USD | TRY *and* USD (mixed) | TRY |
| **Declared in payload?** | ❌ never | ❌ never | ❌ never | ❌ never | ⚠️ hardcoded `TRY`, wrong for USD assets | ❌ never |
| Price basis | last | last | last traded | last traded | **satış/ask** of canlidoviz *Serbest Piyasa* | NAV |
| Splits adjusted | ❌ **not by default** | ✅ always | — | — | — | — |
| Dividends adjusted | ❌ **never** | ✅ always | — | — | — | ✅ accrue into NAV |
| `adjust` flag | ✅ honoured (but flaky) | ❌ **accepted and ignored** | — | — | — | — |
| Date format | `2026-06-01T00:00:00` (naive) | `...T00:00:00-04:00` (NY) | UTC datetime | UTC datetime | `2026-07-11` | `2026-07-10` |
| Date means | Istanbul session date | NY session date | UTC day | UTC day | Istanbul day | **publication date; value = close of D−1** |
| Row order | ascending | ascending | ascending | **descending** | ascending | ascending (provider) / **descending** (tool) |
| Shape | OHLCV | OHLCV | OHLCV | OHLCV | OHLC, no volume | **close-only NAV** |
| Window cap | — | — | — | **350 candles** | — | **5 years** |

### 3.2 The three findings that would have made `compare_assets` produce garbage

**BIST is raw; US is fully adjusted.** They are directly incomparable. BIMAS did a 100% bonus
issue (bedelsiz) on 2026-05-14: at the default `adjust=False` the series goes 813.00 → 414.00
across that date. A comparison spanning it would have reported **−49% for BIMAS** — a company
that did nothing but split. Meanwhile AAPL would sit in the next row as a dividend-and-split
adjusted total-return series.

Worse, **you cannot tell which series you got.** BIST's `adjust=False` path un-adjusts the
TradingView frame using İş Yatırım split data fetched inside a bare `try/except: return df`. That
fetch is flaky; when it fails, `adjust=False` silently returns the *adjusted* frame. Same call,
same parameter, two different series.

**A fund's window is shifted one trading day.** Measured by regressing TI2's daily NAV returns
against XU100: correlation **0.014 at lag 0, 0.938 at lag 1** (confirmed on AFA, a different
founder's fund). The NAV stamped date D is marked to market at the **close of D−1**. TEFAS's
`tarih` is the publication date, and it is the only date the data exposes. So a fund's `[A, B]`
is economically `[A−1, B−1]`, and the freshest NAV always trails the freshest stock close by one
trading day — structurally, not as a weekend artifact.

**Currency is never declared.** A BTCTRY close of 3,005,375 and a BTC-USD close of 64,034 arrive
in identically-shaped payloads.

### 3.3 Decision: price return, not total return

`include_dividends=True` cannot be honoured consistently across BIST and US today. US bundles
split *and* dividend adjustment together inside yfinance's `auto_adjust=True`; BIST never adjusts
dividends in any mode, so a BIST total-return series would have to be reconstructed from dividend
history (İş Yatırım gives `brut_oran` as a percentage of nominal, which needs its own validation
before anyone's return depends on it).

**v1 computes a price return:**

- **Splits are adjusted everywhere.** BIST: request `adjust=True`. US: fetch with
  `auto_adjust=False` and take the **raw `Close`**, which is split-adjusted but not
  dividend-adjusted, matching BIST.
- **Dividends are adjusted nowhere.** Results are labelled a **price return, excluding
  dividends**, and say so in `## Warnings` rather than in a footnote nobody reads.
- **Funds keep their asymmetry, disclosed.** Fund NAV accrues underlying dividends and there is no
  distribution stream in the data to strip out. A fund therefore *is* a total return while the
  stocks beside it are not. This is stated in the output, not hidden.

Total return is a v2 feature, gated on validating the BIST dividend-per-share reconstruction.

### 3.4 What Phase 1 must therefore build

Not a document — a **normalization layer**. A canonical series adapter that, for any
(symbol, market), returns:

- rows sorted **ascending**, always;
- a `date` as a plain `YYYY-MM-DD` in one convention, per market's session date;
- for funds, both the published date and the derived **valuation date** (D−1);
- a **declared** `currency`, correct per asset (not hardcoded);
- a **declared** `price_basis` (`last`, `ask`, `nav`);
- a **declared** `adjustment` stating what was actually applied — including detecting the BIST
  un-adjust failure rather than trusting the flag;
- an explicit stale-price tolerance, so a suspended asset cannot silently reach far outside the
  requested window;
- provider window caps surfaced as their real cause (Coinbase's 350-candle limit currently
  reports "no data" when the truth is "window too wide").

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
