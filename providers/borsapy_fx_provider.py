"""
Borsapy FX Provider
Primary provider for currency, precious metals, and commodity data via borsapy library.
Includes legacy fallback for assets not available in borsapy (WTI, diesel, gasoline, lpg).
"""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
import borsapy as bp

from models import (
    DovizcomGuncelSonucu, DovizcomDakikalikSonucu, DovizcomArsivSonucu,
    DovizcomVarligi, DovizcomOHLCVarligi
)
from .dovizcom_legacy_provider import DovizcomProvider as LegacyProvider

logger = logging.getLogger(__name__)


class BorsapyFXProvider:
    """Currency, metals, and commodities via borsapy FX class with legacy fallback."""

    # Assets that require legacy dovizcom fallback (not available in borsapy)
    FALLBACK_ASSETS = {"WTI", "diesel", "gasoline", "lpg"}

    # Map old asset names to borsapy names
    ASSET_MAPPING = {
        # Major currencies (direct mapping)
        "USD": "USD",
        "EUR": "EUR",
        "GBP": "GBP",
        "JPY": "JPY",
        "CHF": "CHF",
        "CAD": "CAD",
        "AUD": "AUD",

        # Turkish precious metals
        "gram-altin": "gram-altin",
        "gumus": "gram-gumus",  # Renamed in borsapy

        # International precious metals
        "ons": "ons-altin",  # Renamed in borsapy
        "XAG-USD": "XAG-USD",
        "XPT-USD": "gram-platin",  # Different naming in borsapy
        "XPD-USD": "XPD-USD",

        # Energy
        "BRENT": "BRENT",
    }

    # Supported assets (including legacy fallback)
    SUPPORTED_ASSETS = {
        # Major Currencies
        "USD": "USD",
        "EUR": "EUR",
        "GBP": "GBP",
        "JPY": "JPY",
        "CHF": "CHF",
        "CAD": "CAD",
        "AUD": "AUD",

        # Turkish Precious Metals (TRY-based)
        "gram-altin": "Gram Altın",
        "gumus": "Gümüş",

        # International Precious Metals (USD-based)
        "ons": "Ons Altın (USD)",
        "XAG-USD": "Gümüş (USD)",
        "XPT-USD": "Platin (USD)",
        "XPD-USD": "Paladyum (USD)",

        # Energy Commodities
        "BRENT": "Brent Petrol",
        "WTI": "WTI Petrol",

        # Fuel Prices (TRY-based) - Legacy fallback
        "diesel": "Motorin",
        "gasoline": "Benzin",
        "lpg": "LPG"
    }

    def __init__(self, http_client: httpx.AsyncClient):
        """Initialize with HTTP client for legacy provider."""
        self._http_client = http_client
        self._legacy_provider: Optional[LegacyProvider] = None

    def _get_legacy_provider(self) -> LegacyProvider:
        """Lazy initialization of legacy provider."""
        if self._legacy_provider is None:
            self._legacy_provider = LegacyProvider(self._http_client)
        return self._legacy_provider

    def _get_borsapy_asset(self, asset: str) -> str:
        """Get the borsapy asset name from our asset code."""
        return self.ASSET_MAPPING.get(asset, asset)

    async def get_asset_current(self, asset: str) -> DovizcomGuncelSonucu:
        """
        Get current rate/price for an asset.
        Uses borsapy for most assets, legacy provider for WTI and fuel.
        """
        try:
            # Validate asset
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomGuncelSonucu(
                    asset=asset,
                    guncel_deger=None,
                    guncelleme_tarihi=None,
                    cached=False,
                    error_message=f"Unsupported asset: {asset}. Supported: {list(self.SUPPORTED_ASSETS.keys())}"
                )

            # Use legacy provider for fallback assets
            if asset in self.FALLBACK_ASSETS:
                logger.info(f"Using legacy provider for {asset}")
                return await self._get_legacy_provider().get_asset_current(asset)

            # Use borsapy for all other assets
            borsapy_asset = self._get_borsapy_asset(asset)
            logger.info(f"Fetching {asset} via borsapy (mapped to: {borsapy_asset})")

            fx = bp.FX(borsapy_asset)
            current_data = fx.current

            # Extract value - borsapy returns dict with 'buy', 'sell', 'last' etc.
            if isinstance(current_data, dict):
                value = current_data.get('last') or current_data.get('sell') or current_data.get('buy')
                update_time = current_data.get('update_time')
            else:
                value = float(current_data) if current_data else None
                update_time = None

            return DovizcomGuncelSonucu(
                asset=asset,
                guncel_deger=value,
                guncelleme_tarihi=update_time if update_time else datetime.now(),
                cached=False,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching current data for {asset}: {e}")
            return DovizcomGuncelSonucu(
                asset=asset,
                guncel_deger=None,
                guncelleme_tarihi=None,
                cached=False,
                error_message=str(e)
            )

    async def get_asset_daily(self, asset: str, limit: int = 60) -> DovizcomDakikalikSonucu:
        """
        Get minute-by-minute data for an asset (up to 60 data points).
        Uses borsapy history with interval="1m" for most assets.
        """
        try:
            # Validate asset
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomDakikalikSonucu(
                    asset=asset,
                    veri_noktalari=[],
                    toplam_veri=0,
                    limit=limit,
                    error_message=f"Unsupported asset: {asset}"
                )

            # Use legacy provider for fallback assets
            if asset in self.FALLBACK_ASSETS:
                logger.info(f"Using legacy provider for {asset} daily data")
                return await self._get_legacy_provider().get_asset_daily(asset, limit)

            # Use borsapy history with 1-minute interval
            borsapy_asset = self._get_borsapy_asset(asset)
            logger.info(f"Fetching {asset} minute data via borsapy")

            fx = bp.FX(borsapy_asset)
            # Get intraday data - borsapy supports 1m interval for up to 1 day
            df = fx.history(period="1g", interval="1m")

            if df is None or df.empty:
                return DovizcomDakikalikSonucu(
                    asset=asset,
                    veri_noktalari=[],
                    toplam_veri=0,
                    limit=limit,
                    error_message="No minute data available"
                )

            # Convert to our model format
            data_points = []
            for idx, row in df.tail(limit).iterrows():
                data_points.append(DovizcomVarligi(
                    close=float(row['Close']),
                    update_date=idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
                ))

            return DovizcomDakikalikSonucu(
                asset=asset,
                veri_noktalari=data_points,
                toplam_veri=len(data_points),
                limit=limit,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching minute data for {asset}: {e}")
            return DovizcomDakikalikSonucu(
                asset=asset,
                veri_noktalari=[],
                toplam_veri=0,
                limit=limit,
                error_message=str(e)
            )

    async def get_asset_archive(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> DovizcomArsivSonucu:
        """
        Get historical OHLC data for an asset between dates.
        Uses borsapy history with date range for most assets.
        """
        try:
            # Validate asset
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomArsivSonucu(
                    asset=asset,
                    ohlc_verileri=[],
                    toplam_veri=0,
                    start_date=start_date,
                    end_date=end_date,
                    error_message=f"Unsupported asset: {asset}"
                )

            # Use legacy provider for fallback assets
            if asset in self.FALLBACK_ASSETS:
                logger.info(f"Using legacy provider for {asset} historical data")
                return await self._get_legacy_provider().get_asset_archive(asset, start_date, end_date)

            # Use borsapy history with date range
            borsapy_asset = self._get_borsapy_asset(asset)
            logger.info(f"Fetching {asset} historical data via borsapy ({start_date} to {end_date})")

            fx = bp.FX(borsapy_asset)
            df = fx.history(start=start_date, end=end_date)

            if df is None or df.empty:
                return DovizcomArsivSonucu(
                    asset=asset,
                    ohlc_verileri=[],
                    toplam_veri=0,
                    start_date=start_date,
                    end_date=end_date,
                    error_message="No historical data available for the specified date range"
                )

            # Convert to our model format
            ohlc_data = []
            for idx, row in df.iterrows():
                ohlc_data.append(DovizcomOHLCVarligi(
                    update_date=idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx,
                    open=float(row['Open']) if 'Open' in row else 0.0,
                    high=float(row['High']) if 'High' in row else 0.0,
                    low=float(row['Low']) if 'Low' in row else 0.0,
                    close=float(row['Close']) if 'Close' in row else 0.0,
                    close_try=float(row['Close']) if 'Close' in row else 0.0,  # Same as close for TRY assets
                    close_usd=0.0,  # Not available from borsapy
                    volume=float(row['Volume']) if 'Volume' in row else 0.0
                ))

            return DovizcomArsivSonucu(
                asset=asset,
                ohlc_verileri=ohlc_data,
                toplam_veri=len(ohlc_data),
                start_date=start_date,
                end_date=end_date,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching historical data for {asset}: {e}")
            return DovizcomArsivSonucu(
                asset=asset,
                ohlc_verileri=[],
                toplam_veri=0,
                start_date=start_date,
                end_date=end_date,
                error_message=str(e)
            )
