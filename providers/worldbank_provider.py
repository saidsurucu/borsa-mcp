"""
World Bank Provider

Fetches economic indicators from World Bank API.
Primary use: GDP growth data for terminal growth rate in DCF calculations.
"""
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class WorldBankProvider:
    """Provider for World Bank economic indicators."""

    BASE_URL = "https://api.worldbank.org/v2"

    def __init__(self, http_client: httpx.AsyncClient):
        """
        Initialize the World Bank Provider.

        Args:
            http_client: Shared httpx AsyncClient instance
        """
        self.client = http_client
        logger.info("Initialized World Bank Provider")

    async def get_gdp_growth(
        self,
        country_code: str = "TR",
        years: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch GDP growth data for a country.

        Args:
            country_code: ISO 2-letter country code (default: TR for Turkey)
            years: Number of years to fetch (default: 10)

        Returns:
            Dict containing GDP growth data and average
        """
        try:
            # Calculate date range
            from datetime import datetime
            end_year = datetime.now().year
            start_year = end_year - years + 1

            # Construct API URL
            url = f"{self.BASE_URL}/country/{country_code}/indicator/NY.GDP.MKTP.KD.ZG"
            params = {
                'format': 'json',
                'date': f'{start_year}:{end_year}'
            }

            logger.info(f"Fetching GDP growth for {country_code} ({start_year}-{end_year})")

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Parse response
            if len(data) < 2:
                return {
                    'error': 'Invalid response from World Bank API',
                    'gdp_data': [],
                    'average_growth': None
                }

            gdp_records = []
            gdp_values = []

            for item in data[1]:
                year = item.get('date')
                value = item.get('value')

                if value is not None:
                    gdp_records.append({
                        'year': year,
                        'gdp_growth_pct': round(value, 2),
                        'gdp_growth_decimal': round(value / 100, 4)
                    })
                    gdp_values.append(value)

            # Calculate average
            if gdp_values:
                avg_growth_pct = sum(gdp_values) / len(gdp_values)
                avg_growth_decimal = avg_growth_pct / 100
            else:
                avg_growth_pct = None
                avg_growth_decimal = None

            return {
                'country_code': country_code,
                'country_name': data[1][0]['country']['value'] if data[1] else None,
                'indicator': 'GDP growth (annual %)',
                'start_year': start_year,
                'end_year': end_year,
                'gdp_data': gdp_records,
                'data_points': len(gdp_records),
                'average_growth_pct': round(avg_growth_pct, 2) if avg_growth_pct else None,
                'average_growth_decimal': round(avg_growth_decimal, 4) if avg_growth_decimal else None,
                'source': 'World Bank Open Data',
                'api_url': url
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching GDP growth: {e}")
            return {
                'error': f'HTTP hatası: {str(e)}',
                'gdp_data': [],
                'average_growth': None
            }
        except Exception as e:
            logger.error(f"Error fetching GDP growth: {e}")
            return {
                'error': str(e),
                'gdp_data': [],
                'average_growth': None
            }

    async def get_terminal_growth_rate(
        self,
        country_code: str = "TR",
        years: int = 10,
        conservative: bool = True
    ) -> Optional[float]:
        """
        Get terminal growth rate for DCF calculations.

        This is a convenience method that returns the average GDP growth
        as a decimal, suitable for use in DCF terminal value calculations.

        Args:
            country_code: ISO 2-letter country code
            years: Number of years to average
            conservative: If True, cap at 3% (Buffett's recommendation)

        Returns:
            Terminal growth rate as decimal (e.g., 0.0479 for 4.79%)
        """
        try:
            result = await self.get_gdp_growth(country_code, years)

            if 'error' in result:
                logger.error(f"Error getting terminal growth rate: {result['error']}")
                return None

            avg_growth = result.get('average_growth_decimal')

            if avg_growth is None:
                return None

            # Apply conservative cap if requested
            if conservative and avg_growth > 0.03:
                logger.info(f"Capping terminal growth from {avg_growth:.4f} to 0.03 (conservative)")
                return 0.03

            return avg_growth

        except Exception as e:
            logger.error(f"Error getting terminal growth rate: {e}")
            return None
