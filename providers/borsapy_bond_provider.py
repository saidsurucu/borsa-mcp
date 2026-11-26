"""
Turkish government bond yields (2Y, 5Y, 10Y) from doviz.com.

borsapy 0.11.0 reads the same page but still expects its previous markup, so the
page is parsed here.
"""
import logging
import math
import re
from typing import Dict, Any, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BondYieldsUnavailableError(RuntimeError):
    """Not a single Turkish bond yield could be read from the source."""


def _parse_number(text: str) -> Optional[float]:
    """Parse a doviz.com cell such as '36,950' or '%-0,97'."""
    try:
        number = float(text.replace("%", "").replace(",", ".").strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


class BorsapyBondProvider:
    """Turkish government bond yields from doviz.com."""

    SOURCE_URL = "https://www.doviz.com/tahvil"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # The table also lists foreign bonds; only the "tr-" links are Turkish.
    TURKISH_BOND_LINK = re.compile(r"/tahvil/tr-(\d+)-yillik-tahvil/?$")

    # Supported maturities
    SUPPORTED_MATURITIES = ["2Y", "5Y", "10Y"]

    # Bond name mapping
    BOND_NAMES = {
        "2Y": "T.C. Hazine Müsteşarlığı 2 Yıllık Tahvil",
        "5Y": "T.C. Hazine Müsteşarlığı 5 Yıllık Tahvil",
        "10Y": "T.C. Hazine Müsteşarlığı 10 Yıllık Tahvil"
    }

    def __init__(self):
        """Initialize bond provider."""
        logger.info("Initialized Bond Provider")

    def _unavailable(self, reason: str) -> BondYieldsUnavailableError:
        return BondYieldsUnavailableError(
            f"Turkish bond yields are unavailable from {self.SOURCE_URL}: {reason}"
        )

    async def _fetch_page(self) -> bytes:
        try:
            async with httpx.AsyncClient(
                timeout=30.0, headers=self.HEADERS, follow_redirects=True
            ) as client:
                response = await client.get(self.SOURCE_URL)
                response.raise_for_status()
        except httpx.HTTPError as e:
            raise self._unavailable(f"request failed ({type(e).__name__}) {e}") from e
        return response.content

    def _parse_page(self, page: bytes) -> Dict[str, Dict[str, Any]]:
        """Map maturity ('10Y') to the Turkish bond row found for it."""
        table = BeautifulSoup(page, "html.parser").find("table", id="bonds")
        if table is None:
            raise self._unavailable(
                "the bond table is missing, so the page layout has probably changed"
            )

        bonds: Dict[str, Dict[str, Any]] = {}
        for link in table.find_all("a", href=self.TURKISH_BOND_LINK):
            maturity = f"{self.TURKISH_BOND_LINK.search(link['href']).group(1)}Y"
            row = link.find_parent("tr")
            cells = row.find_all("td") if row else []
            if maturity not in self.SUPPORTED_MATURITIES or len(cells) < 3:
                continue

            yield_rate = _parse_number(cells[1].get_text())
            # A zero or negative lira yield is a placeholder, not a market rate.
            if yield_rate is None or yield_rate <= 0:
                continue

            bonds[maturity] = {
                'tahvil_adi': self.BOND_NAMES[maturity],
                'vade': maturity,
                'faiz_orani': yield_rate,
                'faiz_orani_decimal': yield_rate / 100,
                'degisim_yuzde': _parse_number(cells[2].get_text()),
                'tahvil_url': link['href']
            }

        if not bonds:
            raise self._unavailable("the bond table has no readable Turkish yield")
        return bonds

    async def get_tahvil_faizleri(self) -> Dict[str, Any]:
        """
        Fetch current Turkish government bond yields for all maturities.

        Returns:
            Dict containing bond yields for 2Y, 5Y, and 10Y maturities:
            {
                'tahviller': [...],  # List of bond data
                'toplam_tahvil': 3,  # Count
                'tahvil_lookup': {'2Y': 0.28, '5Y': 0.29, '10Y': 0.31},  # Quick lookup
                'kaynak_url': 'https://www.doviz.com/tahvil',
                'not': 'Faiz oranları yüzde (%) olarak verilmiştir...',
                'uyarilar': [...]  # Only when some maturities are missing
            }

        Raises:
            BondYieldsUnavailableError: If no maturity at all could be read.
        """
        logger.info("Fetching bond yields from doviz.com")
        bonds = self._parse_page(await self._fetch_page())

        tahviller = [bonds[m] for m in self.SUPPORTED_MATURITIES if m in bonds]
        result = {
            'tahviller': tahviller,
            'toplam_tahvil': len(tahviller),
            'tahvil_lookup': {t['vade']: t['faiz_orani_decimal'] for t in tahviller},
            'kaynak_url': self.SOURCE_URL,
            'not': 'Faiz oranları yüzde (%) olarak verilmiştir. Decimal değerler için faiz_orani_decimal kullanın.'
        }

        missing = [m for m in self.SUPPORTED_MATURITIES if m not in bonds]
        if missing:
            result['uyarilar'] = [f"{m}: tahvil faizi okunamadı" for m in missing]
            logger.warning(f"Bond yields missing for: {', '.join(missing)}")

        return result

    async def get_10y_tahvil_faizi(self) -> Optional[float]:
        """
        Get current 10-year Turkish government bond yield as decimal.

        This is a convenience method for use in DCF calculations.

        Returns:
            10Y bond yield as decimal (e.g., 0.3179 for 31.79%), or None if unavailable
        """
        try:
            result = await self.get_tahvil_faizleri()
        except BondYieldsUnavailableError as e:
            logger.error(f"Error getting 10Y bond yield: {e}")
            return None
        return result['tahvil_lookup'].get("10Y")
