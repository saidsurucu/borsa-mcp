# Design: LLM-UX Improvements + Repository Cleanup

**Date:** 2026-06-12
**Status:** Approved (user delegated spec/plan authority)

## Problem

Real-world usage of the unified MCP server (28 tools) shows three LLM-side problems,
all confirmed in code:

1. **Token bloat** — responses are returned raw with no size governance on several
   high-volume paths. Worst offenders: `get_evds_data` `datagroup_data` (137 series ×
   1000 rows default), `get_historical_data` over long ranges, `get_financial_statements`
   (full statement tables), `screen_securities` at `limit=250`. `TokenOptimizer` exists
   and IS used by some providers (crypto, OHLC, fund search, news) but EVDS, financial
   statements and screeners bypass it. Null fields are serialized throughout.
2. **Non-actionable errors** — tools wrap exceptions as `"X failed: {str(e)}"` with no
   guidance. EVDS routing validation returns `{"error_message": ...}` dicts inside a
   *successful* response, so the LLM treats failures as data.
3. **Confusing parameters** — `get_evds_data` has 18 params with action-dependent
   requirements invisible in the schema; `screen_securities` accepts `preset` +
   `custom_filters` together with undefined behavior; `get_fund_data` silently ignores
   `include_portfolio/performance` in multi-fund mode; `get_technical_analysis`
   timeframe is unvalidated.

Separately, the repository is cluttered: a deprecated 81-tool legacy server, ~100
root-level `test_*.py`/`debug_*.py` scripts, stale result JSON/CSV artifacts.

## Goals

- Phase 1: remove the legacy server and root clutter; organize surviving tests under `tests/`.
- Phase 2: response size governance, an actionable error contract, and parameter
  validation across the unified server.

## Non-Goals

- No new data sources or tools.
- No changes to provider external APIs or to the `symbol` parameter convention.
- No attempt to keep legacy (`borsa-mcp-legacy`) working — it is deleted outright.

## Verified dependency facts (drive the cleanup rules)

- `unified_mcp_server.py` → `providers/market_router.py` → `borsa_client.py` (**keep** `borsa_client.py`).
- Providers (btcturk, borsapy, tefas, yfinance, mynet) lazily import `token_optimizer.py`,
  which lazily imports `compact_json_optimizer.py` (**keep both**).
- `array_format_optimizer.py` is referenced only by the legacy server and old tests (**delete**).
- `fon_mevzuat_kisa.md` / `fon_mevzuat_kisa.py` back the `get_regulations` tool (**keep**).

## Phase 1 — Cleanup

1. **Delete legacy server**: `borsa_mcp_server.py`; remove the `borsa-mcp-legacy`
   entry point from `pyproject.toml`. Delete `array_format_optimizer.py`.
2. **Root artifact purge**: delete `debug_*.py`, `verify_tier2_data.py`,
   `check_mcp_tools_count.py`, `test_unified_results.json`,
   `tcmb_inflation_test_results.json`, `trading_economics_test_results.json`,
   `tcmb_inflation_data.csv`, `ornek.jpeg`, `fon-ornek.png` (after confirming no README
   reference; if referenced, keep). Move `fast-mcp-docs.md` to `docs/`.
3. **Test reorganization**: create `tests/`. Mechanical rule:
   - Delete any `test_*.py` importing `borsa_mcp_server` or `array_format_optimizer`.
   - Move every remaining root `test_*.py` into `tests/`.
   - Run `pytest tests/ --collect-only`; delete files that fail *collection* because
     they reference deleted modules. (Failing assertions are out of scope; only
     import-time breakage from this cleanup is grounds for deletion.)
4. **Docs**: update `pyproject.toml`, `README.md`, `CLAUDE.md` — remove all legacy-server
   sections and the 81-tool listing; reflect the new test layout.

## Phase 2 — LLM-UX

### A. Response shaping (`providers/response_shaper.py`, new module)

A single post-processing step applied in `unified_mcp_server.py` tool bodies (not in
providers) before returning a payload:

- `strip_nulls(payload)` — recursively drop `None`-valued keys and empty lists/dicts
  from dict payloads. Applied to every tool's response. (Biggest cheap win.)
- Per-tool caps with truncation metadata. When a cap fires, the response gains
  `meta: {truncated: true, guidance: "<how to narrow>"}` (English text):
  - `get_evds_data`: cap total returned observations at **2,000 per call** across all
    series; lower the default `limit` from 1000 to **100**. Guidance suggests narrowing
    `start_date`/`end_date`, using `formula`/`frequency` aggregation, or selecting fewer series.
  - `get_historical_data`: if the requested range yields > **300** points at the chosen
    interval, downsample (daily→weekly→monthly) and say so in guidance.
  - `get_financial_statements`: keep existing `last_n` defaults but drop line items that
    are null across all periods.
  - `screen_securities` / `scan_stocks`: existing row limits stay; per-row null-stripping applies.

### B. Error contract

- Helper in `unified_mcp_server.py`: `raise_tool_error(message: str, suggestion: str)`
  → raises `ToolError(f"{message} | Try: {suggestion}")`. All text English.
- Replace every generic `except Exception as e: ... f"X failed: {e}"` wrapper with a
  classifier that maps common cases to suggestions:
  - symbol/ticker not found → "Verify the symbol with search_symbol first."
  - missing `EVDS_API_KEY` → "Catalog actions work without a key; data actions need
    EVDS_API_KEY from https://evds3.tcmb.gov.tr."
  - rate limit / timeout → "Retry once; if it persists, narrow the query."
  - unknown/unclassified → keep the original exception text, add "If the symbol or
    parameters look wrong, check the tool description for valid values."
- EVDS routing validation in `market_router.py` (`{"error_message": ...}` payload
  returns) must become raised `ToolError`s so the LLM sees a real tool failure.

### C. Parameter validation & schema clarity

All validation happens at the top of the tool function and raises `ToolError` with a
corrective, English message:

- `get_evds_data`: explicit action→required-params map validated up front; the tool
  description gains a compact table (action → required params → needs API key).
- `screen_securities`: `preset` and `custom_filters` together → ToolError telling the
  LLM to pick one.
- `get_fund_data`: multi-fund list + `include_portfolio`/`include_performance` → do not
  fail; add a `warnings` entry stating these flags only apply to single-fund queries.
- `get_technical_analysis`: validate `timeframe` against the allowed set per market.

### Testing

New `tests/test_response_shaper.py` (strip_nulls, caps, truncation metadata) and
`tests/test_param_validation.py` (each validation rule above, asserting ToolError and
message content). Existing `tests/test_models_import.py`-style smoke check that the
unified server still imports and exposes 28 tools.

## Constraints

- All LLM-visible text (descriptions, errors, guidance) in **English**.
- `symbol` (str|list) parameter convention unchanged.
- Response shaping must not alter field names or structures consumed by existing
  clients — it only removes nulls, truncates rows, and adds `meta`.

## Execution order

Phase 1 first (smaller diff surface for Phase 2), each phase as its own commit series
on `feature/llm-ux-and-cleanup`.
