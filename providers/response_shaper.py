"""
Response shaping for the unified MCP server.

Applied at tool boundaries in unified_mcp_server.py before payloads are
returned to the LLM. Removes null fields, caps oversized series, and attaches
truncation guidance. Never renames or restructures existing fields.
"""
from typing import Any, Dict


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


def _attach_meta(payload: Dict[str, Any], guidance: str) -> None:
    meta = payload.setdefault("meta", {})
    meta["truncated"] = True
    meta["guidance"] = guidance


def cap_evds_payload(payload: Dict[str, Any], max_total: int = 2000) -> Dict[str, Any]:
    """Cap EVDS observation lists ('gozlemler' or 'veriler') at max_total rows.

    Keeps the most recent rows (tail). Adds meta.truncated/guidance when fired.
    Mutates payload in place and returns it.
    """
    for key in ("gozlemler", "veriler"):
        rows = payload.get(key)
        if isinstance(rows, list) and len(rows) > max_total:
            original_total = len(rows)
            payload[key] = rows[-max_total:]
            payload["toplam_gozlem"] = len(payload[key])
            _attach_meta(
                payload,
                f"Response truncated to the most recent {max_total} of {original_total} observations. "
                "Narrow the date range (start_date/end_date), reduce the number of "
                "series, or use frequency/formula aggregation to fit more history.",
            )
    return payload


def drop_allnull_statement_rows(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove financial-statement line items whose values are null in every period.

    Operates on payload['statements'][*]['data'] ({item: [value per period]}).
    Partial rows are kept untouched so period alignment is preserved.
    Mutates payload in place and returns it.
    """
    statements = payload.get("statements")
    if not isinstance(statements, list):
        return payload
    for stmt in statements:
        data = stmt.get("data") if isinstance(stmt, dict) else None
        if isinstance(data, dict):
            stmt["data"] = {
                item: values for item, values in data.items()
                if not (isinstance(values, list) and values and all(v is None for v in values))
            }
    return payload


def downsample_ohlcv(payload: Dict[str, Any], max_points: int = 300) -> Dict[str, Any]:
    """Downsample the OHLCV row list under 'data' by stride so len <= max_points.

    The rows live under 'data'; 'data_points' is their integer count, and is kept
    consistent. (This function previously read 'data_points', got an int, failed
    its isinstance check and returned immediately — it never fired in production.)

    The final (most recent) point is always preserved exactly. Adds
    meta.truncated/guidance when fired. Mutates payload in place and returns it.
    """
    points = payload.get("data")
    if not isinstance(points, list) or len(points) <= max_points:
        return payload
    original_len = len(points)
    stride = -(-original_len // max_points)  # ceil division
    sampled = points[::stride]
    # Ensure the most recent point is exact; keep total within max_points.
    if sampled[-1] is not points[-1]:
        if len(sampled) >= max_points:
            sampled = sampled[:-1]  # drop last strided point to make room
        sampled.append(points[-1])
    payload["data"] = sampled
    payload["data_points"] = len(sampled)
    _attach_meta(
        payload,
        f"Series downsampled from {original_len} to {len(sampled)} points "
        f"(every {stride}th point; the most recent point is exact). For full "
        "resolution, request a shorter date range or a coarser interval.",
    )
    return payload
