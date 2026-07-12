"""One price contract across BIST, US, crypto, FX and TEFAS funds.

Every field this module declares is true, or it raises. The six markets disagree on
currency, price basis, adjustment, date format and row order — see the design doc
§3.1, where every cell was measured against live data rather than inferred from the
code. Downstream callers, above all `compare_assets`, must not have to know which
market they are holding.

The rule that earns this module its existence: a declared field is never guessed.
`ons` was a lira series labelled USD because a default was cheaper than a lookup.
"""
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timedelta
from typing import Any, List, Optional

# What a price actually is, per market.
PriceBasis = str   # "last" | "ask" | "nav"
Adjustment = str   # "split" | "none" | "n/a"

# A long weekend plus a national-holiday run. Beyond this, an asset is not merely
# untraded — it is suspended, and pricing a window from outside it is a fiction.
DEFAULT_MAX_STALENESS_DAYS = 10


class StalePriceError(Exception):
    """No observation close enough to the requested date to be usable."""


def normalize_date(value: Any) -> str:
    """Reduce any market's date to a plain YYYY-MM-DD session date.

    BIST emits "2026-06-01T00:00:00" (naive; the T00:00 is a round-trip artifact,
    not a real timestamp — the date is the Istanbul session date). US emits
    "2024-06-10T00:00:00-04:00" (tz-aware New York). FX and funds emit date-only.
    Crypto emits a UTC-midnight datetime, and the UTC day IS the session day —
    converting it to Istanbul would roll it forward and pick the wrong bar at a
    window boundary.

    In every case the calendar date as written is already the session date, so the
    correct normalization is to take it and drop the time. Never convert the zone.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, _date):
        return value.isoformat()

    text = str(value).strip()
    head = text[:10]
    try:
        datetime.strptime(head, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"unparseable date: {value!r}") from exc
    return head


@dataclass(frozen=True)
class Bar:
    date: str                        # YYYY-MM-DD, session date
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None   # float: 6.779 BTC is not 6


@dataclass(frozen=True)
class SeriesMeta:
    symbol: str
    market: str
    currency: str            # "TRY" | "USD" — declared, never assumed
    price_basis: PriceBasis
    adjustment: Adjustment
    source: str
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        for name in ("currency", "price_basis", "adjustment", "source"):
            if not getattr(self, name):
                raise ValueError(
                    f"SeriesMeta.{name} must be declared; guessing a default is how "
                    "a lira series ends up labelled USD"
                )


@dataclass(frozen=True)
class CanonicalSeries:
    meta: SeriesMeta
    bars: List[Bar]

    def __post_init__(self):
        object.__setattr__(self, "bars", sorted(self.bars, key=lambda b: b.date))

    def first_on_or_after(
        self, target: str, max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS
    ) -> Bar:
        """The first tradable bar at or after `target` — the START of a window.

        Asymmetric with `last_on_or_before` on purpose: you cannot buy on a Saturday
        at Friday's already-passed close.
        """
        for bar in self.bars:                       # ascending, guaranteed
            if bar.date >= target:
                self._check_gap(bar.date, target, max_staleness_days)
                return bar
        raise StalePriceError(
            f"{self.meta.symbol}: no observation on or after {target}"
        )

    def last_on_or_before(
        self, target: str, max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS
    ) -> Bar:
        """The last bar at or before `target` — the END of a window."""
        for bar in reversed(self.bars):
            if bar.date <= target:
                self._check_gap(bar.date, target, max_staleness_days)
                return bar
        raise StalePriceError(
            f"{self.meta.symbol}: no observation on or before {target}"
        )

    @staticmethod
    def _check_gap(found: str, target: str, max_days: int) -> None:
        gap = abs(
            (datetime.strptime(found, "%Y-%m-%d")
             - datetime.strptime(target, "%Y-%m-%d")).days
        )
        if gap > max_days:
            raise StalePriceError(
                f"nearest observation is {found}, {gap} days from {target} "
                f"(limit {max_days}). The asset is likely suspended or delisted; "
                "using it would silently price the window from outside it."
            )
