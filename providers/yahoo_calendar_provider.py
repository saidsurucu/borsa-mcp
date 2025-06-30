"""
Yahoo Calendar Provider
This module is responsible for all interactions with the
Yahoo Finance economic calendar API, including fetching economic events.
"""
import httpx
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from borsa_models import (
    EkonomikTakvimSonucu, EkonomikOlay, EkonomikOlayDetayi
)

logger = logging.getLogger(__name__)

class YahooCalendarProvider:
    BASE_URL = "https://query1.finance.yahoo.com/ws/screeners/v1/finance/calendar-events"
    
    # Supported country codes
    SUPPORTED_COUNTRIES = {
        "US": "United States",
        "GB": "United Kingdom", 
        "JP": "Japan",
        "IN": "India",
        "CH": "Switzerland",
        "DE": "Germany",
        "FR": "France",
        "CA": "Canada",
        "AU": "Australia",
        "CN": "China",
        "KR": "South Korea",
        "BR": "Brazil",
        "IT": "Italy",
        "ES": "Spain",
        "NL": "Netherlands",
        "SE": "Sweden",
        "NO": "Norway",
        "DK": "Denmark",
        "FI": "Finland",
        "BE": "Belgium",
        "AT": "Austria",
        "IE": "Ireland",
        "PT": "Portugal",
        "GR": "Greece",
        "TR": "Turkey"
    }
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get appropriate headers for Yahoo Finance API request."""
        return {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://finance.yahoo.com',
            'Referer': 'https://finance.yahoo.com/calendar/economic',
            'Sec-Ch-Ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
        }
    
    def _date_to_timestamp(self, date_str: str) -> int:
        """Convert YYYY-MM-DD date string to Unix timestamp."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # Set to start of day (00:00:00)
            return int(dt.timestamp() * 1000)  # Yahoo API expects milliseconds
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")
    
    def _timestamp_to_datetime(self, timestamp: int) -> datetime:
        """Convert Unix timestamp (milliseconds) to datetime."""
        return datetime.fromtimestamp(timestamp / 1000)
    
    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Yahoo Finance economic calendar API."""
        try:
            headers = self._get_request_headers()
            
            response = await self._http_client.get(self.BASE_URL, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('finance', {}).get('error'):
                error_msg = data['finance']['error']
                raise Exception(f"Yahoo Finance API Error: {error_msg}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for economic calendar: {e}")
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error making request to economic calendar API: {e}")
            raise
    
    async def get_economic_calendar(
        self, 
        start_date: str, 
        end_date: str,
        high_importance_only: bool = True,
        country_filter: Optional[str] = None,
        count_per_day: int = 25
    ) -> EkonomikTakvimSonucu:
        """
        Get economic calendar events for the specified date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            high_importance_only: Only include high importance events
            country_filter: Comma-separated country codes (e.g., "US,GB,JP")
            count_per_day: Maximum events per day (default: 25)
        """
        try:
            # Validate date format and convert to timestamps
            start_timestamp = self._date_to_timestamp(start_date)
            end_timestamp = self._date_to_timestamp(end_date)
            
            # Validate date range
            if start_timestamp >= end_timestamp:
                return EkonomikTakvimSonucu(
                    start_date=start_date,
                    end_date=end_date,
                    economic_events=[],
                    total_events=0,
                    high_importance_only=high_importance_only,
                    error_message="Start date must be before end date"
                )
            
            # Validate country filter
            if country_filter:
                countries = [c.strip().upper() for c in country_filter.split(',')]
                invalid_countries = [c for c in countries if c not in self.SUPPORTED_COUNTRIES]
                if invalid_countries:
                    return EkonomikTakvimSonucu(
                        start_date=start_date,
                        end_date=end_date,
                        economic_events=[],
                        total_events=0,
                        high_importance_only=high_importance_only,
                        error_message=f"Unsupported country codes: {invalid_countries}. Supported: {list(self.SUPPORTED_COUNTRIES.keys())}"
                    )
            
            # Build API parameters
            params = {
                'startDate': start_timestamp,
                'endDate': end_timestamp,
                'countPerDay': min(max(count_per_day, 1), 100),  # Limit between 1-100
                'economicEventsHighImportanceOnly': str(high_importance_only).lower(),
                'modules': 'economicEvents',
                'lang': 'en-US',
                'region': 'US'
            }
            
            if country_filter:
                params['economicEventsRegionFilter'] = country_filter.upper()
            
            # Make API request
            data = await self._make_request(params)
            
            # Parse response
            finance_data = data.get('finance', {})
            result_data = finance_data.get('result', {})
            economic_events_data = result_data.get('economicEvents', [])
            
            # Process economic events
            all_events = []
            total_count = 0
            
            for day_data in economic_events_data:
                day_timestamp = day_data.get('timestamp', 0)
                day_date = self._timestamp_to_datetime(day_timestamp)
                timezone = day_data.get('timezone', 'America/New_York')
                
                day_events = []
                records = day_data.get('records', [])
                
                for record in records:
                    event_time = record.get('eventTime', day_timestamp)
                    
                    # Create event detail
                    event_detail = EkonomikOlayDetayi(
                        event_name=record.get('event', ''),
                        country_code=record.get('countryCode', ''),
                        country_name=self.SUPPORTED_COUNTRIES.get(record.get('countryCode', ''), ''),
                        event_time=self._timestamp_to_datetime(event_time),
                        period=record.get('period', ''),
                        actual=record.get('actual'),
                        prior=record.get('prior'),
                        forecast=record.get('forecast'),
                        revised_from=record.get('revisedFrom'),
                        description=record.get('description', '')
                    )
                    day_events.append(event_detail)
                
                # Create day event
                if day_events:
                    day_event = EkonomikOlay(
                        date=day_date.date(),
                        timezone=timezone,
                        event_count=len(day_events),
                        events=day_events
                    )
                    all_events.append(day_event)
                    total_count += len(day_events)
            
            return EkonomikTakvimSonucu(
                start_date=start_date,
                end_date=end_date,
                economic_events=all_events,
                total_events=total_count,
                high_importance_only=high_importance_only,
                country_filter=country_filter
            )
            
        except Exception as e:
            logger.error(f"Error getting economic calendar for {start_date} to {end_date}: {e}")
            return EkonomikTakvimSonucu(
                start_date=start_date,
                end_date=end_date,
                economic_events=[],
                total_events=0,
                high_importance_only=high_importance_only,
                country_filter=country_filter,
                error_message=str(e)
            )