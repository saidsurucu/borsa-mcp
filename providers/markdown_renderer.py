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
