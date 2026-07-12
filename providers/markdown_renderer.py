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

# String fields at least this long render as a markdown body, not a cell.
PROSE_MIN_CHARS = 200


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
        work = dict(payload)
        notes: List[str] = []
        meta = work.pop("meta", None)
        if isinstance(meta, dict) and meta.get("guidance"):
            notes.append(str(meta["guidance"]))
        warnings = work.pop("warnings", None)
        if isinstance(warnings, list):
            notes.extend(str(w) for w in warnings)
        # Hoist nested metadata.warnings (multi-ticker failures, etc.) to blockquotes.
        # Shallow-copy the metadata dict so we never mutate the caller's payload.
        if isinstance(work.get("metadata"), dict):
            meta_copy = dict(work["metadata"])
            nested_warnings = meta_copy.pop("warnings", None)
            if isinstance(nested_warnings, list):
                notes.extend(str(w) for w in nested_warnings)
            work["metadata"] = meta_copy
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


def _render_value(key: str, value: Any, level: int) -> List[str]:
    if isinstance(value, dict):
        heading = "#" * min(level, 6)
        return [f"{heading} {key}"] + _render_dict(value, level + 1)
    if isinstance(value, list):
        if not value:
            # Omit rather than announce a failure. A nested empty list is a
            # presentation detail; saying "Sonuç bulunamadı." here printed a
            # failure message next to perfectly good sibling data. Explaining an
            # empty result is the provider's job (warnings), not the renderer's.
            # A wholly empty payload is still reported, in render_markdown().
            return []
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
