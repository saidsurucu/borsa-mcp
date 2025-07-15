"""
Main BorsaApiClient
This class acts as an orchestrator or service layer. It initializes
all data providers (KAP, yfinance) and delegates calls to the 
appropriate provider.
"""
import httpx
import logging
from typing import List, Dict, Any, Optional

# Assuming provider files are in a 'providers' directory
from providers.kap_provider import KAPProvider
from providers.yfinance_provider import YahooFinanceProvider
# from providers.mynet_provider import MynetProvider # Mynet provider is now fully replaced
from models import (
    SirketInfo, FinansalVeriSonucu, YFinancePeriodEnum, SirketProfiliSonucu, 
    FinansalTabloSonucu, SirketAramaSonucu, TaramaKriterleri, TaramaSonucu,
    KatilimFinansUygunlukSonucu, EndeksAramaSonucu,
    EndeksSirketleriSonucu, EndeksSirketDetayi, EndeksKoduAramaSonucu,
    FonAramaSonucu, FonDetayBilgisi, FonPerformansSonucu, FonPortfoySonucu,
    FonKarsilastirmaSonucu, FonTaramaKriterleri, FonTaramaSonucu,
    FonMevzuatSonucu,
    KriptoExchangeInfoSonucu, KriptoTickerSonucu, KriptoOrderbookSonucu,
    KriptoTradesSonucu, KriptoOHLCSonucu, KriptoKlineSonucu, KriptoTeknikAnalizSonucu,
    CoinbaseExchangeInfoSonucu, CoinbaseTickerSonucu, CoinbaseOrderbookSonucu,
    CoinbaseTradesSonucu, CoinbaseOHLCSonucu, CoinbaseServerTimeSonucu, CoinbaseTeknikAnalizSonucu,
    DovizcomGuncelSonucu, DovizcomDakikalikSonucu, DovizcomArsivSonucu,
    EkonomikTakvimSonucu
)
from models.tcmb_models import TcmbEnflasyonSonucu

logger = logging.getLogger(__name__)

class BorsaApiClient:
    def __init__(self, timeout: float = 60.0):
        # A single httpx client for providers that need it (like KAP)
        # SSL verification disabled to avoid certificate issues
        self._http_client = httpx.AsyncClient(timeout=timeout, verify=False)
        
        # Initialize all data providers
        self.kap_provider = KAPProvider(self._http_client)
        self.yfinance_provider = YahooFinanceProvider()
        # Import MynetProvider for hybrid approach
        from providers.mynet_provider import MynetProvider
        self.mynet_provider = MynetProvider(self._http_client)
        # Import TefasProvider for fund data
        from providers.tefas_provider import TefasProvider
        self.tefas_provider = TefasProvider()
        # Import BtcTurkProvider for crypto data
        from providers.btcturk_provider import BtcTurkProvider
        self.btcturk_provider = BtcTurkProvider(self._http_client)
        # Import CoinbaseProvider for global crypto data
        from providers.coinbase_provider import CoinbaseProvider
        self.coinbase_provider = CoinbaseProvider(self._http_client)
        # Import DovizcomProvider for currency and commodities data
        from providers.dovizcom_provider import DovizcomProvider
        self.dovizcom_provider = DovizcomProvider(self._http_client)
        # Import DovizcomCalendarProvider for Turkish economic calendar data
        from providers.dovizcom_calendar_provider import DovizcomCalendarProvider
        self.dovizcom_calendar_provider = DovizcomCalendarProvider(self._http_client)
        # Import TcmbProvider for Turkish inflation data
        from providers.tcmb_provider import TcmbProvider
        self.tcmb_provider = TcmbProvider(self._http_client)

    async def close(self):
        await self._http_client.aclose()
        
    # --- KAP Provider Methods ---
    async def search_companies_from_kap(self, query: str) -> SirketAramaSonucu:
        """Delegates company search to KAPProvider."""
        results = await self.kap_provider.search_companies(query)
        return SirketAramaSonucu(
            arama_terimi=query,
            sonuclar=results,
            sonuc_sayisi=len(results)
        )
    
    async def get_katilim_finans_uygunluk(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates participation finance compatibility data fetching to KAPProvider."""
        return await self.kap_provider.get_katilim_finans_uygunluk(ticker_kodu)
    
    
    async def search_indices_from_kap(self, query: str) -> EndeksKoduAramaSonucu:
        """Delegates index search to KAPProvider."""
        return await self.kap_provider.search_indices(query)

    async def get_endeks_sirketleri(self, endeks_kodu: str) -> EndeksSirketleriSonucu:
        """Get basic company information (ticker and name) for all companies in a given index."""
        try:
            # Get companies directly from Mynet
            ticker_list = await self._fetch_companies_direct_by_code(endeks_kodu)
            
            if not ticker_list:
                return EndeksSirketleriSonucu(
                    endeks_kodu=endeks_kodu,
                    endeks_adi=None,
                    toplam_sirket=0,
                    sirketler=[],
                    error_message=f"No companies found for index '{endeks_kodu}'"
                )
            
            # Create basic company details (just ticker and name from Mynet)
            sirket_detaylari = []
            for ticker, name in ticker_list:
                sirket_detay = EndeksSirketDetayi(
                    ticker_kodu=ticker,
                    sirket_adi=name if name else None
                )
                sirket_detaylari.append(sirket_detay)
            
            return EndeksSirketleriSonucu(
                endeks_kodu=endeks_kodu,
                endeks_adi=f"BIST {endeks_kodu}",  # Simple name based on code
                toplam_sirket=len(sirket_detaylari),
                sirketler=sirket_detaylari
            )
            
        except Exception as e:
            logger.error(f"Error in get_endeks_sirketleri for {endeks_kodu}: {e}")
            return EndeksSirketleriSonucu(
                endeks_kodu=endeks_kodu,
                toplam_sirket=0,
                sirketler=[],
                error_message=str(e)
            )

    async def _fetch_companies_direct_by_code(self, endeks_kodu: str) -> List[tuple]:
        """Fetch companies directly by index code from Mynet."""
        try:
            # Map common index codes to Mynet URLs
            index_url_map = {
                'XU100': 'https://finans.mynet.com/borsa/endeks/xu100-bist-100/',
                'XU050': 'https://finans.mynet.com/borsa/endeks/xu050-bist-50/',
                'XU030': 'https://finans.mynet.com/borsa/endeks/xu030-bist-30/',
                'XBANK': 'https://finans.mynet.com/borsa/endeks/xbank-bist-bankaciligi/',
                'XUTEK': 'https://finans.mynet.com/borsa/endeks/xutek-bist-teknoloji/',
                'XHOLD': 'https://finans.mynet.com/borsa/endeks/xhold-bist-holding-ve-yatirim/',
                'XUSIN': 'https://finans.mynet.com/borsa/endeks/xusin-bist-sinai/',
                'XUMAL': 'https://finans.mynet.com/borsa/endeks/xumal-bist-mali/',
                'XUHIZ': 'https://finans.mynet.com/borsa/endeks/xuhiz-bist-hizmetler/',
                'XGIDA': 'https://finans.mynet.com/borsa/endeks/xgida-bist-gida-icecek/',
                'XELKT': 'https://finans.mynet.com/borsa/endeks/xelkt-bist-elektrik/',
                'XILTM': 'https://finans.mynet.com/borsa/endeks/xiltm-bist-iletisim/',
                'XK100': 'https://finans.mynet.com/borsa/endeks/xk100-bist-katilim-100/',
                'XK050': 'https://finans.mynet.com/borsa/endeks/xk050-bist-katilim-50/',
                'XK030': 'https://finans.mynet.com/borsa/endeks/xk030-bist-katilim-30/'
            }
            
            endeks_kodu_upper = endeks_kodu.upper()
            if endeks_kodu_upper not in index_url_map:
                logger.error(f"Index code {endeks_kodu} not supported")
                return []
            
            endeks_url = index_url_map[endeks_kodu_upper]
            return await self._fetch_companies_with_names_direct(endeks_url)
            
        except Exception as e:
            logger.error(f"Error in _fetch_companies_direct_by_code for {endeks_kodu}: {e}")
            return []
    
    async def _fetch_companies_with_names_direct(self, endeks_url: str) -> List[tuple]:
        """Fetch companies with names from Mynet endeks page."""
        try:
            # Construct the companies URL
            if not endeks_url.endswith('/'):
                endeks_url += '/'
            companies_url = endeks_url + 'endekshisseleri/'
            
            response = await self._http_client.get(companies_url)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'lxml')
            
            table = soup.select_one("table.table-data")
            if not table:
                return []
            
            tbody = table.find("tbody")
            if not tbody:
                return []
            
            companies = []
            for row in tbody.find_all("tr"):
                first_cell = row.find("td")
                if first_cell:
                    company_link = first_cell.find("a")
                    if company_link:
                        title_attr = company_link.get("title", "")
                        if title_attr:
                            parts = title_attr.split()
                            if parts and len(parts) >= 2:
                                ticker = parts[0].upper()
                                # Get company name (everything after ticker)
                                company_name = " ".join(parts[1:])
                                # Validate ticker format (3-6 uppercase letters)
                                import re
                                if re.match(r'^[A-Z]{3,6}$', ticker):
                                    companies.append((ticker, company_name))
            
            return companies
            
        except Exception as e:
            logger.error(f"Error in _fetch_companies_with_names_direct from {endeks_url}: {e}")
            return []

    async def _fetch_companies_direct(self, endeks_url: str) -> List[str]:
        """Direct fetching of companies from Mynet to bypass integration issues."""
        try:
            # Construct the companies URL
            if not endeks_url.endswith('/'):
                endeks_url += '/'
            companies_url = endeks_url + 'endekshisseleri/'
            
            response = await self._http_client.get(companies_url)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'lxml')
            
            table = soup.select_one("table.table-data")
            if not table:
                return []
            
            tbody = table.find("tbody")
            if not tbody:
                return []
            
            companies = []
            for row in tbody.find_all("tr"):
                first_cell = row.find("td")
                if first_cell:
                    company_link = first_cell.find("a")
                    if company_link:
                        title_attr = company_link.get("title", "")
                        if title_attr:
                            parts = title_attr.split()
                            if parts:
                                ticker = parts[0].upper()
                                # Validate ticker format (3-6 uppercase letters)
                                import re
                                if re.match(r'^[A-Z]{3,6}$', ticker):
                                    companies.append(ticker)
            
            return companies
            
        except Exception as e:
            logger.error(f"Error in direct company fetching from {endeks_url}: {e}")
            return []

    # --- YFinance Provider Methods ---
    async def get_finansal_veri(self, ticker_kodu: str, zaman_araligi: YFinancePeriodEnum) -> Dict[str, Any]:
        """Delegates historical data fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_finansal_veri(ticker_kodu, zaman_araligi)
        
    async def get_sirket_bilgileri_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates company info fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_sirket_bilgileri(ticker_kodu)
    
    async def get_sirket_bilgileri_mynet(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates company info fetching to MynetProvider."""
        return await self.mynet_provider.get_sirket_bilgileri(ticker_kodu)
    
    async def get_kap_haberleri_mynet(self, ticker_kodu: str, limit: int = 10) -> Dict[str, Any]:
        """Delegates KAP news fetching to MynetProvider."""
        return await self.mynet_provider.get_kap_haberleri(ticker_kodu, limit)
    
    async def get_kap_haber_detayi_mynet(self, haber_url: str, sayfa_numarasi: int = 1) -> Dict[str, Any]:
        """Delegates KAP news detail fetching to MynetProvider with pagination support."""
        return await self.mynet_provider.get_kap_haber_detayi(haber_url, sayfa_numarasi)
    
    async def get_sirket_bilgileri_hibrit(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Fetches comprehensive company information from both Yahoo Finance and Mynet.
        Combines international financial data with Turkish-specific company details.
        """
        try:
            # Get Yahoo Finance data (financial metrics, ratios, market data)
            yahoo_result = await self.yfinance_provider.get_sirket_bilgileri(ticker_kodu)
            
            # Get Mynet data (Turkish-specific company details)
            mynet_result = await self.mynet_provider.get_sirket_bilgileri(ticker_kodu)
            
            # Combine results
            combined_result = {
                "ticker_kodu": ticker_kodu,
                "kaynak": "hibrit",
                "yahoo_data": yahoo_result,
                "mynet_data": mynet_result,
                "veri_kalitesi": {
                    "yahoo_basarili": not yahoo_result.get("error"),
                    "mynet_basarili": not mynet_result.get("error"),
                    "toplam_kaynak": 2,
                    "basarili_kaynak": sum([
                        not yahoo_result.get("error"),
                        not mynet_result.get("error")
                    ])
                }
            }
            
            # If both sources failed, return error
            if yahoo_result.get("error") and mynet_result.get("error"):
                return {
                    "error": "Her iki kaynaktan da veri alınamadı",
                    "yahoo_error": yahoo_result.get("error"),
                    "mynet_error": mynet_result.get("error")
                }
            
            return combined_result
            
        except Exception as e:
            logger.exception(f"Error in hybrid company info for {ticker_kodu}")
            return {"error": f"Hibrit veri alma sırasında hata: {str(e)}"}
        
        
    async def get_bilanco_yfinance(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Delegates balance sheet fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_bilanco(ticker_kodu, period_type)

    async def get_kar_zarar_yfinance(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Delegates income statement fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_kar_zarar(ticker_kodu, period_type)
    
    async def get_nakit_akisi_yfinance(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Delegates cash flow statement fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_nakit_akisi(ticker_kodu, period_type)
    
    async def get_analist_verileri_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates analyst data fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_analist_verileri(ticker_kodu)
    
    async def get_temettu_ve_aksiyonlar_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates dividend and corporate actions fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_temettu_ve_aksiyonlar(ticker_kodu)
    
    async def get_hizli_bilgi_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates fast info fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_hizli_bilgi(ticker_kodu)
    
    async def get_kazanc_takvimi_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates earnings calendar fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_kazanc_takvimi(ticker_kodu)
    
    async def get_teknik_analiz_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates technical analysis to YahooFinanceProvider."""
        return self.yfinance_provider.get_teknik_analiz(ticker_kodu)
    
    async def get_sektor_karsilastirmasi_yfinance(self, ticker_listesi: List[str]) -> Dict[str, Any]:
        """Delegates sector analysis to YahooFinanceProvider."""
        return self.yfinance_provider.get_sektor_karsilastirmasi(ticker_listesi)
        
    # --- Mynet Provider Methods (Permanently Disabled as per migration to yfinance) ---
    async def get_hisse_detayi(self, ticker_kodu: str) -> Dict[str, Any]:
        logger.warning("Mynet-based get_hisse_detayi is disabled. Use yfinance-based tools.")
        return {"error": "This function is deprecated and disabled. Please use yfinance-based tools."}
    
    async def get_mevcut_bilanco_donemleri(self, ticker_kodu: str) -> Dict[str, Any]:
        logger.warning("Mynet-based get_mevcut_bilanco_donemleri is disabled.")
        return {"error": "This function is deprecated and disabled."}
        
    async def get_mevcut_kar_zarar_donemleri(self, ticker_kodu: str) -> Dict[str, Any]:
        logger.warning("Mynet-based get_mevcut_kar_zarar_donemleri is disabled.")
        return {"error": "This function is deprecated and disabled."}
        
    # --- Stock Screening Methods ---
    async def hisse_tarama(self, kriterler: TaramaKriterleri) -> Dict[str, Any]:
        """
        Comprehensive stock screening with flexible criteria.
        Gets company list from KAP and applies screening via yfinance.
        """
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Retrieved {len(all_companies)} companies from KAP for screening")
            
            # Delegate screening to yfinance provider
            return await self.yfinance_provider.hisse_tarama(kriterler, all_companies)
        except Exception as e:
            logger.exception(f"Error in client-level stock screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def deger_yatirim_taramasi(self) -> Dict[str, Any]:
        """Value investing screening preset - stocks with low P/E, P/B ratios."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting value investment screening with {len(all_companies)} companies")
            
            # Apply value investing screening
            return await self.yfinance_provider.deger_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception(f"Error in value investment screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def temettu_yatirim_taramasi(self) -> Dict[str, Any]:
        """Dividend investing screening preset - stocks with high dividend yields."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting dividend investment screening with {len(all_companies)} companies")
            
            # Apply dividend investing screening
            return await self.yfinance_provider.temettu_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception(f"Error in dividend investment screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def buyume_yatirim_taramasi(self) -> Dict[str, Any]:
        """Growth investing screening preset - stocks with high revenue/earnings growth."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting growth investment screening with {len(all_companies)} companies")
            
            # Apply growth investing screening
            return await self.yfinance_provider.buyume_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception(f"Error in growth investment screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def muhafazakar_yatirim_taramasi(self) -> Dict[str, Any]:
        """Conservative investing screening preset - low-risk, stable stocks."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting conservative investment screening with {len(all_companies)} companies")
            
            # Apply conservative investing screening
            return await self.yfinance_provider.muhafazakar_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception(f"Error in conservative investment screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def buyuk_sirket_taramasi(self, min_market_cap: float = 50_000_000_000) -> Dict[str, Any]:
        """Large cap stocks screening - companies above specified market cap threshold."""
        try:
            kriterler = TaramaKriterleri(min_market_cap=min_market_cap)
            return await self.hisse_tarama(kriterler)
        except Exception as e:
            logger.exception(f"Error in large cap screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20) -> FonAramaSonucu:
        """Search for funds by name, code, or founder."""
        try:
            result = await self.tefas_provider.search_funds(search_term, limit)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }
    
    async def sektor_taramasi(self, sectors: List[str]) -> Dict[str, Any]:
        """Sector-specific screening - filter companies by specific sectors."""
        try:
            kriterler = TaramaKriterleri(sectors=sectors)
            return await self.hisse_tarama(kriterler)
        except Exception as e:
            logger.exception(f"Error in sector screening")
            return {"error": str(e)}
    
    # --- TEFAS Fund Methods ---
    async def search_funds(self, search_term: str, limit: int = 20, use_takasbank: bool = True) -> FonAramaSonucu:
        """Search for funds by name, code, or founder using Takasbank data by default."""
        try:
            result = self.tefas_provider.search_funds(search_term, limit, use_takasbank)
            return FonAramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error searching funds with term {search_term}")
            return FonAramaSonucu(
                arama_terimi=search_term,
                sonuclar=[],
                sonuc_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_detail(self, fund_code: str, include_price_history: bool = False) -> FonDetayBilgisi:
        """Get detailed information about a specific fund."""
        try:
            result = self.tefas_provider.get_fund_detail(fund_code, include_price_history)
            return FonDetayBilgisi(**result)
        except Exception as e:
            logger.exception(f"Error getting fund detail for {fund_code}")
            return FonDetayBilgisi(
                fon_kodu=fund_code,
                fon_adi="",
                tarih="",
                fiyat=0,
                tedavuldeki_pay_sayisi=0,
                toplam_deger=0,
                birim_pay_degeri=0,
                yatirimci_sayisi=0,
                kurulus="",
                yonetici="",
                fon_turu="",
                risk_degeri=0,
                error_message=str(e)
            )
    
    async def get_fund_performance(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPerformansSonucu:
        """Get historical performance data for a fund."""
        try:
            result = self.tefas_provider.get_fund_performance(fund_code, start_date, end_date)
            return FonPerformansSonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund performance for {fund_code}")
            return FonPerformansSonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                fiyat_geçmisi=[],
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def get_fund_portfolio(self, fund_code: str, start_date: str = None, end_date: str = None) -> FonPortfoySonucu:
        """Get portfolio allocation composition of a fund using official TEFAS BindHistoryAllocation API."""
        try:
            result = self.tefas_provider.get_fund_portfolio(fund_code, start_date, end_date)
            return FonPortfoySonucu(**result)
        except Exception as e:
            logger.exception(f"Error getting fund portfolio for {fund_code}")
            return FonPortfoySonucu(
                fon_kodu=fund_code,
                baslangic_tarihi=start_date or "",
                bitis_tarihi=end_date or "",
                portfoy_geçmisi=[],
                son_portfoy_dagilimi={},
                veri_sayisi=0,
                error_message=str(e)
            )
    
    async def compare_funds(self, fund_codes: List[str]) -> FonKarsilastirmaSonucu:
        """Compare multiple funds side by side."""
        try:
            result = self.tefas_provider.compare_funds(fund_codes)
            return FonKarsilastirmaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error comparing funds")
            return FonKarsilastirmaSonucu(
                karsilastirilan_fonlar=fund_codes,
                karsilastirma_verileri=[],
                fon_sayisi=0,
                tarih="",
                error_message=str(e)
            )
    
    async def screen_funds(self, criteria: FonTaramaKriterleri) -> FonTaramaSonucu:
        """Screen funds based on various criteria."""
        try:
            result = self.tefas_provider.screen_funds(criteria.dict(exclude_none=True))
            return FonTaramaSonucu(**result)
        except Exception as e:
            logger.exception(f"Error screening funds")
            return FonTaramaSonucu(
                tarama_kriterleri=criteria,
                bulunan_fonlar=[],
                toplam_sonuc=0,
                tarih="",
                error_message=str(e)
            )
    
    async def compare_funds_advanced(self, fund_codes: List[str] = None, fund_type: str = "EMK", 
                                   start_date: str = None, end_date: str = None, 
                                   periods: List[str] = None, founder: str = "Tümü") -> Dict[str, Any]:
        """
        Advanced fund comparison using TEFAS official comparison API.
        Uses the same endpoint as TEFAS website's fund comparison page.
        """
        try:
            result = self.tefas_provider.compare_funds_advanced(
                fund_codes=fund_codes,
                fund_type=fund_type,
                start_date=start_date,
                end_date=end_date,
                periods=periods,
                founder=founder
            )
            return result
        except Exception as e:
            logger.exception(f"Error in advanced fund comparison")
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
                'tarih': "",
                'error_message': str(e)
            }


    # --- Fon Mevzuat Methods ---
    async def get_fon_mevzuati(self) -> FonMevzuatSonucu:
        """
        Yatırım fonları mevzuat rehberini getirir.
        Bu mevzuat sadece yatırım fonlarına ilişkin düzenlemeleri içerir, tüm borsa mevzuatını kapsamaz.
        """
        try:
            import os
            from datetime import datetime
            import importlib.resources
            
            # Try different approaches to read the regulation content
            try:
                # Approach 1: Try to import from fon_mevzuat_kisa module (for installed package)
                try:
                    from fon_mevzuat_kisa import FON_MEVZUAT_KISA
                    mevzuat_icerik = FON_MEVZUAT_KISA
                    guncelleme_tarihi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    logger.info("Loaded regulation from fon_mevzuat_kisa.py module")
                except ImportError:
                    logger.warning("fon_mevzuat_kisa module not found, trying local file")
                    
                    # Approach 2: Try local file (development mode)
                    mevzuat_dosya_yolu = os.path.join(os.path.dirname(__file__), "fon_mevzuat_kisa.md")
                    
                    if not os.path.exists(mevzuat_dosya_yolu):
                        return FonMevzuatSonucu(
                            mevzuat_adi="Yatırım Fonları Mevzuat Rehberi",
                            icerik="",
                            karakter_sayisi=0,
                            kaynak_dosya="fon_mevzuat_kisa.md",
                            error_message="Fon mevzuat dosyası bulunamadı (ne Python modülü ne de .md dosyası)"
                        )
                    
                    # Dosyayı oku
                    with open(mevzuat_dosya_yolu, 'r', encoding='utf-8') as file:
                        mevzuat_icerik = file.read()
                    
                    # Dosya bilgilerini al
                    dosya_stat = os.stat(mevzuat_dosya_yolu)
                    guncelleme_tarihi = datetime.fromtimestamp(dosya_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    logger.info("Loaded regulation from local file")
                    
            except Exception as fallback_error:
                logger.error(f"All regulation loading methods failed: {fallback_error}")
                # Son fallback - minimal content
                mevzuat_icerik = """# Yatırım Fonları Mevzuat Rehberi

**UYARI:** Bu içerik yalnızca test amaçlıdır. Tam mevzuat içeriği package'da bulunamadı.

## Temel Fon Düzenlemeleri
- Portföy sınırlamaları
- Risk yönetimi gereklilikleri  
- Fon türleri ve yapıları

Detaylı mevzuat için SPK resmi web sitesini ziyaret edin.
"""
                guncelleme_tarihi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return FonMevzuatSonucu(
                mevzuat_adi="Yatırım Fonları Mevzuat Rehberi",
                icerik=mevzuat_icerik,
                karakter_sayisi=len(mevzuat_icerik),
                kaynak_dosya="fon_mevzuat_kisa.md",
                guncelleme_tarihi=guncelleme_tarihi
            )
            
        except Exception as e:
            logger.exception(f"Error reading fund regulation document")
            return FonMevzuatSonucu(
                mevzuat_adi="Yatırım Fonları Mevzuat Rehberi",
                icerik="",
                karakter_sayisi=0,
                kaynak_dosya="fon_mevzuat_kisa.md",
                error_message=f"Fon mevzuat dosyası okunurken hata: {str(e)}"
            )

    # --- BtcTurk Kripto Provider Methods ---
    
    async def get_kripto_exchange_info(self) -> KriptoExchangeInfoSonucu:
        """Get detailed information about all trading pairs and currencies on BtcTurk."""
        return await self.btcturk_provider.get_exchange_info()
    
    async def get_kripto_ticker(self, pair_symbol: Optional[str] = None, quote_currency: Optional[str] = None) -> KriptoTickerSonucu:
        """Get ticker data for specific trading pair(s) or all pairs."""
        return await self.btcturk_provider.get_ticker(pair_symbol, quote_currency)
    
    async def get_kripto_orderbook(self, pair_symbol: str, limit: int = 100) -> KriptoOrderbookSonucu:
        """Get order book data for a specific trading pair."""
        return await self.btcturk_provider.get_orderbook(pair_symbol, limit)
    
    async def get_kripto_trades(self, pair_symbol: str, last: int = 50) -> KriptoTradesSonucu:
        """Get recent trades for a specific trading pair."""
        return await self.btcturk_provider.get_trades(pair_symbol, last)
    
    async def get_kripto_ohlc(self, pair: str, from_time: Optional[int] = None, to_time: Optional[int] = None) -> KriptoOHLCSonucu:
        """Get OHLC data for a specific trading pair."""
        return await self.btcturk_provider.get_ohlc(pair, from_time, to_time)
    
    async def get_kripto_kline(self, symbol: str, resolution: str, from_time: int, to_time: int) -> KriptoKlineSonucu:
        """Get Kline (candlestick) data for a specific symbol."""
        return await self.btcturk_provider.get_kline(symbol, resolution, from_time, to_time)
    
    async def get_kripto_teknik_analiz(self, symbol: str, resolution: str = "1D") -> KriptoTeknikAnalizSonucu:
        """Get comprehensive technical analysis for cryptocurrency pairs."""
        return await self.btcturk_provider.get_kripto_teknik_analiz(symbol, resolution)

    # --- Coinbase Global Crypto Provider Methods ---
    
    async def get_coinbase_exchange_info(self) -> CoinbaseExchangeInfoSonucu:
        """Get detailed information about all trading pairs and currencies on Coinbase."""
        return await self.coinbase_provider.get_exchange_info()
    
    async def get_coinbase_ticker(self, product_id: Optional[str] = None, quote_currency: Optional[str] = None) -> CoinbaseTickerSonucu:
        """Get ticker data for specific trading pair(s) or all pairs on Coinbase."""
        return await self.coinbase_provider.get_ticker(product_id, quote_currency)
    
    async def get_coinbase_orderbook(self, product_id: str, limit: int = 100) -> CoinbaseOrderbookSonucu:
        """Get order book data for a specific trading pair on Coinbase."""
        return await self.coinbase_provider.get_orderbook(product_id, limit)
    
    async def get_coinbase_trades(self, product_id: str, limit: int = 100) -> CoinbaseTradesSonucu:
        """Get recent trades for a specific trading pair on Coinbase."""
        return await self.coinbase_provider.get_trades(product_id, limit)
    
    async def get_coinbase_ohlc(self, product_id: str, start: Optional[str] = None, end: Optional[str] = None, granularity: str = "ONE_HOUR") -> CoinbaseOHLCSonucu:
        """Get OHLC data for a specific trading pair on Coinbase."""
        return await self.coinbase_provider.get_ohlc(product_id, start, end, granularity)
    
    async def get_coinbase_server_time(self) -> CoinbaseServerTimeSonucu:
        """Get Coinbase server time and status."""
        return await self.coinbase_provider.get_server_time()
    
    async def get_coinbase_teknik_analiz(self, product_id: str, granularity: str = "ONE_DAY") -> "CoinbaseTeknikAnalizSonucu":
        """Get comprehensive technical analysis for Coinbase crypto pairs."""
        return await self.coinbase_provider.get_coinbase_teknik_analiz(product_id, granularity)
    
    # --- Dovizcom Provider Methods ---
    async def get_dovizcom_guncel_kur(self, asset: str) -> "DovizcomGuncelSonucu":
        """Get current exchange rate or commodity price from doviz.com."""
        return await self.dovizcom_provider.get_asset_current(asset)
    
    async def get_dovizcom_dakikalik_veri(self, asset: str, limit: int = 60) -> "DovizcomDakikalikSonucu":
        """Get minute-by-minute data from doviz.com."""
        return await self.dovizcom_provider.get_asset_daily(asset, limit)
    
    async def get_dovizcom_arsiv_veri(self, asset: str, start_date: str, end_date: str) -> "DovizcomArsivSonucu":
        """Get historical OHLC archive data from doviz.com."""
        return await self.dovizcom_provider.get_asset_archive(asset, start_date, end_date)
    
    # --- Dovizcom Calendar Provider Methods ---
    async def get_economic_calendar(
        self, 
        start_date: str, 
        end_date: str,
        high_importance_only: bool = True,
        country_filter: Optional[str] = None
    ) -> "EkonomikTakvimSonucu":
        """Get Turkish economic calendar events from Doviz.com."""
        return await self.dovizcom_calendar_provider.get_economic_calendar(
            start_date, end_date, high_importance_only, country_filter
        )
    
    # --- TCMB Provider Methods ---
    async def get_turkiye_enflasyon(
        self,
        inflation_type: str = 'tufe',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> "TcmbEnflasyonSonucu":
        """Get Turkish inflation data from TCMB."""
        return await self.tcmb_provider.get_inflation_data(
            inflation_type, start_date, end_date, limit
        )
    
    async def calculate_inflation(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        basket_value: float = 100.0
    ) -> "EnflasyonHesaplamaSonucu":
        """Calculate cumulative inflation using TCMB calculator API."""
        return await self.tcmb_provider.calculate_inflation(
            start_year, start_month, end_year, end_month, basket_value
        )
