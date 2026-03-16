"""
TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) provider for Turkish mutual funds.
Provides comprehensive fund data, performance metrics, and screening capabilities.
"""

import requests
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
import logging
from zoneinfo import ZoneInfo
import os
import borsapy as bp

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
            except OSError:
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
        Advanced fund search using borsapy (WAF-safe, handles chunked requests).
        Provides comprehensive and up-to-date fund data with performance metrics.

        Args:
            search_term: Search term for fund name, code, or founder
            limit: Maximum number of results to return
            fund_type: Fund type - "YAT" (Investment), "EMK" (Pension), "BYF" (ETF), etc.
            fund_category: Fund category filter for detailed classification

        Returns:
            Dictionary with advanced search results including performance data
        """
        try:
            import asyncio
            # borsapy.search_funds is sync, run in executor
            results = await asyncio.get_event_loop().run_in_executor(
                None, lambda: bp.search_funds(search_term, limit=limit)
            )

            matching_funds = []
            for fund in results:
                matching_funds.append({
                    'fon_kodu': fund.get('fund_code', ''),
                    'fon_adi': fund.get('name', ''),
                    'fon_turu': fund.get('fund_type', ''),
                    'getiri_1_ay': fund.get('return_1m'),
                    'getiri_3_ay': fund.get('return_3m'),
                    'getiri_6_ay': fund.get('return_6m'),
                    'getiri_1_yil': fund.get('return_1y'),
                    'getiri_yil_basi': fund.get('return_ytd'),
                    'getiri_3_yil': fund.get('return_3y'),
                    'getiri_5_yil': fund.get('return_5y'),
                    'api_source': 'borsapy'
                })

            # Sort by 1-year return (descending, null values last)
            matching_funds.sort(key=lambda x: x.get('getiri_1_yil') or -999999, reverse=True)

            # Limit results
            limited_funds = matching_funds[:limit]

            # Apply token optimization to fund search results
            from token_optimizer import TokenOptimizer
            optimized_funds = TokenOptimizer.optimize_fund_search_results(limited_funds, limit)

            return {
                'arama_terimi': search_term,
                'sonuclar': optimized_funds,
                'sonuc_sayisi': len(optimized_funds),
                'toplam_bulunan': len(matching_funds),
                'kaynak': 'borsapy',
                'fund_type': fund_type,
                'fund_category': fund_category,
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
                'kaynak': 'borsapy',
                'fund_type': fund_type,
                'fund_category': fund_category,
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
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
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
                
                # Risk metrics - try API first, fallback to borsapy calculation
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

            # Fill missing risk metrics from borsapy if API didn't provide them
            if result_data.get('sharpe_orani') is None or result_data.get('standart_sapma') is None:
                try:
                    bp_fund = bp.Fund(fund_code)
                    risk = bp_fund.risk_metrics()
                    if result_data.get('sharpe_orani') is None and risk.get('sharpe_ratio') is not None:
                        result_data['sharpe_orani'] = float(risk['sharpe_ratio'])
                    if result_data.get('standart_sapma') is None and risk.get('annualized_volatility') is not None:
                        result_data['standart_sapma'] = float(risk['annualized_volatility'])
                except Exception as e:
                    logger.debug(f"Could not fetch risk metrics from borsapy for {fund_code}: {e}")

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
        Get historical performance data for a fund using borsapy (WAF-safe, chunked requests).

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

            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            # Use borsapy Fund.history() - handles WAF chunking internally
            fund = bp.Fund(fund_code)
            df = fund.history(start=start_date, end=end_date)

            if df.empty:
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

            # Convert DataFrame to list of dicts (newest first)
            price_history = []
            for date_idx, row in df.iterrows():
                if hasattr(date_idx, 'strftime'):
                    formatted_date = date_idx.strftime('%Y-%m-%d')
                else:
                    formatted_date = str(date_idx)[:10]
                price_history.append({
                    'tarih': formatted_date,
                    'fiyat': float(row.get('Price', 0)),
                    'toplam_deger': float(row.get('FundSize', 0)),
                    'yatirimci_sayisi': int(row.get('Investors', 0)),
                })

            # Sort by date (newest first)
            price_history.sort(key=lambda x: x['tarih'], reverse=True)

            # Calculate time frame for optimization
            time_frame_days = (end_dt - start_dt).days

            # Apply token optimization
            from token_optimizer import TokenOptimizer
            optimized_history = TokenOptimizer.optimize_fund_performance(price_history, time_frame_days)

            # Calculate returns
            total_return = None
            annualized_return = None
            if len(optimized_history) >= 2:
                latest_price = optimized_history[0]['fiyat']
                oldest_price = optimized_history[-1]['fiyat']

                if oldest_price > 0:
                    total_return = ((latest_price - oldest_price) / oldest_price) * 100
                    days = (end_dt - start_dt).days
                    if days > 0:
                        annualized_return = ((latest_price / oldest_price) ** (365 / days) - 1) * 100
                    else:
                        annualized_return = total_return

            return {
                'fon_kodu': fund_code,
                'baslangic_tarihi': start_date,
                'bitis_tarihi': end_date,
                'fiyat_geçmisi': optimized_history,
                'toplam_getiri': total_return,
                'yillik_getiri': annualized_return,
                'veri_sayisi': len(optimized_history),
                'kaynak': 'borsapy'
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
                sorted_by_return = sorted(comparison_data, key=lambda x: x.get('getiri_1_yil') or 0, reverse=True)
                for i, fund in enumerate(sorted_by_return):
                    fund['getiri_siralamasi'] = i + 1

                # Rank by Sharpe ratio
                sorted_by_sharpe = sorted(comparison_data, key=lambda x: x.get('sharpe_orani') or 0, reverse=True)
                for i, fund in enumerate(sorted_by_sharpe):
                    fund['risk_ayarli_getiri_siralamasi'] = i + 1

                # Rank by size
                sorted_by_size = sorted(comparison_data, key=lambda x: x.get('toplam_deger') or 0, reverse=True)
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
        Screen funds based on various criteria using borsapy (WAF-safe).

        Args:
            criteria: Dictionary with screening criteria
                - fund_type: Fund type (e.g., 'YAT', 'EMK')
                - min_return_1y: Minimum 1-year return
                - min_return_1m: Minimum 1-month return
                - min_return_3m: Minimum 3-month return
                - min_return_6m: Minimum 6-month return
                - min_return_ytd: Minimum year-to-date return
                - founder: Specific founder/company code

        Returns:
            Dictionary with screening results
        """
        try:
            # Use borsapy.screen_funds - handles WAF internally
            screen_df = bp.screen_funds(
                fund_type=criteria.get('fund_type', 'YAT'),
                founder=criteria.get('founder'),
                min_return_1m=criteria.get('min_return_1m'),
                min_return_3m=criteria.get('min_return_3m'),
                min_return_6m=criteria.get('min_return_6m'),
                min_return_ytd=criteria.get('min_return_ytd'),
                min_return_1y=criteria.get('min_return_1y'),
                min_return_3y=criteria.get('min_return_3y'),
                limit=50,
            )

            screened_funds = []
            if hasattr(screen_df, 'iterrows'):
                for _, row in screen_df.iterrows():
                    screened_funds.append({
                        'fon_kodu': row.get('fund_code', ''),
                        'fon_adi': row.get('name', ''),
                        'fon_turu': row.get('fund_type', ''),
                        'getiri_1_ay': row.get('return_1m'),
                        'getiri_3_ay': row.get('return_3m'),
                        'getiri_6_ay': row.get('return_6m'),
                        'getiri_yil_basi': row.get('return_ytd'),
                        'getiri_1_yil': row.get('return_1y'),
                        'getiri_3_yil': row.get('return_3y'),
                        'getiri_5_yil': row.get('return_5y'),
                    })

            return {
                'tarama_kriterleri': criteria,
                'bulunan_fonlar': screened_funds,
                'toplam_sonuc': len(screened_funds),
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'kaynak': 'borsapy'
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
        Advanced fund comparison using borsapy (WAF-safe).

        Args:
            fund_codes: List of specific fund codes to compare (optional)
            fund_type: Fund type - "YAT" (Investment), "EMK" (Pension), "BYF" (ETF), "GYF" (REIT), "GSYF" (VC)
            start_date: Start date in DD.MM.YYYY format
            end_date: End date in DD.MM.YYYY format
            periods: List of period codes ["1A", "3A", "6A", "YB", "1Y", "3Y", "5Y"]
            founder: Founder company filter (default "Tümü" for all)

        Returns:
            Dictionary with advanced comparison data
        """
        try:
            if not periods:
                periods = ["1A", "3A", "6A", "YB", "1Y"]

            if fund_codes:
                # Use borsapy.compare_funds for specific fund codes
                result = bp.compare_funds(fund_codes)

                comparison_results = []
                for fund_data in result.get('funds', []):
                    fund_result = {
                        'fon_kodu': fund_data.get('fund_code', ''),
                        'fon_adi': fund_data.get('name', ''),
                        'fon_turu': fund_data.get('fund_type', ''),
                        'kurulus': fund_data.get('founder', ''),
                        'risk_degeri': fund_data.get('risk_value', 0),
                        'fiyat': fund_data.get('price', 0),
                        'toplam_deger': fund_data.get('fund_size', 0),
                        'yatirimci_sayisi': fund_data.get('investor_count', 0),
                        'getiri_1_ay': fund_data.get('return_1m'),
                        'getiri_3_ay': fund_data.get('return_3m'),
                        'getiri_6_ay': fund_data.get('return_6m'),
                        'getiri_yil_basi': fund_data.get('return_ytd'),
                        'getiri_1_yil': fund_data.get('return_1y'),
                        'getiri_3_yil': fund_data.get('return_3y'),
                        'getiri_5_yil': fund_data.get('return_5y'),
                        'response_type': 'period_based',
                        'api_source': 'borsapy'
                    }
                    comparison_results.append(fund_result)
            else:
                # Use borsapy.screen_funds to get all funds of the type
                screen_result = bp.screen_funds(fund_type=fund_type, limit=50)

                comparison_results = []
                if hasattr(screen_result, 'iterrows'):
                    for _, row in screen_result.iterrows():
                        fund_result = {
                            'fon_kodu': row.get('fund_code', ''),
                            'fon_adi': row.get('name', ''),
                            'fon_turu': row.get('fund_type', ''),
                            'getiri_1_ay': row.get('return_1m'),
                            'getiri_3_ay': row.get('return_3m'),
                            'getiri_6_ay': row.get('return_6m'),
                            'getiri_yil_basi': row.get('return_ytd'),
                            'getiri_1_yil': row.get('return_1y'),
                            'getiri_3_yil': row.get('return_3y'),
                            'getiri_5_yil': row.get('return_5y'),
                            'response_type': 'period_based',
                            'api_source': 'borsapy'
                        }
                        comparison_results.append(fund_result)

            # Calculate summary statistics
            total_funds = len(comparison_results)
            returns_1m = [f.get('getiri_1_ay', 0) for f in comparison_results if f.get('getiri_1_ay') is not None]
            returns_1y = [f.get('getiri_1_yil', 0) for f in comparison_results if f.get('getiri_1_yil') is not None]

            avg_1m_return = sum(returns_1m) / len(returns_1m) if returns_1m else 0
            avg_1y_return = sum(returns_1y) / len(returns_1y) if returns_1y else 0
            max_return = max(returns_1y, default=0) if returns_1y else 0
            min_return = min(returns_1y, default=0) if returns_1y else 0

            return {
                'karsilastirma_tipi': 'borsapy',
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
                    'response_type': 'period_based',
                    'ortalama_aylik_getiri': round(avg_1m_return, 2) if avg_1m_return else None,
                    'ortalama_yillik_getiri': round(avg_1y_return, 2) if avg_1y_return else None,
                    'en_yuksek_getiri': round(max_return, 2) if max_return else None,
                    'en_dusuk_getiri': round(min_return, 2) if min_return else None
                },
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'api_source': 'borsapy'
            }

        except Exception as e:
            logger.error(f"Error in advanced fund comparison: {e}")
            return {
                'karsilastirma_tipi': 'borsapy',
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
                    'en_yuksek_getiri': 0,
                    'en_dusuk_getiri': 0
                },
                'tarih': datetime.now().strftime('%Y-%m-%d'),
                'error_message': str(e)
            }
