# LLM-UX Improvements + Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy 81-tool server and root clutter, then add response size governance, an actionable error contract, and parameter validation to the 28-tool unified MCP server.

**Architecture:** Phase 1 is mechanical deletion/reorganization guided by a verified dependency map. Phase 2 adds one new module (`providers/response_shaper.py`) applied at tool boundaries in `unified_mcp_server.py`, an error-classification helper in the same file, and up-front parameter validation in tool bodies. No provider external APIs change.

**Tech Stack:** Python 3.11+, FastMCP, Pydantic, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-06-12-llm-ux-and-cleanup-design.md`

**Working branch:** `feature/llm-ux-and-cleanup` (already created; spec committed).

**Verified dependency facts (do NOT delete these):**
- `borsa_client.py` — imported by `providers/market_router.py:24`.
- `token_optimizer.py` — lazily imported by providers (btcturk, borsapy, tefas, yfinance, mynet).
- `compact_json_optimizer.py` — lazily imported by `token_optimizer.py:475`.
- `fon_mevzuat_kisa.md` / `fon_mevzuat_kisa.py` — back the `get_regulations` tool.
- `ornek.jpeg`, `fon-ornek.png` — referenced by `README.md` lines 7 and 9. KEEP.

**Key payload shapes (for Phase 2):**
- `get_historical_data` → `{"data_points": [{date, open, high, low, close, volume, adj_close}], ...}` (`market_router.py` ~line 390).
- EVDS `series` → `{"seri_kodu", "gozlemler": [{tarih, deger}], "toplam_gozlem", ...}`.
- EVDS `multi_series` / `datagroup_data` → `{"veriler": [records], "toplam_gozlem", ...}`.

**Run all commands from repo root:** `/Users/saidsurucu/Documents/GitHub/borsa-mcp`

---

## Phase 1 — Cleanup

### Task 1: Delete legacy server and legacy-only optimizer

**Files:**
- Delete: `borsa_mcp_server.py`, `array_format_optimizer.py`
- Modify: `pyproject.toml` (remove `borsa-mcp-legacy` entry point)

- [ ] **Step 1: Confirm nothing kept imports the deleted modules**

Run:
```bash
grep -rn "import borsa_mcp_server\|from borsa_mcp_server\|array_format_optimizer" unified_mcp_server.py providers/ models/ borsa_client.py token_optimizer.py compact_json_optimizer.py app.py database.py 2>/dev/null
```
Expected: no output. If there IS output, STOP and report — the dependency map is wrong.

- [ ] **Step 2: Delete files and entry point**

```bash
git rm borsa_mcp_server.py array_format_optimizer.py
```
In `pyproject.toml`, delete the line:
```toml
borsa-mcp-legacy = "borsa_mcp_server:main"
```

- [ ] **Step 3: Verify the unified server still imports**

Run: `uv run python -c "from unified_mcp_server import app; print('Server OK')"`
Expected: `Server OK`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove legacy 81-tool server and unused array optimizer"
```

### Task 2: Purge root artifacts

**Files:**
- Delete: `debug_client.py`, `debug_gasoline_archive.py`, `debug_grafik.py`, `debug_owner_earnings.py`, `debug_roe_step_by_step.py`, `debug_zero_metrics.py`, `verify_tier2_data.py`, `check_mcp_tools_count.py`, `test_unified_results.json`, `tcmb_inflation_test_results.json`, `trading_economics_test_results.json`, `tcmb_inflation_data.csv`
- Move: `fast-mcp-docs.md` → `docs/fast-mcp-docs.md`
- Keep: `ornek.jpeg`, `fon-ornek.png` (README references), `fon_mevzuat_*.md/py`, `mcp_servers_config.json`, `app.py`, `database.py`, `borsa_client.py`, `borsa_models.py`, `token_optimizer.py`, `compact_json_optimizer.py`

- [ ] **Step 1: Confirm no kept code reads the data artifacts**

Run:
```bash
grep -rn "tcmb_inflation_data.csv\|tcmb_inflation_test_results\|trading_economics_test_results\|test_unified_results" unified_mcp_server.py providers/ models/ borsa_client.py app.py 2>/dev/null
```
Expected: no output. If a kept module reads one of these files, keep that file and note it in the commit message.

- [ ] **Step 2: Delete and move**

```bash
git rm debug_client.py debug_gasoline_archive.py debug_grafik.py debug_owner_earnings.py debug_roe_step_by_step.py debug_zero_metrics.py verify_tier2_data.py check_mcp_tools_count.py test_unified_results.json tcmb_inflation_test_results.json trading_economics_test_results.json tcmb_inflation_data.csv
git mv fast-mcp-docs.md docs/fast-mcp-docs.md
```

- [ ] **Step 3: Verify server still imports**

Run: `uv run python -c "from unified_mcp_server import app; print('Server OK')"`
Expected: `Server OK`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: purge root debug scripts and stale result artifacts"
```

### Task 3: Reorganize tests into tests/

**Files:**
- Create: `tests/` directory
- Move/Delete: all root `test_*.py` files per the rules below

- [ ] **Step 1: Delete tests that import deleted modules**

```bash
mkdir -p tests
grep -ln "borsa_mcp_server\|array_format_optimizer" test_*.py | xargs -r git rm
```

- [ ] **Step 2: Move every remaining root test into tests/**

```bash
for f in test_*.py; do git mv "$f" "tests/$f"; done
```
Note: moved tests that use `from borsa_client import ...` style imports still work because pytest runs from repo root and the root stays on `sys.path` via rootdir; if collection shows import errors for repo-root modules, add `tests/conftest.py` containing exactly:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 3: Collection check — delete files broken by this cleanup**

Run: `uv run python -m pytest tests/ --collect-only -q 2>&1 | tail -30`

For each file that fails COLLECTION (import error), check the cause:
- If it imports a module deleted in Tasks 1-2 → `git rm` it.
- If it imports a module that never existed / was deleted long ago (pre-existing breakage) → `git rm` it.
- If it fails for a missing third-party dep that the project genuinely uses → leave it; note it in the commit message.
Re-run collection until remaining failures are only third-party-dep related (or zero).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: move tests to tests/, drop tests for deleted legacy modules"
```

### Task 4: Update documentation for the post-cleanup layout

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: README.md**

Remove any mention of `borsa-mcp-legacy`, the legacy server, and the 81-tool interface. Keep image references intact.

- [ ] **Step 2: CLAUDE.md**

- Delete the entire "Legacy Tool Interface (81 tools - backwards compatibility)" section and all legacy tool listings.
- Remove `borsa_mcp_server.py` from the Architecture section.
- Update "Key Development Commands": remove legacy commands; change test command examples to `uv run python -m pytest tests/ -q`.
- Update the test-files list in "Testing & Quality Assurance" to reference `tests/` paths.
- Remove the "Legacy Server (backwards compatibility) - 81 Tools" row/section in the Tool Count Summary.

- [ ] **Step 3: Verify no stale references remain**

Run: `grep -rn "borsa-mcp-legacy\|borsa_mcp_server" README.md CLAUDE.md pyproject.toml`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md && git commit -m "docs: remove legacy server references, reflect tests/ layout"
```

---

## Phase 2 — LLM-UX

### Task 5: response_shaper module — strip_nulls

**Files:**
- Create: `providers/response_shaper.py`
- Test: `tests/test_response_shaper.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_response_shaper.py`:
```python
"""Tests for providers.response_shaper."""
from providers.response_shaper import strip_nulls


def test_strip_nulls_removes_none_values():
    payload = {"a": 1, "b": None, "c": {"d": None, "e": 2}}
    assert strip_nulls(payload) == {"a": 1, "c": {"e": 2}}


def test_strip_nulls_handles_lists_of_dicts():
    payload = {"rows": [{"x": 1, "y": None}, {"x": None, "y": 2}]}
    assert strip_nulls(payload) == {"rows": [{"x": 1}, {"y": 2}]}


def test_strip_nulls_keeps_empty_containers():
    # Empty lists/dicts are meaningful (e.g. "no results") and must survive.
    payload = {"results": [], "meta": {}, "v": None}
    assert strip_nulls(payload) == {"results": [], "meta": {}}


def test_strip_nulls_keeps_falsy_non_none():
    payload = {"zero": 0, "false": False, "empty_str": "", "none": None}
    assert strip_nulls(payload) == {"zero": 0, "false": False, "empty_str": ""}


def test_strip_nulls_non_dict_passthrough():
    assert strip_nulls([1, None, 2]) == [1, None, 2]  # only dict keys are stripped
    assert strip_nulls("text") == "text"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_response_shaper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'providers.response_shaper'`

- [ ] **Step 3: Implement**

Create `providers/response_shaper.py`:
```python
"""
Response shaping for the unified MCP server.

Applied at tool boundaries in unified_mcp_server.py before payloads are
returned to the LLM. Removes null fields, caps oversized series, and attaches
truncation guidance. Never renames or restructures existing fields.
"""
from typing import Any, Dict, List


def strip_nulls(payload: Any) -> Any:
    """Recursively remove None-valued keys from dicts.

    List elements that are None are preserved (positional data may be
    meaningful); empty lists/dicts are preserved (they signal 'no results').
    """
    if isinstance(payload, dict):
        return {k: strip_nulls(v) for k, v in payload.items() if v is not None}
    if isinstance(payload, list):
        return [strip_nulls(item) if isinstance(item, (dict, list)) else item for item in payload]
    return payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_response_shaper.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add providers/response_shaper.py tests/test_response_shaper.py
git commit -m "feat: add response_shaper with recursive null stripping"
```

### Task 6: response_shaper — series caps and OHLCV downsampling

**Files:**
- Modify: `providers/response_shaper.py`
- Test: `tests/test_response_shaper.py`

- [ ] **Step 1: Write failing tests (append to tests/test_response_shaper.py)**

```python
from providers.response_shaper import cap_evds_payload, downsample_ohlcv

def _obs(n):
    return [{"tarih": f"2024-01-{i + 1:02d}", "deger": float(i)} for i in range(n)]


def test_cap_evds_payload_under_cap_untouched():
    payload = {"gozlemler": _obs(10), "toplam_gozlem": 10}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["gozlemler"]) == 10
    assert "meta" not in result


def test_cap_evds_payload_truncates_gozlemler():
    payload = {"gozlemler": _obs(3000), "toplam_gozlem": 3000}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["gozlemler"]) == 2000
    # most recent observations kept (tail of the list)
    assert result["gozlemler"][-1]["deger"] == 2999.0
    assert result["meta"]["truncated"] is True
    assert "narrow" in result["meta"]["guidance"].lower() or "reduce" in result["meta"]["guidance"].lower()


def test_cap_evds_payload_truncates_veriler():
    payload = {"veriler": [{"date": i} for i in range(5000)], "toplam_gozlem": 5000}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["veriler"]) == 2000
    assert result["meta"]["truncated"] is True


def _points(n):
    return [
        {"date": f"2020-{(i % 12) + 1:02d}-01", "open": 1.0, "high": 2.0,
         "low": 0.5, "close": 1.5, "volume": 100, "adj_close": None}
        for i in range(n)
    ]


def test_downsample_ohlcv_under_limit_untouched():
    payload = {"data_points": _points(100)}
    result = downsample_ohlcv(payload, max_points=300)
    assert len(result["data_points"]) == 100
    assert "meta" not in result


def test_downsample_ohlcv_reduces_points_and_flags():
    payload = {"data_points": _points(1200)}
    result = downsample_ohlcv(payload, max_points=300)
    assert len(result["data_points"]) <= 300
    # last point always kept
    assert result["data_points"][-1] == _points(1200)[-1]
    assert result["meta"]["truncated"] is True
    assert "interval" in result["meta"]["guidance"].lower() or "range" in result["meta"]["guidance"].lower()


def test_downsample_ohlcv_no_data_points_key():
    payload = {"error": "x"}
    assert downsample_ohlcv(payload, max_points=300) == {"error": "x"}
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run python -m pytest tests/test_response_shaper.py -v`
Expected: previous 5 pass, new tests FAIL with ImportError.

- [ ] **Step 3: Implement (append to providers/response_shaper.py)**

```python
def _attach_meta(payload: Dict[str, Any], guidance: str) -> None:
    meta = payload.setdefault("meta", {})
    meta["truncated"] = True
    meta["guidance"] = guidance


def cap_evds_payload(payload: Dict[str, Any], max_total: int = 2000) -> Dict[str, Any]:
    """Cap EVDS observation lists ('gozlemler' or 'veriler') at max_total rows.

    Keeps the most recent rows (tail). Adds meta.truncated/guidance when fired.
    """
    for key in ("gozlemler", "veriler"):
        rows = payload.get(key)
        if isinstance(rows, list) and len(rows) > max_total:
            payload[key] = rows[-max_total:]
            payload["toplam_gozlem"] = len(payload[key])
            _attach_meta(
                payload,
                f"Response truncated to the most recent {max_total} observations. "
                "Narrow the date range (start_date/end_date), reduce the number of "
                "series, or use frequency/formula aggregation to fit more history.",
            )
    return payload


def downsample_ohlcv(payload: Dict[str, Any], max_points: int = 300) -> Dict[str, Any]:
    """Downsample 'data_points' OHLCV lists by stride so len <= max_points.

    The final (most recent) point is always preserved exactly. Adds
    meta.truncated/guidance when fired.
    """
    points = payload.get("data_points")
    if not isinstance(points, list) or len(points) <= max_points:
        return payload
    stride = -(-len(points) // max_points)  # ceil division
    sampled = points[::stride]
    if sampled[-1] is not points[-1]:
        sampled.append(points[-1])
    payload["data_points"] = sampled
    _attach_meta(
        payload,
        f"Series downsampled from {len(points)} to {len(sampled)} points "
        f"(every {stride}th point; the most recent point is exact). For full "
        "resolution, request a shorter date range or a coarser interval.",
    )
    return payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_response_shaper.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add providers/response_shaper.py tests/test_response_shaper.py
git commit -m "feat: add EVDS observation cap and OHLCV downsampling to response shaper"
```

### Task 7: Wire shaping into the unified server

**Files:**
- Modify: `unified_mcp_server.py`

- [ ] **Step 1: Import the shaper**

After line 27 (`from providers.market_router import market_router`) add:
```python
from providers.response_shaper import strip_nulls, cap_evds_payload, downsample_ohlcv
```

- [ ] **Step 2: Apply strip_nulls at every tool return**

For each of the 28 `@app.tool` functions, wrap the routed result. Pattern — change:
```python
        return await market_router.get_quick_info(...)
```
to:
```python
        return strip_nulls(await market_router.get_quick_info(...))
```
Apply to EVERY `return await market_router.<method>(...)` inside `unified_mcp_server.py` tool bodies (use grep to find them all: `grep -n "return await market_router" unified_mcp_server.py`). Some tools build dicts locally before returning (e.g. `screen_funds`); wrap those final returns too: `return strip_nulls(result_dict)`.

- [ ] **Step 3: Apply caps to the two heavy tools**

In `get_historical_data` (around line 305), change the return to:
```python
        return strip_nulls(downsample_ohlcv(
            await market_router.get_historical_data(
                symbol, MarketType(market), period, start_date, end_date, adjust=adjust
            )
        ))
```

In `get_evds_data` (around line 1711), change the return to:
```python
        return strip_nulls(cap_evds_payload(
            await market_router.get_evds_data(
                action=action,
                category_id=category_id,
                datagroup_code=datagroup_code,
                keyword=keyword,
                scope=scope,
                lang=lang,
                series_code=series_code,
                series_codes=series_codes,
                period=period,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                aggregation=aggregation,
                formula=formula,
                decimals=decimals,
                dashboard_name=dashboard_name,
                dashboard_id=dashboard_id,
                limit=limit,
            )
        ))
```

- [ ] **Step 4: Lower the EVDS default limit 1000 → 100**

In the `get_evds_data` signature (~line 1682), change the `limit` field to:
```python
    limit: Annotated[Optional[int], Field(
        description=(
            "Max observations / records returned per series (payload safety cap). "
            "Default 100 keeps responses compact; raise it (max 5000) only when "
            "long history is genuinely needed."
        ),
        default=100,
        ge=1,
        le=5000
    )] = 100,
```

- [ ] **Step 5: Verify**

Run:
```bash
uv run python -c "from unified_mcp_server import app; print('Server OK')"
grep -c "strip_nulls(" unified_mcp_server.py
uv run python -m pytest tests/test_response_shaper.py -q
```
Expected: `Server OK`; strip_nulls count >= 28; shaper tests pass.

- [ ] **Step 6: Commit**

```bash
git add unified_mcp_server.py
git commit -m "feat: apply null stripping and size caps at all tool boundaries"
```

### Task 8: Actionable error contract

**Files:**
- Modify: `unified_mcp_server.py`
- Test: `tests/test_error_contract.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_error_contract.py`:
```python
"""Tests for the error classification helper in unified_mcp_server."""
import pytest
from fastmcp.exceptions import ToolError

from unified_mcp_server import classify_tool_error


def test_symbol_not_found_suggests_search():
    err = classify_tool_error(ValueError("No data found for ticker XYZX"), "Profile fetch")
    assert isinstance(err, ToolError)
    assert "search_symbol" in str(err)


def test_missing_evds_key_explains_setup():
    err = classify_tool_error(RuntimeError("EVDS_API_KEY is not configured"), "EVDS operation")
    assert "EVDS_API_KEY" in str(err)
    assert "evds3.tcmb.gov.tr" in str(err)


def test_rate_limit_suggests_retry():
    err = classify_tool_error(Exception("429 Too Many Requests"), "Quick info fetch")
    assert "retry" in str(err).lower()


def test_timeout_suggests_retry():
    err = classify_tool_error(TimeoutError("Read timed out"), "Historical data fetch")
    assert "retry" in str(err).lower()


def test_unknown_error_preserves_message_and_adds_hint():
    err = classify_tool_error(Exception("weird internal failure"), "Scanning")
    assert "weird internal failure" in str(err)
    assert "Try:" in str(err)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_error_contract.py -v`
Expected: FAIL with ImportError (`classify_tool_error` not defined)

- [ ] **Step 3: Implement the helper**

Add to `unified_mcp_server.py`, after the imports and before the first tool definition:
```python
def classify_tool_error(e: Exception, context: str) -> ToolError:
    """Map an exception to a ToolError whose message tells the LLM what to try next.

    Always returns (never raises); callers `raise classify_tool_error(e, "...")`.
    """
    msg = str(e)
    lower = msg.lower()

    if "evds_api_key" in lower:
        suggestion = (
            "Catalog actions (categories, datagroups, series_list, search, "
            "search_server, series_info, dashboards) work without a key; data "
            "actions need the EVDS_API_KEY env var (free key at "
            "https://evds3.tcmb.gov.tr)."
        )
    elif any(t in lower for t in ("not found", "no data", "invalid ticker", "unknown symbol", "delisted")):
        suggestion = "Verify the symbol with search_symbol first, and confirm the market parameter matches it."
    elif any(t in lower for t in ("429", "too many requests", "rate limit")):
        suggestion = "The data source is rate limiting. Retry once after a short wait; if it persists, narrow the query."
    elif any(t in lower for t in ("timed out", "timeout", "connection")):
        suggestion = "Transient network issue. Retry once; if it persists, the upstream source may be down."
    else:
        suggestion = "If the symbol or parameters look wrong, check the tool description for valid values."

    return ToolError(f"{context} failed: {msg} | Try: {suggestion}")
```

- [ ] **Step 4: Replace every generic wrapper**

Find all generic handlers: `grep -n 'raise ToolError(f"' unified_mcp_server.py`.
For each `raise ToolError(f"<Context> failed: {str(e)}")` replace with `raise classify_tool_error(e, "<Context>")`, e.g.:
```python
    except Exception as e:
        logger.exception(f"Error in get_profile for '{symbol}'")
        raise classify_tool_error(e, "Profile fetch")
```
Do NOT touch validation-specific `raise ToolError("...")` calls that carry their own message (e.g. `get_news` line ~709).

IMPORTANT: validation ToolErrors raised inside `try` blocks must not be re-wrapped. Where a tool raises ToolError inside its own try block, add a re-raise guard above the generic handler:
```python
    except ToolError:
        raise
    except Exception as e:
        ...
```

- [ ] **Step 5: Run tests and import check**

Run:
```bash
uv run python -m pytest tests/test_error_contract.py -v
uv run python -c "from unified_mcp_server import app; print('Server OK')"
```
Expected: 5 passed; `Server OK`

- [ ] **Step 6: Commit**

```bash
git add unified_mcp_server.py tests/test_error_contract.py
git commit -m "feat: actionable error contract via classify_tool_error"
```

### Task 9: EVDS routing — raise instead of returning error dicts

**Files:**
- Modify: `providers/market_router.py:2222-2298`
- Test: `tests/test_param_validation.py` (created here, extended in Task 10)

- [ ] **Step 1: Write failing tests**

Create `tests/test_param_validation.py`:
```python
"""Validation behavior tests for unified tools and EVDS routing."""
import pytest

from providers.market_router import market_router


@pytest.mark.asyncio
async def test_evds_datagroups_requires_category_id():
    with pytest.raises(ValueError, match="category_id"):
        await market_router.get_evds_data(action="datagroups")


@pytest.mark.asyncio
async def test_evds_series_requires_series_code():
    with pytest.raises(ValueError, match="series_code"):
        await market_router.get_evds_data(action="series")


@pytest.mark.asyncio
async def test_evds_unknown_action_raises():
    with pytest.raises(ValueError, match="Unknown EVDS action"):
        await market_router.get_evds_data(action="bogus")
```
If `pytest-asyncio` is not installed (check `uv run python -c "import pytest_asyncio"`), add it: `uv add --dev pytest-asyncio` and set `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` in `pyproject.toml` (create the section if missing; if using auto mode, drop the `@pytest.mark.asyncio` decorators).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_param_validation.py -v`
Expected: FAIL — currently these return payload dicts instead of raising.

- [ ] **Step 3: Convert error_message payloads to raises**

In `providers/market_router.py` `get_evds_data` (lines ~2222-2298), replace each
`payload = {"error_message": "<X> is required for action='<Y>'"}` branch with:
```python
            raise ValueError("<X> is required for action='<Y>'")
```
(keeping the original message text), and the final else branch with:
```python
            raise ValueError(f"Unknown EVDS action: {action}")
```
The surrounding `if/elif` structure simplifies, e.g.:
```python
        elif action == "datagroups":
            if category_id is None:
                raise ValueError("category_id is required for action='datagroups'")
            payload = await p.get_datagroups(category_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_param_validation.py tests/test_response_shaper.py -v`
Expected: all pass. (`classify_tool_error` in the tool's except block converts these ValueErrors into ToolErrors for the LLM.)

- [ ] **Step 5: Commit**

```bash
git add providers/market_router.py tests/test_param_validation.py pyproject.toml uv.lock
git commit -m "fix: EVDS routing raises on missing params instead of returning error payloads"
```

### Task 10: Up-front parameter validation in tool bodies

**Files:**
- Modify: `unified_mcp_server.py` (`get_evds_data`, `screen_securities`, `get_fund_data`, `get_technical_analysis`)
- Test: `tests/test_param_validation.py`

- [ ] **Step 1: Write failing tests (append to tests/test_param_validation.py)**

```python
from fastmcp.exceptions import ToolError

from unified_mcp_server import (
    validate_evds_params,
    validate_screen_params,
    fund_flags_warning,
    timeframe_warning,
)


def test_evds_validation_lists_required_params():
    with pytest.raises(ToolError, match="series_code"):
        validate_evds_params("series", {"series_code": None})
    # valid combo passes silently
    validate_evds_params("series", {"series_code": "TP.DK.USD.A.YTL"})
    validate_evds_params("categories", {})


def test_evds_validation_multi_series():
    with pytest.raises(ToolError, match="series_codes"):
        validate_evds_params("multi_series", {"series_codes": None})


def test_screen_rejects_preset_plus_custom_filters():
    with pytest.raises(ToolError, match="one of"):
        validate_screen_params(preset="value_stocks", custom_filters=[["eq", ["sector", "Technology"]]])
    validate_screen_params(preset="value_stocks", custom_filters=None)
    validate_screen_params(preset=None, custom_filters=[["eq", ["sector", "Technology"]]])


def test_fund_flags_warning_multi_fund():
    w = fund_flags_warning(is_multi=True, include_portfolio=True, include_performance=False)
    assert w is not None and "single-fund" in w
    assert fund_flags_warning(is_multi=False, include_portfolio=True, include_performance=True) is None
    assert fund_flags_warning(is_multi=True, include_portfolio=False, include_performance=False) is None


def test_timeframe_warning_for_stock_markets():
    w = timeframe_warning(market="bist", timeframe="1h")
    assert w is not None and "daily" in w.lower()
    assert timeframe_warning(market="bist", timeframe="1d") is None
    assert timeframe_warning(market="crypto_tr", timeframe="1h") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_param_validation.py -v`
Expected: new tests FAIL with ImportError.

- [ ] **Step 3: Implement the validators**

Add to `unified_mcp_server.py` near `classify_tool_error`:
```python
_EVDS_REQUIRED_PARAMS: Dict[str, List[str]] = {
    "categories": [],
    "datagroups": ["category_id"],
    "series_list": ["datagroup_code"],
    "search": ["keyword"],
    "search_server": ["keyword"],
    "series_info": ["series_code"],
    "dashboards": [],
    "dashboard": [],  # dashboard_name OR dashboard_id, checked below
    "series": ["series_code"],
    "multi_series": ["series_codes"],
    "datagroup_data": ["datagroup_code"],
}


def validate_evds_params(action: str, params: Dict[str, Any]) -> None:
    """Raise ToolError if required params for this EVDS action are missing."""
    required = _EVDS_REQUIRED_PARAMS.get(action)
    if required is None:
        raise ToolError(f"Unknown EVDS action '{action}'. | Try: one of {sorted(_EVDS_REQUIRED_PARAMS)}.")
    missing = [name for name in required if not params.get(name)]
    if missing:
        raise ToolError(
            f"action='{action}' requires {', '.join(missing)}. | Try: provide "
            f"{', '.join(missing)}; discover valid values via action='categories', "
            "'datagroups', 'series_list' or 'search'."
        )
    if action == "dashboard" and not (params.get("dashboard_name") or params.get("dashboard_id")):
        raise ToolError(
            "action='dashboard' requires dashboard_name or dashboard_id. "
            "| Try: list them via action='dashboards' first."
        )


def validate_screen_params(preset: Any, custom_filters: Any) -> None:
    """preset and custom_filters are mutually exclusive."""
    if preset is not None and custom_filters is not None:
        raise ToolError(
            "Provide only one of 'preset' or 'custom_filters', not both. "
            "| Try: drop custom_filters to use the preset, or drop preset to screen with custom filters."
        )


def fund_flags_warning(is_multi: bool, include_portfolio: bool, include_performance: bool) -> Optional[str]:
    """Warning text when single-fund-only flags are used in multi-fund mode."""
    if is_multi and (include_portfolio or include_performance):
        return (
            "include_portfolio/include_performance apply to single-fund queries only "
            "and were ignored in comparison mode. Query one fund at a time to get them."
        )
    return None


def timeframe_warning(market: str, timeframe: str) -> Optional[str]:
    """Warning when timeframe is ignored for stock markets (always daily)."""
    if market in ("bist", "us") and timeframe != "1d":
        return (
            f"timeframe='{timeframe}' is ignored for market='{market}': stock technical "
            "analysis is computed on daily data. Timeframe applies to crypto markets only."
        )
    return None
```

- [ ] **Step 4: Wire validators into the four tools**

In `get_evds_data`, as the FIRST statements of the body (before the try block):
```python
    validate_evds_params(action, {
        "category_id": category_id,
        "datagroup_code": datagroup_code,
        "keyword": keyword,
        "series_code": series_code,
        "series_codes": series_codes,
        "dashboard_name": dashboard_name,
        "dashboard_id": dashboard_id,
    })
```

In `screen_securities`, first statement of the body:
```python
    validate_screen_params(preset, custom_filters)
```

In `get_fund_data`, inside the try block after `is_multi` is computed, capture the result and attach the warning:
```python
        if is_multi or compare_mode:
            result = await market_router.compare_funds(symbol_list)
            warning = fund_flags_warning(is_multi or compare_mode, include_portfolio, include_performance)
            if warning:
                result.setdefault("warnings", []).append(warning)
            return strip_nulls(result)
```

In `get_technical_analysis`, capture the result and attach the warning:
```python
        result = await market_router.get_technical_analysis(symbol, MarketType(market), timeframe)
        warning = timeframe_warning(market, timeframe)
        if warning:
            result.setdefault("warnings", []).append(warning)
        return strip_nulls(result)
```

- [ ] **Step 5: Add the action→param map to the get_evds_data description**

Extend the `description=` in the `@app.tool` decorator of `get_evds_data` with:
```
"Required params by action: datagroups→category_id; series_list/datagroup_data→"
"datagroup_code; search/search_server→keyword; series/series_info→series_code; "
"multi_series→series_codes; dashboard→dashboard_name or dashboard_id."
```
(append as an extra string inside the existing parenthesized concatenation).

- [ ] **Step 6: Run the full new-test suite and import check**

Run:
```bash
uv run python -m pytest tests/test_param_validation.py tests/test_error_contract.py tests/test_response_shaper.py -v
uv run python -c "from unified_mcp_server import app; print('Server OK')"
```
Expected: all pass; `Server OK`

- [ ] **Step 7: Commit**

```bash
git add unified_mcp_server.py tests/test_param_validation.py
git commit -m "feat: up-front parameter validation with corrective messages"
```

### Task 11: Final verification and docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Tool count and server smoke check**

Run:
```bash
uv run python -c "
import asyncio
from unified_mcp_server import app
tools = asyncio.run(app.get_tools())
print(len(tools), 'tools')
assert len(tools) == 28, 'tool count changed!'
"
```
Expected: `28 tools`. (If `app.get_tools()` is not the right FastMCP API, use `app._tool_manager.list_tools()` or check fastmcp docs — the assertion on 28 is what matters.)

- [ ] **Step 2: Run the new test files plus whatever in tests/ collects cleanly**

Run: `uv run python -m pytest tests/test_response_shaper.py tests/test_error_contract.py tests/test_param_validation.py -q`
Expected: all pass.

- [ ] **Step 3: Update CLAUDE.md**

Add a short section under "Recent Major Updates":
```markdown
### LLM-UX Hardening + Legacy Removal (June 2026)
- **Legacy server removed**: `borsa_mcp_server.py` and the `borsa-mcp-legacy` entry point are gone; the 28-tool unified server is the only interface.
- **Response shaping** (`providers/response_shaper.py`): all tool responses are recursively null-stripped; `get_evds_data` observations are capped at 2,000/call (default `limit` now 100); `get_historical_data` auto-downsamples beyond 300 points. Truncation adds `meta: {truncated, guidance}`.
- **Actionable errors**: `classify_tool_error` maps failures to suggestions (unknown symbol → use search_symbol; missing EVDS_API_KEY → setup hint; rate limit/timeout → retry guidance).
- **Parameter validation**: EVDS action→required-param map enforced up front; `screen_securities` rejects preset+custom_filters; `get_fund_data` and `get_technical_analysis` warn when flags are ignored.
- **Tests** live in `tests/` (run `uv run python -m pytest tests/ -q`).
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md && git commit -m "docs: document LLM-UX hardening and legacy removal"
```
