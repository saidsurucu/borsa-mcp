"""
Borsapy FX Provider
Primary provider for currency, precious metals, and commodity data via borsapy library.
Includes legacy fallback for assets not available in borsapy (WTI, diesel, gasoline, lpg).
"""
import logging
import httpx
from typing import Optional
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
                    varlik_adi=asset,
                    guncel_deger=None,
                    son_guncelleme=None,
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

            # Determine category based on asset type
            if asset in ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]:
                kategori = "doviz"
                birim = "TRY"
            elif asset in ["gram-altin", "gumus", "ons", "XAG-USD", "XPT-USD", "XPD-USD"]:
                kategori = "emtia"
                birim = "TRY" if asset in ["gram-altin", "gumus"] else "USD"
            elif asset in ["BRENT", "WTI"]:
                kategori = "emtia"
                birim = "USD"
            else:
                kategori = "yakit"
                birim = "TRY"

            return DovizcomGuncelSonucu(
                varlik_adi=asset,
                guncel_deger=value,
                son_guncelleme=update_time if update_time else datetime.now(),
                birim=birim,
                kategori=kategori,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching current data for {asset}: {e}")
            return DovizcomGuncelSonucu(
                varlik_adi=asset,
                guncel_deger=None,
                son_guncelleme=None,
                error_message=str(e)
            )

    # Assets that support intraday data via TradingView (borsapy 0.5.3+)
    INTRADAY_ASSETS = {
        "USD", "EUR", "GBP", "JPY",  # Major FX pairs with TRY
        "ons", "XAG-USD", "XPT-USD", "XPD-USD",  # Precious metals
        "BRENT", "WTI"  # Energy
    }

    async def get_asset_daily(self, asset: str, limit: int = 60) -> DovizcomDakikalikSonucu:
        """
        Get minute-by-minute data for an asset (up to 60 data points).
        Uses borsapy TradingView integration for supported assets (USD, EUR, GBP, JPY, metals, energy).
        Falls back to legacy provider for other assets.
        """
        try:
            # Validate asset
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomDakikalikSonucu(
                    varlik_adi=asset,
                    veri_noktalari=[],
                    veri_sayisi=0,
                    error_message=f"Unsupported asset: {asset}"
                )

            # Use legacy provider for fallback assets (fuel prices)
            if asset in self.FALLBACK_ASSETS:
                logger.info(f"Using legacy provider for {asset} (fallback asset)")
                return await self._get_legacy_provider().get_asset_daily(asset, limit)

            # Check if asset supports intraday via TradingView
            if asset not in self.INTRADAY_ASSETS:
                # Assets like CHF, CAD, AUD don't have TRY pairs on TradingView
                logger.info(f"Asset {asset} doesn't support intraday, using legacy provider")
                return await self._get_legacy_provider().get_asset_daily(asset, limit)

            # Use borsapy with interval parameter (TradingView data)
            borsapy_asset = self._get_borsapy_asset(asset)
            logger.info(f"Fetching {asset} minute data via borsapy TradingView (mapped to: {borsapy_asset})")

            fx = bp.FX(borsapy_asset)
            # Get intraday data - borsapy 0.5.3+ supports interval parameter
            df = fx.history(period="1g", interval="1m")

            if df is None or df.empty:
                return DovizcomDakikalikSonucu(
                    varlik_adi=asset,
                    veri_noktalari=[],
                    veri_sayisi=0,
                    error_message="No minute data available"
                )

            # Convert to our model format (Turkish field names)
            data_points = []
            for idx, row in df.tail(limit).iterrows():
                # Handle timezone-aware timestamps
                if hasattr(idx, 'to_pydatetime'):
                    dt = idx.to_pydatetime()
                    # Remove timezone info if present for consistency
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                else:
                    dt = idx

                data_points.append(DovizcomVarligi(
                    tarih=dt,
                    deger=float(row['Close'])
                ))

            # Calculate analysis metrics
            values = [dp.deger for dp in data_points]
            en_yuksek = max(values) if values else None
            en_dusuk = min(values) if values else None
            ortalama = sum(values) / len(values) if values else None

            return DovizcomDakikalikSonucu(
                varlik_adi=asset,
                zaman_araligi=f"Son {len(data_points)} dakika",
                veri_noktalari=data_points,
                veri_sayisi=len(data_points),
                baslangic_tarihi=data_points[0].tarih if data_points else None,
                bitis_tarihi=data_points[-1].tarih if data_points else None,
                en_yuksek_deger=en_yuksek,
                en_dusuk_deger=en_dusuk,
                ortalama_deger=ortalama,
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching minute data for {asset}: {e}")
            return DovizcomDakikalikSonucu(
                varlik_adi=asset,
                veri_noktalari=[],
                veri_sayisi=0,
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
            # Parse dates
            from datetime import datetime as dt_module
            start_dt = dt_module.strptime(start_date, "%Y-%m-%d").date()
            end_dt = dt_module.strptime(end_date, "%Y-%m-%d").date()

            # Validate asset
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomArsivSonucu(
                    varlik_adi=asset,
                    baslangic_tarihi=start_dt,
                    bitis_tarihi=end_dt,
                    ohlc_verileri=[],
                    veri_sayisi=0,
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
                    varlik_adi=asset,
                    baslangic_tarihi=start_dt,
                    bitis_tarihi=end_dt,
                    ohlc_verileri=[],
                    veri_sayisi=0,
                    error_message="No historical data available for the specified date range"
                )

            # Convert to our model format (Turkish field names)
            ohlc_data = []
            for idx, row in df.iterrows():
                # Extract date from index
                if hasattr(idx, 'to_pydatetime'):
                    dt = idx.to_pydatetime()
                    tarih = dt.date() if hasattr(dt, 'date') else dt
                elif hasattr(idx, 'date'):
                    tarih = idx.date()
                else:
                    tarih = idx

                ohlc_data.append(DovizcomOHLCVarligi(
                    tarih=tarih,
                    acilis=float(row['Open']) if 'Open' in row else 0.0,
                    en_yuksek=float(row['High']) if 'High' in row else 0.0,
                    en_dusuk=float(row['Low']) if 'Low' in row else 0.0,
                    kapanis=float(row['Close']) if 'Close' in row else 0.0
                ))

            # Calculate technical analysis metrics
            if ohlc_data:
                closes = [d.kapanis for d in ohlc_data]
                highs = [d.en_yuksek for d in ohlc_data]
                lows = [d.en_dusuk for d in ohlc_data]

                en_yuksek_fiyat = max(highs) if highs else None
                en_dusuk_fiyat = min(lows) if lows else None

                # Calculate return
                if closes[0] and closes[-1]:
                    toplam_getiri = ((closes[-1] - closes[0]) / closes[0]) * 100
                else:
                    toplam_getiri = None

                # Determine trend
                if toplam_getiri:
                    if toplam_getiri > 1:
                        trend_yonu = "yukselis"
                    elif toplam_getiri < -1:
                        trend_yonu = "dusulis"
                    else:
                        trend_yonu = "yatay"
                else:
                    trend_yonu = None

                # Determine market type
                if asset in ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]:
                    piyasa_tipi = "doviz"
                elif asset in ["gram-altin", "gumus", "ons", "XAG-USD", "XPT-USD", "XPD-USD"]:
                    piyasa_tipi = "kiymetli_maden"
                elif asset in ["BRENT", "WTI"]:
                    piyasa_tipi = "enerji"
                else:
                    piyasa_tipi = "yakit"
            else:
                en_yuksek_fiyat = None
                en_dusuk_fiyat = None
                toplam_getiri = None
                trend_yonu = None
                piyasa_tipi = None

            return DovizcomArsivSonucu(
                varlik_adi=asset,
                baslangic_tarihi=start_dt,
                bitis_tarihi=end_dt,
                ohlc_verileri=ohlc_data,
                veri_sayisi=len(ohlc_data),
                trend_yonu=trend_yonu,
                en_yuksek_fiyat=en_yuksek_fiyat,
                en_dusuk_fiyat=en_dusuk_fiyat,
                toplam_getiri=toplam_getiri,
                piyasa_tipi=piyasa_tipi,
                referans_para_birimi="TRY",
                error_message=None
            )

        except Exception as e:
            logger.error(f"Error fetching historical data for {asset}: {e}")
            return DovizcomArsivSonucu(
                varlik_adi=asset,
                ohlc_verileri=[],
                veri_sayisi=0,
                error_message=str(e)
            )
