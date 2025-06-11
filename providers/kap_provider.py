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
import pandas as pd
from typing import List, Optional, Dict, Any
from borsa_models import (
    SirketInfo, KatilimFinansUygunlukBilgisi, KatilimFinansUygunlukSonucu,
    EndeksBilgisi, EndeksAramaSonucu, EndeksKoduAramaSonucu
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class KAPProvider:
    PDF_URL = "https://www.kap.org.tr/tr/api/company/generic/pdf/IGS/A/sirketler-IGS"
    INDICES_PDF_URL = "https://www.kap.org.tr/tr/api/company/indices/pdf/endeksler"
    INDICES_EXCEL_URL = "https://www.kap.org.tr/tr/api/company/indices/excel"
    CACHE_DURATION = 24 * 60 * 60

    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._company_list: List[SirketInfo] = []
        self._last_fetch_time: float = 0
        self._indices_list: List[EndeksBilgisi] = []
        self._last_indices_fetch_time: float = 0

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

    async def get_katilim_finans_uygunluk(self, ticker_kodu: str) -> KatilimFinansUygunlukSonucu:
        """
        Fetches participation finance compatibility data for a specific ticker from KAP.
        """
        ticker_kodu = ticker_kodu.upper().strip()
        
        try:
            url = "https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
            }
            
            response = await self._http_client.get(url, headers=headers)
            response.raise_for_status()
            
            html_content = response.text
            sirketler = []
            
            # Find all self.__next_f.push() calls
            push_calls = re.findall(r'self\.__next_f\.push\(\[1,"([^"]+)"\]\)', html_content)
            
            # Look for table data in the push calls
            table_data = ""
            for push_data in push_calls:
                if 'tbody' in push_data and ('ARCLK' in push_data or 'FLAP' in push_data or 'EFORC' in push_data):
                    table_data = push_data
                    break
            
            if table_data:
                # Extract company rows from the table data
                # Look for patterns like: ["$","tr","0",{"children":[["$","td",null,{"children":"ARCLK"}]
                
                # Find all table rows
                tr_matches = re.findall(r'\["\\"\$\\",\\"tr\\",\\"(\d+)\\",\{[^}]*\\"children\\":\[([^\]]+)\]', table_data)
                
                for row_num, row_data in tr_matches:
                    try:
                        # Extract ticker code (first bold cell)
                        ticker_match = re.search(r'\\"font-semibold[^}]*\\"children\\":\\"([A-Z]+)\\"', row_data)
                        if not ticker_match:
                            continue
                        ticker = ticker_match.group(1)
                        
                        # Extract company name (second bold cell)
                        name_pattern = r'\\"font-semibold[^}]*\\"children\\":\\"([^"]+A\.Ş\.[^"]*)\\"'
                        name_match = re.search(name_pattern, row_data)
                        company_name = name_match.group(1) if name_match else f"Company {ticker}"
                        
                        # Extract all td cell values
                        cell_values = re.findall(r'\\"border border-gray-300 p-2 text-center\\",\\"children\\":\\"([^"]+)\\"', row_data)
                        
                        if len(cell_values) >= 7:  # We need at least 7 data cells
                            sirket = KatilimFinansUygunlukBilgisi(
                                ticker_kodu=ticker,
                                sirket_adi=company_name,
                                para_birimi=cell_values[0] if len(cell_values) > 0 else "TL",
                                finansal_donem=cell_values[1] if len(cell_values) > 1 else "2024 / Yıllık",
                                tablo_niteligi=cell_values[2] if len(cell_values) > 2 else "Konsolide",
                                uygun_olmayan_faaliyet=cell_values[3] if len(cell_values) > 3 else "HAYIR",
                                uygun_olmayan_imtiyaz=cell_values[4] if len(cell_values) > 4 else "HAYIR",
                                destekleme_eylemi=cell_values[5] if len(cell_values) > 5 else "HAYIR",
                                dogrudan_uygun_olmayan_faaliyet=cell_values[6] if len(cell_values) > 6 else "HAYIR",
                                uygun_olmayan_gelir_orani=cell_values[7] if len(cell_values) > 7 else "0,00",
                                uygun_olmayan_varlik_orani=cell_values[8] if len(cell_values) > 8 else "0,00",
                                uygun_olmayan_borc_orani=cell_values[9] if len(cell_values) > 9 else "0,00"
                            )
                            sirketler.append(sirket)
                            
                    except Exception as e:
                        logger.warning(f"Error parsing row {row_num}: {e}")
                        continue
            
            # If no data parsed, log the issue and continue with empty results
            if not sirketler:
                logger.warning("Could not parse table data from KAP participation finance page")
            
            # Search for the specific ticker in the data
            found_company = None
            for sirket in sirketler:
                if sirket.ticker_kodu == ticker_kodu:
                    found_company = sirket
                    break
            
            logger.info(f"Searched for ticker {ticker_kodu} in participation finance data")
            
            # Check participation finance indices regardless of KAP data availability
            katilim_endeks_bilgisi = await self.check_katilim_endeksleri(ticker_kodu)
            
            if found_company:
                return KatilimFinansUygunlukSonucu(
                    ticker_kodu=ticker_kodu,
                    sirket_bilgisi=found_company,
                    veri_bulundu=True,
                    katilim_endeksi_dahil=katilim_endeks_bilgisi.get("katilim_endeksi_dahil", False),
                    katilim_endeksleri=katilim_endeks_bilgisi.get("katilim_endeksleri", []),
                    kaynak_url=url
                )
            else:
                return KatilimFinansUygunlukSonucu(
                    ticker_kodu=ticker_kodu,
                    sirket_bilgisi=None,
                    veri_bulundu=False,
                    katilim_endeksi_dahil=katilim_endeks_bilgisi.get("katilim_endeksi_dahil", False),
                    katilim_endeksleri=katilim_endeks_bilgisi.get("katilim_endeksleri", []),
                    kaynak_url=url
                )
            
        except Exception as e:
            logger.error(f"Error fetching participation finance data: {e}")
            # Even if KAP fails, try to check participation indices
            try:
                katilim_endeks_bilgisi = await self.check_katilim_endeksleri(ticker_kodu)
                return KatilimFinansUygunlukSonucu(
                    ticker_kodu=ticker_kodu,
                    sirket_bilgisi=None,
                    veri_bulundu=False,
                    katilim_endeksi_dahil=katilim_endeks_bilgisi.get("katilim_endeksi_dahil", False),
                    katilim_endeksleri=katilim_endeks_bilgisi.get("katilim_endeksleri", []),
                    kaynak_url="https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid",
                    error_message=str(e)
                )
            except Exception as index_error:
                logger.error(f"Error checking participation indices for {ticker_kodu}: {index_error}")
                return KatilimFinansUygunlukSonucu(
                    ticker_kodu=ticker_kodu,
                    sirket_bilgisi=None,
                    veri_bulundu=False,
                    katilim_endeksi_dahil=False,
                    katilim_endeksleri=[],
                    kaynak_url="https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid",
                    error_message=str(e)
                )

    async def search_indices(self, query: str) -> EndeksKoduAramaSonucu:
        """
        Search for BIST indices by name or code.
        Note: Implementation removed as part of cleanup. Returns empty result.
        """
        logger.warning("Index search functionality has been removed. Use get_endeks_sirketleri with known index codes.")
        return EndeksKoduAramaSonucu(
            arama_terimi=query,
            sonuclar=[],
            sonuc_sayisi=0,
            error_message="Index search functionality has been removed. Use get_endeks_sirketleri with known index codes like 'XU100', 'XBANK', etc."
        )

    async def check_katilim_endeksleri(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Check if a company is included in participation finance indices by fetching from Mynet.
        """
        ticker_upper = ticker_kodu.upper()
        
        # Participation finance index codes and their Mynet URLs
        katilim_endeksleri = {
            'XK100': 'https://finans.mynet.com/borsa/endeks/xk100-bist-katilim-100/',
            'XK050': 'https://finans.mynet.com/borsa/endeks/xk050-bist-katilim-50/',
            'XK030': 'https://finans.mynet.com/borsa/endeks/xk030-bist-katilim-30/'
        }
        
        found_in_indices = []
        
        try:
            # Check each participation finance index
            for endeks_kodu, endeks_url in katilim_endeksleri.items():
                try:
                    # Construct the companies URL
                    if not endeks_url.endswith('/'):
                        endeks_url += '/'
                    companies_url = endeks_url + 'endekshisseleri/'
                    
                    response = await self._http_client.get(companies_url)
                    response.raise_for_status()
                    
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, 'lxml')
                    
                    # Find the companies table
                    table = soup.select_one("table.table-data")
                    if not table:
                        logger.warning(f"Could not find companies table for {endeks_kodu}")
                        continue
                    
                    tbody = table.find("tbody")
                    if not tbody:
                        logger.warning(f"Could not find table body for {endeks_kodu}")
                        continue
                    
                    # Check if our ticker is in this index
                    for row in tbody.find_all("tr"):
                        try:
                            first_cell = row.find("td")
                            if not first_cell:
                                continue
                            
                            company_link = first_cell.find("a")
                            if not company_link:
                                continue
                            
                            # Extract ticker from the title attribute
                            title_attr = company_link.get("title", "")
                            if title_attr:
                                parts = title_attr.split()
                                if parts:
                                    found_ticker = parts[0].upper()
                                    if found_ticker == ticker_upper:
                                        found_in_indices.append(endeks_kodu)
                                        logger.info(f"Found {ticker_upper} in {endeks_kodu}")
                                        break
                        
                        except Exception as e:
                            logger.warning(f"Error parsing company row in {endeks_kodu}: {e}")
                            continue
                
                except Exception as e:
                    logger.warning(f"Error checking {endeks_kodu} for {ticker_upper}: {e}")
                    continue
            
            return {
                "katilim_endeksi_dahil": len(found_in_indices) > 0,
                "katilim_endeksleri": found_in_indices
            }
            
        except Exception as e:
            logger.error(f"Error checking participation finance indices for {ticker_upper}: {e}")
            return {
                "katilim_endeksi_dahil": False,
                "katilim_endeksleri": []
            }
