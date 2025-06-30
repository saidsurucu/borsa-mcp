"""
KAP (Public Disclosure Platform) related models.
Contains models for company search, participation finance compatibility,
and BIST index information.
"""
from pydantic import BaseModel, Field
from typing import List, Optional

# --- KAP Company Search Models ---
class SirketInfo(BaseModel):
    """Represents basic information for a single company from KAP."""
    sirket_adi: str = Field(description="The full and official name of the company.")
    ticker_kodu: str = Field(description="The official ticker code (symbol) of the company on Borsa Istanbul.")
    sehir: str = Field(description="The city where the company is registered.")

class SirketAramaSonucu(BaseModel):
    """The result of a company search operation from KAP."""
    arama_terimi: str = Field(description="The term used for the search.")
    sonuclar: List[SirketInfo] = Field(description="List of companies matching the search criteria.")
    sonuc_sayisi: int = Field(description="Total number of results found.")
    error_message: Optional[str] = Field(None, description="Contains an error message if an error occurred during the search.")

# --- KAP Participation Finance Models ---
class KatilimFinansUygunlukBilgisi(BaseModel):
    """Single participation finance compatibility entry."""
    ticker_kodu: str = Field(description="BIST ticker code.")
    sirket_adi: str = Field(description="Company name.")
    para_birimi: str = Field(description="Presentation currency.")
    finansal_donem: str = Field(description="Financial statement year/period.")
    tablo_niteligi: str = Field(description="Financial statement nature (Consolidated/Non-consolidated).")
    uygun_olmayan_faaliyet: str = Field(description="Does the company have activities incompatible with participation finance principles?")
    uygun_olmayan_imtiyaz: str = Field(description="Does the company have privileges incompatible with participation finance principles?")
    destekleme_eylemi: str = Field(description="Does the company support actions defined in standards?")
    dogrudan_uygun_olmayan_faaliyet: str = Field(description="Does the company have direct activities incompatible with participation finance?")
    uygun_olmayan_gelir_orani: str = Field(description="Percentage of income incompatible with participation finance principles.")
    uygun_olmayan_varlik_orani: str = Field(description="Percentage of assets incompatible with participation finance principles.")
    uygun_olmayan_borc_orani: str = Field(description="Percentage of debts incompatible with participation finance principles.")

class KatilimFinansUygunlukSonucu(BaseModel):
    """Result of participation finance compatibility query for a specific company."""
    ticker_kodu: str = Field(description="The ticker code that was searched.")
    sirket_bilgisi: Optional[KatilimFinansUygunlukBilgisi] = Field(None, description="Company's participation finance compatibility data if found.")
    veri_bulundu: bool = Field(description="Whether participation finance data was found for this company.")
    katilim_endeksi_dahil: bool = Field(False, description="Whether the company is included in any participation finance index (XK100, XK050, XK030).")
    katilim_endeksleri: List[str] = Field(default_factory=list, description="List of participation finance indices that include this company.")
    kaynak_url: str = Field(description="Source URL of the data.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- BIST Index Models ---
class EndeksBilgisi(BaseModel):
    """Single BIST index information."""
    endeks_kodu: str = Field(description="Index code (e.g., 'XU100', 'XBANK').")
    endeks_adi: str = Field(description="Index name (e.g., 'BIST 100', 'BIST Bankacılık').")
    sirket_sayisi: int = Field(description="Number of companies in the index.")
    sirketler: List[str] = Field(description="List of ticker codes in the index.")

class EndeksAramaSonucu(BaseModel):
    """Result of searching for a specific index."""
    arama_terimi: str = Field(description="The search term used.")
    endeks_bilgisi: Optional[EndeksBilgisi] = Field(None, description="Index information if found.")
    veri_bulundu: bool = Field(description="Whether the index was found.")
    kaynak_url: str = Field(description="Source URL of the data.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class EndeksAramaOgesi(BaseModel):
    """Simple index search result item."""
    endeks_kodu: str = Field(description="Index code (e.g., 'XU100', 'XBANK').")
    endeks_adi: str = Field(description="Index name (e.g., 'BIST 100', 'BIST Bankacılık').")

class EndeksKoduAramaSonucu(BaseModel):
    """Result of searching for BIST index codes."""
    arama_terimi: str = Field(description="The search term used (index name or code).")
    sonuclar: List[EndeksAramaOgesi] = Field(description="List of matching indices.")
    sonuc_sayisi: int = Field(description="Number of matching indices found.")
    kaynak_url: str = Field(default="https://www.kap.org.tr/tr/Endeksler", description="Source URL of the data.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class EndeksSirketDetayi(BaseModel):
    """Basic information for a company within an index."""
    ticker_kodu: str = Field(description="The ticker code of the company.")
    sirket_adi: Optional[str] = Field(None, description="The full name of the company.")

class EndeksSirketleriSonucu(BaseModel):
    """Result of fetching basic company information for companies in an index."""
    endeks_kodu: str = Field(description="The index code that was queried.")
    endeks_adi: Optional[str] = Field(None, description="The full name of the index.")
    toplam_sirket: int = Field(description="Total number of companies in the index.")
    sirketler: List[EndeksSirketDetayi] = Field(description="Basic information for each company in the index.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")