"""
Mynet Provider
This module is responsible for all interactions with Mynet Finans,
including scraping URLs, real-time data, and financial statements.
"""
import httpx
import logging
import time
import re
import json
import io
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
from markitdown import MarkItDown
from models import (
    HisseDetay, SirketGenelBilgileri, Istirak, Ortak, Yonetici, 
    PiyasaDegeri, BilancoKalemi, MevcutDonem, KarZararKalemi,
    FinansalVeriNoktasi, ZamanAraligiEnum, EndeksBilgisi
)

logger = logging.getLogger(__name__)

class MynetProvider:
    BASE_URL = "https://finans.mynet.com/borsa/hisseler/"
    CACHE_DURATION = 24 * 60 * 60

    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._ticker_to_url: Dict[str, str] = {}
        self._last_fetch_time: float = 0
        self._markitdown = MarkItDown()
        
    async def _fetch_ticker_urls(self) -> Optional[Dict[str, str]]:
        try:
            response = await self._http_client.get(self.BASE_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            table_body = soup.select_one("div.scrollable-box-hisseler tbody.tbody-type-default")
            if not table_body: return None
            url_map = {}
            for row in table_body.find_all("tr"):
                link_tag = row.select_one("td > strong > a")
                if link_tag and link_tag.has_attr('href') and link_tag.has_attr('title'):
                    title_attr = link_tag['title']
                    if title_attr and title_attr.split():
                        ticker = title_attr.split()[0]
                        url_map[ticker.upper()] = link_tag['href']
            return url_map
        except Exception:
            logger.exception("Error in MynetProvider._fetch_ticker_urls")
            return None

    async def get_url_map(self) -> Dict[str, str]:
        current_time = time.time()
        
        # Type safety check to prevent the error
        if not isinstance(self._last_fetch_time, (int, float)):
            logger.warning(f"_last_fetch_time has wrong type: {type(self._last_fetch_time)}, resetting to 0")
            self._last_fetch_time = 0
        
        if not self._ticker_to_url or (current_time - self._last_fetch_time) > self.CACHE_DURATION:
            url_map = await self._fetch_ticker_urls()
            if url_map:
                self._ticker_to_url = url_map
                self._last_fetch_time = current_time
        return self._ticker_to_url

    def _clean_and_convert_value(self, value_str: str) -> Any:
        if not isinstance(value_str, str): return value_str
        cleaned_str = value_str.replace('TL', '').strip()
        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', cleaned_str): return cleaned_str
        standardized_num_str = cleaned_str.replace('.', '').replace(',', '.') if ',' in cleaned_str else cleaned_str
        try:
            num = float(standardized_num_str)
            return int(num) if num.is_integer() else num
        except (ValueError, TypeError):
            return cleaned_str
            
    async def get_hisse_detay(self, ticker_kodu: str) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page for the specified ticker could not be found."}
        target_url = url_map[ticker_upper]
        try:
            response = await self._http_client.get(target_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            data_container = soup.select_one("div.flex-list-2-col")
            if not data_container: return {"error": "Could not parse the stock details content."}
            data = {"mynet_url": target_url}
            LABEL_TO_FIELD_MAP = {
                "Hissenin ilk işlem tarihi": "ilk_islem_tarihi", "Son İşlem Fiyatı": "son_islem_fiyati", "Alış": "alis", "Satış": "satis", "Günlük Değişim": "gunluk_degisim", "Günlük Değişim (%)": "gunluk_degisim_yuzde", "Günlük Hacim (Lot)": "gunluk_hacim_lot", "Günlük Hacim (TL)": "gunluk_hacim_tl", "Günlük Ortalama": "gunluk_ortalama", "Gün İçi En Düşük": "gun_ici_en_dusuk", "Gün İçi En Yüksek": "gun_ici_en_yuksek", "Açılış Fiyatı": "acilis_fiyati", "Fiyat Adımı": "fiyat_adimi", "Önceki Kapanış Fiyatı": "onceki_kapanis_fiyati", "Alt Marj Fiyatı": "alt_marj_fiyati", "Üst Marj Fiyatı": "ust_marj_fiyati", "20 Günlük Ortalama": "20_gunluk_ortalama", "52 Günlük Ortalama": "52_gunluk_ortalama", "Haftalık En Düşük": "haftalik_en_dusuk", "Haftalık En Yüksek": "haftalik_en_yuksek", "Aylık En Düşük": "aylik_en_dusuk", "Aylık En Yüksek": "aylik_en_yuksek", "Yıllık En Düşük": "yillik_en_dusuk", "Yıllık En Yüksek": "yillik_en_yuksek", "Baz Fiyatı": "baz_fiyat"
            }
            for li in data_container.find_all("li"):
                spans = li.find_all("span")
                if len(spans) == 2:
                    label, value = spans[0].get_text(strip=True), spans[1].get_text(strip=True)
                    if label in LABEL_TO_FIELD_MAP: data[LABEL_TO_FIELD_MAP[label]] = self._clean_and_convert_value(value)
            return data
        except Exception as e:
            logger.exception(f"Error processing detail page for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}
    
    async def get_kap_haberleri(self, ticker_kodu: str, limit: int = 10) -> Dict[str, Any]:
        """Fetches KAP news for a specific ticker from Mynet."""
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: 
            return {"error": "Mynet Finans page for the specified ticker could not be found."}
        
        target_url = url_map[ticker_upper]
        try:
            response = await self._http_client.get(target_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find KAP news section
            kap_container = soup.select_one("div.card.kap")
            if not kap_container:
                return {"error": "KAP news section not found on the page."}
            
            # Find news list
            news_list = kap_container.select_one("ul.list-type-link-box")
            if not news_list:
                return {"error": "KAP news list not found."}
            
            haberler = []
            news_items = news_list.find_all("li")  # Get all news items first
            
            for item in news_items:
                link_tag = item.find("a")
                if not link_tag:
                    continue
                
                # Extract news data
                title_tag = link_tag.find("em", class_="title")
                date_tag = link_tag.find("span", class_="date")
                
                if title_tag and date_tag:
                    haber = {
                        "baslik": title_tag.get_text(strip=True),
                        "tarih": date_tag.get_text(strip=True),
                        "url": link_tag.get("href"),
                        "haber_id": link_tag.get("data-id"),
                        "title_attr": link_tag.get("title")
                    }
                    haberler.append(haber)
            
            # Apply token optimization to news data
            from token_optimizer import TokenOptimizer
            original_count = len(haberler)
            optimized_haberler = TokenOptimizer.optimize_news_data(haberler, limit)
            
            return {
                "ticker_kodu": ticker_kodu,
                "kap_haberleri": optimized_haberler,
                "toplam_haber": len(optimized_haberler),
                "kaynak_url": target_url
            }
            
        except Exception as e:
            logger.exception(f"Error fetching KAP news for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}
    
    async def get_kap_haber_detayi(self, haber_url: str, sayfa_numarasi: int = 1) -> Dict[str, Any]:
        """Fetches detailed KAP news content and converts to markdown using MarkItDown with pagination support."""
        try:
            response = await self._http_client.get(haber_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find KAP detail container
            kap_detail = soup.select_one("div.card.kap-detail-news-page")
            if not kap_detail:
                return {"error": "KAP detail content not found on the page."}
            
            # Extract title
            title_tag = kap_detail.select_one("h1")
            title = title_tag.get_text(strip=True) if title_tag else "Başlık Bulunamadı"
            
            # Extract page header (document type)
            page_header = kap_detail.select_one("div.page-header")
            doc_type = page_header.get_text(strip=True) if page_header else ""
            
            # Use MarkItDown to convert HTML to markdown
            kap_detail_html = str(kap_detail)
            html_bytes = kap_detail_html.encode('utf-8')
            html_stream = io.BytesIO(html_bytes)
            markdown_result = self._markitdown.convert_stream(html_stream, file_extension=".html")
            
            # Clean up and enhance the markdown content
            markdown_content = markdown_result.text_content if hasattr(markdown_result, 'text_content') else str(markdown_result)
            
            # Add custom header and document type if MarkItDown didn't capture them well
            if title and title not in markdown_content[:200]:
                enhanced_markdown = f"# {title}\n\n"
                if doc_type:
                    enhanced_markdown += f"**Belge Türü:** {doc_type}\n\n"
                enhanced_markdown += "---\n\n"
                enhanced_markdown += markdown_content
                markdown_content = enhanced_markdown
            
            full_content = markdown_content.strip()
            toplam_karakter = len(full_content)
            sayfa_boyutu = 5000
            
            # Check if pagination is needed
            if toplam_karakter <= sayfa_boyutu:
                # Small document, no pagination needed
                return {
                    "baslik": title,
                    "belge_turu": doc_type,
                    "markdown_icerik": full_content,
                    "toplam_karakter": toplam_karakter,
                    "sayfa_numarasi": 1,
                    "toplam_sayfa": 1,
                    "sonraki_sayfa_var": False,
                    "sayfa_boyutu": sayfa_boyutu,
                    "haber_url": haber_url
                }
            
            # Large document, apply pagination
            toplam_sayfa = (toplam_karakter + sayfa_boyutu - 1) // sayfa_boyutu  # Ceiling division
            
            # Validate page number
            if sayfa_numarasi < 1 or sayfa_numarasi > toplam_sayfa:
                return {"error": f"Geçersiz sayfa numarası. Geçerli aralık: 1-{toplam_sayfa}"}
            
            # Extract content for the requested page
            start_index = (sayfa_numarasi - 1) * sayfa_boyutu
            end_index = min(start_index + sayfa_boyutu, toplam_karakter)
            sayfa_icerik = full_content[start_index:end_index]
            
            # Add page indicators if it's a paginated document
            if toplam_sayfa > 1:
                if sayfa_numarasi == 1:
                    sayfa_icerik += f"\n\n---\n*Sayfa {sayfa_numarasi}/{toplam_sayfa} - Sonraki sayfa için sayfa numarasını belirtin*"
                elif sayfa_numarasi == toplam_sayfa:
                    sayfa_icerik = f"*Sayfa {sayfa_numarasi}/{toplam_sayfa} (Son sayfa)*\n\n---\n\n" + sayfa_icerik
                else:
                    sayfa_icerik = f"*Sayfa {sayfa_numarasi}/{toplam_sayfa}*\n\n---\n\n" + sayfa_icerik + f"\n\n---\n*Sonraki sayfa için sayfa numarasını belirtin*"
            
            return {
                "baslik": title,
                "belge_turu": doc_type,
                "markdown_icerik": sayfa_icerik,
                "toplam_karakter": toplam_karakter,
                "sayfa_numarasi": sayfa_numarasi,
                "toplam_sayfa": toplam_sayfa,
                "sonraki_sayfa_var": sayfa_numarasi < toplam_sayfa,
                "sayfa_boyutu": sayfa_boyutu,
                "haber_url": haber_url
            }
            
        except Exception as e:
            logger.exception(f"Error fetching KAP news detail from {haber_url}")
            return {"error": f"An unexpected error occurred: {e}"}
    
        
    async def get_sirket_bilgileri(self, ticker_kodu: str) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page for the specified ticker could not be found."}
        target_url = f"{url_map[ticker_upper]}sirket-bilgileri/"
        try:
            response = await self._http_client.get(target_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            data_container = soup.select_one("div.flex-list-1-col")
            if not data_container: return {"error": "Could not find the company information content."}
            parsed_info = {}
            for li in data_container.select("ul > li.li-c-2-L"):
                key_tag, value_tag = li.find("strong"), li.find("span", class_="text-r")
                if key_tag and value_tag and key_tag.get_text(strip=True) and value_tag.get_text(strip=True):
                    parsed_info[key_tag.get_text(strip=True)] = value_tag.get_text(strip=True)
            for li in data_container.select("ul > li.flex-column"):
                key_tag, table = li.find("strong"), li.find("table")
                if key_tag and table:
                    key = key_tag.get_text(strip=True)
                    table_data = [[col.get_text(strip=True) for col in row.find_all("td")] for row in table.find_all("tr") if any(c.get_text(strip=True) for c in row.find_all("td"))]
                    parsed_info[key] = table_data
            piyasa_degeri_data = parsed_info.get("Piyasa Değeri", [])
            piyasa_degeri_model = None
            if piyasa_degeri_data:
                # Extract currency position data if available
                doviz_varliklari = next((row[1] for row in piyasa_degeri_data if "Döviz Varlıkları" in row[0]), None)
                doviz_yukumlulukleri = next((row[1] for row in piyasa_degeri_data if "Döviz Yükümlülükleri" in row[0]), None)
                net_pozisyon = next((row[1] for row in piyasa_degeri_data if "Net Döviz Pozisyonu" in row[0]), None)
                
                # Convert string numbers to float
                def parse_currency_value(val):
                    if not val:
                        return None
                    return float(val.replace('.', '').replace(',', '.')) if isinstance(val, str) else val
                
                pd_dict = {
                    "doviz_pozisyonu": {
                        "varlıklar": parse_currency_value(doviz_varliklari), 
                        "yükümlülükler": parse_currency_value(doviz_yukumlulukleri)
                    } if doviz_varliklari or doviz_yukumlulukleri else None,
                    "net_kur_pozisyonu": parse_currency_value(net_pozisyon)
                }
                piyasa_degeri_model = PiyasaDegeri(**pd_dict)
            sirket_bilgileri = SirketGenelBilgileri(
                bist_kodu=parsed_info.get("BIST Kodu", ticker_upper),
                sirket_adi=parsed_info.get("Şirket Ünvanı", ""),
                faaliyet_konusu=parsed_info.get("Faaliyet Alanı"),
                sermaye=float(parsed_info.get("Sermaye", "0").replace('.', '').replace(',', '.')) if parsed_info.get("Sermaye") else None,
                genel_mudur=parsed_info.get("Genel Müdür"),
                personel_sayisi=int(parsed_info.get("Personel Sayısı")) if parsed_info.get("Personel Sayısı", "").isdigit() else None,
                web_sitesi=parsed_info.get("Web Adresi"),
                yonetim_kurulu=[Yonetici(adi_soyadi=item[0], gorevi=item[1] if len(item) > 1 else "Yönetim Kurulu Üyesi") for item in parsed_info.get("Yön. Kurulu Üyeleri", []) if item],
                istirakler=[Istirak(sirket_adi=item[0], pay_orani=float(item[2].replace(',', '.').replace('%', '')) if len(item) >= 3 and item[2] else 0) for item in parsed_info.get("İştirakler", []) if len(item) >= 2],
                ortaklar=[Ortak(ortak_adi=item[0], pay_orani=float(item[2].replace(',', '.').replace('%', '')) if len(item) >= 3 and item[2] else 0) for item in parsed_info.get("Ortaklar", []) if len(item) >= 1 and "TOPLAM" not in item[0].upper()],
                piyasa_degeri_detay=piyasa_degeri_model
            )
            return {"bilgiler": sirket_bilgileri, "mynet_url": target_url}
        except Exception as e:
            logger.exception(f"Error parsing company info page for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}
    
    async def get_finansal_veri(self, ticker_kodu: str, zaman_araligi: ZamanAraligiEnum) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page for the specified ticker could not be found."}
        target_url = url_map[ticker_upper]
        try:
            response = await self._http_client.get(target_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            chart_script = next((s.string for s in soup.find_all("script") if s.string and "initChartData" in s.string), None)
            if not chart_script: return {"error": "Could not find chart data script on the page."}
            match = re.search(r'"data"\s*:\s*(\[\[.*?\]\])', chart_script, re.DOTALL)
            if not match: return {"error": "Could not parse 'data' array from the chart script."}
            raw_data_list = json.loads(match.group(1))
            all_data_points = []
            for i, point in enumerate(raw_data_list):
                try:
                    if not isinstance(point, list) or len(point) < 5: continue
                    all_data_points.append(FinansalVeriNoktasi(tarih=datetime.fromtimestamp(float(point[0]) / 1000), acilis=float(point[1]), en_yuksek=float(point[2]), en_dusuk=float(point[3]), kapanis=float(point[1]), hacim=float(point[4])))
                except (ValueError, TypeError, IndexError) as e:
                    logger.error(f"Could not convert data point #{i+1}: {point}. Error: {e}. Skipping.")
            if not all_data_points: return {"veri_noktalari": []}
            if zaman_araligi == ZamanAraligiEnum.TUMU: return {"veri_noktalari": all_data_points}
            latest_date = all_data_points[-1].tarih
            delta_map = {ZamanAraligiEnum.GUNLUK: timedelta(days=1), ZamanAraligiEnum.HAFTALIK: timedelta(weeks=1), ZamanAraligiEnum.AYLIK: timedelta(days=30), ZamanAraligiEnum.UC_AYLIK: timedelta(days=90), ZamanAraligiEnum.ALTI_AYLIK: timedelta(days=180), ZamanAraligiEnum.YILLIK: timedelta(days=365), ZamanAraligiEnum.UC_YILLIK: timedelta(days=3*365), ZamanAraligiEnum.BES_YILLIK: timedelta(days=5*365)}
            start_date = latest_date - delta_map.get(zaman_araligi, timedelta(days=0))
            return {"veri_noktalari": [p for p in all_data_points if p.tarih >= start_date]}
        except Exception as e:
            logger.exception(f"Error getting financial data for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}

    async def _get_available_periods(self, ticker_kodu: str, page_type: str) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page for the specified ticker could not be found."}
        try:
            response = await self._http_client.get(f"{url_map[ticker_upper]}{page_type}/")
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            select_box = soup.find("select", {"id": "i"})
            if not select_box: return {"error": "Could not find the period selection dropdown."}
            donemler = [MevcutDonem(yil=int(p[0]), donem=int(p[1]), aciklama=opt.get_text(strip=True)) for opt in select_box.find_all("option") if (p := opt['value'].strip('/').split('/')[-2].split('-')) and len(p) == 2]
            return {"mevcut_donemler": donemler}
        except Exception as e:
            logger.exception(f"Error parsing available periods for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}

    async def get_available_bilanco_periods(self, ticker_kodu: str) -> Dict[str, Any]: return await self._get_available_periods(ticker_kodu, "bilanco")
    async def get_available_kar_zarar_periods(self, ticker_kodu: str) -> Dict[str, Any]: return await self._get_available_periods(ticker_kodu, "karzarar")

    async def get_bilanco(self, ticker_kodu: str, yil: int, donem: int) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page could not be found."}
        try:
            response = await self._http_client.get(f"{url_map[ticker_upper]}bilanco/{yil}-{donem}/1/")
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            data_container = soup.select_one("div.flex-list-1-col")
            if not data_container: return {"error": "Balance sheet content could not be found."}
            kalemler = [BilancoKalemi(kalem=k.get_text(strip=True), deger=v.get_text(strip=True)) for li in data_container.select("ul > li") if (k := li.find("strong")) and (v := li.find("span", class_="text-r"))]
            return {"bilanco": kalemler}
        except Exception as e:
            logger.exception(f"Error parsing balance sheet for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}

    async def get_kar_zarar(self, ticker_kodu: str, yil: int, donem: int) -> Dict[str, Any]:
        ticker_upper = ticker_kodu.upper()
        url_map = await self.get_url_map()
        if ticker_upper not in url_map: return {"error": "Mynet Finans page for the specified ticker could not be found."}
        try:
            response = await self._http_client.get(f"{url_map[ticker_upper]}karzarar/{yil}-{donem}/1/")
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            data_container = soup.select_one("div.flex-list-1-col")
            if not data_container: return {"error": "P/L statement content could not be found."}
            kalemler = [KarZararKalemi(kalem=k.get_text(strip=True), deger=v.get_text(strip=True)) for li in data_container.select("ul > li") if (k := li.find("strong")) and (v := li.find("span", class_="text-r"))]
            return {"kar_zarar_tablosu": kalemler}
        except Exception as e:
            logger.exception(f"Error parsing P/L statement for {ticker_upper}")
            return {"error": f"An unexpected error occurred: {e}"}
    
    async def get_endeks_listesi(self) -> List[EndeksBilgisi]:
        """
        Fetches BIST indices list from Mynet Finans endeks page and parses HTML table.
        """
        try:
            endeks_url = "https://finans.mynet.com/borsa/endeks/"
            response = await self._http_client.get(endeks_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find the main table containing index data
            table = soup.select_one("table.table-data")
            if not table:
                logger.error("Could not find indices table on Mynet page")
                return []
            
            indices = []
            
            # Parse table rows
            tbody = table.find("tbody")
            if not tbody:
                logger.error("Could not find table body in indices table")
                return []
            
            for row in tbody.find_all("tr"):
                try:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    
                    # First cell contains index name and possibly code
                    name_cell = cells[0]
                    name_link = name_cell.find("a")
                    if name_link:
                        index_name = name_link.get_text(strip=True)
                        index_url = name_link.get("href", "")
                    else:
                        index_name = name_cell.get_text(strip=True)
                        index_url = ""
                    
                    # Filter for actual BIST indices only
                    if not self._is_bist_index(index_name):
                        continue
                    
                    # Extract index code from URL first, fallback to name-based extraction
                    index_code = self._extract_index_code_from_url(index_url) or self._extract_index_code_from_name(index_name)
                    
                    # Create EndeksBilgisi object with empty companies list for now
                    # We'll populate companies separately to avoid making too many requests
                    endeks = EndeksBilgisi(
                        endeks_kodu=index_code,
                        endeks_adi=index_name,
                        sirket_sayisi=0,  # Will be updated when companies are fetched
                        sirketler=[]     # Will be populated when needed
                    )
                    
                    # Store the URL for later use in fetching companies
                    endeks._mynet_url = index_url  # Store URL as private attribute
                    
                    indices.append(endeks)
                    
                except Exception as e:
                    logger.warning(f"Error parsing index row: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(indices)} indices from Mynet Finans")
            return indices
            
        except Exception as e:
            logger.error(f"Error fetching indices from Mynet Finans: {e}")
            return []
    
    def _is_bist_index(self, name: str) -> bool:
        """Check if the name represents a BIST index rather than a fund or portfolio."""
        name_upper = name.upper()
        
        # Exclude non-BIST items
        exclude_keywords = [
            "PORTFOY", "FONU", "PORTFOLIO", "AK PORTFOY", "IS PORTFOY", 
            "GARANTI PORTFOY", "YKB PORTFOY", "VAKIF PORTFOY", "HALK PORTFOY",
            "OYAK PORTFOY", "ZİRAAT PORTFOY", "TEB PORTFOY", "HSBC PORTFOY"
        ]
        
        for keyword in exclude_keywords:
            if keyword in name_upper:
                return False
        
        # Include BIST indices
        include_patterns = [
            "BIST",
            "AGIRLIK SINIRLAMALI",  # These are BIST index variants
            "KATILIM",              # Participation indices
        ]
        
        for pattern in include_patterns:
            if pattern in name_upper:
                return True
        
        # Additional check for index codes
        if any(code in name_upper for code in ["XU", "X10", "XBANK", "XTECH", "XHOLD"]):
            return True
        
        return False
    
    def _extract_index_code_from_url(self, url: str) -> str:
        """Extract index code from Mynet URL format.
        
        URL format: https://finans.mynet.com/borsa/endeks/[INDEX_CODE]-[description]/
        Example: https://finans.mynet.com/borsa/endeks/xu100-bist-100/ -> xu100
        """
        if not url:
            return ""
        
        try:
            # Extract the part after '/endeks/' and before the first '-'
            import re
            
            # Pattern to match: /endeks/([^-]+)-
            pattern = r'/endeks/([^/-]+)-'
            match = re.search(pattern, url)
            
            if match:
                index_code = match.group(1).upper()
                logger.debug(f"Extracted index code '{index_code}' from URL: {url}")
                return index_code
            else:
                logger.debug(f"Could not extract index code from URL: {url}")
                return ""
                
        except Exception as e:
            logger.warning(f"Error extracting index code from URL {url}: {e}")
            return ""
    
    def _extract_index_code_from_name(self, name: str) -> str:
        """Extract or derive index code from index name."""
        name = name.strip()
        
        # Look for codes in parentheses
        parentheses_match = re.search(r'\(([A-Z0-9]+)\)', name)
        if parentheses_match:
            return parentheses_match.group(1)
        
        # Map common index names to known codes  
        name_to_code_map = {
            "BIST 100": "XU100",
            "BIST 50": "XU050", 
            "BIST 30": "XU030",
            "BIST 100-30": "XYUZO",
            "100 AGIRLIK SINIRLAMALI 10": "X100S",
            "100 AGIRLIK SINIRLAMALI 25": "X100C",
            "BIST BANKACILIĞI": "XBANK",
            "BIST TEKNOLOJİ": "XUTEK",
            "BIST HOLDİNG VE YATIRIM": "XHOLD",
            "BIST SINAİ": "XUSIN",
            "BIST MALİ": "XUMAL",
            "BIST HİZMETLER": "XUHIZ",
            "BIST GIDA İÇECEK": "XGIDA",
            "BIST ELEKTRİK": "XELKT",
            "BIST İLETİŞİM": "XILTM",
            "BIST TEMETTÜ": "XTMTU",
            "BIST TEMETTÜ 25": "XTM25",
            "BIST KURUMSAL YÖNETİM": "XKURY",
            "BIST SÜRDÜRÜLEBİLİRLİK": "XUSRD",
            "BIST LİKİT BANKA": "XLBNK",
            "BIST METAL ANA": "XMANA",
            "BIST METAL EŞYA MAKİNA": "XMESY",
            "BIST KİMYA PETROL PLASTİK": "XKMYA",
            "BIST TAŞ TOPRAK": "XTAST",
            "BIST TEKSTİL DERİ": "XTEKS",
            "BIST ORMAN KAĞIT BASIM": "XKAGT",
            "BIST İNŞAAT": "XINSA",
            "BIST TİCARET": "XTCRT",
            "BIST TURİZM": "XTRZM",
            "BIST ULAŞTIRMA": "XULAS",
            "BIST SİGORTA": "XSGRT",
            "BIST FİNANSAL KİRALAMA FAKTORİNG": "XFINK",
            "BIST GAYRİMENKUL YATIRIM ORTAKLIĞI": "XGMYO",
            "BIST KATILIM TÜM": "XKTUM",
            "BIST KATILIM 100": "XK100",
            "BIST KATILIM 50": "XK050",
            "BIST KATILIM 30": "XK030"
        }
        
        # Check for exact matches first
        upper_name = name.upper()
        for name_key, code in name_to_code_map.items():
            if name_key.upper() == upper_name:
                return code
        
        # Check for partial matches
        for name_key, code in name_to_code_map.items():
            if name_key.upper() in upper_name or upper_name in name_key.upper():
                return code
        
        # If no match found, derive code from name
        # Remove common words and create abbreviation
        words = name.upper().replace("BIST", "").replace("ENDEKSİ", "").strip().split()
        if len(words) >= 2:
            # Take first 2-3 letters from first word and first 2-3 from second word
            code = words[0][:3] + words[1][:3]
            return code[:6]  # Limit to 6 characters
        elif len(words) == 1:
            return words[0][:6]
        else:
            # Fallback
            clean_name = re.sub(r'[^A-Z0-9]', '', name.upper())
            return clean_name[:6] if clean_name else "UNKNOWN"
    
    async def get_endeks_sirketleri(self, endeks_url: str) -> List[str]:
        """
        Fetch companies in an index from Mynet Finans.
        
        Args:
            endeks_url: The index URL from Mynet (e.g., 'https://finans.mynet.com/borsa/endeks/xu100-bist-100/')
        
        Returns:
            List of ticker codes in the index
        """
        if not endeks_url:
            return []
        
        try:
            # Construct the companies URL by adding 'endekshisseleri/'
            if not endeks_url.endswith('/'):
                endeks_url += '/'
            companies_url = endeks_url + 'endekshisseleri/'
            
            response = await self._http_client.get(companies_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find the companies table
            table = soup.select_one("table.table-data")
            if not table:
                logger.warning(f"Could not find companies table at {companies_url}")
                return []
            
            tbody = table.find("tbody")
            if not tbody:
                logger.warning(f"Could not find table body at {companies_url}")
                return []
            
            companies = []
            
            for row in tbody.find_all("tr"):
                try:
                    # First cell contains the company link and ticker
                    first_cell = row.find("td")
                    if not first_cell:
                        continue
                    
                    # Find the company link
                    company_link = first_cell.find("a")
                    if not company_link:
                        continue
                    
                    # Extract ticker from the title attribute
                    # The title is in format: "TICKER COMPANY_NAME"
                    title_attr = company_link.get("title", "")
                    
                    # Extract ticker (first word before space in title)
                    ticker = None
                    if title_attr:
                        parts = title_attr.split()
                        if parts:
                            ticker = parts[0].upper()
                    
                    # Validate ticker format (3-6 uppercase letters)
                    if ticker and re.match(r'^[A-Z]{3,6}$', ticker):
                        companies.append(ticker)
                        logger.debug(f"Found company: {ticker}")
                    
                except Exception as e:
                    logger.warning(f"Error parsing company row: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(companies)} companies from {companies_url}")
            return companies
            
        except Exception as e:
            logger.error(f"Error fetching companies from {endeks_url}: {e}")
            return []
