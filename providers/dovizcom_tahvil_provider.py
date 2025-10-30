"""
Doviz.com Tahvil (Bond) Provider

Fetches Turkish government bond yields from doviz.com.
Provides real-time interest rates for 2Y, 5Y, and 10Y bonds.
"""
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

class DovizcomTahvilProvider:
    """Provider for Turkish government bond yields from doviz.com."""

    BASE_URL = "https://www.doviz.com/tahvil"

    def __init__(self, http_client: httpx.AsyncClient):
        """
        Initialize the Dovizcom Tahvil Provider.

        Args:
            http_client: Shared httpx AsyncClient instance
        """
        self.client = http_client
        logger.info("Initialized Dovizcom Tahvil Provider")

    async def get_tahvil_faizleri(self) -> Dict[str, Any]:
        """
        Fetch current Turkish government bond yields.

        Returns:
            Dict containing bond yields for 2Y, 5Y, and 10Y maturities
        """
        try:
            logger.info(f"Fetching bond yields from {self.BASE_URL}")

            response = await self.client.get(self.BASE_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')

            # Find the commodities table
            table = soup.find('table', {'id': 'commodities'})
            if not table:
                return {
                    'error': 'Tahvil tablosu bulunamadı',
                    'tahviller': [],
                    'kaynak_url': self.BASE_URL
                }

            tahviller = []
            tbody = table.find('tbody')

            if not tbody:
                return {
                    'error': 'Tahvil verileri bulunamadı',
                    'tahviller': [],
                    'kaynak_url': self.BASE_URL
                }

            for row in tbody.find_all('tr'):
                try:
                    cells = row.find_all('td')
                    if len(cells) < 3:
                        continue

                    # Parse bond name and URL
                    name_link = cells[0].find('a', class_='name')
                    if not name_link:
                        continue

                    tahvil_adi = name_link.text.strip()
                    tahvil_url = name_link.get('href', '')

                    # Parse current rate
                    son_fiyat_text = cells[1].text.strip()
                    son_fiyat = self._parse_float(son_fiyat_text)

                    # Parse change percentage
                    degisim_text = cells[2].text.strip()
                    degisim = self._parse_change(degisim_text)

                    # Determine maturity type
                    vade = None
                    if '2 Yıllık' in tahvil_adi or '2 yıllık' in tahvil_adi:
                        vade = '2Y'
                    elif '5 Yıllık' in tahvil_adi or '5 yıllık' in tahvil_adi:
                        vade = '5Y'
                    elif '10 Yıllık' in tahvil_adi or '10 yıllık' in tahvil_adi:
                        vade = '10Y'

                    tahvil_data = {
                        'tahvil_adi': tahvil_adi,
                        'vade': vade,
                        'faiz_orani': son_fiyat,
                        'faiz_orani_decimal': son_fiyat / 100 if son_fiyat else None,
                        'degisim_yuzde': degisim,
                        'tahvil_url': tahvil_url
                    }

                    tahviller.append(tahvil_data)

                except Exception as e:
                    logger.error(f"Error parsing bond row: {e}")
                    continue

            # Create quick lookup dict
            tahvil_lookup = {}
            for tahvil in tahviller:
                if tahvil['vade']:
                    tahvil_lookup[tahvil['vade']] = tahvil['faiz_orani_decimal']

            return {
                'tahviller': tahviller,
                'toplam_tahvil': len(tahviller),
                'tahvil_lookup': tahvil_lookup,
                'kaynak_url': self.BASE_URL,
                'not': 'Faiz oranları yüzde (%) olarak verilmiştir. Decimal değerler için faiz_orani_decimal kullanın.'
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching bond yields: {e}")
            return {
                'error': f'HTTP hatası: {str(e)}',
                'tahviller': [],
                'kaynak_url': self.BASE_URL
            }
        except Exception as e:
            logger.error(f"Error fetching bond yields: {e}")
            return {
                'error': str(e),
                'tahviller': [],
                'kaynak_url': self.BASE_URL
            }

    def _parse_float(self, text: str) -> Optional[float]:
        """Parse float from Turkish-formatted text."""
        try:
            # Remove whitespace and replace Turkish decimal comma with dot
            cleaned = text.strip().replace(',', '.')
            # Remove any percent signs
            cleaned = cleaned.replace('%', '')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _parse_change(self, text: str) -> Optional[float]:
        """Parse change percentage from text."""
        try:
            # Remove whitespace and percent sign
            cleaned = text.strip().replace('%', '').replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    async def get_10y_tahvil_faizi(self) -> Optional[float]:
        """
        Get current 10-year Turkish government bond yield as decimal.

        This is a convenience method for use in DCF calculations.

        Returns:
            10Y bond yield as decimal (e.g., 0.3179 for 31.79%)
        """
        try:
            result = await self.get_tahvil_faizleri()

            if 'error' in result:
                logger.error(f"Error getting 10Y bond yield: {result['error']}")
                return None

            tahvil_lookup = result.get('tahvil_lookup', {})
            return tahvil_lookup.get('10Y')

        except Exception as e:
            logger.error(f"Error getting 10Y bond yield: {e}")
            return None
