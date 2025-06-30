"""
Dovizcom Calendar Provider
This module is responsible for all interactions with the
Doviz.com economic calendar API, including fetching Turkish economic events.
"""
import httpx
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from models import (
    EkonomikTakvimSonucu, EkonomikOlay, EkonomikOlayDetayi
)

logger = logging.getLogger(__name__)

class DovizcomCalendarProvider:
    BASE_URL = "https://www.doviz.com/calendar/getCalendarEvents"
    
    # Turkish importance levels mapping
    IMPORTANCE_MAPPING = {
        "low": "düşük",
        "mid": "orta", 
        "high": "yüksek"
    }
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get appropriate headers for Dovizcom API request."""
        return {
            'authorization': 'Bearer d00c1214cbca6a7a1b4728a8cc78cd69ba99e0d2ddb6d0687d2ed34f6a547b48',
            'accept': 'application/json',
            'accept-language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def _parse_date_from_turkish(self, date_str: str) -> datetime:
        """Parse Turkish date format to datetime object."""
        # Handle formats like "30 Haziran 2025"
        turkish_months = {
            'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4,
            'Mayıs': 5, 'Haziran': 6, 'Temmuz': 7, 'Ağustos': 8,
            'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12
        }
        
        try:
            parts = date_str.strip().split()
            if len(parts) == 3:
                day = int(parts[0])
                month = turkish_months.get(parts[1])
                year = int(parts[2])
                
                if month:
                    return datetime(year, month, day)
        except (ValueError, IndexError):
            pass
        
        # Fallback to today's date
        return datetime.now()
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        """Parse time string and return formatted time."""
        if not time_str or time_str.strip() == '':
            return None
        
        # Handle formats like "10:00", "14:30", etc.
        time_pattern = r'^\d{1,2}:\d{2}$'
        if re.match(time_pattern, time_str.strip()):
            return time_str.strip()
        
        return None
    
    def _extract_period_from_event(self, event_name: str) -> str:
        """Extract period information from event name."""
        # Look for patterns like (Mayıs), (Haziran), (Q1), etc.
        period_pattern = r'\(([^)]+)\)$'
        match = re.search(period_pattern, event_name)
        if match:
            return match.group(1)
        return ""
    
    def _parse_html_content(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse HTML content and extract economic events."""
        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        current_date = None
        
        # Find all content containers
        content_divs = soup.find_all('div', id=lambda x: x and 'calendar-content-' in x)
        
        for content_div in content_divs:
            # Find date header
            date_header = content_div.find('div', class_='text-center mt-8 mb-8 text-bold')
            if date_header:
                date_text = date_header.get_text(strip=True)
                current_date = self._parse_date_from_turkish(date_text)
            
            # Find all table rows with events
            rows = content_div.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 7:  # Expected number of columns
                    try:
                        # Extract data from cells
                        time_cell = cells[0]
                        country_cell = cells[1]
                        importance_cell = cells[2]
                        event_cell = cells[3]
                        actual_cell = cells[4]
                        expected_cell = cells[5]
                        previous_cell = cells[6]
                        
                        # Parse time
                        time_text = time_cell.get_text(strip=True)
                        event_time = self._parse_time(time_text)
                        
                        # Parse country
                        country = country_cell.get_text(strip=True)
                        
                        # Parse importance
                        importance_span = importance_cell.find('span', class_=lambda x: x and 'importance' in x)
                        importance = None
                        if importance_span:
                            importance_classes = importance_span.get('class', [])
                            for cls in importance_classes:
                                if cls in ['low', 'mid', 'high']:
                                    importance = cls
                                    break
                        
                        # Parse event details
                        event_name = event_cell.get_text(strip=True)
                        actual = actual_cell.get_text(strip=True) or None
                        expected = expected_cell.get_text(strip=True) or None
                        previous = previous_cell.get_text(strip=True) or None
                        
                        # Extract period from event name
                        period = self._extract_period_from_event(event_name)
                        
                        # Create event object
                        if event_name and current_date:
                            event_data = {
                                'date': current_date,
                                'time': event_time,
                                'country': country,
                                'country_code': 'TR',  # All events are Turkish
                                'event_name': event_name,
                                'importance': importance,
                                'period': period,
                                'actual': actual,
                                'expected': expected,
                                'previous': previous
                            }
                            events.append(event_data)
                            
                    except Exception as e:
                        logger.warning(f"Error parsing event row: {e}")
                        continue
        
        return events
    
    async def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Dovizcom economic calendar API."""
        try:
            headers = self._get_request_headers()
            
            response = await self._http_client.get(self.BASE_URL, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for required keys
            if 'calendarHTML' not in data:
                raise Exception("Invalid response format: missing 'calendarHTML'")
            
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
        high_importance_only: bool = False,
        country_filter: Optional[str] = None,
        count_per_day: int = 25
    ) -> EkonomikTakvimSonucu:
        """
        Get Turkish economic calendar events from Dovizcom.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            high_importance_only: Only include high importance events
            country_filter: Not used (always Turkey), kept for compatibility
            count_per_day: Not used, kept for compatibility
        """
        try:
            # Build API parameters - Dovizcom API is simpler
            params = {
                'country': 'TR',  # Always Turkey
                'importance': '3,2,1' if not high_importance_only else '3'  # 3=high, 2=mid, 1=low
            }
            
            # Make API request
            data = await self._make_request(params)
            
            # Parse HTML content
            html_content = data.get('calendarHTML', '')
            raw_events = self._parse_html_content(html_content)
            
            # Filter events by date range if needed
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Group events by date
            events_by_date = {}
            total_events = 0
            
            for event_data in raw_events:
                event_date = event_data['date']
                
                # Check if event is within date range
                if start_dt.date() <= event_date.date() <= end_dt.date():
                    # Filter by importance if requested
                    if high_importance_only and event_data.get('importance') != 'high':
                        continue
                    
                    date_key = event_date.date()
                    
                    if date_key not in events_by_date:
                        events_by_date[date_key] = []
                    
                    # Create event detail
                    event_detail = EkonomikOlayDetayi(
                        event_name=event_data['event_name'],
                        country_code=event_data['country_code'],
                        country_name=event_data['country'],
                        event_time=event_data['time'],
                        period=event_data['period'],
                        actual=event_data['actual'],
                        prior=event_data['previous'],
                        forecast=event_data['expected'],
                        importance=event_data['importance'],
                        description=f"Turkish economic indicator: {event_data['event_name']}"
                    )
                    
                    events_by_date[date_key].append(event_detail)
                    total_events += 1
            
            # Convert to final format
            all_events = []
            for date_key, day_events in sorted(events_by_date.items()):
                # Calculate summary statistics
                high_importance_count = sum(1 for e in day_events if e.importance == 'high')
                event_types = list(set([e.event_name.split('(')[0].strip() for e in day_events]))
                
                day_event = EkonomikOlay(
                    date=date_key.strftime('%Y-%m-%d'),
                    timezone='Europe/Istanbul',
                    event_count=len(day_events),
                    events=day_events,
                    high_importance_count=high_importance_count,
                    countries_involved=['Turkey'],
                    event_types=event_types[:10]  # Limit to avoid too long lists
                )
                all_events.append(day_event)
            
            # Calculate summary statistics
            countries_covered = ['Turkey']
            high_impact_events = sum(1 for event in all_events for detail in event.events if detail.importance == 'high')
            
            # Extract major release categories
            major_releases = []
            market_moving_events = []
            
            for event in all_events:
                for detail in event.events:
                    event_lower = detail.event_name.lower()
                    if any(keyword in event_lower for keyword in ['işsizlik', 'enflasyon', 'üretim', 'gdp', 'büyüme']):
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
                country_filter='TR',
                countries_covered=countries_covered,
                high_impact_events=high_impact_events,
                major_releases=list(set(major_releases))[:20],  # Limit to top 20
                market_moving_events=list(set(market_moving_events))[:10],  # Limit to top 10
                query_timestamp=datetime.now(),
                data_source='Doviz.com',
                api_endpoint=self.BASE_URL
            )
            
        except Exception as e:
            logger.error(f"Error getting economic calendar for {start_date} to {end_date}: {e}")
            return EkonomikTakvimSonucu(
                start_date=start_date,
                end_date=end_date,
                economic_events=[],
                total_events=0,
                high_importance_only=high_importance_only,
                country_filter='TR',
                error_message=str(e),
                data_source='Doviz.com',
                api_endpoint=self.BASE_URL
            )