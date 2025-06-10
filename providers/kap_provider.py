"""
KAP Provider
This module is responsible for all interactions with the
Public Disclosure Platform (KAP), including fetching and searching companies.
"""
import httpx
import logging
import time
import io
import re
import pdfplumber
from typing import List, Optional
from borsa_models import SirketInfo

logger = logging.getLogger(__name__)

class KAPProvider:
    PDF_URL = "https://www.kap.org.tr/tr/api/company/generic/pdf/IGS/A/sirketler-IGS"
    CACHE_DURATION = 24 * 60 * 60

    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._company_list: List[SirketInfo] = []
        self._last_fetch_time: float = 0

    async def _fetch_company_data(self) -> Optional[List[SirketInfo]]:
        try:
            response = await self._http_client.get(self.PDF_URL)
            response.raise_for_status()
            all_companies = []
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        for row in table:
                            if not row or len(row) < 3 or row[0] is None or "BIST KODU" in row[0]: continue
                            ticker, name, city = (row[0] or "").strip(), (row[1] or "").strip(), (row[2] or "").strip()
                            if ticker and name:
                                all_companies.append(SirketInfo(sirket_adi=name, ticker_kodu=ticker, sehir=city))
            logger.info(f"Successfully fetched {len(all_companies)} companies from KAP PDF.")
            return all_companies
        except Exception as e:
            logger.exception("Error in KAPProvider._fetch_company_data")
            return None

    async def get_all_companies(self) -> List[SirketInfo]:
        current_time = time.time()
        if not self._company_list or (current_time - self._last_fetch_time) > self.CACHE_DURATION:
            companies = await self._fetch_company_data()
            if companies:
                self._company_list = companies
                self._last_fetch_time = current_time
        return self._company_list
    
    def _normalize_text(self, text: str) -> str:
        tr_map = str.maketrans("İıÖöÜüŞşÇçĞğ", "iioouussccgg")
        return re.sub(r"[\.,']|\s+a\.s\.?|\s+anonim sirketi", "", text.translate(tr_map).lower()).strip()

    async def search_companies(self, query: str) -> List[SirketInfo]:
        if not query: return []
        all_companies = await self.get_all_companies()
        if not all_companies: return []
        normalized_query = self._normalize_text(query)
        query_tokens = set(normalized_query.split())
        scored_results = []
        for company in all_companies:
            score = 0
            normalized_ticker = self._normalize_text(company.ticker_kodu)
            normalized_name = self._normalize_text(company.sirket_adi)
            if normalized_query == normalized_ticker: score += 1000
            matched_tokens = query_tokens.intersection(set(normalized_name.split()))
            if matched_tokens:
                score += len(matched_tokens) * 100
                if normalized_name.startswith(normalized_query): score += 300
                if matched_tokens == query_tokens: score += 200
            if score > 0: scored_results.append((score, company))
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [company for score, company in scored_results]
