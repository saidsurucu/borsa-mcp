"""
Mynet Finans provider models.
Contains models for hybrid company data, KAP news, financial statements,
and Turkish-specific company information.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
from .base import ZamanAraligiEnum

# --- Mynet Provider Models ---

class HisseDetay(BaseModel):
    """Detailed stock information from Mynet Finans."""
    bist_kodu: str = Field(description="BIST ticker code.")
    sirket_adi: str = Field(description="Company name.")
    sektor: Optional[str] = Field(None, description="Company sector.")
    alt_sektor: Optional[str] = Field(None, description="Sub-sector.")
    piyasa: Optional[str] = Field(None, description="Market segment (Ana Pazar, Alt Pazar, etc.).")
    
    # Market data
    son_fiyat: Optional[float] = Field(None, description="Last trading price.")
    degisim: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzde: Optional[float] = Field(None, description="Price change percentage.")
    hacim: Optional[int] = Field(None, description="Trading volume.")
    
    # Company metrics
    piyasa_degeri: Optional[float] = Field(None, description="Market capitalization.")
    personel_sayisi: Optional[int] = Field(None, description="Number of employees.")
    kurulis_yili: Optional[int] = Field(None, description="Establishment year.")
    web_sitesi: Optional[str] = Field(None, description="Official website.")
    adres: Optional[str] = Field(None, description="Company address.")
    telefon: Optional[str] = Field(None, description="Phone number.")
    faks: Optional[str] = Field(None, description="Fax number.")
    email: Optional[str] = Field(None, description="Email address.")

class Yonetici(BaseModel):
    """Company executive information."""
    adi_soyadi: str = Field(description="Executive name.")
    gorevi: str = Field(description="Executive position/title.")
    deneyim: Optional[str] = Field(None, description="Professional experience.")
    egitim: Optional[str] = Field(None, description="Educational background.")

class Ortak(BaseModel):
    """Shareholder information."""
    ortak_adi: str = Field(description="Shareholder name.")
    pay_orani: float = Field(description="Ownership percentage.")
    pay_grubu: Optional[str] = Field(None, description="Share class (A, B, C, etc.).")
    oy_hakki: Optional[float] = Field(None, description="Voting rights percentage.")

class Istirak(BaseModel):
    """Subsidiary/affiliate information."""
    sirket_adi: str = Field(description="Subsidiary company name.")
    pay_orani: float = Field(description="Ownership percentage.")
    faaliyet_konusu: Optional[str] = Field(None, description="Business activity.")
    ulke: Optional[str] = Field(None, description="Country of operation.")

class PiyasaDegeri(BaseModel):
    """Market value and currency position (mainly for banks)."""
    kur_riski: Optional[str] = Field(None, description="Currency risk exposure.")
    doviz_pozisyonu: Optional[Dict[str, float]] = Field(None, description="Foreign currency positions.")
    net_kur_pozisyonu: Optional[float] = Field(None, description="Net currency position.")

class SirketGenelBilgileri(BaseModel):
    """General company information from Mynet."""
    bist_kodu: str = Field(description="BIST ticker code.")
    sirket_adi: str = Field(description="Company name.")
    faaliyet_konusu: Optional[str] = Field(None, description="Business activity.")
    personel_sayisi: Optional[int] = Field(None, description="Number of employees.")
    genel_mudur: Optional[str] = Field(None, description="General Manager.")
    yonetim_kurulu_baskani: Optional[str] = Field(None, description="Chairman of the Board.")
    
    # Leadership and governance
    yonetim_kurulu: List[Yonetici] = Field(default_factory=list, description="Board of directors.")
    ust_duzey_yoneticiler: List[Yonetici] = Field(default_factory=list, description="Senior executives.")
    
    # Ownership structure
    ortaklar: List[Ortak] = Field(default_factory=list, description="Shareholders.")
    istirakler: List[Istirak] = Field(default_factory=list, description="Subsidiaries and affiliates.")
    
    # Market and financial data
    piyasa_degeri_detay: Optional[PiyasaDegeri] = Field(None, description="Detailed market value information.")
    sermaye: Optional[float] = Field(None, description="Paid-in capital.")
    nominal_sermaye: Optional[float] = Field(None, description="Nominal capital.")
    
    # Contact and administrative info
    merkez_adresi: Optional[str] = Field(None, description="Headquarters address.")
    telefon: Optional[str] = Field(None, description="Phone number.")
    web_sitesi: Optional[str] = Field(None, description="Official website.")
    
    # Additional data
    veri_kaynak: str = Field(default="mynet", description="Data source indicator.")
    son_guncelleme: Optional[datetime.datetime] = Field(None, description="Last update timestamp.")

# --- Financial Statement Models (Legacy) ---

class BilancoKalemi(BaseModel):
    """Balance sheet line item."""
    kalem_adi: str = Field(description="Line item name.")
    deger: Optional[float] = Field(None, description="Value in thousands of TL.")
    onceki_donem: Optional[float] = Field(None, description="Previous period value.")

class KarZararKalemi(BaseModel):
    """Income statement line item."""
    kalem_adi: str = Field(description="Line item name.")
    deger: Optional[float] = Field(None, description="Current period value.")
    onceki_donem: Optional[float] = Field(None, description="Previous period value.")
    degisim_yuzde: Optional[float] = Field(None, description="Change percentage.")

class MevcutDonem(BaseModel):
    """Available financial period."""
    yil: int = Field(description="Year.")
    donem: str = Field(description="Period (Q1, Q2, Q3, Annual).")
    donem_kodu: str = Field(description="Period code.")

# --- KAP News Models ---

class KapHaberi(BaseModel):
    """Individual KAP news item."""
    baslik: str = Field(description="News headline.")
    tarih: str = Field(description="Publication date and time.")
    url: str = Field(description="Full URL to the news detail.")
    haber_id: str = Field(description="Unique news identifier.")
    title_attr: Optional[str] = Field(None, description="Title attribute from link.")

class KapHaberleriSonucu(BaseModel):
    """Result of KAP news query."""
    ticker_kodu: Optional[str] = Field(None, description="Company ticker code.")
    kap_haberleri: List[KapHaberi] = Field(default_factory=list, description="List of KAP news items.")
    toplam_haber: Optional[int] = Field(None, description="Total number of news items retrieved.")
    kaynak_url: Optional[str] = Field(None, description="Source URL for the news.")
    error_message: Optional[str] = Field(None, description="Error message if query failed.")

class KapHaberDetayi(BaseModel):
    """Detailed KAP news content."""
    baslik: str = Field(description="News headline.")
    belge_turu: Optional[str] = Field(None, description="Document type (e.g., 'Sirket Genel Bilgi Formu').")
    markdown_icerik: str = Field(description="Clean markdown content converted from HTML.")
    
    # Removed for cleaner API (available in KapHaberleriSonucu)
    # url: Optional[str] = Field(None, description="Original news URL.")
    # ham_html: Optional[str] = Field(None, description="Raw HTML content.")

class KapHaberSayfasi(BaseModel):
    """Paginated KAP news content for large documents."""
    baslik: str = Field(description="News headline.")
    belge_turu: Optional[str] = Field(None, description="Document type.")
    sayfa_numarasi: int = Field(description="Current page number.")
    toplam_karakter: int = Field(description="Total character count of full document.")
    sayfa_karakter: int = Field(description="Character count of this page.")
    markdown_icerik: str = Field(description="Markdown content for this page.")
    daha_var: bool = Field(description="Whether there are more pages to fetch.")
    sonraki_sayfa: Optional[int] = Field(None, description="Next page number if available.")