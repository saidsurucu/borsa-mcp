"""
Borsapy Calendar Provider
Provides economic calendar events via borsapy EconomicCalendar class.
Supports TR, US, EU, DE, GB, JP, CN countries with importance filtering.

borsapy's EconomicCalendar currently returns an empty frame for every country and
period, while doviz.com itself still publishes a full calendar, so this falls back
to parsing that page directly.
"""
import asyncio
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

import borsapy as bp
import httpx
from bs4 import BeautifulSoup

from models import (
    EkonomikTakvimSonucu, EkonomikOlay, EkonomikOlayDetayi
)

logger = logging.getLogger(__name__)

DOVIZ_CALENDAR_URL = "https://www.doviz.com/ekonomik-takvim"

# The page server-renders four tab panes; the month pane is the widest window on
# offer, so parsing all of them and de-duplicating gives maximum coverage.
CALENDAR_CONTAINERS = [
    "calendar-content-0",  # today
    "calendar-content-1",  # tomorrow
    "calendar-content-2",  # this week
    "calendar-content-3",  # this month
]

TURKISH_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}

# doviz.com labels importance as low/mid/high on the marker span.
DOVIZ_IMPORTANCE = {"low": "low", "mid": "medium", "high": "high"}

# The page names countries in Turkish; only these map onto the codes this tool
# accepts. Unmapped countries are still returned, just without a code, so an
# unfiltered query keeps showing them.
DOVIZ_COUNTRY_CODES = {
    "Türkiye": "TR",
    "ABD": "US",
    "Euro Bölgesi": "EU",
    "Almanya": "DE",
    "İngiltere": "GB",
    "Japonya": "JP",
    "Çin": "CN",
}


class BorsapyCalendarProvider:
    """Economic calendar via borsapy EconomicCalendar class."""

    # Supported countries (borsapy supports these 7)
    SUPPORTED_COUNTRIES = {"TR", "US", "EU", "DE", "GB", "JP", "CN"}

    # Country code to name mapping
    COUNTRY_MAPPING = {
        'TR': 'Türkiye',
        'US': 'ABD',
        'EU': 'Euro Bölgesi',
        'DE': 'Almanya',
        'GB': 'Birleşik Krallık',
        'JP': 'Japonya',
        'CN': 'Çin'
    }

    # Important keywords for market-moving events
    IMPORTANT_KEYWORDS = [
        # Turkish keywords
        'işsizlik', 'enflasyon', 'üretim', 'büyüme', 'faiz', 'merkez bankası', 'tüfe', 'gdp',
        # English keywords
        'unemployment', 'inflation', 'gdp', 'growth', 'interest', 'federal reserve',
        'employment', 'cpi', 'ppi', 'retail sales', 'manufacturing', 'nonfarm', 'payroll'
    ]

    def __init__(self):
        """Initialize calendar provider."""
        pass

    def _parse_countries(self, country_filter: Optional[str]) -> List[str]:
        """Parse country filter string to list of country codes."""
        if not country_filter:
            return ["TR", "US"]  # Default to Turkey and USA

        countries = []
        for code in country_filter.upper().split(','):
            code = code.strip()
            if code in self.SUPPORTED_COUNTRIES:
                countries.append(code)
            else:
                logger.warning(f"Unsupported country code: {code}. Supported: {self.SUPPORTED_COUNTRIES}")

        return countries if countries else ["TR", "US"]

    def _calculate_period(self, start_date: str, end_date: str) -> str:
        """Calculate period string for borsapy from date range."""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end_dt - start_dt).days + 1

            if days <= 1:
                return "1g"  # 1 day
            elif days <= 7:
                return "1w"  # 1 week
            elif days <= 30:
                return "1ay"  # 1 month
            else:
                return "1ay"  # Max 1 month for calendar
        except (ValueError, TypeError):
            return "1w"  # Default to 1 week

    @staticmethod
    def _parse_turkish_date(text: str) -> Optional[datetime]:
        """Parse a '06 Temmuz 2026' heading into a datetime."""
        m = re.match(r"(\d{1,2})\s+(\S+)\s+(\d{4})", text.strip())
        if not m:
            return None
        day, month_name, year = m.groups()
        month = TURKISH_MONTHS.get(month_name.lower())
        if not month:
            return None
        return datetime(int(year), month, int(day))

    async def _scrape_doviz_events(self) -> List[Dict]:
        """Parse doviz.com's economic calendar page into raw event dicts.

        The page is fully server-rendered -- every tab pane's rows are already in the
        HTML -- so a plain GET is enough; no browser or JS execution is needed.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(DOVIZ_CALENDAR_URL, headers=headers)
            resp.raise_for_status()
            html = resp.text

        def parse() -> List[Dict]:
            soup = BeautifulSoup(html, "html.parser")
            events: Dict[tuple, Dict] = {}

            for container_id in CALENDAR_CONTAINERS:
                container = soup.find(id=container_id)
                if not container:
                    continue

                # Panes are a flat run of [date heading, table, date heading, table...],
                # so a row's date is whichever heading most recently preceded it.
                current_date = None
                for child in container.find_all(["div"], recursive=False):
                    classes = child.get("class") or []

                    if "text-bold" in classes:
                        current_date = self._parse_turkish_date(child.get_text())
                        continue

                    table = child.find("table")
                    if table is None or current_date is None:
                        continue

                    # The served HTML omits <tbody> (browsers synthesize it), so select
                    # rows directly. Header rows use <th> and fall out of the td check.
                    for tr in table.find_all("tr"):
                        tds = tr.find_all("td")
                        if len(tds) < 7:
                            continue

                        marker = tr.find("span", class_="importance")
                        marker_classes = marker.get("class") if marker else []
                        importance = next(
                            (DOVIZ_IMPORTANCE[c] for c in marker_classes if c in DOVIZ_IMPORTANCE),
                            "low"
                        )

                        time_text = tds[0].get_text(strip=True)
                        country_name = tds[1].get_text(strip=True)
                        event_name = " ".join(tds[3].get_text(strip=True).split())

                        if not event_name:
                            continue

                        event_dt = current_date
                        m = re.match(r"(\d{1,2}):(\d{2})", time_text)
                        if m:
                            event_dt = current_date.replace(
                                hour=int(m.group(1)), minute=int(m.group(2))
                            )

                        def clean(td):
                            return td.get_text(strip=True) or None

                        key = (event_dt, country_name, event_name)
                        events[key] = {
                            "date": event_dt,
                            "time": time_text or None,
                            "country_code": DOVIZ_COUNTRY_CODES.get(country_name),
                            "country_name": country_name,
                            "event_name": event_name,
                            "importance": importance,
                            "actual": clean(tds[4]),
                            "forecast": clean(tds[5]),
                            "previous": clean(tds[6]),
                            "period": "",
                        }

            return list(events.values())

        # BeautifulSoup over ~1200 rows is CPU-bound; keep it off the event loop.
        return await asyncio.get_event_loop().run_in_executor(None, parse)

    async def get_economic_calendar(
        self,
        start_date: str,
        end_date: str,
        high_importance_only: bool = True,
        country_filter: Optional[str] = None
    ) -> EkonomikTakvimSonucu:
        """
        Get economic calendar events for the specified date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            high_importance_only: If True, only return high importance events
            country_filter: Comma-separated country codes (TR,US,EU,DE,GB,JP,CN)

        Returns:
            EkonomikTakvimSonucu with events grouped by date
        """
        try:
            countries = self._parse_countries(country_filter)
            period = self._calculate_period(start_date, end_date)

            logger.info(f"Fetching economic calendar for {start_date} to {end_date}, countries: {countries}")

            # Create calendar instance
            cal = bp.EconomicCalendar()

            # Determine importance filter
            importance_filter = "high" if high_importance_only else None

            all_raw_events = []
            actual_countries_covered = []

            # Fetch events for each country
            for country_code in countries:
                try:
                    # Get events from borsapy
                    df = cal.events(
                        period=period,
                        country=country_code,
                        importance=importance_filter
                    )

                    if df is not None and not df.empty:
                        # Convert DataFrame to list of events
                        for _, row in df.iterrows():
                            event_data = {
                                'date': row.get('Date') or row.get('date') or datetime.now(),
                                'time': str(row.get('Time', '')) if row.get('Time') else None,
                                'country_code': country_code,
                                'country_name': self.COUNTRY_MAPPING.get(country_code, country_code),
                                'event_name': str(row.get('Event', '')) or str(row.get('event', '')),
                                'importance': str(row.get('Importance', 'medium')).lower(),
                                'actual': str(row.get('Actual', '')) if row.get('Actual') else None,
                                'forecast': str(row.get('Forecast', '')) if row.get('Forecast') else None,
                                'previous': str(row.get('Previous', '')) if row.get('Previous') else None,
                                'period': ''  # Not available from borsapy
                            }
                            all_raw_events.append(event_data)

                        actual_countries_covered.append(country_code)
                        logger.info(f"Found {len(df)} events for {country_code}")
                    else:
                        logger.warning(f"No events found for country {country_code}")

                except Exception as e:
                    logger.error(f"Error fetching events for country {country_code}: {e}")
                    continue

            # borsapy's calendar feed has gone silent -- it returns an empty frame for
            # every country and period, while doviz.com still publishes the calendar.
            # Scrape the page directly rather than reporting an empty week.
            if not all_raw_events:
                logger.warning("borsapy calendar returned no events; scraping doviz.com")
                try:
                    scraped = await self._scrape_doviz_events()
                    all_raw_events = [
                        e for e in scraped if e["country_code"] in countries
                    ]
                    actual_countries_covered = sorted(
                        {e["country_code"] for e in all_raw_events}
                    )
                    logger.info(f"Scraped {len(all_raw_events)} events from doviz.com")
                except Exception as e:
                    logger.error(f"doviz.com calendar scrape failed: {e}")

            # Parse date range for filtering
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Group events by date
            events_by_date: Dict[str, List[EkonomikOlayDetayi]] = {}
            total_events = 0

            for event_data in all_raw_events:
                try:
                    # Get event date
                    event_date = event_data['date']
                    if isinstance(event_date, str):
                        event_date = datetime.strptime(event_date, "%Y-%m-%d")
                    elif hasattr(event_date, 'to_pydatetime'):
                        event_date = event_date.to_pydatetime()

                    # Check if event is within date range
                    if start_dt.date() <= event_date.date() <= end_dt.date():
                        # Filter by importance if requested
                        if high_importance_only and event_data.get('importance') != 'high':
                            continue

                        date_key = event_date.strftime('%Y-%m-%d')

                        if date_key not in events_by_date:
                            events_by_date[date_key] = []

                        # Create event detail
                        country_name = event_data['country_name']
                        description = f"{country_name} economic indicator: {event_data['event_name']}"

                        # Convert event_date to string for the model
                        event_time_str = event_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(event_date, 'strftime') else str(event_date)

                        event_detail = EkonomikOlayDetayi(
                            event_name=event_data['event_name'],
                            country_code=event_data['country_code'],
                            country_name=country_name,
                            event_time=event_time_str,
                            period=event_data['period'],
                            actual=event_data['actual'],
                            prior=event_data['previous'],
                            forecast=event_data['forecast'],
                            importance=event_data['importance'],
                            description=description
                        )

                        events_by_date[date_key].append(event_detail)
                        total_events += 1

                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue

            # Convert to final format
            all_events = []
            for date_key in sorted(events_by_date.keys()):
                day_events = events_by_date[date_key]

                # Calculate summary statistics
                high_importance_count = sum(1 for e in day_events if e.importance == 'high')
                event_types = list(set([e.event_name.split('(')[0].strip() for e in day_events]))
                countries_in_day = list(set([e.country_name for e in day_events]))

                day_event = EkonomikOlay(
                    date=date_key,
                    timezone='Europe/Istanbul',
                    event_count=len(day_events),
                    events=day_events,
                    high_importance_count=high_importance_count,
                    countries_involved=countries_in_day,
                    event_types=event_types[:10]
                )
                all_events.append(day_event)

            # Calculate summary statistics
            countries_covered = [self.COUNTRY_MAPPING.get(code, code) for code in actual_countries_covered]
            high_impact_events = sum(
                1 for event in all_events
                for detail in event.events
                if detail.importance == 'high'
            )

            # Extract major releases and market-moving events
            major_releases = []
            market_moving_events = []

            for event in all_events:
                for detail in event.events:
                    event_lower = detail.event_name.lower()
                    if any(keyword in event_lower for keyword in self.IMPORTANT_KEYWORDS):
                        if detail.importance == 'high':
                            market_moving_events.append(detail.event_name)
                        major_releases.append(detail.event_name)

            return EkonomikTakvimSonucu(
                start_date=start_date,
                end_date=end_date,
                economic_events=all_events,
                total_events=total_events,
                total_days=len(all_events),
                high_importance_only=high_importance_only,
                country_filter=','.join(countries),
                countries_covered=countries_covered,
                high_impact_events=high_impact_events,
                major_releases=list(set(major_releases))[:20],
                market_moving_events=list(set(market_moving_events))[:10],
                query_timestamp=datetime.now(),
                data_source='borsapy (doviz.com)',
                api_endpoint='bp.EconomicCalendar'
            )

        except Exception as e:
            logger.error(f"Error getting economic calendar for {start_date} to {end_date}: {e}")
            countries = self._parse_countries(country_filter)
            return EkonomikTakvimSonucu(
                start_date=start_date,
                end_date=end_date,
                economic_events=[],
                total_events=0,
                high_importance_only=high_importance_only,
                country_filter=','.join(countries),
                error_message=str(e),
                data_source='borsapy',
                api_endpoint='bp.EconomicCalendar'
            )
