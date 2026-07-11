"""
FRED CPI Provider — monthly consumer price indices for the US and the euro area.

Sourced from FRED's keyless CSV export. Two things this module refuses to do,
both learned the hard way in this repo (CLAUDE.md #5, #7):

  * accept any non-empty parse. An upstream that answers HTTP 200 with an HTML
    error page, a renamed column, or a truncated feed must fail loudly.
  * merge two sources into one series. FRED and the fallbacks use different base
    years, so a series assembled from both yields ratios that are silently wrong.
"""

import asyncio
import csv
import io
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import httpx
from borsapy.exceptions import DataNotAvailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    label: str
    start_year: int
    currency: str


@dataclass
class IndexSeries:
    """A monthly price index plus where it came from.

    `source` and `degraded` are not decoration: a caller must be able to see that
    an answer came from a fallback, and how fresh it is, rather than assume it.
    """
    region: str
    source: str
    values: Dict[str, float]          # "YYYY-MM" -> index level
    degraded: bool = False
    warnings: List[str] = field(default_factory=list)

    @property
    def first_month(self) -> str:
        return min(self.values)

    @property
    def last_month(self) -> str:
        return max(self.values)


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

MIN_OBSERVATIONS = 200
CACHE_TTL_SECONDS = 6 * 3600

# CPI/HICP land a few weeks after the month they cover, so in mid-July the newest
# published month is May -- two months back and perfectly healthy. Only a longer
# gap suggests the feed itself has stalled. (Eurostat's API sat at 2025-12 well
# into July 2026: seven months, unmistakably stale.)
MAX_PUBLICATION_LAG_MONTHS = 3


def parse_fred_csv(text: str, series_id: str) -> Dict[str, float]:
    """Parse FRED's `observation_date,<SERIES_ID>` CSV. Raise on anything else."""
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []

    if "observation_date" not in fieldnames or series_id not in fieldnames:
        raise ValueError(
            f"FRED response for {series_id} lacks the expected column: got "
            f"{fieldnames or 'no header'}. The endpoint may have changed or "
            f"returned an error page."
        )

    values: Dict[str, float] = {}
    for row in reader:
        raw = (row.get(series_id) or "").strip()
        if raw in ("", "."):          # FRED encodes a missing observation as '.'
            continue
        observation = (row.get("observation_date") or "").strip()
        if len(observation) < 7:
            continue
        values[observation[:7]] = float(raw)

    return values


def validate_series(
    values: Dict[str, float],
    expected_start_year: int,
    min_observations: int = MIN_OBSERVATIONS,
) -> None:
    """Reject a series that parsed but cannot be what we asked for."""
    if len(values) < min_observations:
        raise ValueError(
            f"Series has only {len(values)} observations, expected at least "
            f"{min_observations}. The feed looks truncated."
        )

    first = min(values)
    if int(first[:4]) > expected_start_year + 1:
        raise ValueError(
            f"Series starts at {first} but should start near {expected_start_year}. "
            f"The feed looks truncated."
        )

    for month, level in values.items():
        if not (level > 0) or level in (float("inf"), float("-inf")):
            raise ValueError(
                f"Series has a non-positive or non-finite level at {month}: {level}"
            )


def months_between(start: str, end: str) -> int:
    """Count month-to-month intervals. 2010-01 -> 2011-01 is 12."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    return (ey - sy) * 12 + (em - sm)


class FredCpiProvider:
    """US CPI-U and euro-area HICP, with validated parsing and provenance."""

    SERIES: Dict[str, SeriesSpec] = {
        "us": SeriesSpec(
            series_id="CPIAUCNS",
            label="US CPI-U, not seasonally adjusted (BLS via FRED)",
            start_year=1913,
            currency="USD",
        ),
        # Changing composition (EA11 -> ... -> EA19 -> EA20). NOT CP0000EZ19M086NEST,
        # which is frozen at 19 countries, excludes Croatia, and drifts from EA20.
        "eu": SeriesSpec(
            series_id="CP0000EZCCM086NEST",
            label="Euro area HICP, changing composition (Eurostat via FRED)",
            start_year=1996,
            currency="EUR",
        ),
    }

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, tuple] = {}          # region -> (fetched_at, IndexSeries)
        self._locks: Dict[str, asyncio.Lock] = {}   # region -> single-flight lock

    def _lock(self, region: str) -> asyncio.Lock:
        if region not in self._locks:
            self._locks[region] = asyncio.Lock()
        return self._locks[region]

    async def get_index_series(
        self, region: str, today: Optional[date] = None
    ) -> IndexSeries:
        if region not in self.SERIES:
            raise ValueError(
                f"Unknown region '{region}'. Supported: {sorted(self.SERIES)}."
            )

        # Single-flight: a cold start with concurrent callers makes one upstream
        # call, not N. This also protects the anonymous BLS quota (25/day/IP).
        async with self._lock(region):
            cached = self._cache.get(region)
            if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
                return cached[1]

            series = await self._fetch_primary(region)
            if series is None:
                series = await self._fetch_fallback(region)
            if series is None:
                raise DataNotAvailableError(
                    f"Could not fetch a valid {region.upper()} price index from "
                    f"FRED or its fallback."
                )

            self._annotate_freshness(series, today or date.today())
            self._cache[region] = (time.time(), series)
            return series

    async def _fetch_primary(self, region: str) -> Optional[IndexSeries]:
        spec = self.SERIES[region]
        try:
            response = await self._client.get(
                FRED_CSV_URL.format(series_id=spec.series_id)
            )
            response.raise_for_status()
            values = parse_fred_csv(response.text, spec.series_id)
            validate_series(values, expected_start_year=spec.start_year)
        except Exception as e:
            logger.warning(f"FRED primary fetch failed for {region}: {e}")
            return None

        return IndexSeries(
            region=region,
            source=f"FRED ({spec.series_id})",
            values=values,
        )

    async def _fetch_fallback(self, region: str) -> Optional[IndexSeries]:
        # Implemented in the next task. Until then there is no second leg.
        return None

    def _annotate_freshness(self, series: IndexSeries, today: date) -> None:
        """Staleness must be an observable fact, not an assumption.

        Measured in calendar months, not days. CPI and HICP are published a few
        weeks after the month they cover, so in mid-July the newest month on offer
        is May -- that is health, not staleness. Warning on every healthy call
        would just teach the reader to ignore warnings.
        """
        last = series.last_month
        current = f"{today.year}-{today.month:02d}"
        months_late = months_between(last, current)

        if months_late > MAX_PUBLICATION_LAG_MONTHS:
            series.warnings.append(
                f"Latest available observation is {last}, {months_late} months "
                f"before {current}. The source may be lagging or stale."
            )
