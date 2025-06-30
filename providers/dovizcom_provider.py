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
from borsa_models import (
    DovizcomGuncelSonucu, DovizcomDakikalikSonucu, DovizcomArsivSonucu,
    DovizcomVarligi, DovizcomOHLCVarligi
)

logger = logging.getLogger(__name__)

class DovizcomProvider:
    BASE_URL = "https://api.doviz.com/api/v12"
    CACHE_DURATION = 60  # 1 minute cache for current data
    
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
    
    def _get_request_headers(self, asset: str) -> Dict[str, str]:
        """Get appropriate headers for the asset request."""
        # Different origins for different asset types
        if asset in ["gram-altin", "gumus", "ons"]:
            origin = "https://altin.doviz.com"
            referer = "https://altin.doviz.com/"
        else:
            origin = "https://www.doviz.com"
            referer = "https://www.doviz.com/"
        
        return {
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Authorization': 'Bearer d9e5ca031c76ccdbf776941b6cf9339a24f83f3e1f7e055de3c3a4bfea41bd5b',
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
    
    async def _make_request(self, endpoint: str, asset: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to doviz.com API with proper headers."""
        try:
            url = f"{self.BASE_URL}{endpoint}"
            headers = self._get_request_headers(asset)
            
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
    
    async def get_asset_current(self, asset: str) -> DovizcomGuncelSonucu:
        """
        Get current exchange rate or commodity price for the specified asset.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomGuncelSonucu(
                    asset=asset,
                    guncel_deger=None,
                    guncelleme_tarihi=None,
                    error_message=f"Unsupported asset: {asset}. Supported assets: {list(self.SUPPORTED_ASSETS.keys())}"
                )
            
            # Check cache
            cache_key = f"current_{asset}"
            current_time = time.time()
            if (cache_key in self._cache and 
                (current_time - self._last_fetch_times.get(cache_key, 0)) < self.CACHE_DURATION):
                cached_data = self._cache[cache_key]
                return DovizcomGuncelSonucu(
                    asset=asset,
                    guncel_deger=cached_data.get('close'),
                    guncelleme_tarihi=cached_data.get('update_date'),
                    cached=True
                )
            
            # Fetch current data (get latest from daily endpoint)
            endpoint = f"/assets/{asset}/daily"
            params = {"limit": 1}
            
            data = await self._make_request(endpoint, asset, params)
            
            archive_data = data.get('data', {}).get('archive', [])
            if not archive_data:
                return DovizcomGuncelSonucu(
                    asset=asset,
                    guncel_deger=None,
                    guncelleme_tarihi=None,
                    error_message="No data available for this asset"
                )
            
            latest = archive_data[0]  # Most recent data point
            
            # Cache the result
            self._cache[cache_key] = latest
            self._last_fetch_times[cache_key] = current_time
            
            # Convert timestamp to datetime if it's a number
            update_date = latest.get('update_date')
            if isinstance(update_date, (int, float)):
                update_date = datetime.fromtimestamp(update_date)
            
            return DovizcomGuncelSonucu(
                asset=asset,
                guncel_deger=float(latest.get('close', 0)),
                guncelleme_tarihi=update_date
            )
            
        except Exception as e:
            logger.error(f"Error getting current data for {asset}: {e}")
            return DovizcomGuncelSonucu(
                asset=asset,
                guncel_deger=None,
                guncelleme_tarihi=None,
                error_message=str(e)
            )
    
    async def get_asset_daily(self, asset: str, limit: int = 60) -> DovizcomDakikalikSonucu:
        """
        Get minute-by-minute data for the specified asset.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomDakikalikSonucu(
                    asset=asset,
                    veri_noktalari=[],
                    toplam_veri=0,
                    limit=limit,
                    error_message=f"Unsupported asset: {asset}. Supported assets: {list(self.SUPPORTED_ASSETS.keys())}"
                )
            
            # Limit between 1 and 60
            limit = max(1, min(limit, 60))
            
            endpoint = f"/assets/{asset}/daily"
            params = {"limit": limit}
            
            data = await self._make_request(endpoint, asset, params)
            
            archive_data = data.get('data', {}).get('archive', [])
            
            # Parse data points
            veri_noktalari = []
            for point in archive_data:
                # Convert timestamp to datetime if it's a number
                update_date = point.get('update_date')
                if isinstance(update_date, (int, float)):
                    update_date = datetime.fromtimestamp(update_date)
                
                veri_noktasi = DovizcomVarligi(
                    close=float(point.get('close', 0)),
                    update_date=update_date
                )
                veri_noktalari.append(veri_noktasi)
            
            return DovizcomDakikalikSonucu(
                asset=asset,
                veri_noktalari=veri_noktalari,
                toplam_veri=len(veri_noktalari),
                limit=limit
            )
            
        except Exception as e:
            logger.error(f"Error getting daily data for {asset}: {e}")
            return DovizcomDakikalikSonucu(
                asset=asset,
                veri_noktalari=[],
                toplam_veri=0,
                limit=limit,
                error_message=str(e)
            )
    
    async def get_asset_archive(self, asset: str, start_date: str, end_date: str) -> DovizcomArsivSonucu:
        """
        Get historical OHLC data for the specified asset within a date range.
        """
        try:
            if asset not in self.SUPPORTED_ASSETS:
                return DovizcomArsivSonucu(
                    asset=asset,
                    ohlc_verileri=[],
                    toplam_veri=0,
                    start_date=start_date,
                    end_date=end_date,
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
                    asset=asset,
                    ohlc_verileri=[],
                    toplam_veri=0,
                    start_date=start_date,
                    end_date=end_date,
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
                
                ohlc_veri = DovizcomOHLCVarligi(
                    update_date=update_date,
                    open=float(ohlc.get('open', 0)),
                    high=float(ohlc.get('highest', 0)),
                    low=float(ohlc.get('lowest', 0)),
                    close=float(ohlc.get('close', 0)),
                    close_try=float(ohlc.get('close_try', 0)),
                    close_usd=float(ohlc.get('close_usd', 0)),
                    volume=float(ohlc.get('volume', 0))
                )
                ohlc_verileri.append(ohlc_veri)
            
            return DovizcomArsivSonucu(
                asset=asset,
                ohlc_verileri=ohlc_verileri,
                toplam_veri=len(ohlc_verileri),
                start_date=start_date,
                end_date=end_date
            )
            
        except Exception as e:
            logger.error(f"Error getting archive data for {asset}: {e}")
            return DovizcomArsivSonucu(
                asset=asset,
                ohlc_verileri=[],
                toplam_veri=0,
                start_date=start_date,
                end_date=end_date,
                error_message=str(e)
            )