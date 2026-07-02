# Markdown/TSV Tool Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All 28 MCP tools return compact markdown text (TSV code blocks for row lists) instead of JSON dicts, cutting token cost for LLM consumers.

**Architecture:** A new pure module `providers/markdown_renderer.py` exposes `render_markdown(payload: dict) -> str`. It is applied as the final step at every tool boundary in `unified_mcp_server.py`, after the existing shapers (`strip_nulls`, `cap_evds_payload`, `downsample_ohlcv`, `drop_allnull_statement_rows`), which stay unchanged. Spec: `docs/superpowers/specs/2026-07-02-markdown-output-design.md`.

**Tech Stack:** Python 3, stdlib only (json). Tests with pytest. Run everything via `uv run`.

## Global Constraints

- The renderer must NEVER raise; on any internal error it returns `json.dumps(payload, ensure_ascii=False, default=str)`.
- Integers are never abbreviated (no K/M/B) so the LLM can do arithmetic.
- Floats: at most 4 decimal places, trailing zeros stripped; ratio-like keys (containing `oran`, `ratio`, `yield`, `pct`, `change`, `yuzde`, `getiri`, case-insensitive) get 2 decimal places.
- Tabs/newlines inside TSV cell values are replaced with a single space.
- `meta.truncated`/`meta.guidance` and `warnings` must survive as `> Not: ...` blockquote lines at the end of the output (the LLM must still see truncation guidance).
- Empty top-level result → the literal line `Sonuç bulunamadı.`
- Existing router-level tests must stay green: `uv run python -m pytest tests/ -q --ignore=tests/adhoc`.
- Do not modify `providers/response_shaper.py` or `providers/market_router.py`.

---

### Task 1: Renderer core — number formatting, sanitization, flat dict rendering

**Files:**
- Create: `providers/markdown_renderer.py`
- Test: `tests/test_markdown_renderer.py`

**Interfaces:**
- Produces: `render_markdown(payload: Dict[str, Any]) -> str` (public), `fmt_number(value: Any, key: str = "") -> str`, `_sanitize_cell(value: Any, key: str = "") -> str` (used by Task 2 table code).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_markdown_renderer.py`:

```python
"""Tests for the markdown/TSV tool-output renderer."""
from providers.markdown_renderer import render_markdown, fmt_number


# --- fmt_number ---

def test_fmt_number_strips_float_noise():
    assert fmt_number(45.79999999999999) == "45.8"


def test_fmt_number_max_4_decimals():
    assert fmt_number(1.123456789) == "1.1235"


def test_fmt_number_integers_untouched():
    assert fmt_number(12500000) == "12500000"


def test_fmt_number_ratio_keys_get_2_decimals():
    assert fmt_number(3.14159, key="fk_orani") == "3.14"
    assert fmt_number(5.0, key="dividendYield") == "5"
    assert fmt_number(1.239, key="pct_change") == "1.24"


def test_fmt_number_tiny_floats_keep_significance():
    # crypto micro-prices must not collapse to "0"
    assert fmt_number(0.00001234) != "0"


def test_fmt_number_non_numeric_passthrough():
    assert fmt_number("GARAN") == "GARAN"
    assert fmt_number(True) == "True"


# --- flat dict rendering ---

def test_render_scalar_fields_as_key_value_lines():
    out = render_markdown({"symbol": "GARAN", "price": 45.79999999999999, "volume": 12500000})
    assert "symbol: GARAN" in out
    assert "price: 45.8" in out
    assert "volume: 12500000" in out


def test_render_empty_payload():
    assert render_markdown({}) == "Sonuç bulunamadı."


def test_render_never_raises():
    class Weird:
        def __str__(self):
            raise RuntimeError("boom")
    out = render_markdown({"x": Weird()})
    assert isinstance(out, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'providers.markdown_renderer'`

- [ ] **Step 3: Write the implementation**

Create `providers/markdown_renderer.py`:

```python
"""Markdown/TSV renderer for tool outputs.

Applied as the last step at tool boundaries in unified_mcp_server.py,
after response_shaper. Converts shaped dict payloads into compact
markdown text: scalar fields as `key: value` lines, homogeneous dict
lists as TSV code blocks. Never raises — falls back to compact JSON.

Design: docs/superpowers/specs/2026-07-02-markdown-output-design.md
"""
import json
import math
from typing import Any, Dict, List

RATIO_KEY_HINTS = ("oran", "ratio", "yield", "pct", "change", "yuzde", "getiri")

EMPTY_RESULT_LINE = "Sonuç bulunamadı."


def fmt_number(value: Any, key: str = "") -> str:
    """Compact string form of a value. Floats capped at 4 decimals
    (2 for ratio-like keys), trailing zeros stripped; ints untouched."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if math.isnan(value) or math.isinf(value):
        return str(value)
    key_l = key.lower()
    decimals = 2 if any(h in key_l for h in RATIO_KEY_HINTS) else 4
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    if (text == "0" or text == "-0") and value != 0:
        # Tiny magnitudes (crypto micro-prices): keep significance instead.
        text = f"{value:.6g}"
    return text or "0"


def _sanitize_cell(value: Any, key: str = "") -> str:
    """Cell-safe text: numbers via fmt_number, containers as compact JSON,
    tabs/newlines collapsed to spaces."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = fmt_number(value, key)
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def render_markdown(payload: Dict[str, Any]) -> str:
    """Render a shaped tool payload as compact markdown. Never raises."""
    try:
        body = _render_dict(payload, level=2)
        text = "\n".join(body).strip()
        return text or EMPTY_RESULT_LINE
    except Exception:
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            return str(payload)


def _render_dict(d: Dict[str, Any], level: int) -> List[str]:
    lines: List[str] = []
    for key, value in d.items():
        lines.extend(_render_value(str(key), value, level))
    return lines


def _render_value(key: str, value: Any, level: int) -> List[str]:
    # Task 2 extends this for dicts and lists.
    return [f"{key}: {_sanitize_cell(value, key)}"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: all PASS. (`test_render_never_raises`: `str(Weird())` raises inside `_sanitize_cell`, caught by `render_markdown`; the JSON fallback's `default=str` raises too, caught again; the final `str(payload)` uses `dict.__repr__` → `object.__repr__` for `Weird`, which does not raise.)

- [ ] **Step 5: Commit**

```bash
git add providers/markdown_renderer.py tests/test_markdown_renderer.py
git commit -m "feat(renderer): markdown renderer core with number formatting"
```

---

### Task 2: TSV tables, scalar lists, nested dicts

**Files:**
- Modify: `providers/markdown_renderer.py` (replace `_render_value`)
- Test: `tests/test_markdown_renderer.py` (append)

**Interfaces:**
- Consumes: `fmt_number`, `_sanitize_cell` from Task 1.
- Produces: full generic rendering — `_render_table(rows: List[dict]) -> List[str]` and the extended `_render_value`. Task 3 relies on `_render_table` for the statement matrix.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_markdown_renderer.py`:

```python
# --- TSV tables and containers ---

def test_list_of_dicts_renders_tsv_block():
    out = render_markdown({"data_points": [
        {"date": "2026-06-30", "close": 45.8, "volume": 12500000},
        {"date": "2026-07-01", "close": 46.2, "volume": 9800000},
    ]})
    assert "```tsv" in out
    assert "date\tclose\tvolume" in out
    assert "2026-06-30\t45.8\t12500000" in out
    assert out.count("```") == 2


def test_table_columns_are_union_of_keys():
    out = render_markdown({"rows": [
        {"a": 1, "b": 2},
        {"a": 3, "c": 4},
    ]})
    assert "a\tb\tc" in out
    # missing values are empty cells
    assert "3\t\t4" in out


def test_table_cells_sanitize_tabs_and_newlines():
    out = render_markdown({"rows": [
        {"name": "line1\nline2", "note": "tab\there"},
        {"name": "x", "note": "y"},
    ]})
    assert "line1 line2\ttab here" in out


def test_single_dict_list_renders_as_nested_not_table():
    out = render_markdown({"results": [{"symbol": "GARAN", "price": 45.8}]})
    assert "```tsv" not in out
    assert "symbol: GARAN" in out


def test_scalar_list_renders_inline():
    out = render_markdown({"tickers": ["GARAN", "AKBNK", "THYAO"]})
    assert "tickers: GARAN, AKBNK, THYAO" in out


def test_empty_list_renders_empty_marker():
    out = render_markdown({"results": []})
    assert "results: Sonuç bulunamadı." in out


def test_nested_dict_renders_subheading():
    out = render_markdown({"symbol": "GARAN", "valuation": {"pe": 5.2, "pb": 1.1}})
    assert "## valuation" in out
    assert "pe: 5.2" in out


def test_deep_nesting_increases_heading_level():
    out = render_markdown({"a": {"b": {"c": 1}}})
    assert "## a" in out
    assert "### b" in out
    assert "c: 1" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: the new tests FAIL (everything currently renders as one `key: value` line).

- [ ] **Step 3: Implement**

In `providers/markdown_renderer.py`, replace `_render_value` and add `_render_table`:

```python
def _render_value(key: str, value: Any, level: int) -> List[str]:
    if isinstance(value, dict):
        heading = "#" * min(level, 6)
        return [f"{heading} {key}"] + _render_dict(value, level + 1)
    if isinstance(value, list):
        if not value:
            return [f"{key}: {EMPTY_RESULT_LINE}"]
        if all(isinstance(item, dict) for item in value):
            if len(value) == 1:
                heading = "#" * min(level, 6)
                return [f"{heading} {key}"] + _render_dict(value[0], level + 1)
            return [f"{'#' * min(level, 6)} {key}"] + _render_table(value)
        if all(not isinstance(item, (dict, list)) for item in value):
            joined = ", ".join(_sanitize_cell(item, key) for item in value)
            return [f"{key}: {joined}"]
        # heterogeneous / list of lists: compact JSON fallback for the subtree
        return [f"{key}: {_sanitize_cell(value, key)}"]
    return [f"{key}: {_sanitize_cell(value, key)}"]


def _render_table(rows: List[Dict[str, Any]]) -> List[str]:
    columns: List[str] = []
    for row in rows:
        for col in row:
            if col not in columns:
                columns.append(col)
    lines = ["```tsv", "\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_sanitize_cell(row.get(col), col) for col in columns))
    lines.append("```")
    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add providers/markdown_renderer.py tests/test_markdown_renderer.py
git commit -m "feat(renderer): TSV tables, scalar lists, nested headings"
```

---

### Task 3: meta/warnings blockquotes, prose body passthrough, financial-statement matrix

**Files:**
- Modify: `providers/markdown_renderer.py`
- Test: `tests/test_markdown_renderer.py` (append)

**Interfaces:**
- Consumes: `_render_table`, `_render_dict`, `_sanitize_cell` from Tasks 1–2.
- Produces: final `render_markdown` behavior used by Task 4. No new public names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_markdown_renderer.py`:

```python
# --- meta / warnings / special cases ---

def test_meta_and_warnings_become_trailing_blockquotes():
    out = render_markdown({
        "symbol": "GARAN",
        "meta": {"truncated": True, "guidance": "Narrow the date range."},
        "warnings": ["ISCTR: boom"],
    })
    lines = out.splitlines()
    assert "> Not: Narrow the date range." in lines
    assert "> Not: ISCTR: boom" in lines
    # blockquotes come last
    assert lines[-1].startswith("> Not:")
    assert "## meta" not in out


def test_long_content_field_renders_as_body():
    body = "# ASELSAN\n\nŞirketimiz sözleşme imzalamıştır. " + "x" * 300
    out = render_markdown({"title": "ASELSAN KAP", "content": body, "total_pages": 1})
    assert "title: ASELSAN KAP" in out
    assert "content:" not in out
    assert "Şirketimiz sözleşme imzalamıştır." in out
    # body keeps its newlines (not cell-sanitized)
    assert "# ASELSAN\n" in out


def test_financial_statements_render_as_period_matrix():
    out = render_markdown({"statements": [{
        "symbol": "GARAN",
        "statement_type": "balance_sheet",
        "periods": ["2024", "2023"],
        "data": {
            "Total Assets": [100.0, 90.0],
            "Cash": [50.5, None],
        },
    }]})
    assert "Kalem\t2024\t2023" in out
    assert "Total Assets\t100\t90" in out
    assert "Cash\t50.5\t" in out
    assert "symbol: GARAN" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: the 3 new tests FAIL.

- [ ] **Step 3: Implement**

In `providers/markdown_renderer.py`:

1. Add the prose-body threshold constant near the top:

```python
# String fields at least this long render as a markdown body, not a cell.
PROSE_MIN_CHARS = 200
```

2. Replace `render_markdown` with:

```python
def render_markdown(payload: Dict[str, Any]) -> str:
    """Render a shaped tool payload as compact markdown. Never raises."""
    try:
        work = dict(payload)
        notes: List[str] = []
        meta = work.pop("meta", None)
        if isinstance(meta, dict) and meta.get("guidance"):
            notes.append(str(meta["guidance"]))
        warnings = work.pop("warnings", None)
        if isinstance(warnings, list):
            notes.extend(str(w) for w in warnings)
        body = _render_dict(work, level=2)
        for note in notes:
            body.append(f"> Not: {_sanitize_cell(note)}")
        text = "\n".join(body).strip()
        return text or EMPTY_RESULT_LINE
    except Exception:
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            return str(payload)
```

3. In `_render_dict`, intercept the statement shape and prose bodies. Replace `_render_dict` with:

```python
def _render_dict(d: Dict[str, Any], level: int) -> List[str]:
    lines: List[str] = []
    for key, value in d.items():
        if key == "statements" and _is_statement_list(value):
            for stmt in value:
                lines.extend(_render_statement(stmt, level))
            continue
        if isinstance(value, str) and len(value) >= PROSE_MIN_CHARS:
            lines.extend(["", value, ""])
            continue
        lines.extend(_render_value(str(key), value, level))
    return lines


def _is_statement_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(
            isinstance(s, dict)
            and isinstance(s.get("data"), dict)
            and isinstance(s.get("periods"), list)
            for s in value
        )
    )


def _render_statement(stmt: Dict[str, Any], level: int) -> List[str]:
    periods = [str(p) for p in stmt["periods"]]
    data: Dict[str, Any] = stmt["data"]
    lines: List[str] = []
    for key, value in stmt.items():
        if key in ("data", "periods"):
            continue
        lines.extend(_render_value(str(key), value, level))
    lines.extend(["```tsv", "\t".join(["Kalem"] + periods)])
    for item, values in data.items():
        cells = [_sanitize_cell(item)]
        row_values = values if isinstance(values, list) else [values]
        cells.extend(_sanitize_cell(v, item) for v in row_values)
        lines.append("\t".join(cells))
    lines.append("```")
    return lines
```

- [ ] **Step 4: Run the full renderer test file**

Run: `uv run python -m pytest tests/test_markdown_renderer.py -q`
Expected: all PASS (including Tasks 1–2 tests — regressions here mean the new `_render_dict` broke a generic path).

- [ ] **Step 5: Commit**

```bash
git add providers/markdown_renderer.py tests/test_markdown_renderer.py
git commit -m "feat(renderer): meta blockquotes, prose bodies, statement matrix"
```

---

### Task 4: Wire the renderer into all 28 tool boundaries

**Files:**
- Modify: `unified_mcp_server.py` (import + ~30 `return strip_nulls(...)` sites + `-> Dict[str, Any]:` tool annotations)
- Test: existing suite (`tests/`), no new test file

**Interfaces:**
- Consumes: `render_markdown(payload) -> str` from Task 3.
- Produces: every `@app.tool` function returns `str`. A module-level helper `def shape(payload: Dict[str, Any]) -> str` in `unified_mcp_server.py` wraps `render_markdown(strip_nulls(payload))`.

- [ ] **Step 1: Add the shape helper**

In `unified_mcp_server.py`, next to the existing response_shaper import (near the top), add the renderer import and helper:

```python
from providers.markdown_renderer import render_markdown
```

and after the `classify_tool_error` / validation helpers (around line 200, before the first `@app.tool`):

```python
def shape(payload: Dict[str, Any]) -> str:
    """Final tool-boundary step: strip nulls, then render compact markdown."""
    return render_markdown(strip_nulls(payload))
```

- [ ] **Step 2: Verify the call-site inventory before mass edit**

Run: `grep -c "return strip_nulls(" unified_mcp_server.py && grep -c ") -> Dict\[str, Any\]:" unified_mcp_server.py`
Expected: 30 call sites (some tools like `get_news`/`get_fund_data` have two return paths) and 28 annotations. If the counts differ, list them with `grep -n` and reconcile before continuing.

- [ ] **Step 3: Mass-replace call sites and annotations**

```bash
sed -i '' 's/return strip_nulls(/return shape(/g; s/) -> Dict\[str, Any\]:/) -> str:/g' unified_mcp_server.py
```

Then confirm nothing was missed and `strip_nulls` is still imported (used inside `shape`):

```bash
grep -n "return strip_nulls(" unified_mcp_server.py   # expected: no output
grep -n "strip_nulls" unified_mcp_server.py            # expected: import line + shape()
```

Note: the inner shapers stay where they are — e.g. `return shape(downsample_ohlcv(...))` and `return shape(cap_evds_payload(...))` are the correct final forms; sed produces them automatically since they were nested inside `strip_nulls(...)`.

- [ ] **Step 4: Import check and full test suite**

```bash
uv run python -c "from unified_mcp_server import app; print('Server OK')"
uv run python -m pytest tests/ -q --ignore=tests/adhoc
```
Expected: `Server OK`; all tests PASS (existing tests exercise `MarketRouter` dicts and helpers, not the tool boundary, so they should be untouched — investigate any failure, do not skip it).

- [ ] **Step 5: One end-to-end sanity check through FastMCP**

Run a live in-memory call to confirm the MCP text content is markdown, not JSON:

```bash
uv run python - <<'EOF'
import asyncio
from fastmcp import Client
from unified_mcp_server import app

async def main():
    async with Client(app) as client:
        res = await client.call_tool("get_screener_help", {"market": "bist"})
        text = res.content[0].text
        assert not text.lstrip().startswith("{"), "still JSON!"
        print(text[:500])

asyncio.run(main())
EOF
```
Expected: markdown output (key: value lines / tsv block), no leading `{`.

- [ ] **Step 6: Commit**

```bash
git add unified_mcp_server.py
git commit -m "feat(server): render all 28 tool outputs as markdown/TSV"
```

---

### Task 5: Token-savings measurement and docs

**Files:**
- Create: `tests/adhoc/measure_markdown_savings.py` (gitignored, local-only)
- Modify: `CLAUDE.md` (Recent Major Updates section)

**Interfaces:**
- Consumes: `render_markdown` and `strip_nulls`.
- Produces: a before/after size report (chars and ~tokens at 4 chars/token) for 4 representative payloads; a CLAUDE.md changelog entry.

- [ ] **Step 1: Write the measurement script**

Create `tests/adhoc/measure_markdown_savings.py`:

```python
"""Ad-hoc: compare JSON vs markdown rendering size on live payloads.

Local-only (tests/adhoc is gitignored). Makes real network calls.
Run: uv run python tests/adhoc/measure_markdown_savings.py
"""
import asyncio
import json

from providers.market_router import MarketRouter
from providers.response_shaper import strip_nulls, downsample_ohlcv, drop_allnull_statement_rows
from providers.markdown_renderer import render_markdown
from models.unified_base import MarketType, StatementType, PeriodType


async def main():
    router = MarketRouter()
    samples = {}

    hist = await router.get_historical_data("GARAN", MarketType.BIST, period="1y")
    samples["historical_1y"] = strip_nulls(downsample_ohlcv(hist))

    scr = await router.screen_securities(MarketType.US, preset="large_cap", limit=50)
    samples["screener_50"] = strip_nulls(scr)

    fin = await router.get_financial_statements(
        "GARAN", MarketType.BIST, StatementType.BALANCE_SHEET, PeriodType.ANNUAL, 5
    )
    samples["balance_sheet"] = strip_nulls(drop_allnull_statement_rows(fin))

    qi = await router.get_quick_info(["GARAN", "AKBNK", "THYAO", "TUPRS", "ASELS"], MarketType.BIST)
    samples["quick_info_5"] = strip_nulls(qi)

    print(f"{'payload':<16}{'json chars':>12}{'md chars':>12}{'saving':>9}")
    for name, payload in samples.items():
        j = len(json.dumps(payload, ensure_ascii=False, default=str))
        m = len(render_markdown(payload))
        print(f"{name:<16}{j:>12}{m:>12}{(1 - m / j) * 100:>8.1f}%")


asyncio.run(main())
```

- [ ] **Step 2: Run it and record results**

Run: `uv run python tests/adhoc/measure_markdown_savings.py`
Expected: a 4-row table; markdown should be meaningfully smaller on the row-list payloads (historical, screener). If a `screen_securities`/`get_financial_statements` router signature differs from the call above, check the signature in `providers/market_router.py` and adjust the script (it is ad-hoc, not part of the suite). Copy the printed table — it goes into the final report to the user.

- [ ] **Step 3: Update CLAUDE.md**

In `CLAUDE.md`, add a new entry at the TOP of the "Recent Major Updates" section:

```markdown
### Markdown/TSV Tool Output (July 2026)
- **All 28 tools now return markdown text instead of JSON** for token savings.
- New module `providers/markdown_renderer.py` (`render_markdown`): scalar fields as `key: value` lines, homogeneous dict lists as TSV code blocks, nested dicts as subheadings.
- Financial statements render as a `Kalem` × periods TSV matrix; long prose fields (news detail content) pass through as markdown body.
- Numbers: floats max 4 decimals (ratio-like keys 2), integers untouched (no K/M/B).
- `meta.truncated` guidance and `warnings` are preserved as trailing `> Not: ...` lines.
- Renderer never raises; unknown structures fall back to compact JSON. Applied at tool boundaries via `shape()` in `unified_mcp_server.py` (chain: `strip_nulls → existing shapers → render_markdown`).
- Design: `docs/superpowers/specs/2026-07-02-markdown-output-design.md`.
```

- [ ] **Step 4: Final full-suite run and commit**

```bash
uv run python -m pytest tests/ -q --ignore=tests/adhoc
git add CLAUDE.md
git commit -m "docs: document markdown/TSV tool output migration"
```
(`tests/adhoc/measure_markdown_savings.py` is gitignored and must NOT be committed.)
