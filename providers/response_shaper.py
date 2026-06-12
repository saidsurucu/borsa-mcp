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
