"""Volume the source never published must not be reported as a number.

TradingView — which borsapy reaches for every BIST symbol — publishes no volume for
most BIST sub-indices (XHOLD, XULAS, XUSIN, ...). It says so in two different dialects,
and both of them arrived here looking like measurements:

  * a quote carries the sentinel ``1e100`` — TradingView's "no data" marker
  * a candle omits the volume field entirely, and borsapy substitutes ``0.0``
    (see its ``timescale_update`` handler: "Some symbols (e.g. XGIDA and other
    indices) return candles without a volume field")

Neither is an observation. ``0`` reads as *nothing traded in the BIST holding sector
today*, which is false — XHOLD's 49 constituents turned over ~15.8bn TL on the day this
was written. And ``1e100`` did worse than lie: ``HizliBilgi.volume`` is an
``Optional[int]``, so ``get_quote("XHOLD")`` died with a Pydantic ``int_parsing_size``
error and the sub-index was reported as a *failed symbol* — CLAUDE.md #15, a swallowed
upstream quirk laundered into a claim about the market.

XU100 and XBANK *do* carry real volume from the same feed, so this cannot key off "is
this an index". It keys off what the feed actually said, per symbol, per request.
"""
import math
from typing import Any, Dict, List, Optional

# TradingView's chart protocol uses 1e100 for "this symbol has no such series".
# Real BIST volume peaks around 1e10 lots (XU100 ~ 8e9); a TL-denominated figure
# stays under 1e13. Anything past 1e15 is a marker, not a measurement.
SENTINEL_THRESHOLD = 1e15

NO_VOLUME_WARNING = (
    "Volume is not published for this symbol by the upstream feed (TradingView), "
    "so it is reported as absent rather than as 0. Most BIST sub-indices "
    "(XHOLD, XULAS, XUSIN, ...) carry no volume series; XU100 and XBANK do. "
    "A zero here would mean 'nothing traded', which is not what the source said."
)


def sanitize_volume(value: Any) -> Optional[float]:
    """One volume value: the number, or None when the source published none.

    Zero survives: a single zero bar is a real observation (a halted stock, an
    untraded session). Only a whole series with no volume anywhere is evidence that
    the feed carries none — that judgement belongs to ``sanitize_series_volume``.
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    if abs(num) >= SENTINEL_THRESHOLD:
        return None
    return value if isinstance(value, int) else num


def sanitize_series_volume(
    rows: List[Dict[str, Any]],
    key: str = "volume",
) -> bool:
    """Clean a bar series' volume in place. Returns True if the feed published any.

    When every bar is zero or missing, the column is nulled out: that pattern is the
    feed saying "I have no volume for this symbol", and forwarding a wall of zeros
    turns its silence into a false statement. When some bars carry volume, individual
    zeros are kept — there they are data.
    """
    if not rows:
        return False

    published = False
    for row in rows:
        clean = sanitize_volume(row.get(key))
        row[key] = clean
        if clean:
            published = True

    if not published:
        for row in rows:
            row[key] = None

    return published
