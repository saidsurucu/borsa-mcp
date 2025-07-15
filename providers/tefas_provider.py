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
        # Disable SSL verification to avoid certificate issues
        self.session.verify = False
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
        # First convert to lowercase
        text_norm = text.lower()
        
        # Then apply replacements (including i̇ from İ.lower())
        replacements = {
            'ı': 'i', 'i̇': 'i',  # Both ı and i̇ (from İ.lower())
            'ğ': 'g', 'ü': 'u',
            'ş': 's', 'ö': 'o',
            'ç': 'c'
        }
        
        for tr_char, latin_char in replacements.items():
            text_norm = text_norm.replace(tr_char, latin_char)
        return text_norm
    
    def _calculate_data_completeness_score(self, fund_info: dict, fund_return: dict, fund_prices_1a: list, fund_profile: dict = None, fund_allocation: list = None) -> float:
        """
        Calculate comprehensive data completeness score based on all available API sections.
        Returns a score between 0.0 and 1.0 indicating data quality.
        """
        score = 0.0
        total_checks = 0
        
        # Essential fund info checks
        essential_fields = ['SONFIYAT', 'FONUNVAN', 'KURUCU', 'YONETICI', 'FONTUR', 'FONKATEGORI']
        for field in essential_fields:
            total_checks += 1
            if fund_info.get(field):
                score += 1
        
        # Performance data checks
        if fund_return:
            total_checks += 1
            score += 1
            
            performance_fields = ['GETIRI1A', 'GETIRI3A', 'GETIRI1Y', 'GETIRI3Y', 'GETIRI5Y']
            for field in performance_fields:
                total_checks += 1
                if fund_return.get(field) is not None:
                    score += 1
        
        # NEW: Fund profile completeness
        if fund_profile:
            total_checks += 1
            score += 1
            
            profile_fields = ['ISINKOD', 'SONISSAAT', 'KAPLINK', 'TEFASDURUM']
            for field in profile_fields:
                total_checks += 1
                if fund_profile.get(field):
                    score += 1
        
        # NEW: Portfolio allocation completeness  
        if fund_allocation:
            total_checks += 2
            score += 2  # Bonus for having allocation data
            
            # Check if allocation sums to reasonable total
            total_allocation = sum(item.get('PORTFOYORANI', 0) for item in fund_allocation)
            if 95 <= total_allocation <= 105:  # Allow some variance
                total_checks += 1
                score += 1
        
        # Daily return validity check (like in widget: != -100)
        total_checks += 1
        if fund_info.get('GUNLUKGETIRI', -100) != -100:
            score += 1
        
        # Price history availability
        total_checks += 1
        if fund_prices_1a and len(fund_prices_1a) > 0:
            score += 1
        
        # Additional metrics availability
        additional_fields = ['PORTBUYUKLUK', 'YATIRIMCISAYI', 'RISKDEGERI']
        for field in additional_fields:
            total_checks += 1
            if fund_info.get(field):
                score += 1
        
        return round(score / total_checks, 2) if total_checks > 0 else 0.0
    
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
        
    async def search_funds_advanced(self, search_term: str, limit: int = 20, fund_type: str = "YAT", fund_category: str = "all") -> Dict[str, Any]:
        """
        Advanced fund search using the same BindComparisonFundReturns API as compare_funds.
        Provides more comprehensive and up-to-date fund data with performance metrics.
        
        Args:
            search_term: Search term for fund name, code, or founder
            limit: Maximum number of results to return
            fund_type: Fund type - "YAT" (Investment), "EMK" (Pension), "BYF" (ETF), etc.
            fund_category: Fund category filter for detailed classification
            
        Returns:
            Dictionary with advanced search results including performance data
        """
        try:
            # Map human-readable category to TEFAS category code
            category_mapping = {
                "all": "Tümü",
                "debt": "100",  # Borçlanma Araçları Şemsiye Fonu
                "variable": "101",  # Değişken Şemsiye Fonu
                "basket": "102",  # Fon Sepeti Şemsiye Fonu
                "guaranteed": "103",  # Garantili Şemsiye Fonu
                "real_estate": "173",  # Gayrimenkul Şemsiye Fonu
                "venture": "172",  # Girişim Sermayesi Şemsiye Fonu
                "equity": "104",  # Hisse Senedi Şemsiye Fonu
                "mixed": "110",  # Karma Şemsiye Fonu
                "participation": "114",  # Katılım Şemsiye Fonu
                "precious_metals": "105",  # Kıymetli Madenler Şemsiye Fonu
                "money_market": "107",  # Para Piyasası Şemsiye Fonu
                "flexible": "108"  # Serbest Şemsiye Fonu
            }
            
            # Get the category code
            category_code = category_mapping.get(fund_category, "Tümü")
            
            # Use the same official TEFAS comparison API
            comparison_url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
            
            # Set parameters for comprehensive fund list retrieval
            data = {
                'calismatipi': '2',  # Search/list mode
                'fontip': fund_type,  # Fund type
                'sfontur': category_code,  # Sub fund type (category filter)
                'kurucukod': '',  # No founder filter (get all)
                'fongrup': '',  # Fund group
                'bastarih': 'Başlangıç',  # Start date placeholder
                'bittarih': 'Bitiş',  # End date placeholder
                'fonturkod': '',  # Fund type code
                'fonunvantip': '',  # Fund title type
                'strperiod': '1,1,1,1,1,1,1',  # All periods
                'islemdurum': '1'  # Active funds only
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://www.tefas.gov.tr',
                'Referer': 'https://www.tefas.gov.tr/FonKarsilastirma.aspx',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(comparison_url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            result_data = response.json()
            all_funds = result_data.get('data', []) if isinstance(result_data, dict) else result_data
            
            # Filter funds based on search term
            search_term_norm = self._normalize_turkish(search_term.lower())
            matching_funds = []
            
            for fund in all_funds:
                fund_code = fund.get('FONKODU', '').lower()
                fund_name = self._normalize_turkish(fund.get('FONUNVAN', '').lower())
                fund_desc = self._normalize_turkish(fund.get('FONTURACIKLAMA', '').lower())
                
                # Check if search term matches code, name, or description
                if (search_term_norm in fund_code or 
                    search_term_norm in fund_name or 
                    search_term_norm in fund_desc or
                    any(word in fund_name for word in search_term_norm.split() if len(word) > 2)):
                    
                    matching_funds.append({
                        'fon_kodu': fund.get('FONKODU', ''),
                        'fon_adi': fund.get('FONUNVAN', ''),
                        'fon_turu': fund.get('FONTURACIKLAMA', ''),
                        'getiri_1_ay': fund.get('GETIRI1A'),
                        'getiri_3_ay': fund.get('GETIRI3A'),
                        'getiri_6_ay': fund.get('GETIRI6A'),
                        'getiri_1_yil': fund.get('GETIRI1Y'),
                        'getiri_yil_basi': fund.get('GETIRIYB'),
                        'getiri_3_yil': fund.get('GETIRI3Y'),
                        'getiri_5_yil': fund.get('GETIRI5Y'),
                        'api_source': 'BindComparisonFundReturns'
                    })
            
            # Sort by 1-year return (descending, null values last)
            matching_funds.sort(key=lambda x: x.get('getiri_1_yil') or -999999, reverse=True)
            
            # Limit results
            limited_funds = matching_funds[:limit]
            
            # Apply token optimization to fund search results
            from token_optimizer import TokenOptimizer
            original_count = len(matching_funds)
            optimized_funds = TokenOptimizer.optimize_fund_search_results(matching_funds, limit)
            
            return {
                'arama_terimi': search_term,
                'sonuclar': optimized_funds,
                'sonuc_sayisi': len(optimized_funds),
                'toplam_bulunan': len(matching_funds),
                'kaynak': 'TEFAS BindComparisonFundReturns API',
                'fund_type': fund_type,
                'fund_category': fund_category,
                'category_code': category_code,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'performans_dahil': True
            }
            
        except Exception as e:
            logger.error(f"Error in advanced fund search: {e}")
            return {
                'arama_terimi': search_term,
                'sonuclar': [],
                'sonuc_sayisi': 0,
                'toplam_bulunan': 0,
                'kaynak': 'TEFAS BindComparisonFundReturns API',
                'fund_type': fund_type,
                'fund_category': fund_category,
                'category_code': category_code,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'performans_dahil': True,
                'error_message': str(e)
            }

    async def search_funds(self, search_term: str, limit: int = 20, use_takasbank: bool = True) -> Dict[str, Any]:
        """
        Search for funds by name, code, or founder.
        Now uses advanced TEFAS API by default for more comprehensive results with performance data.
        
        Args:
            search_term: Search term for fund name, code, or founder
            limit: Maximum number of results to return
            use_takasbank: Use Takasbank Excel data (True) or TEFAS API (False)
            
        Returns:
            Dictionary with search results
        """
        # Use advanced TEFAS API by default for better data quality
        if not use_takasbank:
            return await self.search_funds_advanced(search_term, limit, "YAT", getattr(self, '_current_fund_category', 'all'))
        
        # Fallback to Takasbank for basic search if specified
        return self.search_funds_takasbank(search_term, limit)
    
    def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> Dict[str, Any]:
        """
        Get detailed information about a specific fund using the reliable alternative API.
        Uses GetAllFundAnalyzeData endpoint which provides comprehensive fund data.
        
        Args:
            fund_code: TEFAS fund code
            
        Returns:
            Dictionary with fund details
        """
        # Use only the alternative API (from iOS Scriptable widget) as it's more reliable
        logger.info(f"Getting fund details for {fund_code} using GetAllFundAnalyzeData API (price_history={include_price_history})")
        result = self.get_fund_detail_alternative(fund_code, include_price_history)
        
        if not result.get('error_message'):
            logger.info(f"Successfully retrieved fund details for {fund_code}")
            return result
        else:
            logger.error(f"Failed to get fund details for {fund_code}: {result.get('error_message')}")
            return result
    
    def get_fund_detail_alternative(self, fund_code: str, include_price_history: bool = False) -> Dict[str, Any]:
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
            
            # Extract all available data sections
            fund_info = result['fundInfo'][0]
            fund_return = result.get('fundReturn', [{}])[0] if result.get('fundReturn') else {}
            fund_profile = result.get('fundProfile', [{}])[0] if result.get('fundProfile') else {}
            fund_allocation = result.get('fundAllocation', [])
            
            # Price history data (optional)
            fund_prices_1h = result.get('fundPrices1H', [])  # 1 haftalık
            fund_prices_1a = result.get('fundPrices1A', [])  # 1 aylık
            fund_prices_3a = result.get('fundPrices3A', [])  # 3 aylık
            fund_prices_6a = result.get('fundPrices6A', [])  # 6 aylık
            
            # Calculate additional metrics from price history (like in the widget)
            previous_day_price = None
            daily_change_amount = None
            if fund_prices_1a and len(fund_prices_1a) >= 2:
                try:
                    current_price = float(fund_info.get('SONFIYAT', 0) or 0)
                    previous_day_price = float(fund_prices_1a[-2].get('FIYAT', 0))
                    if previous_day_price > 0:
                        daily_change_amount = current_price - previous_day_price
                except (ValueError, IndexError, KeyError):
                    previous_day_price = None
                    daily_change_amount = None
            
            # Helper function to convert price history
            def convert_price_history(prices_data):
                return [
                    {
                        'tarih': datetime.fromisoformat(item.get('TARIH', '').replace('T00:00:00', '')).strftime('%Y-%m-%d') if item.get('TARIH') else '',
                        'fiyat': float(item.get('FIYAT', 0)),
                        'kategori_derece': item.get('KATEGORIDERECE'),
                        'kategori_fon_sayisi': item.get('KATEGORIFONSAY')
                    }
                    for item in prices_data
                ]
            
            # Build comprehensive result with all available data
            result_data = {
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
                'risk_degeri': int(fund_profile.get('RISKDEGERI', fund_info.get('RISKDEGERI', 0)) or 0),
                
                # Performance metrics from fundReturn
                'getiri_1_ay': fund_return.get('GETIRI1A'),
                'getiri_3_ay': fund_return.get('GETIRI3A'),
                'getiri_6_ay': fund_return.get('GETIRI6A'),
                'getiri_yil_basi': fund_return.get('GETIRIYB'),
                'getiri_1_yil': fund_return.get('GETIRI1Y', fund_return.get('GETIRI365')),
                'getiri_3_yil': fund_return.get('GETIRI3Y'),
                'getiri_5_yil': fund_return.get('GETIRI5Y'),
                
                # Enhanced performance data from fundInfo (like in widget)
                'gunluk_getiri': fund_info.get('GUNLUKGETIRI'),
                'haftalik_getiri': fund_info.get('HAFTALIKGETIRI'),
                'gunluk_degisim_miktar': daily_change_amount,
                'onceki_gun_fiyat': previous_day_price,
                
                # NEW: Category and ranking information from fundInfo
                'fon_kategori': fund_info.get('FONKATEGORI'),
                'kategori_derece': fund_info.get('KATEGORIDERECE'),
                'kategori_fon_sayisi': fund_info.get('KATEGORIFONSAY'),
                'pazar_payi': fund_info.get('PAZARPAYI'),
                'kategori_derece_birlesik': fund_info.get('KATEGORIDERECEBIRLESIK'),
                
                # NEW: Fund profile information from fundProfile
                'fon_profil': {
                    'isin_kod': fund_profile.get('ISINKOD'),
                    'son_islem_saati': fund_profile.get('SONISSAAT'),
                    'min_alis': fund_profile.get('MINALIS'),
                    'min_satis': fund_profile.get('MINSATIS'),
                    'max_alis': fund_profile.get('MAXALIS'),
                    'max_satis': fund_profile.get('MAXSATIS'),
                    'kap_link': fund_profile.get('KAPLINK'),
                    'tefas_durum': fund_profile.get('TEFASDURUM'),
                    'cikis_komisyonu': fund_profile.get('CIKISKOMISYONU'),
                    'giris_komisyonu': fund_profile.get('GIRISKOMISYONU'),
                    'basis_saat': fund_profile.get('BASISSAAT'),
                    'fon_satis_valor': fund_profile.get('FONSATISVALOR'),
                    'fon_geri_alis_valor': fund_profile.get('FONGERIALISVALOR'),
                    'faiz_icerigi': fund_profile.get('FAIZICERIGI')
                } if fund_profile else None,
                
                # NEW: Portfolio allocation from fundAllocation
                'portfoy_dagilimi': [
                    {
                        'kiymet_tip': item.get('KIYMETTIP'),
                        'portfoy_orani': item.get('PORTFOYORANI')
                    }
                    for item in fund_allocation
                ] if fund_allocation else None,
                
                # Price history metadata
                'fiyat_gecmisi_1ay_sayisi': len(fund_prices_1a),
                'fiyat_gecmisi_1ay_mevcut': len(fund_prices_1a) > 0,
                
                # Risk metrics (may not be available in this endpoint)
                'standart_sapma': fund_info.get('STANDARTSAPMA'),
                'sharpe_orani': fund_info.get('SHARPEORANI'),
                'alpha': fund_info.get('ALPHA'),
                'beta': fund_info.get('BETA'),
                'tracking_error': fund_info.get('TRACKINGERROR'),
                
                # Enhanced API metadata
                'api_source': 'GetAllFundAnalyzeData',
                'veri_kalitesi': {
                    'fiyat_gecmisi_var': len(fund_prices_1a) > 0,
                    'performans_verisi_var': bool(fund_return),
                    'profil_verisi_var': bool(fund_profile),
                    'portfoy_dagilimi_var': bool(fund_allocation),
                    'gunluk_getiri_gecerli': fund_info.get('GUNLUKGETIRI', -100) != -100,
                    'veri_tamamligi_skoru': self._calculate_data_completeness_score(fund_info, fund_return, fund_prices_1a)
                }
            }
            
            # Add optional price history if requested
            if include_price_history:
                if fund_prices_1h:
                    result_data['fiyat_gecmisi_1hafta'] = convert_price_history(fund_prices_1h)
                if fund_prices_1a:
                    result_data['fiyat_gecmisi_1ay'] = convert_price_history(fund_prices_1a)
                if fund_prices_3a:
                    result_data['fiyat_gecmisi_3ay'] = convert_price_history(fund_prices_3a)
                if fund_prices_6a:
                    result_data['fiyat_gecmisi_6ay'] = convert_price_history(fund_prices_6a)
            
            return result_data
            
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
        Get historical performance data for a fund using official TEFAS BindHistoryInfo API.
        
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
            
            # Official TEFAS historical data API endpoint
            history_url = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
            
            # POST data matching TEFAS website format
            data = {
                'fontip': 'YAT',  # Fund type
                'sfontur': '',     # Sub fund type (empty for all)
                'fonkod': fund_code,
                'fongrup': '',     # Fund group (empty for all)
                'bastarih': start_dt.strftime('%d.%m.%Y'),
                'bittarih': end_dt.strftime('%d.%m.%Y'),
                'fonturkod': '',   # Fund type code (empty for all)
                'fonunvantip': '', # Fund title type (empty for all)
                'kurucukod': ''    # Founder code (empty for all)
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://www.tefas.gov.tr',
                'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(history_url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            # Check if we have data
            if not result.get('data'):
                return {
                    'fon_kodu': fund_code,
                    'baslangic_tarihi': start_date,
                    'bitis_tarihi': end_date,
                    'fiyat_geçmisi': [],
                    'toplam_getiri': None,
                    'yillik_getiri': None,
                    'veri_sayisi': 0,
                    'error_message': 'No historical data found for this fund'
                }
            
            price_history = []
            
            for item in result['data']:
                # Convert timestamp to readable date
                timestamp = int(item.get('TARIH', 0))
                if timestamp > 0:
                    # Convert milliseconds to seconds
                    date_obj = datetime.fromtimestamp(timestamp / 1000, tz=self.turkey_tz)
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                else:
                    formatted_date = ''
                
                price_history.append({
                    'tarih': formatted_date,
                    'fiyat': float(item.get('FIYAT', 0)),
                    'tedavuldeki_pay_sayisi': float(item.get('TEDPAYSAYISI', 0)),
                    'toplam_deger': float(item.get('PORTFOYBUYUKLUK', 0)),
                    'yatirimci_sayisi': int(item.get('KISISAYISI', 0)),
                    'fon_unvan': item.get('FONUNVAN', ''),
                    'borsa_bulten_fiyat': item.get('BORSABULTENFIYAT', '-')
                })
            
            # Sort by date (newest first)
            price_history.sort(key=lambda x: x['tarih'], reverse=True)
            
            # Calculate time frame for optimization
            time_frame_days = (end_dt - start_dt).days
            
            # Apply token optimization
            from token_optimizer import TokenOptimizer
            original_count = len(price_history)
            optimized_history = TokenOptimizer.optimize_fund_performance(price_history, time_frame_days)
            
            # Calculate returns
            if len(optimized_history) >= 2:
                # Get first and last prices (sorted newest first)
                latest_price = optimized_history[0]['fiyat']
                oldest_price = optimized_history[-1]['fiyat']
                
                if oldest_price > 0:
                    total_return = ((latest_price - oldest_price) / oldest_price) * 100
                    
                    # Calculate annualized return
                    days = (end_dt - start_dt).days
                    if days > 0:
                        annualized_return = ((latest_price / oldest_price) ** (365 / days) - 1) * 100
                    else:
                        annualized_return = total_return
                else:
                    total_return = None
                    annualized_return = None
            else:
                total_return = None
                annualized_return = None
            
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date,
                'bitis_tarihi': end_date,
                'fiyat_geçmisi': optimized_history,
                'toplam_getiri': total_return,
                'yillik_getiri': annualized_return,
                'veri_sayisi': len(optimized_history),
                'kaynak': 'TEFAS BindHistoryInfo API'
            }
            
        except Exception as e:
            logger.error(f"Error getting performance for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date or '',
                'bitis_tarihi': end_date or '',
                'fiyat_geçmisi': [],
                'toplam_getiri': None,
                'yillik_getiri': None,
                'veri_sayisi': 0,
                'error_message': str(e)
            }
    
    def get_fund_portfolio(self, fund_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API.
        
        Args:
            fund_code: TEFAS fund code
            start_date: Start date in YYYY-MM-DD format (default: 1 week ago)
            end_date: End date in YYYY-MM-DD format (default: today)
            
        Returns:
            Dictionary with portfolio allocation data over time
        """
        try:
            # Default dates if not provided (use short range for allocation data)
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Convert dates to TEFAS format (DD.MM.YYYY)
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Official TEFAS portfolio allocation API endpoint
            allocation_url = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"
            
            # POST data matching TEFAS website format
            data = {
                'fontip': 'YAT',  # Fund type
                'sfontur': '',     # Sub fund type (empty for all)
                'fonkod': fund_code,
                'fongrup': '',     # Fund group (empty for all)
                'bastarih': start_dt.strftime('%d.%m.%Y'),
                'bittarih': end_dt.strftime('%d.%m.%Y'),
                'fonturkod': '',   # Fund type code (empty for all)
                'fonunvantip': '', # Fund title type (empty for all)
                'kurucukod': ''    # Founder code (empty for all)
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://www.tefas.gov.tr',
                'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(allocation_url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            # Check if we have data
            if not result.get('data'):
                return {
                    'fon_kodu': fund_code,
                    'baslangic_tarihi': start_date,
                    'bitis_tarihi': end_date,
                    'portfoy_geçmisi': [],
                    'son_portfoy_dagilimi': {},
                    'veri_sayisi': 0,
                    'error_message': 'No allocation data found for this fund'
                }
            
            portfolio_history = []
            asset_type_mapping = {
                'BB': 'Banka Bonosu',
                'BYF': 'Borsa Yatırım Fonu',
                'D': 'Döviz',
                'DB': 'Devlet Bonusu',
                'DT': 'Devlet Tahvili',
                'DÖT': 'Döviz Ödenekli Tahvil',
                'EUT': 'Eurobond Tahvil',
                'FB': 'Finansman Bonosu',
                'FKB': 'Fon Katılma Belgesi',
                'GAS': 'Gümüş Alım Satım',
                'GSYKB': 'Girişim Sermayesi Yatırım Katılma Belgesi',
                'GSYY': 'Girişim Sermayesi Yatırım',
                'GYKB': 'Gayrimenkul Yatırım Katılma Belgesi',
                'GYY': 'Gayrimenkul Yatırım',
                'HB': 'Hazine Bonosu',
                'HS': 'Hisse Senedi',
                'KBA': 'Kira Sertifikası Alım',
                'KH': 'Katılım Hesabı',
                'KHAU': 'Katılım Hesabı ABD Doları',
                'KHD': 'Katılım Hesabı Döviz',
                'KHTL': 'Katılım Hesabı Türk Lirası',
                'KKS': 'Kira Sertifikası',
                'KKSD': 'Kira Sertifikası Döviz',
                'KKSTL': 'Kira Sertifikası Türk Lirası',
                'KKSYD': 'Kira Sertifikası Yabancı Döviz',
                'KM': 'Kıymetli Maden',
                'KMBYF': 'Kıymetli Maden Borsa Yatırım Fonu',
                'KMKBA': 'Kıymetli Maden Katılma Belgesi Alım',
                'KMKKS': 'Kıymetli Maden Kira Sertifikası',
                'KİBD': 'Kira Sertifikası İpotekli Borçlanma',
                'OSKS': 'Özel Sektör Kira Sertifikası',
                'OST': 'Özel Sektör Tahvili',
                'R': 'Repo',
                'T': 'Tahvil',
                'TPP': 'Ters Repo Para Piyasası',
                'TR': 'Ters Repo',
                'VDM': 'Vadeli Mevduat',
                'VM': 'Vadesiz Mevduat',
                'VMAU': 'Vadesiz Mevduat ABD Doları',
                'VMD': 'Vadesiz Mevduat Döviz',
                'VMTL': 'Vadesiz Mevduat Türk Lirası',
                'VİNT': 'Varlık İpotek Tahvil',
                'YBA': 'Yabancı Borçlanma Araçları',
                'YBKB': 'Yabancı Borsa Katılma Belgesi',
                'YBOSB': 'Yabancı Borsa Özel Sektör Bonusu',
                'YBYF': 'Yabancı Borsa Yatırım Fonu',
                'YHS': 'Yabancı Hisse Senedi',
                'YMK': 'Yabancı Menkul Kıymet',
                'YYF': 'Yabancı Yatırım Fonu',
                'ÖKSYD': 'Özel Sektör Kira Sertifikası Yabancı Döviz',
                'ÖSDB': 'Özel Sektör Devlet Bonusu'
            }
            
            for item in result['data']:
                # Convert timestamp to readable date
                timestamp = int(item.get('TARIH', 0))
                if timestamp > 0:
                    # Convert milliseconds to seconds
                    date_obj = datetime.fromtimestamp(timestamp / 1000, tz=self.turkey_tz)
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                else:
                    formatted_date = ''
                
                # Extract allocation data
                allocation_data = {}
                for key, value in item.items():
                    if key not in ['TARIH', 'FONKODU', 'FONUNVAN', 'BilFiyat'] and value is not None:
                        asset_name = asset_type_mapping.get(key, key)
                        allocation_data[asset_name] = float(value)
                
                portfolio_history.append({
                    'tarih': formatted_date,
                    'fon_kodu': item.get('FONKODU', fund_code),
                    'fon_unvan': item.get('FONUNVAN', ''),
                    'portfoy_dagilimi': allocation_data,
                    'bil_fiyat': item.get('BilFiyat', '')
                })
            
            # Sort by date (newest first)
            portfolio_history.sort(key=lambda x: x['tarih'], reverse=True)
            
            # Get latest allocation for summary
            latest_allocation = portfolio_history[0]['portfoy_dagilimi'] if portfolio_history else {}
            
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date,
                'bitis_tarihi': end_date,
                'portfoy_geçmisi': portfolio_history,
                'son_portfoy_dagilimi': latest_allocation,
                'veri_sayisi': len(portfolio_history),
                'kaynak': 'TEFAS BindHistoryAllocation API'
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio allocation for {fund_code}: {e}")
            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date or '',
                'bitis_tarihi': end_date or '',
                'portfoy_geçmisi': [],
                'son_portfoy_dagilimi': {},
                'veri_sayisi': 0,
                'error_message': str(e)
            }
    
    def compare_funds(self, fund_codes: List[str]) -> Dict[str, Any]:
        """
        Compare multiple funds side by side.
        Enhanced with batch processing approach inspired by widget's Promise.all pattern.
        
        Args:
            fund_codes: List of TEFAS fund codes to compare
            
        Returns:
            Dictionary with comparison data
        """
        try:
            comparison_data = []
            success_count = 0
            error_count = 0
            
            for fund_code in fund_codes[:5]:  # Limit to 5 funds
                fund_detail = self.get_fund_detail(fund_code)
                
                if 'error_message' not in fund_detail:
                    success_count += 1
                    # Enhanced comparison data with widget-inspired fields
                    comparison_item = {
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
                        'yatirimci_sayisi': fund_detail['yatirimci_sayisi'],
                        
                        # Enhanced fields from widget approach
                        'gunluk_getiri': fund_detail.get('gunluk_getiri'),
                        'gunluk_degisim_miktar': fund_detail.get('gunluk_degisim_miktar'),
                        'onceki_gun_fiyat': fund_detail.get('onceki_gun_fiyat'),
                        'veri_kalitesi_skoru': fund_detail.get('veri_kalitesi', {}).get('veri_tamamligi_skoru', 0.0),
                        'api_source': fund_detail.get('api_source', 'unknown')
                    }
                    comparison_data.append(comparison_item)
                else:
                    error_count += 1
                    logger.warning(f"Failed to get details for fund {fund_code}: {fund_detail.get('error_message', 'Unknown error')}")
            
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
            
            # Widget-inspired summary calculations
            total_fund_value = sum(fund.get('toplam_deger', 0) for fund in comparison_data)
            avg_daily_return = sum(fund.get('gunluk_getiri', 0) for fund in comparison_data if fund.get('gunluk_getiri') is not None) / len(comparison_data) if comparison_data else 0
            
            return {
                'karsilastirilan_fonlar': fund_codes,
                'karsilastirma_verileri': comparison_data,
                'fon_sayisi': len(comparison_data),
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                
                # Enhanced summary statistics (inspired by widget's allTotal calculation)
                'basari_orani': round(success_count / len(fund_codes), 2) if fund_codes else 0,
                'basarili_fon_sayisi': success_count,
                'basarisiz_fon_sayisi': error_count,
                'toplam_fon_degeri': round(total_fund_value, 2),
                'ortalama_gunluk_getiri': round(avg_daily_return, 2),
                'veri_kalitesi_ozeti': {
                    'ortalama_skor': round(sum(fund.get('veri_kalitesi_skoru', 0) for fund in comparison_data) / len(comparison_data), 2) if comparison_data else 0,
                    'api_kaynaklari': list(set(fund.get('api_source', 'unknown') for fund in comparison_data))
                }
            }
            
        except Exception as e:
            logger.error(f"Error comparing funds: {e}")
            return {
                'karsilastirilan_fonlar': fund_codes,
                'karsilastirma_verileri': [],
                'fon_sayisi': 0,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
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
                'bulunan_fonlar': [],
                'toplam_sonuc': 0,
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'error_message': str(e)
            }
    
    def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                              start_date: str = None, end_date: str = None, 
                              periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        This uses the same endpoint as TEFAS website's fund comparison page.
        
        Args:
            fund_codes: List of specific fund codes to compare (optional)
            fund_type: Fund type - "YAT" (Investment), "EMK" (Pension), "BYF" (ETF), "GYF" (REIT), "GSYF" (VC)
            start_date: Start date in DD.MM.YYYY format
            end_date: End date in DD.MM.YYYY format  
            periods: List of period codes ["1A", "3A", "6A", "YB", "1Y", "3Y", "5Y"]
            founder: Founder company filter (default "Tümü" for all)
            
        Returns:
            Dictionary with advanced comparison data from official TEFAS API
        """
        try:
            # Set default dates if not provided (last month)
            if not end_date:
                end_date = datetime.now().strftime('%d.%m.%Y')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%d.%m.%Y')
            
            # Set default periods if not provided
            if not periods:
                periods = ["1A", "3A", "6A", "YB", "1Y"]
            
            # Official TEFAS comparison API endpoint
            comparison_url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
            
            # Prepare form data (same structure as TEFAS website)
            period_string = ",".join(["1"] * len(periods))  # "1,1,1,1,1" format
            
            data = {
                'calismatipi': '1',  # Working type
                'fontip': fund_type,  # Fund type
                'sfontur': '',  # Sub fund type
                'kurucukod': founder if founder != "Tümü" else '',  # Founder code
                'fongrup': '',  # Fund group
                'bastarih': start_date,  # Start date
                'bittarih': end_date,  # End date
                'fonturkod': '',  # Fund type code
                'fonunvantip': '',  # Fund title type
                'strperiod': period_string,  # Period string
                'islemdurum': '1'  # Transaction status (1 = active)
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://www.tefas.gov.tr',
                'Referer': 'https://www.tefas.gov.tr/FonKarsilastirma.aspx',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(comparison_url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse the response (could be JSON or HTML table)
            try:
                # Try JSON first
                result_data = response.json()
                comparison_results = []
                
                # Process JSON response - handle both response types
                if isinstance(result_data, dict) and 'data' in result_data:
                    # DataTable format response
                    fund_list = result_data['data']
                elif isinstance(result_data, list):
                    # Direct list format response
                    fund_list = result_data
                else:
                    fund_list = []
                
                for fund_data in fund_list:
                    # Handle both response formats
                    fund_result = {
                        'fon_kodu': fund_data.get('FONKODU', ''),
                        'fon_adi': fund_data.get('FONUNVAN', ''),
                        'fon_turu': fund_data.get('FONTURACIKLAMA', fund_data.get('FONTUR', '')),
                        'kurulus': fund_data.get('KURUCU', ''),
                        'risk_degeri': fund_data.get('RISKDEGERI', 0),
                        'fiyat': fund_data.get('FIYAT', 0),
                        'toplam_deger': fund_data.get('TOPLAMBIRIMFONDEGER', 0),
                        'yatirimci_sayisi': fund_data.get('KISISAYISI', 0),
                        'sharpe_orani': fund_data.get('SHARPEORANI'),
                        'standart_sapma': fund_data.get('STANDARTSAPMA'),
                        'api_source': 'BindComparisonFundReturns'
                    }
                    
                    # Check if we have period-based returns or single return
                    if 'GETIRI1A' in fund_data:
                        # Period-based response (multiple return periods)
                        fund_result.update({
                            'getiri_1_ay': fund_data.get('GETIRI1A'),
                            'getiri_3_ay': fund_data.get('GETIRI3A'),
                            'getiri_6_ay': fund_data.get('GETIRI6A'),
                            'getiri_yil_basi': fund_data.get('GETIRIYB'),
                            'getiri_1_yil': fund_data.get('GETIRI1Y'),
                            'getiri_3_yil': fund_data.get('GETIRI3Y'),
                            'getiri_5_yil': fund_data.get('GETIRI5Y'),
                            'response_type': 'period_based'
                        })
                    elif 'GETIRIORANI' in fund_data:
                        # Date range response (single return rate)
                        fund_result.update({
                            'getiri_orani': fund_data.get('GETIRIORANI'),
                            'response_type': 'date_range'
                        })
                    
                    comparison_results.append(fund_result)
                
            except ValueError:
                # If not JSON, parse HTML table
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for comparison table data
                comparison_results = []
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    if len(rows) > 1:  # Has header and data
                        headers_row = rows[0]
                        header_cells = [th.get_text().strip() for th in headers_row.find_all(['th', 'td'])]
                        
                        for row in rows[1:]:
                            cells = [td.get_text().strip() for td in row.find_all(['td', 'th'])]
                            if len(cells) >= 3:  # At least fund code, name, and some data
                                fund_item = {
                                    'fon_kodu': cells[0] if len(cells) > 0 else '',
                                    'fon_adi': cells[1] if len(cells) > 1 else '',
                                    'fon_turu': cells[2] if len(cells) > 2 else '',
                                    'api_source': 'BindComparisonFundReturns_HTML'
                                }
                                
                                # Map additional columns based on headers
                                for i, header in enumerate(header_cells[3:], 3):
                                    if i < len(cells):
                                        try:
                                            value = float(cells[i].replace('%', '').replace(',', '.'))
                                            fund_item[f'column_{i}_{header.lower().replace(" ", "_")}'] = value
                                        except:
                                            fund_item[f'column_{i}_{header.lower().replace(" ", "_")}'] = cells[i]
                                
                                comparison_results.append(fund_item)
            
            # Filter by specific fund codes if provided
            if fund_codes:
                comparison_results = [
                    fund for fund in comparison_results 
                    if fund.get('fon_kodu', '').upper() in [code.upper() for code in fund_codes]
                ]
            
            # Calculate summary statistics based on response type
            total_funds = len(comparison_results)
            avg_1m_return = 0
            avg_1y_return = 0
            avg_return = 0
            max_return = 0
            min_return = 0
            
            if comparison_results:
                # Check response type from first fund
                response_type = comparison_results[0].get('response_type', 'unknown')
                
                if response_type == 'period_based':
                    # Period-based returns (GETIRI1A, GETIRI1Y, etc.)
                    returns_1m = [f.get('getiri_1_ay', 0) for f in comparison_results if f.get('getiri_1_ay') is not None]
                    returns_1y = [f.get('getiri_1_yil', 0) for f in comparison_results if f.get('getiri_1_yil') is not None]
                    
                    avg_1m_return = sum(returns_1m) / len(returns_1m) if returns_1m else 0
                    avg_1y_return = sum(returns_1y) / len(returns_1y) if returns_1y else 0
                    max_return = max(returns_1y, default=0) if returns_1y else 0
                    min_return = min(returns_1y, default=0) if returns_1y else 0
                elif response_type == 'date_range':
                    # Date range return (GETIRIORANI)
                    returns = [f.get('getiri_orani', 0) for f in comparison_results if f.get('getiri_orani') is not None]
                    avg_return = sum(returns) / len(returns) if returns else 0
                    max_return = max(returns, default=0) if returns else 0
                    min_return = min(returns, default=0) if returns else 0
            
            return {
                'karsilastirma_tipi': 'gelismis_tefas_api',
                'parametreler': {
                    'fon_tipi': fund_type,
                    'baslangic_tarihi': start_date,
                    'bitis_tarihi': end_date,
                    'donemler': periods,
                    'kurucu': founder,
                    'hedef_fon_kodlari': fund_codes or []
                },
                'karsilastirma_verileri': comparison_results,
                'fon_sayisi': total_funds,
                'istatistikler': {
                    'response_type': comparison_results[0].get('response_type', 'unknown') if comparison_results else 'unknown',
                    'ortalama_aylik_getiri': round(avg_1m_return, 2) if avg_1m_return else None,
                    'ortalama_yillik_getiri': round(avg_1y_return, 2) if avg_1y_return else None,
                    'ortalama_getiri': round(avg_return, 2) if avg_return else None,
                    'en_yuksek_getiri': round(max_return, 2) if max_return else None,
                    'en_dusuk_getiri': round(min_return, 2) if min_return else None
                },
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'api_source': 'TEFAS_BindComparisonFundReturns'
            }
            
        except Exception as e:
            logger.error(f"Error in advanced fund comparison: {e}")
            return {
                'karsilastirma_tipi': 'gelismis_tefas_api',
                'parametreler': {
                    'fon_tipi': fund_type,
                    'baslangic_tarihi': start_date,
                    'bitis_tarihi': end_date,
                    'donemler': periods or [],
                    'kurucu': founder,
                    'hedef_fon_kodlari': fund_codes or []
                },
                'karsilastirma_verileri': [],
                'fon_sayisi': 0,
                'istatistikler': {
                    'ortalama_aylik_getiri': 0,
                    'ortalama_yillik_getiri': 0,
                    'en_yuksek_aylik_getiri': 0,
                    'en_dusuk_aylik_getiri': 0
                },
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'error_message': str(e)
            }