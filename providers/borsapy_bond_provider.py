"""
Borsapy Bond Provider
Provides Turkish government bond yields via borsapy Bond class.
Supports 2Y, 5Y, and 10Y maturities with real-time data.
"""
import logging
from typing import Dict, Any, Optional, List

import borsapy as bp

logger = logging.getLogger(__name__)


class BorsapyBondProvider:
    """Turkish government bond yields via borsapy Bond class."""

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
        logger.info("Initialized Borsapy Bond Provider")

    async def get_tahvil_faizleri(self) -> Dict[str, Any]:
        """
        Fetch current Turkish government bond yields for all maturities.

        Returns:
            Dict containing bond yields for 2Y, 5Y, and 10Y maturities:
            {
                'tahviller': [...],  # List of bond data
                'toplam_tahvil': 3,  # Count
                'tahvil_lookup': {'2Y': 0.28, '5Y': 0.29, '10Y': 0.31},  # Quick lookup
                'kaynak_url': 'borsapy (doviz.com)',
                'not': 'Faiz oranları yüzde (%) olarak verilmiştir...'
            }
        """
        try:
            logger.info("Fetching bond yields via borsapy")

            tahviller: List[Dict[str, Any]] = []
            tahvil_lookup: Dict[str, float] = {}
            errors = []

            for maturity in self.SUPPORTED_MATURITIES:
                try:
                    bond = bp.Bond(maturity)

                    # Get bond data
                    yield_rate = bond.yield_rate  # Percentage (e.g., 31.79)
                    yield_decimal = bond.yield_decimal  # Decimal (e.g., 0.3179)
                    change_pct = bond.change_pct  # Daily change percentage

                    tahvil_data = {
                        'tahvil_adi': self.BOND_NAMES.get(maturity, f'TR {maturity} Bond'),
                        'vade': maturity,
                        'faiz_orani': yield_rate,
                        'faiz_orani_decimal': yield_decimal,
                        'degisim_yuzde': change_pct,
                        'tahvil_url': f'https://www.doviz.com/tahvil/{maturity.lower()}'
                    }

                    tahviller.append(tahvil_data)

                    if yield_decimal is not None:
                        tahvil_lookup[maturity] = yield_decimal

                    logger.info(f"Fetched {maturity} bond: {yield_rate}%")

                except Exception as e:
                    logger.error(f"Error fetching {maturity} bond: {e}")
                    errors.append(f"{maturity}: {str(e)}")
                    continue

            result = {
                'tahviller': tahviller,
                'toplam_tahvil': len(tahviller),
                'tahvil_lookup': tahvil_lookup,
                'kaynak_url': 'borsapy (doviz.com)',
                'not': 'Faiz oranları yüzde (%) olarak verilmiştir. Decimal değerler için faiz_orani_decimal kullanın.'
            }

            if errors:
                result['uyarilar'] = errors

            return result

        except Exception as e:
            logger.error(f"Error fetching bond yields: {e}")
            return {
                'error': str(e),
                'tahviller': [],
                'toplam_tahvil': 0,
                'tahvil_lookup': {},
                'kaynak_url': 'borsapy (doviz.com)'
            }

    async def get_10y_tahvil_faizi(self) -> Optional[float]:
        """
        Get current 10-year Turkish government bond yield as decimal.

        This is a convenience method for use in DCF calculations.

        Returns:
            10Y bond yield as decimal (e.g., 0.3179 for 31.79%), or None on error
        """
        try:
            # Use borsapy convenience function
            rfr = bp.risk_free_rate()
            if rfr is not None:
                logger.info(f"10Y bond yield via bp.risk_free_rate(): {rfr}")
                return rfr

            # Fallback to direct Bond call
            bond = bp.Bond("10Y")
            return bond.yield_decimal

        except Exception as e:
            logger.error(f"Error getting 10Y bond yield: {e}")
            return None

    def get_risk_free_rate(self) -> Optional[float]:
        """
        Synchronous convenience method for getting risk-free rate.
        Uses borsapy's built-in risk_free_rate() function.

        Returns:
            10Y bond yield as decimal, or None on error
        """
        try:
            return bp.risk_free_rate()
        except Exception as e:
            logger.error(f"Error getting risk-free rate: {e}")
            return None
