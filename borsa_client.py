"""
Main BorsaApiClient
This class acts as an orchestrator or service layer. It initializes
all data providers (KAP, yfinance) and delegates calls to the 
appropriate provider.
"""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional

# Assuming provider files are in a 'providers' directory
from providers.kap_provider import KAPProvider
from providers.yfinance_provider import YahooFinanceProvider
# from providers.mynet_provider import MynetProvider # Mynet provider is now fully replaced
from models import (
    YFinancePeriodEnum,
    SirketAramaSonucu,
    TaramaKriterleri,
    EndeksSirketleriSonucu,
    EndeksSirketDetayi,
    EndeksKoduAramaSonucu,
    FonAramaSonucu,
    FonDetayBilgisi,
    FonPerformansSonucu,
    FonPortfoySonucu,
    FonKarsilastirmaSonucu,
    FonTaramaKriterleri,
    FonTaramaSonucu,
    FonMevzuatSonucu,
    KriptoExchangeInfoSonucu,
    KriptoTickerSonucu,
    KriptoOrderbookSonucu,
    KriptoTradesSonucu,
    KriptoOHLCSonucu,
    KriptoKlineSonucu,
    KriptoTeknikAnalizSonucu,
    CoinbaseExchangeInfoSonucu,
    CoinbaseTickerSonucu,
    CoinbaseOrderbookSonucu,
    CoinbaseTradesSonucu,
    CoinbaseOHLCSonucu,
    CoinbaseServerTimeSonucu,
    CoinbaseTeknikAnalizSonucu,
    DovizcomGuncelSonucu,
    DovizcomDakikalikSonucu,
    DovizcomArsivSonucu,
    EkonomikTakvimSonucu,
)
from models.tcmb_models import EnflasyonHesaplamaSonucu, TcmbEnflasyonSonucu

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
        # Import DovizcomTahvilProvider for bond yields
        from providers.dovizcom_tahvil_provider import DovizcomTahvilProvider
        self.tahvil_provider = DovizcomTahvilProvider(self._http_client)
        # Import WorldBankProvider for GDP growth data
        from providers.worldbank_provider import WorldBankProvider
        self.worldbank_provider = WorldBankProvider(self._http_client)
        # Import BuffettAnalyzerProvider for value investing calculations
        from providers.buffett_analyzer_provider import BuffettAnalyzerProvider
        self.buffett_provider = BuffettAnalyzerProvider(
            tahvil_provider=self.tahvil_provider,
            tcmb_provider=self.tcmb_provider,
            worldbank_provider=self.worldbank_provider,
            yfinance_provider=self.yfinance_provider
        )

        # Import İş Yatırım Provider for financial statements
        from providers.isyatirim_provider import IsYatirimProvider
        self.isyatirim_provider = IsYatirimProvider()

        # Import FinancialRatiosProvider for financial ratio calculations
        # Pass self (BorsaClient) so it uses İş Yatırım integration
        from providers.financial_ratios_provider import FinancialRatiosProvider
        self.financial_ratios_provider = FinancialRatiosProvider(
            data_provider=self  # Use BorsaClient which has İş Yatırım integration
        )

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
    async def get_finansal_veri(
        self,
        ticker_kodu: str,
        zaman_araligi: YFinancePeriodEnum = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Delegates historical data fetching to YahooFinanceProvider.

        Args:
            ticker_kodu: Stock ticker symbol
            zaman_araligi: Time period (optional if start_date/end_date provided)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
        """
        return await self.yfinance_provider.get_finansal_veri(
            ticker_kodu, zaman_araligi, start_date, end_date
        )
        
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
        
        
    # ========== FINANCIAL STATEMENTS (İş Yatırım) ==========

    async def get_bilanco(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches balance sheet from İş Yatırım (primary source).
        Falls back to Yahoo Finance if İş Yatırım fails.
        """
        result = await self.isyatirim_provider.get_bilanco(ticker_kodu, period_type)

        # If İş Yatırım fails or returns no data, fallback to Yahoo Finance
        if result.get("error") or len(result.get("tablo", [])) == 0:
            logger.warning(f"İş Yatırım bilanco failed for {ticker_kodu}, using Yahoo Finance fallback")
            return await self.yfinance_provider.get_bilanco(ticker_kodu, period_type)

        return result

    async def get_kar_zarar(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches income statement from İş Yatırım (primary source).
        Falls back to Yahoo Finance if İş Yatırım fails.
        """
        result = await self.isyatirim_provider.get_kar_zarar(ticker_kodu, period_type)

        if result.get("error") or len(result.get("tablo", [])) == 0:
            logger.warning(f"İş Yatırım kar/zarar failed for {ticker_kodu}, using Yahoo Finance fallback")
            return await self.yfinance_provider.get_kar_zarar(ticker_kodu, period_type)

        return result

    async def get_nakit_akisi(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches cash flow statement from İş Yatırım (primary source).
        Falls back to Yahoo Finance if İş Yatırım fails.
        """
        result = await self.isyatirim_provider.get_nakit_akisi(ticker_kodu, period_type)

        if result.get("error") or len(result.get("tablo", [])) == 0:
            logger.warning(f"İş Yatırım nakit akışı failed for {ticker_kodu}, using Yahoo Finance fallback")
            return await self.yfinance_provider.get_nakit_akisi(ticker_kodu, period_type)

        return result

    # ========== YAHOO FINANCE (Backup) ==========

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
    
    async def get_hizli_bilgi(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates fast info fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_hizli_bilgi(ticker_kodu)

    async def get_hizli_bilgi_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates fast info fetching to YahooFinanceProvider (explicit)."""
        return await self.yfinance_provider.get_hizli_bilgi(ticker_kodu)

    async def get_kazanc_takvimi_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates earnings calendar fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_kazanc_takvimi(ticker_kodu)
    
    async def get_teknik_analiz_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates technical analysis to YahooFinanceProvider."""
        return self.yfinance_provider.get_teknik_analiz(ticker_kodu)

    async def get_pivot_points(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates pivot points calculation to YahooFinanceProvider."""
        return await self.yfinance_provider.get_pivot_points(ticker_kodu)

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
            logger.exception("Error in client-level stock screening")
            return {"error": str(e)}
    
    async def deger_yatirim_taramasi(self) -> Dict[str, Any]:
        """Value investing screening preset - stocks with low P/E, P/B ratios."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting value investment screening with {len(all_companies)} companies")

            # Apply value investing screening
            return await self.yfinance_provider.deger_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception("Error in value investment screening")
            return {"error": str(e)}

    async def temettu_yatirim_taramasi(self) -> Dict[str, Any]:
        """Dividend investing screening preset - stocks with high dividend yields."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting dividend investment screening with {len(all_companies)} companies")

            # Apply dividend investing screening
            return await self.yfinance_provider.temettu_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception("Error in dividend investment screening")
            return {"error": str(e)}

    async def buyume_yatirim_taramasi(self) -> Dict[str, Any]:
        """Growth investing screening preset - stocks with high revenue/earnings growth."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting growth investment screening with {len(all_companies)} companies")

            # Apply growth investing screening
            return await self.yfinance_provider.buyume_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception("Error in growth investment screening")
            return {"error": str(e)}

    async def muhafazakar_yatirim_taramasi(self) -> Dict[str, Any]:
        """Conservative investing screening preset - low-risk, stable stocks."""
        try:
            # Get all companies from KAP
            all_companies = await self.kap_provider.get_all_companies()
            logger.info(f"Starting conservative investment screening with {len(all_companies)} companies")

            # Apply conservative investing screening
            return await self.yfinance_provider.muhafazakar_yatirim_taramasi(all_companies)
        except Exception as e:
            logger.exception("Error in conservative investment screening")
            return {"error": str(e)}

    async def buyuk_sirket_taramasi(self, min_market_cap: float = 50_000_000_000) -> Dict[str, Any]:
        """Large cap stocks screening - companies above specified market cap threshold."""
        try:
            kriterler = TaramaKriterleri(min_market_cap=min_market_cap)
            return await self.hisse_tarama(kriterler)
        except Exception as e:
            logger.exception("Error in large cap screening")
            return {"error": str(e)}

    async def sektor_taramasi(self, sectors: List[str]) -> Dict[str, Any]:
        """Sector-specific screening - filter companies by specific sectors."""
        try:
            kriterler = TaramaKriterleri(sectors=sectors)
            return await self.hisse_tarama(kriterler)
        except Exception as e:
            logger.exception("Error in sector screening")
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
            logger.exception("Error comparing funds")
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
            logger.exception("Error screening funds")
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
            logger.exception("Error in advanced fund comparison")
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
            logger.exception("Error reading fund regulation document")
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
    ) -> EnflasyonHesaplamaSonucu:
        """Calculate cumulative inflation using TCMB calculator API."""
        return await self.tcmb_provider.calculate_inflation(
            start_year, start_month, end_year, end_month, basket_value
        )

    # --- Bond Yields Methods ---
    async def get_tahvil_faizleri(self) -> Dict[str, Any]:
        """Get Turkish government bond yields from Doviz.com."""
        return await self.tahvil_provider.get_tahvil_faizleri()
    
    # --- Buffett Analysis Methods ---
    async def calculate_owner_earnings(
        self,
        net_income: float,
        depreciation: float,
        capex: float,
        working_capital_change: float
    ) -> Dict[str, Any]:
        """Calculate Owner Earnings using Buffett's formula."""
        return self.buffett_provider.calculate_owner_earnings(
            net_income, depreciation, capex, working_capital_change
        )
    
    async def calculate_oe_yield(
        self,
        owner_earnings: float,
        market_cap: float,
        is_quarterly: bool = True
    ) -> Dict[str, Any]:
        """Calculate OE Yield (Owner Earnings Yield)."""
        return self.buffett_provider.calculate_oe_yield(
            owner_earnings, market_cap, is_quarterly
        )
    
    async def calculate_dcf_fisher(
        self,
        ticker_kodu: str,
        owner_earnings_quarterly: float,
        nominal_rate: Optional[float] = None,
        expected_inflation: Optional[float] = None,
        growth_rate_real: Optional[float] = None,
        terminal_growth_real: Optional[float] = None,
        risk_premium: float = 0.10,
        forecast_years: int = 5
    ) -> Dict[str, Any]:
        """Calculate DCF with Fisher Effect using dynamic parameters."""
        return await self.buffett_provider.calculate_dcf_fisher(
            ticker_kodu, owner_earnings_quarterly,
            nominal_rate, expected_inflation,
            growth_rate_real, terminal_growth_real,
            risk_premium, forecast_years
        )
    
    async def calculate_safety_margin(
        self,
        intrinsic_value_total: float,
        current_price: float,
        shares_outstanding: float,
        moat_strength: str = "GÜÇLÜ"
    ) -> Dict[str, Any]:
        """Calculate Safety Margin (Margin of Safety)."""
        return self.buffett_provider.calculate_safety_margin(
            intrinsic_value_total, current_price,
            shares_outstanding, moat_strength
        )

    async def calculate_buffett_value_analysis(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate complete Buffett value analysis (4 metrics: OE, OE Yield, DCF, Safety Margin)."""
        return await self.buffett_provider.calculate_buffett_value_analysis(ticker_kodu)

    # --- Financial Ratios Methods ---
    async def calculate_roe(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Return on Equity (ROE)."""
        return await self.financial_ratios_provider.calculate_roe(ticker_kodu)

    async def calculate_roic(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Return on Invested Capital (ROIC)."""
        return await self.financial_ratios_provider.calculate_roic(ticker_kodu)

    async def calculate_debt_ratios(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate debt and leverage ratios."""
        return await self.financial_ratios_provider.calculate_debt_ratios(ticker_kodu)

    async def calculate_fcf_margin(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Free Cash Flow Margin."""
        return await self.financial_ratios_provider.calculate_fcf_margin(ticker_kodu)

    async def calculate_earnings_quality(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate earnings quality metrics."""
        return await self.financial_ratios_provider.calculate_earnings_quality(ticker_kodu)

    async def calculate_altman_z_score(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Altman Z-Score for bankruptcy prediction."""
        return await self.financial_ratios_provider.calculate_altman_z_score(ticker_kodu)

    async def calculate_real_growth(self, ticker_kodu: str, growth_metric: str = 'revenue') -> Dict[str, Any]:
        """Calculate Real Growth Rate (inflation-adjusted)."""
        return await self.financial_ratios_provider.calculate_real_growth(ticker_kodu, growth_metric)

    async def calculate_comprehensive_analysis(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate comprehensive financial analysis (11 metrics in 4 categories)."""
        return await self.financial_ratios_provider.calculate_comprehensive_analysis(ticker_kodu)

    async def calculate_core_financial_health(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Core Financial Health Analysis (5 metrics in 1 call)."""
        return await self.financial_ratios_provider.calculate_core_financial_health(ticker_kodu)

    async def calculate_advanced_metrics(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculate Advanced Financial Metrics (2 metrics in 1 call)."""
        return await self.financial_ratios_provider.calculate_advanced_metrics(ticker_kodu)

    # ============================================================================
    # MULTI-TICKER DELEGATION METHODS (Phase 1: Yahoo Finance Tools)
    # ============================================================================

    async def get_hizli_bilgi_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Delegates multi-ticker fast info fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_hizli_bilgi_multi(ticker_kodlari)

    async def get_temettu_ve_aksiyonlar_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Delegates multi-ticker dividends fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_temettu_ve_aksiyonlar_multi(ticker_kodlari)

    async def get_analist_verileri_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Delegates multi-ticker analyst data fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_analist_verileri_multi(ticker_kodlari)

    async def get_kazanc_takvimi_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Delegates multi-ticker earnings calendar fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_kazanc_takvimi_multi(ticker_kodlari)

    # ============================================================================
    # MULTI-TICKER DELEGATION METHODS (Phase 2: İş Yatırım Financial Statements)
    # ============================================================================

    async def get_bilanco_multi(self, ticker_kodlari: List[str], period_type: str) -> Dict[str, Any]:
        """Delegates multi-ticker balance sheet fetching to IsYatirimProvider."""
        return await self.isyatirim_provider.get_bilanco_multi(ticker_kodlari, period_type)

    async def get_kar_zarar_multi(self, ticker_kodlari: List[str], period_type: str) -> Dict[str, Any]:
        """Delegates multi-ticker income statement fetching to IsYatirimProvider."""
        return await self.isyatirim_provider.get_kar_zarar_multi(ticker_kodlari, period_type)

    async def get_nakit_akisi_multi(self, ticker_kodlari: List[str], period_type: str) -> Dict[str, Any]:
        """Delegates multi-ticker cash flow statement fetching to IsYatirimProvider."""
        return await self.isyatirim_provider.get_nakit_akisi_multi(ticker_kodlari, period_type)

    # ============================================================================
    # US STOCK MARKET METHODS
    # ============================================================================

    async def search_us_stock(self, query: str) -> Dict[str, Any]:
        """
        Search/validate a US stock ticker using Yahoo Finance.

        Args:
            query: Ticker symbol to validate (e.g., 'AAPL', 'MSFT')

        Returns:
            Company info if ticker is valid, error otherwise
        """
        import datetime
        try:
            result = await self.yfinance_provider.get_sirket_bilgileri(query, market="US")
            if "error" in result:
                return {
                    "query": query,
                    "ticker": None,
                    "name": None,
                    "sector": None,
                    "industry": None,
                    "market_cap": None,
                    "is_valid": False,
                    "query_timestamp": datetime.datetime.now(),
                    "error_message": result.get("error")
                }

            bilgiler = result.get("bilgiler")
            if bilgiler:
                return {
                    "query": query,
                    "ticker": bilgiler.symbol,
                    "name": bilgiler.longName,
                    "sector": bilgiler.sector,
                    "industry": bilgiler.industry,
                    "market_cap": bilgiler.marketCap,
                    "is_valid": True,
                    "query_timestamp": datetime.datetime.now(),
                    "error_message": None
                }
            return {
                "query": query,
                "ticker": None,
                "is_valid": False,
                "query_timestamp": datetime.datetime.now(),
                "error_message": "No data returned"
            }
        except Exception as e:
            logger.exception(f"Error searching US stock: {query}")
            return {
                "query": query,
                "ticker": None,
                "is_valid": False,
                "query_timestamp": datetime.datetime.now(),
                "error_message": str(e)
            }

    async def get_us_company_profile(self, ticker: str) -> Dict[str, Any]:
        """Get US company profile information."""
        result = await self.yfinance_provider.get_sirket_bilgileri(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error")}
        return result

    async def get_us_quick_info(self, ticker: str) -> Dict[str, Any]:
        """Get US stock quick info with key metrics."""
        result = await self.yfinance_provider.get_hizli_bilgi(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}
        result["ticker"] = ticker
        return result

    async def get_us_stock_data(
        self,
        ticker: str,
        period: str = "1mo",
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Get US stock historical OHLCV data."""
        from models import YFinancePeriodEnum

        # Convert string period to enum if needed
        period_enum = None
        if period and not start_date and not end_date:
            try:
                period_enum = YFinancePeriodEnum(period)
            except ValueError:
                period_enum = YFinancePeriodEnum.P1MO

        result = await self.yfinance_provider.get_finansal_veri(
            ticker,
            period=period_enum,
            start_date=start_date,
            end_date=end_date,
            market="US"
        )
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}

        # Map Turkish field names to English for model compatibility
        # Convert FinansalVeriNoktasi objects to USStockDataPoint dicts
        veri_noktalari = result.get("veri_noktalari", [])
        data_points = []
        for vn in veri_noktalari:
            data_points.append({
                "date": vn.tarih,
                "open": vn.acilis,
                "high": vn.en_yuksek,
                "low": vn.en_dusuk,
                "close": vn.kapanis,
                "volume": int(vn.hacim)
            })

        mapped_result = {
            "ticker": ticker,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "data_points": data_points,
            "total_points": len(data_points)
        }
        return mapped_result

    async def get_us_analyst_ratings(self, ticker: str) -> Dict[str, Any]:
        """Get US stock analyst recommendations and price targets."""
        result = await self.yfinance_provider.get_analist_verileri(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}
        result["ticker"] = ticker
        return result

    async def get_us_dividends(self, ticker: str) -> Dict[str, Any]:
        """Get US stock dividends and corporate actions."""
        result = await self.yfinance_provider.get_temettu_ve_aksiyonlar(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}
        result["ticker"] = ticker
        return result

    async def get_us_earnings(self, ticker: str) -> Dict[str, Any]:
        """Get US stock earnings calendar."""
        result = await self.yfinance_provider.get_kazanc_takvimi(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}
        result["ticker"] = ticker
        return result

    async def get_us_technical_analysis(self, ticker: str) -> Dict[str, Any]:
        """Get US stock technical analysis with indicators."""
        result = self.yfinance_provider.get_teknik_analiz(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}

        # Map Turkish field names to English for model compatibility
        fiyat = result.get("fiyat_analizi", {})
        trend = result.get("trend_analizi", {})
        teknik = result.get("teknik_indiktorler", {})
        hareketli = result.get("hareketli_ortalamalar", {})

        # Build indicators dict
        indicators = {
            "rsi_14": teknik.get("rsi_14"),
            "macd": teknik.get("macd"),
            "macd_signal": teknik.get("macd_signal"),
            "macd_histogram": teknik.get("macd_histogram"),
            "sma_20": hareketli.get("sma_20"),
            "sma_50": hareketli.get("sma_50"),
            "sma_200": hareketli.get("sma_200"),
            "ema_12": hareketli.get("ema_12"),
            "ema_26": hareketli.get("ema_26"),
            "bollinger_upper": teknik.get("bollinger_ust"),
            "bollinger_middle": teknik.get("bollinger_orta"),
            "bollinger_lower": teknik.get("bollinger_alt"),
        }

        # Determine overall trend from Turkish trend analysis
        trend_map = {"yukselis": "bullish", "dusulis": "bearish", "yatay": "neutral"}
        overall_trend = trend_map.get(trend.get("orta_vadeli_trend"), "neutral")

        mapped_result = {
            "ticker": ticker,
            "analysis_date": result.get("analiz_tarihi"),
            "current_price": fiyat.get("guncel_fiyat"),
            "indicators": indicators,
            "trend": overall_trend,
            "signal": result.get("al_sat_sinyali"),
            "signal_explanation": result.get("sinyal_aciklamasi"),
        }
        return mapped_result

    async def get_us_pivot_points(self, ticker: str) -> Dict[str, Any]:
        """Get US stock pivot points (support/resistance levels)."""
        result = await self.yfinance_provider.get_pivot_points(ticker, market="US")
        if "error" in result:
            return {"error_message": result.get("error"), "ticker": ticker}
        result["ticker"] = ticker
        return result

    # ============================================================================
    # US STOCK MULTI-TICKER METHODS
    # ============================================================================

    async def get_us_quick_info_multi(self, tickers: List[str]) -> Dict[str, Any]:
        """Get quick info for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_quick_info(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append(result)

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    async def get_us_analyst_ratings_multi(self, tickers: List[str]) -> Dict[str, Any]:
        """Get analyst ratings for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_analyst_ratings(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append(result)

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    async def get_us_dividends_multi(self, tickers: List[str]) -> Dict[str, Any]:
        """Get dividends for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_dividends(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append(result)

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    async def get_us_earnings_multi(self, tickers: List[str]) -> Dict[str, Any]:
        """Get earnings calendar for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_earnings(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append(result)

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    # ============================================================================
    # US STOCK FINANCIAL STATEMENT METHODS
    # ============================================================================

    async def get_us_balance_sheet(self, ticker: str, period_type: str = "annual") -> Dict[str, Any]:
        """Get US stock balance sheet from Yahoo Finance."""
        result = await self.yfinance_provider.get_bilanco(ticker, period_type, market="US")
        if result.get("error"):
            return {"error_message": result.get("error"), "ticker": ticker, "period_type": period_type}
        result["ticker"] = ticker
        result["period_type"] = period_type
        return result

    async def get_us_income_statement(self, ticker: str, period_type: str = "annual") -> Dict[str, Any]:
        """Get US stock income statement from Yahoo Finance."""
        result = await self.yfinance_provider.get_kar_zarar(ticker, period_type, market="US")
        if result.get("error"):
            return {"error_message": result.get("error"), "ticker": ticker, "period_type": period_type}
        result["ticker"] = ticker
        result["period_type"] = period_type
        return result

    async def get_us_cash_flow(self, ticker: str, period_type: str = "annual") -> Dict[str, Any]:
        """Get US stock cash flow statement from Yahoo Finance."""
        result = await self.yfinance_provider.get_nakit_akisi(ticker, period_type, market="US")
        if result.get("error"):
            return {"error_message": result.get("error"), "ticker": ticker, "period_type": period_type}
        result["ticker"] = ticker
        result["period_type"] = period_type
        return result

    # ============================================================================
    # US STOCK FINANCIAL STATEMENT MULTI-TICKER METHODS
    # ============================================================================

    async def get_us_balance_sheet_multi(self, tickers: List[str], period_type: str = "annual") -> Dict[str, Any]:
        """Get balance sheet for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_balance_sheet(t, period_type) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append({"ticker": ticker, **result})

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    async def get_us_income_statement_multi(self, tickers: List[str], period_type: str = "annual") -> Dict[str, Any]:
        """Get income statement for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_income_statement(t, period_type) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append({"ticker": ticker, **result})

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    async def get_us_cash_flow_multi(self, tickers: List[str], period_type: str = "annual") -> Dict[str, Any]:
        """Get cash flow statement for multiple US stocks in parallel."""
        import asyncio
        import datetime

        if not tickers:
            return {"error": "No tickers provided"}
        if len(tickers) > 10:
            return {"error": "Maximum 10 tickers allowed per request"}

        tasks = [self.get_us_cash_flow(t, period_type) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        warnings = []
        data = []

        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                failed.append(ticker)
                warnings.append(f"{ticker}: {str(result)}")
            elif result.get("error_message"):
                failed.append(ticker)
                warnings.append(f"{ticker}: {result['error_message']}")
            else:
                successful.append(ticker)
                data.append({"ticker": ticker, **result})

        return {
            "tickers": tickers,
            "data": data,
            "successful_count": len(successful),
            "failed_count": len(failed),
            "warnings": warnings,
            "query_timestamp": datetime.datetime.now()
        }

    # ======================= US STOCK FINANCIAL ANALYSIS METHODS =======================

    async def calculate_us_buffett_analysis(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate complete Warren Buffett value investing analysis for US stocks.

        Includes 4 key metrics:
        1. Owner Earnings - Real cash flow available to owners
        2. OE Yield - Cash return percentage (>10% target)
        3. DCF Fisher - Inflation-adjusted intrinsic value
        4. Safety Margin - Moat-adjusted buy threshold

        Uses US-specific macro data:
        - Nominal Rate: Yahoo Finance ^TNX (US 10Y Treasury)
        - Inflation: US Fed target (2.5%)
        - Growth: Yahoo Finance analyst data + World Bank US GDP

        Args:
            ticker: US stock ticker (e.g., 'AAPL', 'MSFT', 'GOOGL')

        Returns:
            Dict with BuffettValueAnalysis structure including buffett_score and insights
        """
        result = await self.buffett_provider.calculate_buffett_value_analysis(
            ticker_kodu=ticker,
            market="US"
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def calculate_us_advanced_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate Advanced Financial Metrics for US stocks.

        Consolidates 2 key metrics in 1 call:
        1. Altman Z-Score - Bankruptcy risk prediction
           - Z > 2.99: Safe Zone (low risk)
           - 1.81 < Z < 2.99: Grey Zone (moderate risk)
           - Z < 1.81: Distress Zone (high risk)
        2. Real Growth - Inflation-adjusted growth (Fisher equation)
           - Revenue real growth
           - Earnings real growth

        Args:
            ticker: US stock ticker (e.g., 'AAPL', 'MSFT', 'GOOGL')

        Returns:
            Dict with Altman Z-Score, Real Growth metrics, and assessments
        """
        result = await self.financial_ratios_provider.calculate_advanced_metrics(
            ticker_kodu=ticker,
            market="US"
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def calculate_us_core_health(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate Core Financial Health Analysis for US stocks.

        Consolidates 5 key metrics in 1 call:
        1. ROE - Return on Equity (profitability metric, >15% excellent)
        2. ROIC - Return on Invested Capital (capital efficiency, >15% excellent)
        3. Debt Ratios - 4 debt metrics (D/E, D/A, Interest Coverage, Debt Service)
        4. FCF Margin - Free Cash Flow margin (cash generation, >10% excellent)
        5. Earnings Quality - CF/NI ratio, accruals, working capital impact

        Returns overall health score: STRONG | GOOD | AVERAGE | WEAK

        Args:
            ticker: US stock ticker (e.g., 'AAPL', 'MSFT', 'GOOGL')

        Returns:
            Dict with CoreFinancialHealthAnalysis structure including health_score and insights
        """
        result = await self.financial_ratios_provider.calculate_core_financial_health(
            ticker_kodu=ticker,
            market="US"
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def calculate_us_comprehensive(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate Comprehensive Financial Analysis for US stocks.

        Includes 11 metrics in 4 categories:

        1. LIQUIDITY METRICS (5):
           - Current Ratio: Current Assets / Current Liabilities
           - Quick Ratio: (Current Assets - Inventory) / Current Liabilities
           - OCF Ratio: Operating Cash Flow / Current Liabilities
           - Cash Conversion Cycle: DSO + DIO - DPO (days)
           - Debt/EBITDA: Total Debt / EBITDA (healthy <3.0)

        2. PROFITABILITY MARGINS (3):
           - Gross Margin: Gross Profit / Revenue × 100
           - Operating Margin: Operating Income / Revenue × 100
           - Net Profit Margin: Net Income / Revenue × 100

        3. VALUATION METRICS (2):
           - EV/EBITDA: Enterprise Value / EBITDA
           - Graham Number: √(22.5 × EPS × BVPS)

        4. COMPOSITE SCORES (2):
           - Piotroski F-Score: 0-9 score (simplified)
           - Magic Formula: Earnings Yield + ROIC ranking

        Args:
            ticker: US stock ticker (e.g., 'AAPL', 'MSFT', 'GOOGL')

        Returns:
            Dict with ComprehensiveFinancialAnalysis structure
        """
        result = await self.financial_ratios_provider.calculate_comprehensive_analysis(
            ticker_kodu=ticker,
            market="US"
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def get_us_sector_comparison(self, tickers: List[str]) -> Dict[str, Any]:
        """
        Compare US stocks across sectors with comprehensive metrics.

        Provides sector-level analysis and comparison including:
        - Per-company metrics: P/E, P/B, ROE, debt ratio, profit margin, yearly return, volatility
        - Sector averages: Average P/E, P/B, ROE, debt, margins, returns, volatility
        - Best performing sector (highest average return)
        - Lowest risk sector (lowest average volatility)
        - Largest sector by market cap

        Args:
            tickers: List of US stock tickers (e.g., ['AAPL', 'MSFT', 'GOOGL', 'AMZN'])

        Returns:
            Dict with company data, sector summaries, and overall market stats
        """
        # Use run_in_executor for synchronous Yahoo Finance call
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.yfinance_provider.get_sektor_karsilastirmasi(tickers, market="US")
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def search_us_indices(self, query: str) -> Dict[str, Any]:
        """
        Search US stock market indices by name, ticker, or category.

        Searches through a database of major US indices including:
        - Market indices: S&P 500, Dow Jones, Nasdaq, Russell
        - International indices: FTSE, Nikkei, DAX, CAC 40
        - Sector ETFs: XLK (Tech), XLF (Financial), XLE (Energy), etc.

        Args:
            query: Search term (e.g., 'S&P', 'nasdaq', 'tech', 'small cap')

        Returns:
            Dict with matching indices including ticker, name, description, category
        """
        # Synchronous method, use run_in_executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.yfinance_provider.search_us_indices(query)
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result

    async def get_us_index_info(self, index_ticker: str) -> Dict[str, Any]:
        """
        Get detailed information about a US index including current price and returns.

        Args:
            index_ticker: Index ticker (e.g., '^GSPC', '^DJI', 'XLK')

        Returns:
            Dict with index info, current price, YTD return, 1Y return, etc.
        """
        # Synchronous method, use run_in_executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.yfinance_provider.get_us_index_info(index_ticker)
        )

        if result.get('error'):
            return {"error_message": result.get('error'), **result}

        return result