"""
Dovizcom Provider
This module is responsible for all interactions with the
doviz.com API, including fetching currency, precious metals, and commodity data.
"""
import httpx
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from models import (
    DovizcomGuncelSonucu, DovizcomDakikalikSonucu, DovizcomArsivSonucu,
    DovizcomVarligi, DovizcomOHLCVarligi
)
from .dovizcom_auth import DovizcomAuthManager

logger = logging.getLogger(__name__)

class DovizcomProvider:
    BASE_URL = "https://api.doviz.com/api/v12"
    CACHE_DURATION = 60  # 1 minute cache for current data
    
    # Fuel assets that require archive endpoint (no daily data available)
    FUEL_ASSETS = {"gasoline", "diesel", "lpg"}
    
    # Supported assets
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
        "gram-altin": "gram-altin",
        "gumus": "gumus",
        
        # International Precious Metals (USD-based)
        "ons": "ons",  # Gold USD per troy ounce
        "XAG-USD": "XAG-USD",  # Silver USD
        "XPT-USD": "XPT-USD",  # Platinum USD
        "XPD-USD": "XPD-USD",  # Palladium USD
        
        # Energy Commodities
        "BRENT": "BRENT",
        "WTI": "WTI",
        
        # Fuel Prices (TRY-based)
        "diesel": "diesel",  # Diesel fuel TRY
        "gasoline": "gasoline",  # Gasoline TRY
        "lpg": "lpg"  # LPG TRY
    }
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._cache: Dict[str, Dict] = {}
        self._last_fetch_times: Dict[str, float] = {}
        self._auth_manager = DovizcomAuthManager(client)
    
    async def _get_request_headers(self, asset: str) -> Dict[str, str]:
        """Get appropriate headers for the asset request."""
        # Different origins for different asset types
        if asset in ["gram-altin", "gumus", "ons"]:
            origin = "https://altin.doviz.com"
            referer = "https://altin.doviz.com/"
        else:
            origin = "https://www.doviz.com"
            referer = "https://www.doviz.com/"
        
        # Get dynamic token
        token = await self._auth_manager.get_valid_token('assets')
        
        return {
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Authorization': f'Bearer {token}',
            'Origin': origin,
            'Referer': referer,
            'Sec-Ch-Ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }
    
    async def _make_request(self, endpoint: str, asset: str, params: Dict[str, Any] = None, retry_on_401: bool = True) -> Dict[str, Any]:
        """Make HTTP request to doviz.com API with proper headers."""
        try:
            url = f"{self.BASE_URL}{endpoint}"
            headers = await self._get_request_headers(asset)
            
            response = await self._http_client.get(url, headers=headers, params=params or {})
            
            # Handle 401 errors with token refresh
            if response.status_code == 401 and retry_on_401:
                logger.warning(f"Received 401 for {endpoint}, refreshing token and retrying")
                # Get fresh token
                token = await self._auth_manager.refresh_token_on_401('assets')
                headers['Authorization'] = f'Bearer {token}'
                
                # Retry the request
                response = await self._http_client.get(url, headers=headers, params=params or {})
                
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('error', False):
                raise Exception(f"API Error: {data.get('message', 'Unknown error')}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {endpoint}: {e}")
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error making request to {endpoint}: {e}")
            raise
    
    async def _get_asset_from_archive(self, asset: str, days_back: int = 7) -> Dict[str, Any]:
        """
        Get latest asset data from archive endpoint.
        Used for fuel assets that don't have daily data.
        """
        try:
            # Calculate date range (last N days)
            end_time = int(time.time())
            start_time = end_time - (days_back * 24 * 60 * 60)  # N days ago
            
            endpoint = f"/assets/{asset}/archive"
            params = {
                "start": start_time,
                "end": end_time
            }
            
            data = await self._make_request(endpoint, asset, params)
            
            archive_data = data.get('data', {}).get('archive', [])
            if not archive_data:
                return None
            
            # Get the most recent entry (last in array)
            latest = archive_data[-1]
            return latest
            
        except Exception as e:
            logger.error(f"Error getting archive data for {asset}: {e}")
            return None
    
    async def get_asset_current(self, asset: str) -> DovizcomGuncelSonucu:
        """
        Get current exchange rate or commodity price for the specified asset.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomGuncelSonucu(
                    varlik_adi=asset,
                    guncel_deger=None,
                    son_guncelleme=None,
                    error_message=f"Unsupported asset: {asset}. Supported assets: {list(self.SUPPORTED_ASSETS.keys())}"
                )
            
            # Check cache
            cache_key = f"current_{asset}"
            current_time = time.time()
            if (cache_key in self._cache and 
                (current_time - self._last_fetch_times.get(cache_key, 0)) < self.CACHE_DURATION):
                cached_data = self._cache[cache_key]
                return DovizcomGuncelSonucu(
                    varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                    guncel_deger=cached_data.get('close'),
                    son_guncelleme=cached_data.get('update_date')
                )
            
            # Check if this is a fuel asset that needs archive endpoint
            if asset in self.FUEL_ASSETS:
                # Use archive endpoint for fuel assets
                latest = await self._get_asset_from_archive(asset)
                if not latest:
                    return DovizcomGuncelSonucu(
                        varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                        guncel_deger=None,
                        son_guncelleme=None,
                        error_message="No fuel price data available for this asset"
                    )
            else:
                # Use daily endpoint for non-fuel assets
                endpoint = f"/assets/{asset}/daily"
                params = {"limit": 1}
                
                data = await self._make_request(endpoint, asset, params)
                
                archive_data = data.get('data', {}).get('archive', [])
                if not archive_data:
                    # Fallback to archive endpoint if daily has no data
                    logger.info(f"Daily endpoint empty for {asset}, trying archive fallback")
                    latest = await self._get_asset_from_archive(asset)
                    if not latest:
                        return DovizcomGuncelSonucu(
                            varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                            guncel_deger=None,
                            son_guncelleme=None,
                            error_message="No data available for this asset"
                        )
                else:
                    latest = archive_data[0]  # Most recent data point
            
            # Cache the result
            self._cache[cache_key] = latest
            self._last_fetch_times[cache_key] = current_time
            
            # Convert timestamp to datetime if it's a number
            update_date = latest.get('update_date')
            if isinstance(update_date, (int, float)):
                update_date = datetime.fromtimestamp(update_date)
            
            return DovizcomGuncelSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                guncel_deger=float(latest.get('close', 0)),
                son_guncelleme=update_date
            )
            
        except Exception as e:
            logger.error(f"Error getting current data for {asset}: {e}")
            return DovizcomGuncelSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                guncel_deger=None,
                son_guncelleme=None,
                error_message=str(e)
            )
    
    async def get_asset_daily(self, asset: str, limit: int = 60) -> DovizcomDakikalikSonucu:
        """
        Get minute-by-minute data for the specified asset.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomDakikalikSonucu(
                    varlik_adi=asset,
                    veri_noktalari=[],
                    veri_sayisi=0,
                    error_message=f"Unsupported asset: {asset}. Supported assets: {list(self.SUPPORTED_ASSETS.keys())}"
                )
            
            # Limit between 1 and 60
            limit = max(1, min(limit, 60))
            
            endpoint = f"/assets/{asset}/daily"
            params = {"limit": limit}
            
            data = await self._make_request(endpoint, asset, params)
            
            archive_data = data.get('data', {}).get('archive', []) if data and data.get('data') else []
            
            # Parse data points
            veri_noktalari = []
            if not archive_data:
                # Note: Fuel assets (gasoline, diesel, lpg) typically don't have minute-by-minute data
                # They are updated less frequently (daily/weekly) unlike currencies and commodities
                if asset in self.FUEL_ASSETS:
                    logger.info(f"No minute data for fuel asset {asset} - fuel prices are updated less frequently")
                else:
                    logger.warning(f"No archive data returned for {asset} daily endpoint")
                
            for point in (archive_data or []):
                # Convert timestamp to datetime if it's a number
                update_date = point.get('update_date')
                if isinstance(update_date, (int, float)):
                    update_date = datetime.fromtimestamp(update_date)
                
                veri_noktasi = DovizcomVarligi(
                    tarih=update_date,
                    deger=float(point.get('close', 0))
                )
                veri_noktalari.append(veri_noktasi)
            
            return DovizcomDakikalikSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                veri_noktalari=veri_noktalari,
                veri_sayisi=len(veri_noktalari)
            )
            
        except Exception as e:
            logger.error(f"Error getting daily data for {asset}: {e}")
            return DovizcomDakikalikSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                veri_noktalari=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_asset_archive(self, asset: str, start_date: str, end_date: str) -> DovizcomArsivSonucu:
        """
        Get historical OHLC data for the specified asset within a date range.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                try:
                    baslangic_tarihi = datetime.strptime(start_date, "%Y-%m-%d").date()
                    bitis_tarihi = datetime.strptime(end_date, "%Y-%m-%d").date()
                except:
                    baslangic_tarihi = None
                    bitis_tarihi = None
                    
                return DovizcomArsivSonucu(
                    varlik_adi=asset,
                    baslangic_tarihi=baslangic_tarihi,
                    bitis_tarihi=bitis_tarihi,
                    ohlc_verileri=[],
                    veri_sayisi=0,
                    error_message=f"Unsupported asset: {asset}. Supported assets: {list(self.SUPPORTED_ASSETS.keys())}"
                )
            
            # Convert date strings to timestamps
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                start_timestamp = int(start_dt.timestamp())
                end_timestamp = int(end_dt.timestamp())
            except ValueError:
                return DovizcomArsivSonucu(
                    varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                    baslangic_tarihi=None,
                    bitis_tarihi=None,
                    ohlc_verileri=[],
                    veri_sayisi=0,
                    error_message="Invalid date format. Use YYYY-MM-DD format."
                )
            
            endpoint = f"/assets/{asset}/archive"
            params = {
                "start": start_timestamp,
                "end": end_timestamp
            }
            
            data = await self._make_request(endpoint, asset, params)
            
            archive_data = data.get('data', {}).get('archive', [])
            
            # Parse OHLC data
            ohlc_verileri = []
            for ohlc in archive_data:
                # Convert timestamp to datetime if it's a number
                update_date = ohlc.get('update_date')
                if isinstance(update_date, (int, float)):
                    update_date = datetime.fromtimestamp(update_date)
                
                # Convert to date if update_date is datetime
                tarih = update_date.date() if isinstance(update_date, datetime) else update_date
                
                ohlc_veri = DovizcomOHLCVarligi(
                    tarih=tarih,
                    acilis=float(ohlc.get('open', 0)),
                    en_yuksek=float(ohlc.get('highest', 0)),
                    en_dusuk=float(ohlc.get('lowest', 0)),
                    kapanis=float(ohlc.get('close', 0))
                )
                ohlc_verileri.append(ohlc_veri)
            
            # Parse dates for the result
            try:
                baslangic_tarihi = datetime.strptime(start_date, "%Y-%m-%d").date()
                bitis_tarihi = datetime.strptime(end_date, "%Y-%m-%d").date()
            except:
                baslangic_tarihi = None
                bitis_tarihi = None
            
            return DovizcomArsivSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
                ohlc_verileri=ohlc_verileri,
                veri_sayisi=len(ohlc_verileri)
            )
            
        except Exception as e:
            logger.error(f"Error getting archive data for {asset}: {e}")
            try:
                baslangic_tarihi = datetime.strptime(start_date, "%Y-%m-%d").date()
                bitis_tarihi = datetime.strptime(end_date, "%Y-%m-%d").date()
            except:
                baslangic_tarihi = None
                bitis_tarihi = None
                
            return DovizcomArsivSonucu(
                varlik_adi=self.SUPPORTED_ASSETS.get(asset, asset),
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
                ohlc_verileri=[],
                veri_sayisi=0,
                error_message=str(e)
            )