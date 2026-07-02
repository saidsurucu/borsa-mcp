# Markdown/TSV Tool Output Design

**Date:** 2026-07-02
**Status:** Approved
**Goal:** Convert all 28 unified MCP tool outputs from JSON dicts to compact markdown text (TSV tables for row lists) to reduce token cost for LLM consumers.

## Motivation

Every tool currently returns a dict that FastMCP serializes to JSON. Row-list-heavy tools (historical data, screeners, financial statements, EVDS) repeat key names on every row, which is expensive in tokens. A markdown rendering with TSV code blocks removes that repetition entirely. The server's only consumer is an LLM reading text content, so losing MCP structured content is acceptable.

## Scope

All 28 tools. Every tool boundary in `unified_mcp_server.py` returns a `str` instead of a dict.

## Architecture

New module: `providers/markdown_renderer.py` with one public function:

```python
def render_markdown(payload: dict) -> str
```

The existing shaping chain gains one final step:

```
strip_nulls → (cap_evds_payload / downsample_ohlcv / drop_allnull_statement_rows) → render_markdown → str
```

Existing shapers in `providers/response_shaper.py` are unchanged; the renderer is applied last at each tool boundary.

## Generic Render Rules

| Input shape | Output |
|---|---|
| Scalar field | `key: value` line |
| Homogeneous list of dicts (2+ rows) | TSV code block (```` ```tsv ````); columns = union of keys across rows, missing values = empty cell |
| Nested dict | `## key` subheading + recursive render |
| Single-element list or scalar list | `key: a, b, c` line |
| Empty result list | `Sonuç bulunamadı.` line (matches existing Turkish payload language) |

Additional rules:

- **Cell sanitization:** tab and newline characters inside cell values are replaced with a single space.
- **meta / warnings preservation:** `meta.truncated` + `meta.guidance` and any `warnings` entries are rendered at the end of the output as `> Not: ...` blockquote lines so the LLM still sees truncation guidance.
- **Safe fallback:** the renderer never raises. If it encounters a structure it cannot render (deep heterogeneous nesting), it embeds that subtree as a compact JSON string.

## Special-Case Renderers

1. **Financial statements** (`statements[*].data = {line_item: [value per period]}`): rendered as a single TSV matrix — first column is the line item, remaining columns are the periods. The generic renderer would produce an ugly per-item dump for this shape.
2. **EVDS observations** (`gozlemler` / `veriler`): already a list of dicts, generic TSV suffices; series metadata is rendered as `key: value` lines above the table.
3. **News detail** (`get_news` with `news_id`): content is long prose, passed through as a plain markdown body, never tabulated.

## Number Formatting

One helper `fmt_number()` inside the renderer:

- Floats: at most 4 significant decimal places (`45.79999999999999` → `45.8`).
- Ratio/percentage-style fields: 2 decimal places. Identified by a field-name heuristic (key contains `oran`, `ratio`, `yield`, `pct`, `change`, `yuzde`, `getiri`).
- Integers (volume, market cap, etc.): untouched — no K/M/B abbreviation, so the LLM can do arithmetic safely.

## Error Handling

- The `classify_tool_error` / `ToolError` flow is unchanged; errors are raised before rendering.
- The renderer itself never raises (see safe fallback above).

## Testing

- New `tests/test_markdown_renderer.py`: scalar fields, TSV table generation, nested dicts, empty results, number rounding, tab/newline sanitization, financial-statement matrix, meta/warnings blockquote.
- Existing curated tests (`uv run python -m pytest tests/ -q`) must stay green; tests asserting on dict payloads are updated to assert on the rendered string.
- Verification step: measure before/after token counts on 3–4 representative payloads (1y historical, 50-result screener, balance sheet, EVDS series) and report the savings.

## Out of Scope

- MCP structured output / output schemas (intentionally dropped).
- Per-tool handcrafted formats beyond the three special cases above.
- Changing provider or router return shapes — dicts flow unchanged until the tool boundary.
