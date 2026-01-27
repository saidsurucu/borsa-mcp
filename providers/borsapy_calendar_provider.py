"""
Borsapy Calendar Provider
Provides economic calendar events via borsapy EconomicCalendar class.
Supports TR, US, EU, DE, GB, JP, CN countries with importance filtering.
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

import borsapy as bp

from models import (
    EkonomikTakvimSonucu, EkonomikOlay, EkonomikOlayDetayi
)

logger = logging.getLogger(__name__)


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
