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
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
from borsa_models import (
    HisseDetay, SirketGenelBilgileri, Istirak, Ortak, Yonetici, 
    PiyasaDegeri, BilancoKalemi, MevcutDonem, KarZararKalemi,
    FinansalVeriNoktasi, ZamanAraligiEnum
)

logger = logging.getLogger(__name__)

class MynetProvider:
    BASE_URL = "https://finans.mynet.com/borsa/hisseler/"
    CACHE_DURATION = 24 * 60 * 60

    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._ticker_to_url: Dict[str, str] = {}
        self._last_fetch_time: float = 0
        
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
        if not self._ticker_to_url or (current_time - self._last_fetch_time) > self.CACHE_DURATION:
            url_map = await self._fetch_ticker_urls()
            if url_map:
                self._ticker_to_url, self._last_fetch_time = url_map, current_time
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
                pd_dict = { "doviz_varliklari_tl": next((row[1] for row in piyasa_degeri_data if "Döviz Varlıkları" in row[0]), None), "doviz_yukumlulukleri_tl": next((row[1] for row in piyasa_degeri_data if "Döviz Yükümlülükleri" in row[0]), None), "net_doviz_pozisyonu_tl": next((row[1] for row in piyasa_degeri_data if "Net Döviz Pozisyonu" in row[0]), None), "turev_enstrumanlar_net_pozisyonu_tl": next((row[1] for row in piyasa_degeri_data if "Türev Enstrümanlar" in row[0]), None) }
                piyasa_degeri_model = PiyasaDegeri(**pd_dict)
            sirket_bilgileri = SirketGenelBilgileri(bist_kodu=parsed_info.get("BIST Kodu"), halka_acilma_tarihi=parsed_info.get("Halka Açılma Tarihi"), kurulus_tarihi=parsed_info.get("Kuruluş Tarihi"), faaliyet_alani=parsed_info.get("Faaliyet Alanı"), sermaye=parsed_info.get("Sermaye"), genel_mudur=parsed_info.get("Genel Müdür"), personel_sayisi=int(parsed_info.get("Personel Sayısı")) if parsed_info.get("Personel Sayısı", "").isdigit() else None, web_adresi=parsed_info.get("Web Adresi"), sirket_unvani=parsed_info.get("Şirket Ünvanı"), yonetim_kurulu=[Yonetici(isim=item[0]) for item in parsed_info.get("Yön. Kurulu Üyeleri", []) if item], istirakler=[Istirak(isim=item[0], sermaye=item[1], pay_orani=item[2]) for item in parsed_info.get("İştirakler", []) if len(item) == 3], ortaklar=[Ortak(isim=item[0], sermaye_tutari=item[1], sermaye_orani=item[2]) for item in parsed_info.get("Ortaklar", []) if len(item) == 3 and "TOPLAM" not in item[0].upper()], piyasa_degeri=piyasa_degeri_model)
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
