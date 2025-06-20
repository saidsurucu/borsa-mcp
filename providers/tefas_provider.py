"""
TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) provider for Turkish mutual funds.
Provides comprehensive fund data, performance metrics, and screening capabilities.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
import logging
from zoneinfo import ZoneInfo
import os

logger = logging.getLogger(__name__)

class TefasProvider:
    """Provider for TEFAS mutual fund data."""
    
    def __init__(self):
        self.base_url = "https://www.tefas.gov.tr"
        self.api_url = f"{self.base_url}/api"
        self.takasbank_url = "https://www.takasbank.com.tr/plugins/ExcelExportTefasFundsTradingInvestmentPlatform?language=tr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'tr-TR,tr;q=0.9',
            'Referer': 'https://www.tefas.gov.tr/'
        })
        self.turkey_tz = ZoneInfo("Europe/Istanbul")
        self._fund_list_cache = None
        self._fund_list_cache_time = None
        self._cache_duration = 3600  # 1 hour cache
    
    def _get_takasbank_fund_list(self) -> List[Dict[str, str]]:
        """
        Get complete fund list from Takasbank Excel file.
        Returns list of dicts with 'fon_kodu' and 'fon_adi'.
        """
        try:
            # Check cache first
            if self._fund_list_cache and self._fund_list_cache_time:
                elapsed = datetime.now() - self._fund_list_cache_time
                if elapsed.total_seconds() < self._cache_duration:
                    logger.info("Using cached Takasbank fund list")
                    return self._fund_list_cache
            
            logger.info("Fetching fresh fund list from Takasbank")
            
            # Download Excel file
            response = self.session.get(self.takasbank_url, timeout=10)
            response.raise_for_status()
            
            # Save to temp file
            temp_file = '/tmp/takasbank_funds.xlsx'
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            # Read Excel with pandas
            df = pd.read_excel(temp_file)
            
            # Convert to list of dicts
            fund_list = []
            for _, row in df.iterrows():
                fund_list.append({
                    'fon_kodu': str(row['Fon Kodu']).strip(),
                    'fon_adi': str(row['Fon Adı']).strip()
                })
            
            # Update cache
            self._fund_list_cache = fund_list
            self._fund_list_cache_time = datetime.now()
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
            
            logger.info(f"Successfully loaded {len(fund_list)} funds from Takasbank")
            return fund_list
            
        except Exception as e:
            logger.error(f"Error fetching Takasbank fund list: {e}")
            return []
    
    def _normalize_turkish(self, text: str) -> str:
        """Normalize Turkish characters for better search matching."""
        replacements = {
            'ı': 'i', 'İ': 'i',
            'ğ': 'g', 'Ğ': 'g',
            'ü': 'u', 'Ü': 'u',
            'ş': 's', 'Ş': 's',
            'ö': 'o', 'Ö': 'o',
            'ç': 'c', 'Ç': 'c'
        }
        text_norm = text.lower()
        for tr_char, latin_char in replacements.items():
            text_norm = text_norm.replace(tr_char, latin_char)
        return text_norm
    
    def search_funds_takasbank(self, search_term: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search for funds using Takasbank Excel data.
        More comprehensive and accurate than TEFAS API search.
        """
        try:
            # Get fund list
            all_funds = self._get_takasbank_fund_list()
            
            if not all_funds:
                return {
                    'arama_terimi': search_term,
                    'sonuclar': [],
                    'sonuc_sayisi': 0,
                    'error_message': 'Takasbank fon listesi yüklenemedi'
                }
            
            # Search logic with Turkish normalization
            search_lower = search_term.lower()
            search_normalized = self._normalize_turkish(search_term)
            matched_funds = []
            
            # Split search terms for better matching
            search_words = search_lower.split()
            search_words_normalized = search_normalized.split()
            
            for fund in all_funds:
                fund_name_lower = fund['fon_adi'].lower()
                fund_name_normalized = self._normalize_turkish(fund['fon_adi'])
                fund_code_lower = fund['fon_kodu'].lower()
                
                # Check exact fund code match first
                if fund_code_lower == search_lower:
                    # Exact code match - add to beginning
                    matched_funds.insert(0, {
                        'fon_kodu': fund['fon_kodu'],
                        'fon_adi': fund['fon_adi'],
                        'fon_turu': '',
                        'kurulus': '',
                        'yonetici': '',
                        'risk_degeri': 0,
                        'tarih': ''
                    })
                    continue
                
                # Check if all search words are in fund name (both normal and normalized)
                all_words_match = all(word in fund_name_lower for word in search_words)
                all_words_match_normalized = all(word in fund_name_normalized for word in search_words_normalized)
                
                # Check if search term matches fund code or name
                if (search_lower in fund_code_lower or 
                    search_lower in fund_name_lower or
                    search_normalized in fund_name_normalized or
                    all_words_match or
                    all_words_match_normalized):
                    
                    # Add basic info without TEFAS details (faster)
                    matched_funds.append({
                        'fon_kodu': fund['fon_kodu'],
                        'fon_adi': fund['fon_adi'],
                        'fon_turu': '',
                        'kurulus': '',
                        'yonetici': '',
                        'risk_degeri': 0,
                        'tarih': ''
                    })
                    
                    # Limit results
                    if len(matched_funds) >= limit:
                        break
            
            return {
                'arama_terimi': search_term,
                'sonuclar': matched_funds,
                'sonuc_sayisi': len(matched_funds),
                'kaynak': 'Takasbank'
            }
            
        except Exception as e:
            logger.error(f"Error searching funds in Takasbank list: {e}")
            return {
                'arama_terimi': search_term,
                'sonuclar': [],
                'sonuc_sayisi': 0,
                'error_message': str(e)
            }
        
    def search_funds(self, search_term: str, limit: int = 20, use_takasbank: bool = True) -> Dict[str, Any]:
        """
        Search for funds by name, code, or founder.
        Now uses Takasbank data by default for more comprehensive results.
        
        Args:
            search_term: Search term for fund name, code, or founder
            limit: Maximum number of results to return
            use_takasbank: Use Takasbank Excel data (True) or TEFAS API (False)
            
        Returns:
            Dictionary with search results
        """
        # Use Takasbank by default for better coverage
        if use_takasbank:
            return self.search_funds_takasbank(search_term, limit)
        
        # Original TEFAS API search (as fallback)
        try:
            # TEFAS fund search API endpoint
            search_url = f"{self.api_url}/FundSearch"
            
            params = {
                'q': search_term,
                'fundType': 'YAT',  # All fund types
                'take': limit
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            funds = []
            
            for fund in data.get('data', []):
                funds.append({
                    'fon_kodu': fund.get('FONKODU', ''),
                    'fon_adi': fund.get('FONUNVAN', ''),
                    'fon_turu': fund.get('FONTUR', ''),
                    'kurulus': fund.get('KURUCU', ''),
                    'yonetici': fund.get('YONETICI', ''),
                    'risk_degeri': fund.get('RISKDEGERI', 0),
                    'tarih': fund.get('TARIH', '')
                })
            
            return {
                'arama_terimi': search_term,
                'sonuclar': funds,
                'sonuc_sayisi': len(funds),
                'kaynak': 'TEFAS API'
            }
            
        except Exception as e:
            logger.error(f"Error searching funds with term {search_term}: {e}")
            # Try Takasbank as fallback
            logger.info("Falling back to Takasbank search due to TEFAS API error")
            return self.search_funds_takasbank(search_term, limit)
    
    def get_fund_detail(self, fund_code: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific fund.
        First tries the alternative (more reliable) API, then falls back to the original.
        
        Args:
            fund_code: TEFAS fund code
            
        Returns:
            Dictionary with fund details
        """
        # First, try the alternative API (from iOS Scriptable widget)
        logger.info(f"Trying alternative TEFAS API for fund {fund_code}")
        result = self.get_fund_detail_alternative(fund_code)
        
        # If alternative API worked, return the result
        if not result.get('error_message'):
            logger.info(f"Alternative TEFAS API succeeded for fund {fund_code}")
            return result
        
        # Alternative API failed, try the original API
        logger.info(f"Alternative TEFAS API failed, trying original API for fund {fund_code}")
        
        try:
            # Original Fund detail API endpoint
            detail_url = f"{self.api_url}/FundDetail"
            
            params = {
                'fonKod': fund_code,
                'tarih': datetime.now().strftime('%d.%m.%Y')
            }
            
            response = self.session.get(detail_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return {
                    'fon_kodu': fund_code,
                    'fon_adi': '',
                    'tarih': '',
                    'fiyat': 0.0,
                    'tedavuldeki_pay_sayisi': 0.0,
                    'toplam_deger': 0.0,
                    'birim_pay_degeri': 0.0,
                    'yatirimci_sayisi': 0,
                    'kurulus': '',
                    'yonetici': '',
                    'fon_turu': '',
                    'risk_degeri': 0,
                    'getiri_1_ay': None,
                    'getiri_3_ay': None,
                    'getiri_6_ay': None,
                    'getiri_yil_basi': None,
                    'getiri_1_yil': None,
                    'getiri_3_yil': None,
                    'getiri_5_yil': None,
                    'standart_sapma': None,
                    'sharpe_orani': None,
                    'alpha': None,
                    'beta': None,
                    'tracking_error': None,
                    'error_message': 'Fon bulunamadı'
                }
            
            fund_info = data[0] if isinstance(data, list) else data
            
            return {
                'fon_kodu': fund_info.get('FONKODU', ''),
                'fon_adi': fund_info.get('FONUNVAN', ''),
                'tarih': fund_info.get('TARIH', ''),
                'fiyat': fund_info.get('FIYAT', 0),
                'tedavuldeki_pay_sayisi': fund_info.get('TEDPAYSAYISI', 0),
                'toplam_deger': fund_info.get('TOPLAMBIRIMFONDEGER', 0),
                'birim_pay_degeri': fund_info.get('BIRIMFONDEGER', 0),
                'yatirimci_sayisi': fund_info.get('KISISAYISI', 0),
                'kurulus': fund_info.get('KURUCU', ''),
                'yonetici': fund_info.get('YONETICI', ''),
                'fon_turu': fund_info.get('FONTUR', ''),
                'risk_degeri': fund_info.get('RISKDEGERI', 0),
                'getiri_1_ay': fund_info.get('GETIRIAY1', 0),
                'getiri_3_ay': fund_info.get('GETIRIAY3', 0),
                'getiri_6_ay': fund_info.get('GETIRIAY6', 0),
                'getiri_yil_basi': fund_info.get('GETIRIYILBASI', 0),
                'getiri_1_yil': fund_info.get('GETIRI365', 0),
                'getiri_3_yil': fund_info.get('GETIRI3YIL', 0),
                'getiri_5_yil': fund_info.get('GETIRI5YIL', 0),
                'standart_sapma': fund_info.get('STANDARTSAPMA', 0),
                'sharpe_orani': fund_info.get('SHARPEORANI', 0),
                'alpha': fund_info.get('ALPHA', 0),
                'beta': fund_info.get('BETA', 0),
                'tracking_error': fund_info.get('TRACKINGERROR', 0),
                'api_source': 'FundDetail'
            }
            
        except Exception as e:
            logger.error(f"Both TEFAS APIs failed for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'fon_adi': '',
                'tarih': '',
                'fiyat': 0.0,
                'tedavuldeki_pay_sayisi': 0.0,
                'toplam_deger': 0.0,
                'birim_pay_degeri': 0.0,
                'yatirimci_sayisi': 0,
                'kurulus': '',
                'yonetici': '',
                'fon_turu': '',
                'risk_degeri': 0,
                'getiri_1_ay': None,
                'getiri_3_ay': None,
                'getiri_6_ay': None,
                'getiri_yil_basi': None,
                'getiri_1_yil': None,
                'getiri_3_yil': None,
                'getiri_5_yil': None,
                'standart_sapma': None,
                'sharpe_orani': None,
                'alpha': None,
                'beta': None,
                'tracking_error': None,
                'error_message': f"All TEFAS APIs failed: {str(e)}"
            }
    
    def get_fund_detail_alternative(self, fund_code: str) -> Dict[str, Any]:
        """
        Alternative TEFAS API endpoint for fund details (from iOS Scriptable widget).
        Uses GetAllFundAnalyzeData endpoint which might be more reliable.
        """
        try:
            # Alternative TEFAS API endpoint
            detail_url = "https://www.tefas.gov.tr/api/DB/GetAllFundAnalyzeData"
            
            # POST data as form-encoded
            data = {
                'dil': 'TR',
                'fonkod': fund_code
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'tr-TR,tr;q=0.9'
            }
            
            response = self.session.post(detail_url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # Check if we have fund data
            if not result or not result.get('fundInfo'):
                return {
                    'fon_kodu': fund_code,
                    'fon_adi': '',
                    'tarih': '',
                    'fiyat': 0.0,
                    'tedavuldeki_pay_sayisi': 0.0,
                    'toplam_deger': 0.0,
                    'birim_pay_degeri': 0.0,
                    'yatirimci_sayisi': 0,
                    'kurulus': '',
                    'yonetici': '',
                    'fon_turu': '',
                    'risk_degeri': 0,
                    'getiri_1_ay': None,
                    'getiri_3_ay': None,
                    'getiri_6_ay': None,
                    'getiri_yil_basi': None,
                    'getiri_1_yil': None,
                    'getiri_3_yil': None,
                    'getiri_5_yil': None,
                    'standart_sapma': None,
                    'sharpe_orani': None,
                    'alpha': None,
                    'beta': None,
                    'tracking_error': None,
                    'error_message': 'No fund data found in alternative API'
                }
            
            # Extract fund info
            fund_info = result['fundInfo'][0]
            fund_return = result.get('fundReturn', [{}])[0] if result.get('fundReturn') else {}
            
            # Map the data to our model
            return {
                'fon_kodu': fund_code,
                'fon_adi': fund_info.get('FONUNVAN', fund_info.get('FONADI', '')),
                'tarih': fund_info.get('TARIH', datetime.now().strftime('%Y-%m-%d')),
                'fiyat': float(fund_info.get('SONFIYAT', 0) or 0),
                'tedavuldeki_pay_sayisi': float(fund_info.get('PAYADET', fund_info.get('TEDPAYSAYISI', 0)) or 0),
                'toplam_deger': float(fund_info.get('PORTBUYUKLUK', fund_info.get('PORTFOYDEGERI', 0)) or 0),
                'birim_pay_degeri': float(fund_info.get('SONFIYAT', 0) or 0),  # Same as current price
                'yatirimci_sayisi': int(fund_info.get('YATIRIMCISAYI', fund_info.get('KISISAYISI', 0)) or 0),
                'kurulus': fund_info.get('KURUCU', ''),
                'yonetici': fund_info.get('YONETICI', ''),
                'fon_turu': fund_info.get('FONTUR', fund_info.get('FONTURU', '')),
                'risk_degeri': int(fund_info.get('RISKDEGERI', 0)),
                
                # Performance metrics from fundReturn
                'getiri_1_ay': fund_return.get('GETIRI1A'),
                'getiri_3_ay': fund_return.get('GETIRI3A'),
                'getiri_6_ay': fund_return.get('GETIRI6A'),
                'getiri_yil_basi': fund_return.get('GETIRIYB'),
                'getiri_1_yil': fund_return.get('GETIRI1Y', fund_return.get('GETIRI365')),
                'getiri_3_yil': fund_return.get('GETIRI3Y'),
                'getiri_5_yil': fund_return.get('GETIRI5Y'),
                
                # Additional performance data from fundInfo
                'gunluk_getiri': fund_info.get('GUNLUKGETIRI'),
                'haftalik_getiri': fund_info.get('HAFTALIKGETIRI'),
                
                # Risk metrics (may not be available in this endpoint)
                'standart_sapma': fund_info.get('STANDARTSAPMA'),
                'sharpe_orani': fund_info.get('SHARPEORANI'),
                'alpha': fund_info.get('ALPHA'),
                'beta': fund_info.get('BETA'),
                'tracking_error': fund_info.get('TRACKINGERROR'),
                
                # API source info
                'api_source': 'GetAllFundAnalyzeData'
            }
            
        except Exception as e:
            logger.error(f"Error getting fund detail (alternative) for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'fon_adi': '',
                'tarih': '',
                'fiyat': 0.0,
                'tedavuldeki_pay_sayisi': 0.0,
                'toplam_deger': 0.0,
                'birim_pay_degeri': 0.0,
                'yatirimci_sayisi': 0,
                'kurulus': '',
                'yonetici': '',
                'fon_turu': '',
                'risk_degeri': 0,
                'getiri_1_ay': None,
                'getiri_3_ay': None,
                'getiri_6_ay': None,
                'getiri_yil_basi': None,
                'getiri_1_yil': None,
                'getiri_3_yil': None,
                'getiri_5_yil': None,
                'standart_sapma': None,
                'sharpe_orani': None,
                'alpha': None,
                'beta': None,
                'tracking_error': None,
                'error_message': f"Alternative TEFAS API error: {str(e)}"
            }
    
    def get_fund_performance(self, fund_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get historical performance data for a fund.
        
        Args:
            fund_code: TEFAS fund code
            start_date: Start date in YYYY-MM-DD format (default: 1 year ago)
            end_date: End date in YYYY-MM-DD format (default: today)
            
        Returns:
            Dictionary with performance data
        """
        try:
            # Default dates if not provided
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            # Convert dates to TEFAS format (DD.MM.YYYY)
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Historical data API endpoint
            history_url = f"{self.api_url}/FundPriceHistory"
            
            params = {
                'fonKod': fund_code,
                'baslangicTarihi': start_dt.strftime('%d.%m.%Y'),
                'bitisTarihi': end_dt.strftime('%d.%m.%Y')
            }
            
            response = self.session.get(history_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            price_history = []
            
            for item in data:
                price_history.append({
                    'tarih': item.get('TARIH', ''),
                    'fiyat': item.get('FIYAT', 0),
                    'tedavuldeki_pay_sayisi': item.get('TEDPAYSAYISI', 0),
                    'toplam_deger': item.get('TOPLAMBIRIMFONDEGER', 0),
                    'yatirimci_sayisi': item.get('KISISAYISI', 0)
                })
            
            # Calculate returns
            if len(price_history) >= 2:
                first_price = price_history[-1]['fiyat']
                last_price = price_history[0]['fiyat']
                total_return = ((last_price - first_price) / first_price) * 100
                
                # Calculate annualized return
                days = (end_dt - start_dt).days
                annualized_return = ((last_price / first_price) ** (365 / days) - 1) * 100
            else:
                total_return = None
                annualized_return = None
            
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date,
                'bitis_tarihi': end_date,
                'fiyat_geçmisi': price_history,
                'toplam_getiri': total_return,
                'yillik_getiri': annualized_return,
                'veri_sayisi': len(price_history)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date,
                'bitis_tarihi': end_date,
                'error_message': str(e)
            }
    
    def get_fund_portfolio(self, fund_code: str) -> Dict[str, Any]:
        """
        Get portfolio composition of a fund.
        
        Args:
            fund_code: TEFAS fund code
            
        Returns:
            Dictionary with portfolio composition
        """
        try:
            # Portfolio API endpoint
            portfolio_url = f"{self.api_url}/FundPortfolio"
            
            params = {
                'fonKod': fund_code,
                'tarih': datetime.now().strftime('%d.%m.%Y')
            }
            
            response = self.session.get(portfolio_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            portfolio_items = []
            
            for item in data:
                portfolio_items.append({
                    'varlik_turu': item.get('VARLIKTURU', ''),
                    'alt_varlik_turu': item.get('ALTVARLIKTURU', ''),
                    'tutar': item.get('TUTAR', 0),
                    'oran': item.get('ORAN', 0),
                    'detay': item.get('DETAY', '')
                })
            
            # Group by asset type
            asset_groups = {}
            for item in portfolio_items:
                asset_type = item['varlik_turu']
                if asset_type not in asset_groups:
                    asset_groups[asset_type] = {
                        'tutar': 0,
                        'oran': 0,
                        'alt_kalemler': []
                    }
                asset_groups[asset_type]['tutar'] += item['tutar']
                asset_groups[asset_type]['oran'] += item['oran']
                asset_groups[asset_type]['alt_kalemler'].append(item)
            
            return {
                'fon_kodu': fund_code,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'portfoy_detayi': portfolio_items,
                'varlik_dagilimi': asset_groups,
                'toplam_varlik': sum(item['tutar'] for item in portfolio_items)
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'error_message': str(e)
            }
    
    def compare_funds(self, fund_codes: List[str]) -> Dict[str, Any]:
        """
        Compare multiple funds side by side.
        
        Args:
            fund_codes: List of TEFAS fund codes to compare
            
        Returns:
            Dictionary with comparison data
        """
        try:
            comparison_data = []
            
            for fund_code in fund_codes[:5]:  # Limit to 5 funds
                fund_detail = self.get_fund_detail(fund_code)
                
                if 'error_message' not in fund_detail:
                    comparison_data.append({
                        'fon_kodu': fund_detail['fon_kodu'],
                        'fon_adi': fund_detail['fon_adi'],
                        'fon_turu': fund_detail['fon_turu'],
                        'risk_degeri': fund_detail['risk_degeri'],
                        'fiyat': fund_detail['fiyat'],
                        'getiri_1_ay': fund_detail['getiri_1_ay'],
                        'getiri_3_ay': fund_detail['getiri_3_ay'],
                        'getiri_1_yil': fund_detail['getiri_1_yil'],
                        'sharpe_orani': fund_detail['sharpe_orani'],
                        'standart_sapma': fund_detail['standart_sapma'],
                        'toplam_deger': fund_detail['toplam_deger'],
                        'yatirimci_sayisi': fund_detail['yatirimci_sayisi']
                    })
            
            # Calculate rankings
            if comparison_data:
                # Rank by 1-year return
                sorted_by_return = sorted(comparison_data, key=lambda x: x.get('getiri_1_yil', 0), reverse=True)
                for i, fund in enumerate(sorted_by_return):
                    fund['getiri_siralamasi'] = i + 1
                
                # Rank by Sharpe ratio
                sorted_by_sharpe = sorted(comparison_data, key=lambda x: x.get('sharpe_orani', 0), reverse=True)
                for i, fund in enumerate(sorted_by_sharpe):
                    fund['risk_ayarli_getiri_siralamasi'] = i + 1
                
                # Rank by size
                sorted_by_size = sorted(comparison_data, key=lambda x: x.get('toplam_deger', 0), reverse=True)
                for i, fund in enumerate(sorted_by_size):
                    fund['buyukluk_siralamasi'] = i + 1
            
            return {
                'karsilastirilan_fonlar': fund_codes,
                'karsilastirma_verileri': comparison_data,
                'fon_sayisi': len(comparison_data),
                'tarih': datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error comparing funds: {e}")
            return {
                'karsilastirilan_fonlar': fund_codes,
                'error_message': str(e)
            }
    
    def screen_funds(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Screen funds based on various criteria.
        
        Args:
            criteria: Dictionary with screening criteria
                - fund_type: Fund type (e.g., 'HSF', 'DEF', 'HBF')
                - min_return_1y: Minimum 1-year return
                - max_risk: Maximum risk score
                - min_sharpe: Minimum Sharpe ratio
                - min_size: Minimum fund size
                - founder: Specific founder/company
                
        Returns:
            Dictionary with screening results
        """
        try:
            # Get all funds first (simplified for demo)
            all_funds_url = f"{self.api_url}/FundList"
            
            params = {
                'fontip': criteria.get('fund_type', 'YAT'),  # Default to all
                'tarih': datetime.now().strftime('%d.%m.%Y')
            }
            
            response = self.session.get(all_funds_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            screened_funds = []
            
            for fund in data.get('data', []):
                # Apply filters
                if criteria.get('min_return_1y') and fund.get('GETIRI365', 0) < criteria['min_return_1y']:
                    continue
                if criteria.get('max_risk') and fund.get('RISKDEGERI', 0) > criteria['max_risk']:
                    continue
                if criteria.get('min_sharpe') and fund.get('SHARPEORANI', 0) < criteria['min_sharpe']:
                    continue
                if criteria.get('min_size') and fund.get('TOPLAMBIRIMFONDEGER', 0) < criteria['min_size']:
                    continue
                if criteria.get('founder') and criteria['founder'].lower() not in fund.get('KURUCU', '').lower():
                    continue
                
                screened_funds.append({
                    'fon_kodu': fund.get('FONKODU', ''),
                    'fon_adi': fund.get('FONUNVAN', ''),
                    'fon_turu': fund.get('FONTUR', ''),
                    'kurulus': fund.get('KURUCU', ''),
                    'risk_degeri': fund.get('RISKDEGERI', 0),
                    'getiri_1_yil': fund.get('GETIRI365', 0),
                    'sharpe_orani': fund.get('SHARPEORANI', 0),
                    'toplam_deger': fund.get('TOPLAMBIRIMFONDEGER', 0),
                    'fiyat': fund.get('FIYAT', 0)
                })
            
            # Sort by 1-year return
            screened_funds.sort(key=lambda x: x.get('getiri_1_yil', 0), reverse=True)
            
            return {
                'tarama_kriterleri': criteria,
                'bulunan_fonlar': screened_funds[:50],  # Limit to top 50
                'toplam_sonuc': len(screened_funds),
                'tarih': datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error screening funds: {e}")
            return {
                'tarama_kriterleri': criteria,
                'error_message': str(e)
            }