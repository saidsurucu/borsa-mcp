"""
Main BorsaApiClient
This class acts as an orchestrator or service layer. It initializes
all data providers (KAP, yfinance) and delegates calls to the 
appropriate provider.
"""
import httpx
import logging
from typing import List, Dict, Any

# Assuming provider files are in a 'providers' directory
from providers.kap_provider import KAPProvider
from providers.yfinance_provider import YahooFinanceProvider
# Mynet is kept for potential future use but can be commented out
# from providers.mynet_provider import MynetProvider 
from borsa_models import SirketInfo, FinansalVeriSonucu, YFinancePeriodEnum, SirketProfiliSonucu, FinansalTabloSonucu

logger = logging.getLogger(__name__)

class BorsaApiClient:
    def __init__(self, timeout: float = 60.0):
        # A single httpx client for providers that need it (like KAP)
        self._http_client = httpx.AsyncClient(timeout=timeout)
        
        # Initialize all data providers
        self.kap_provider = KAPProvider(self._http_client)
        self.yfinance_provider = YahooFinanceProvider()
        # self.mynet_provider = MynetProvider(self._http_client) # Mynet provider is now fully replaced

    async def close(self):
        await self._http_client.aclose()
        
    # --- KAP Provider Methods ---
    async def search_companies_from_kap(self, query: str) -> List[SirketInfo]:
        """Delegates company search to KAPProvider."""
        return await self.kap_provider.search_companies(query)

    # --- YFinance Provider Methods ---
    async def get_finansal_veri(self, ticker_kodu: str, zaman_araligi: YFinancePeriodEnum) -> Dict[str, Any]:
        """Delegates historical data fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_finansal_veri(ticker_kodu, zaman_araligi)
        
    async def get_sirket_bilgileri_yfinance(self, ticker_kodu: str) -> Dict[str, Any]:
        """Delegates company info fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_sirket_bilgileri(ticker_kodu)
        
    async def get_bilanco_yfinance(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Delegates balance sheet fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_bilanco(ticker_kodu, period_type)

    async def get_kar_zarar_yfinance(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Delegates income statement fetching to YahooFinanceProvider."""
        return await self.yfinance_provider.get_kar_zarar(ticker_kodu, period_type)
        
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
