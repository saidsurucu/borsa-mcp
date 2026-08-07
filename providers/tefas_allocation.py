"""Shaping for TEFAS fund allocation.

The fetching lives in borsapy (>=0.11.0): `Fund.allocation` and
`Fund.allocation_history()` hit TEFAS's `dagilimSiraliGetirT` JSON endpoint and
own everything upstream-specific — the one-month window cap, the HTTP 429
backoff, the YAT/EMK/BYF universe probe, and the verified code->label map.
This module only turns the DataFrame they return into the tool's response
shape, so there is no HTTP here and nothing to keep in sync with TEFAS.

borsapy leaves `asset_type` as None for a handful of rare codes whose Turkish
labels could not be verified against TEFAS's own rendering. That None is
carried through as `label: null` and reported in a warning rather than being
backfilled with a guess — a wrong label on a right number is undetectable
downstream (CLAUDE.md #14).
"""

from typing import Any, Dict, List

import pandas as pd


def rows_from_frame(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Group borsapy's allocation frame into one entry per publication date.

    Args:
        df: Frame with columns Date, code, asset_type, asset_name, weight.

    Returns:
        [{date, allocation: [{code, label, weight}]}], oldest date first,
        heaviest holding first within each date.
    """
    if df is None or df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for stamp, group in df.groupby("Date", sort=True):
        allocation = [
            {
                "code": record["code"],
                # NaN, not None, is what pandas puts in an object column with
                # missing values — `or None` would also swallow a legitimate
                # empty string, so test for nullness explicitly.
                "label": (
                    None if pd.isna(record["asset_type"]) else record["asset_type"]
                ),
                "weight": float(record["weight"]),
            }
            for record in group.to_dict("records")
        ]
        allocation.sort(key=lambda a: abs(a["weight"]), reverse=True)
        rows.append({"date": str(stamp)[:10], "allocation": allocation})

    return rows


def to_matrix(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten a series of allocations into one row per date, one column per asset.

    A list of nested lists renders as raw JSON stuffed inside a TSV cell, which
    is both unreadable and expensive. A date x asset matrix is the shape the
    question "did this fund rotate into gold?" actually wants, and the markdown
    renderer turns homogeneous dicts into a clean table.

    Columns are labels where a verified one exists, otherwise the raw code, so
    an unlabeled asset is still visible and still traceable.
    """
    columns: List[str] = []
    for row in rows:
        for item in row.get("allocation", []):
            name = item["label"] or item["code"]
            if name not in columns:
                columns.append(name)

    matrix = []
    for row in rows:
        weights = {
            (item["label"] or item["code"]): item["weight"]
            for item in row.get("allocation", [])
        }
        # Every row carries every column so the table stays rectangular; absent
        # holdings are 0, which is what "not held that day" means here.
        entry = {"date": row["date"]}
        entry.update({name: weights.get(name, 0.0) for name in columns})
        matrix.append(entry)
    return matrix


def unlabeled_codes(rows: List[Dict[str, Any]]) -> List[str]:
    """Asset codes present in the data that borsapy has no verified label for."""
    seen = []
    for row in rows:
        for item in row.get("allocation", []):
            if item["label"] is None and item["code"] not in seen:
                seen.append(item["code"])
    return sorted(seen)
