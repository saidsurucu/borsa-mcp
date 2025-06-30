"""
TCMB (Turkish Central Bank) Provider
This module is responsible for scraping inflation data from TCMB website.
Supports both TÜFE (Consumer Price Index) and ÜFE (Producer Price Index) data.
"""

import httpx
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from models.tcmb_models import (
    TcmbEnflasyonSonucu, EnflasyonVerisi, EnflasyonHesaplamaSonucu
)

logger = logging.getLogger(__name__)

class TcmbProvider:
    """Provider for TCMB inflation data scraping"""
    
    BASE_URL = "https://www.tcmb.gov.tr"
    CACHE_DURATION = 3600  # 1 hour cache
    
    # Inflation data URLs
    INFLATION_URLS = {
        'tufe': '/wps/wcm/connect/tr/tcmb+tr/main+menu/istatistikler/enflasyon+verileri',
        'ufe': '/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/Enflasyon+Verileri/Uretici+Fiyatlari'
    }
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._cache: Dict[str, Dict] = {}
        self._last_fetch_times: Dict[str, float] = {}
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get appropriate headers for TCMB website requests."""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def _fetch_page_content(self, url: str) -> str:
        """Fetch page content from TCMB website."""
        try:
            headers = self._get_request_headers()
            response = await self._http_client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            raise
    
    def _parse_inflation_table(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse HTML table and extract inflation data."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            tables = soup.find_all('table')
            
            if not tables:
                raise Exception("No tables found on the page")
            
            inflation_data = []
            table_found = False
            
            for table in tables:
                # Get table headers
                headers_row = table.find('tr')
                if headers_row:
                    headers = [th.get_text(strip=True) for th in headers_row.find_all(['th', 'td'])]
                    header_text = ' '.join(headers).lower()
                    
                    # Check if this is the inflation data table (both TÜFE and ÜFE)
                    if any(keyword in header_text for keyword in ['tüfe', 'üfe', 'enflasyon', 'yıllık', 'aylık', '%']):
                        table_found = True
                        logger.info(f"Found inflation table with headers: {headers}")
                        
                        # Parse table rows
                        rows = table.find_all('tr')[1:]  # Skip header row
                        
                        for row in rows:
                            cells = row.find_all(['td', 'th'])
                            cell_texts = [cell.get_text(strip=True) for cell in cells]
                            
                            # Skip header rows or empty rows
                            if not cell_texts or not cell_texts[0] or 'ÜFE' in cell_texts[0]:
                                continue
                                
                            try:
                                # Handle different table formats
                                if len(cell_texts) >= 5:  # ÜFE format: [Date, ÜFE_yearly, YİÜFE_yearly, ÜFE_monthly, YİÜFE_monthly]
                                    date_str = cell_texts[0]
                                    # Use Yİ-ÜFE (domestic) data - columns 2 and 4 (0-indexed: 1 and 3)
                                    yearly_str = cell_texts[2] if len(cell_texts) > 2 else cell_texts[1]
                                    monthly_str = cell_texts[4] if len(cell_texts) > 4 else cell_texts[3] if len(cell_texts) > 3 else ''
                                elif len(cell_texts) >= 3:  # TÜFE format: [Date, yearly, monthly]
                                    date_str = cell_texts[0]
                                    yearly_str = cell_texts[1]
                                    monthly_str = cell_texts[2]
                                else:
                                    continue
                                
                                # Parse data
                                date_obj = self._parse_date(date_str)
                                yearly_pct = self._parse_percentage(yearly_str)
                                monthly_pct = self._parse_percentage(monthly_str)
                                
                                if date_obj and yearly_pct is not None:
                                    inflation_record = {
                                        'date': date_obj,
                                        'year_month': date_str,
                                        'yearly_inflation': yearly_pct,
                                        'monthly_inflation': monthly_pct
                                    }
                                    inflation_data.append(inflation_record)
                                        
                            except Exception as e:
                                logger.warning(f"Error parsing table row: {e}")
                                continue
                        break
            
            if not table_found:
                raise Exception("Could not find inflation data table")
            
            # Sort by date (newest first)
            inflation_data.sort(key=lambda x: x['date'], reverse=True)
            
            logger.info(f"Successfully parsed {len(inflation_data)} inflation records")
            return inflation_data
            
        except Exception as e:
            logger.error(f"Error parsing inflation table: {e}")
            raise
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string from TCMB format (MM-YYYY)."""
        if not date_str:
            return None
        
        # Clean the date string
        date_str = date_str.strip().replace('.', '').replace(',', '')
        
        # Try MM-YYYY format first
        match = re.search(r'(\d{1,2})-(\d{4})', date_str)
        if match:
            month, year = match.groups()
            try:
                return datetime(int(year), int(month), 1)
            except ValueError:
                pass
        
        logger.warning(f"Could not parse date: '{date_str}'")
        return None
    
    def _parse_percentage(self, pct_str: str) -> Optional[float]:
        """Parse percentage string to float."""
        if not pct_str:
            return None
        
        # Clean the percentage string
        pct_str = pct_str.strip().replace('%', '').replace(',', '.')
        
        # Remove any non-numeric characters except minus and dot
        pct_str = re.sub(r'[^\d\-\.]', '', pct_str)
        
        try:
            return float(pct_str)
        except ValueError:
            logger.warning(f"Could not parse percentage: '{pct_str}'")
            return None
    
    def _filter_by_date_range(self, data: List[Dict[str, Any]], start_date: Optional[str], end_date: Optional[str]) -> List[Dict[str, Any]]:
        """Filter inflation data by date range."""
        if not start_date and not end_date:
            return data
        
        try:
            # Parse date strings
            start_dt = None
            end_dt = None
            
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Filter data
            filtered_data = []
            for record in data:
                record_date = record['date']
                
                # Check if within date range
                if start_dt and record_date < start_dt:
                    continue
                if end_dt and record_date > end_dt:
                    continue
                
                filtered_data.append(record)
            
            return filtered_data
            
        except Exception as e:
            logger.error(f"Error filtering by date range: {e}")
            return data  # Return unfiltered data if error
    
    async def get_inflation_data(
        self, 
        inflation_type: str = 'tufe',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> TcmbEnflasyonSonucu:
        """
        Get inflation data from TCMB website.
        
        Args:
            inflation_type: 'tufe' for Consumer Price Index (currently only supported)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            limit: Maximum number of records to return (optional)
        """
        try:
            if inflation_type not in self.INFLATION_URLS:
                return TcmbEnflasyonSonucu(
                    inflation_type=inflation_type,
                    start_date=start_date,
                    end_date=end_date,
                    data=[],
                    total_records=0,
                    error_message=f"Unsupported inflation type: {inflation_type}. Supported types: {list(self.INFLATION_URLS.keys())}"
                )
            
            # Check cache first
            cache_key = f"inflation_{inflation_type}"
            current_time = datetime.now().timestamp()
            
            if (cache_key in self._cache and 
                (current_time - self._last_fetch_times.get(cache_key, 0)) < self.CACHE_DURATION):
                
                logger.info(f"Using cached data for {inflation_type}")
                cached_data = self._cache[cache_key]
            else:
                # Fetch fresh data
                url = self.BASE_URL + self.INFLATION_URLS[inflation_type]
                logger.info(f"Fetching fresh inflation data from: {url}")
                
                html_content = await self._fetch_page_content(url)
                raw_data = self._parse_inflation_table(html_content)
                
                # Cache the data
                self._cache[cache_key] = raw_data
                self._last_fetch_times[cache_key] = current_time
                cached_data = raw_data
            
            # Filter by date range
            filtered_data = self._filter_by_date_range(cached_data, start_date, end_date)
            
            # Apply limit
            if limit and limit > 0:
                filtered_data = filtered_data[:limit]
            
            # Convert to response models
            inflation_records = []
            for record in filtered_data:
                inflation_veri = EnflasyonVerisi(
                    tarih=record['date'].strftime('%Y-%m-%d'),
                    ay_yil=record['year_month'],
                    yillik_enflasyon=record['yearly_inflation'],
                    aylik_enflasyon=record['monthly_inflation']
                )
                inflation_records.append(inflation_veri)
            
            # Calculate statistics
            if inflation_records:
                yearly_rates = [r.yillik_enflasyon for r in inflation_records if r.yillik_enflasyon is not None]
                monthly_rates = [r.aylik_enflasyon for r in inflation_records if r.aylik_enflasyon is not None]
                
                latest_yearly = yearly_rates[0] if yearly_rates else None
                latest_monthly = monthly_rates[0] if monthly_rates else None
                avg_yearly = sum(yearly_rates) / len(yearly_rates) if yearly_rates else None
                avg_monthly = sum(monthly_rates) / len(monthly_rates) if monthly_rates else None
            else:
                latest_yearly = latest_monthly = avg_yearly = avg_monthly = None
            
            return TcmbEnflasyonSonucu(
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                data=inflation_records,
                total_records=len(inflation_records),
                total_available_records=len(cached_data),
                date_range={
                    'earliest': cached_data[-1]['date'].strftime('%Y-%m-%d') if cached_data else None,
                    'latest': cached_data[0]['date'].strftime('%Y-%m-%d') if cached_data else None
                },
                statistics={
                    'latest_yearly_inflation': latest_yearly,
                    'latest_monthly_inflation': latest_monthly,
                    'average_yearly_inflation': round(avg_yearly, 2) if avg_yearly else None,
                    'average_monthly_inflation': round(avg_monthly, 2) if avg_monthly else None,
                    'min_yearly': min(yearly_rates) if yearly_rates else None,
                    'max_yearly': max(yearly_rates) if yearly_rates else None
                },
                data_source='TCMB (Türkiye Cumhuriyet Merkez Bankası)',
                query_timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting inflation data: {e}")
            return TcmbEnflasyonSonucu(
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                data=[],
                total_records=0,
                error_message=str(e),
                data_source='TCMB (Türkiye Cumhuriyet Merkez Bankası)',
                query_timestamp=datetime.now()
            )
    
    async def calculate_inflation(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        basket_value: float = 100.0
    ) -> EnflasyonHesaplamaSonucu:
        """
        Calculate inflation between two dates using TCMB calculator API.
        
        Args:
            start_year: Starting year (e.g., 2020)
            start_month: Starting month (1-12)
            end_year: Ending year (e.g., 2025)
            end_month: Ending month (1-12)
            basket_value: Initial basket value in TL (default: 100.0)
        """
        try:
            # Get current date for validation
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            
            # Validate input parameters
            if not (1982 <= start_year <= current_year):
                raise ValueError(f"Start year must be between 1982 and {current_year}")
            if not (1 <= start_month <= 12):
                raise ValueError("Start month must be between 1 and 12")
            if not (1982 <= end_year <= current_year):
                raise ValueError(f"End year must be between 1982 and {current_year}")
            if not (1 <= end_month <= 12):
                raise ValueError("End month must be between 1 and 12")
            if basket_value <= 0:
                raise ValueError("Basket value must be positive")
            
            # Check if end date is not in the future (TCMB data availability)
            # TCMB usually publishes data with a slight delay, so we limit to current month
            end_date = datetime(end_year, end_month, 1)
            max_date = datetime(current_year, current_month, 1)
            if end_date > max_date:
                raise ValueError(f"End date cannot be later than {current_year}-{current_month:02d}. TCMB inflation data is not available for future dates. Note: Current month's data may not be available yet - TCMB typically publishes data around the 3rd of each month. If you get an error, please try using the previous month.")
            
            # Check if start date is before end date
            start_date = datetime(start_year, start_month, 1)
            end_date = datetime(end_year, end_month, 1)
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")
            
            # Prepare API request
            url = "https://appg.tcmb.gov.tr/KIMENFH/enflasyon/hesapla"
            
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Content-Type': 'application/json',
                'Origin': 'https://herkesicin.tcmb.gov.tr',
                'Referer': 'https://herkesicin.tcmb.gov.tr/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"'
            }
            
            payload = {
                "baslangicYil": str(start_year),
                "baslangicAy": str(start_month),
                "bitisYil": str(end_year),
                "bitisAy": str(end_month),
                "malSepeti": str(basket_value)
            }
            
            # Make API request
            response = await self._http_client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully calculated inflation from {start_year}-{start_month:02d} to {end_year}-{end_month:02d}")
            
            # Parse response
            return EnflasyonHesaplamaSonucu(
                baslangic_tarih=f"{start_year}-{start_month:02d}",
                bitis_tarih=f"{end_year}-{end_month:02d}",
                baslangic_sepet_degeri=basket_value,
                yeni_sepet_degeri=data.get('yeniSepetDeger', ''),
                toplam_yil=int(data.get('toplamYil', 0)),
                toplam_ay=int(data.get('toplamAy', 0)),
                toplam_degisim=data.get('toplamDegisim', ''),
                ortalama_yillik_enflasyon=data.get('ortalamaYillikEnflasyon', ''),
                ilk_yil_tufe=data.get('ilkYilTufe', ''),
                son_yil_tufe=data.get('sonYilTufe', ''),
                hesaplama_tarihi=datetime.now(),
                data_source='TCMB Enflasyon Hesaplama API'
            )
            
        except Exception as e:
            logger.error(f"Error calculating inflation: {e}")
            return EnflasyonHesaplamaSonucu(
                baslangic_tarih=f"{start_year}-{start_month:02d}",
                bitis_tarih=f"{end_year}-{end_month:02d}",
                baslangic_sepet_degeri=basket_value,
                yeni_sepet_degeri="",
                toplam_yil=0,
                toplam_ay=0,
                toplam_degisim="",
                ortalama_yillik_enflasyon="",
                ilk_yil_tufe="",
                son_yil_tufe="",
                hesaplama_tarihi=datetime.now(),
                data_source='TCMB Enflasyon Hesaplama API',
                error_message=str(e)
            )