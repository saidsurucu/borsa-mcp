"""
TEFAS (Turkish Electronic Fund Trading Platform) related models.
Contains models for fund search, performance analysis, portfolio allocation,
fund comparison, and screening functionality.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime

# --- TEFAS Fund Models ---

class FonBilgisi(BaseModel):
    """Basic fund information with enhanced performance metrics."""
    fon_kodu: str = Field(description="Fund code (unique identifier).")
    fon_adi: str = Field(description="Fund name.")
    kurulus: Optional[str] = Field(None, description="Management company.")
    yonetici: Optional[str] = Field(None, description="Fund manager.")
    fon_turu: Optional[str] = Field(None, description="Fund type.")
    risk_degeri: Optional[int] = Field(None, description="Risk level (1-7 scale).")
    fiyat: Optional[float] = Field(None, description="Current NAV price.")
    tedavuldeki_pay_sayisi: Optional[float] = Field(None, description="Outstanding shares.")
    toplam_deger: Optional[float] = Field(None, description="Total fund size/AUM.")
    yatirimci_sayisi: Optional[int] = Field(None, description="Number of investors.")
    
    # Performance metrics (from search results)
    getiri_1_gun: Optional[float] = Field(None, description="1-day return percentage.")
    getiri_1_hafta: Optional[float] = Field(None, description="1-week return percentage.")
    getiri_1_ay: Optional[float] = Field(None, description="1-month return percentage.")
    getiri_3_ay: Optional[float] = Field(None, description="3-month return percentage.")
    getiri_6_ay: Optional[float] = Field(None, description="6-month return percentage.")
    getiri_yil_basi: Optional[float] = Field(None, description="Year-to-date return percentage.")
    getiri_1_yil: Optional[float] = Field(None, description="1-year return percentage.")
    getiri_3_yil: Optional[float] = Field(None, description="3-year return percentage.")
    getiri_5_yil: Optional[float] = Field(None, description="5-year return percentage.")

class FonAramaSonucu(BaseModel):
    """Result of fund search operation."""
    arama_terimi: Optional[str] = Field(None, description="Search term used.")
    fon_kategorisi: Optional[str] = Field(None, description="Fund category filter applied.")
    sonuclar: List[FonBilgisi] = Field(default_factory=list, description="List of funds matching criteria.")
    sonuc_sayisi: Optional[int] = Field(None, description="Number of results found.")
    
    # Advanced search fields
    toplam_fon_sayisi: Optional[int] = Field(None, description="Total funds available in database.")
    kategori_listesi: Optional[List[str]] = Field(None, description="Available fund categories.")
    siralam_kriteri: Optional[str] = Field(None, description="Sort criteria applied.")
    veri_kaynak: Optional[str] = Field(None, description="Data source: 'takasbank' or 'tefas'.")
    
    error_message: Optional[str] = Field(None, description="Error message if search failed.")

# --- Fund Detail Models ---

class FonProfil(BaseModel):
    """Technical fund profile information."""
    isin_kodu: Optional[str] = Field(None, description="ISIN code.")
    islem_saatleri: Optional[str] = Field(None, description="Trading hours.")
    komisyon: Optional[float] = Field(None, description="Management fee percentage.")
    giris_ucreti: Optional[float] = Field(None, description="Entry fee percentage.")
    cikis_ucreti: Optional[float] = Field(None, description="Exit fee percentage.")
    min_yatirim: Optional[float] = Field(None, description="Minimum investment amount.")
    benchmark: Optional[str] = Field(None, description="Benchmark index.")

class FonPortfoyDagilimi(BaseModel):
    """Portfolio allocation breakdown."""
    hisse_senedi: Optional[float] = Field(None, description="Equity allocation percentage.")
    tahvil_bono: Optional[float] = Field(None, description="Bond allocation percentage.")
    para_piyasasi: Optional[float] = Field(None, description="Money market allocation percentage.")
    altin: Optional[float] = Field(None, description="Gold allocation percentage.")
    doviz: Optional[float] = Field(None, description="Foreign currency allocation percentage.")
    diger: Optional[float] = Field(None, description="Other assets allocation percentage.")

class FonFiyatGecmisi(BaseModel):
    """Historical price data point."""
    tarih: datetime.date = Field(description="Date.")
    fiyat: float = Field(description="NAV price on that date.")
    getiri_gunluk: Optional[float] = Field(None, description="Daily return percentage.")

class FonDetayBilgisi(BaseModel):
    """Comprehensive fund detail information."""
    fon_bilgisi: Optional[FonBilgisi] = Field(None, description="Basic fund information.")
    profil: Optional[FonProfil] = Field(None, description="Technical fund profile.")
    portfoy_dagilimi: Optional[FonPortfoyDagilimi] = Field(None, description="Portfolio allocation.")
    fiyat_gecmisi: List[FonFiyatGecmisi] = Field(default_factory=list, description="Historical price data.")
    
    # Risk and performance metrics
    standart_sapma: Optional[float] = Field(None, description="Standard deviation (volatility).")
    sharpe_orani: Optional[float] = Field(None, description="Sharpe ratio.")
    max_dusus: Optional[float] = Field(None, description="Maximum drawdown percentage.")
    beta: Optional[float] = Field(None, description="Beta coefficient vs benchmark.")
    alpha: Optional[float] = Field(None, description="Alpha vs benchmark.")
    
    # Additional metadata
    api_source: Optional[str] = Field(None, description="API source used for data.")
    son_guncelleme: Optional[datetime.datetime] = Field(None, description="Last update timestamp.")
    veri_tamamlik_skoru: Optional[float] = Field(None, description="Data completeness score (0-100).")
    
    error_message: Optional[str] = Field(None, description="Error message if retrieval failed.")

# --- Performance Analysis Models ---

class FonFiyatNoktasi(BaseModel):
    """Single price point from TEFAS BindHistoryInfo API."""
    tarih: datetime.date = Field(description="Date of the price point.")
    fiyat: float = Field(description="NAV price.")
    portfoy_buyuklugu: Optional[float] = Field(None, description="Portfolio size on that date.")
    birim_pay_sayisi: Optional[float] = Field(None, description="Outstanding unit shares.")
    yatirimci_sayisi: Optional[int] = Field(None, description="Number of investors.")
    fon_baslik: Optional[str] = Field(None, description="Fund title from TEFAS.")
    bulten_fiyat: Optional[float] = Field(None, description="Bulletin price.")

class FonPerformansSonucu(BaseModel):
    """Fund performance history analysis result."""
    fon_kodu: Optional[str] = Field(None, description="Fund code.")
    baslangic_tarihi: Optional[datetime.date] = Field(None, description="Performance analysis start date.")
    bitis_tarihi: Optional[datetime.date] = Field(None, description="Performance analysis end date.")
    
    # Price data
    fiyat_noktalari: List[FonFiyatNoktasi] = Field(default_factory=list, description="Historical price points from TEFAS API.")
    
    # Performance calculations
    toplam_getiri: Optional[float] = Field(None, description="Total return percentage for the period.")
    yillik_getiri: Optional[float] = Field(None, description="Annualized return percentage.")
    en_yuksek_fiyat: Optional[float] = Field(None, description="Highest price in the period.")
    en_dusuk_fiyat: Optional[float] = Field(None, description="Lowest price in the period.")
    volatilite: Optional[float] = Field(None, description="Price volatility (standard deviation).")
    
    # Metadata
    veri_nokta_sayisi: Optional[int] = Field(None, description="Number of data points retrieved.")
    kaynak: Optional[str] = Field(None, description="TEFAS API source.")
    
    error_message: Optional[str] = Field(None, description="Error message if analysis failed.")

# --- Portfolio Analysis Models ---

class PortfoyVarlik(BaseModel):
    """Individual portfolio asset."""
    varlik_adi: str = Field(description="Asset name.")
    varlik_kodu: Optional[str] = Field(None, description="Asset code/ISIN.")
    varlik_turu: str = Field(description="Asset type (e.g., 'Hisse Senedi', 'Devlet Tahvili').")
    oran: float = Field(description="Allocation percentage.")
    deger: Optional[float] = Field(None, description="Asset value in TL.")

class VarlikGrubu(BaseModel):
    """Grouped assets by type with metadata."""
    grup_adi: str = Field(description="Asset group name (e.g., 'Equity', 'Fixed Income').")
    toplam_oran: float = Field(description="Total allocation percentage for this group.")
    varlik_sayisi: int = Field(description="Number of assets in this group.")
    varlıklar: List[PortfoyVarlik] = Field(description="Individual assets in this group.")

class PortfoyTarihselVeri(BaseModel):
    """Historical portfolio allocation data."""
    tarih: datetime.date = Field(description="Allocation date.")
    varlik_turu_kodu: str = Field(description="Asset type code from TEFAS.")
    varlik_turu_adi: str = Field(description="Human-readable asset type name.")
    oran: float = Field(description="Allocation percentage on this date.")

class FonPortfoySonucu(BaseModel):
    """Fund portfolio allocation analysis result."""
    fon_kodu: Optional[str] = Field(None, description="Fund code.")
    baslangic_tarihi: Optional[datetime.date] = Field(None, description="Portfolio analysis start date.")
    bitis_tarihi: Optional[datetime.date] = Field(None, description="Portfolio analysis end date.")
    
    # Current allocation (latest date)
    guncel_portfoy: List[PortfoyVarlik] = Field(default_factory=list, description="Current portfolio allocation.")
    varlik_gruplari: List[VarlikGrubu] = Field(default_factory=list, description="Assets grouped by type.")
    
    # Historical allocation data
    portfoy_gecmisi: List[PortfoyTarihselVeri] = Field(default_factory=list, description="Historical allocation changes.")
    
    # Summary statistics
    cesitlilik_skoru: Optional[float] = Field(None, description="Diversification score (0-100).")
    en_buyuk_holding: Optional[PortfoyVarlik] = Field(None, description="Largest individual holding.")
    grup_sayisi: Optional[int] = Field(None, description="Number of asset groups.")
    toplam_varlik_sayisi: Optional[int] = Field(None, description="Total number of individual assets.")
    
    # Metadata
    veri_nokta_sayisi: Optional[int] = Field(None, description="Number of historical data points.")
    kaynak: Optional[str] = Field(None, description="TEFAS API source.")
    
    error_message: Optional[str] = Field(None, description="Error message if analysis failed.")

# --- Fund Comparison Models ---

class FonKarsilastirmaOgesi(BaseModel):
    """Individual fund in comparison analysis."""
    fon_kodu: str = Field(description="Fund code.")
    fon_adi: str = Field(description="Fund name.")
    fon_turu: Optional[str] = Field(None, description="Fund type.")
    kurulus: Optional[str] = Field(None, description="Management company.")
    risk_degeri: Optional[int] = Field(None, description="Risk level.")
    
    # Performance data
    getiri_1a: Optional[float] = Field(None, description="1-month return.")
    getiri_3a: Optional[float] = Field(None, description="3-month return.")
    getiri_6a: Optional[float] = Field(None, description="6-month return.")
    getiri_yb: Optional[float] = Field(None, description="Year-to-date return.")
    getiri_1y: Optional[float] = Field(None, description="1-year return.")
    getiri_3y: Optional[float] = Field(None, description="3-year return.")
    getiri_5y: Optional[float] = Field(None, description="5-year return.")
    
    # Current data
    guncel_fiyat: Optional[float] = Field(None, description="Current NAV price.")
    toplam_deger: Optional[float] = Field(None, description="Total fund size.")
    yatirimci_sayisi: Optional[int] = Field(None, description="Number of investors.")
    
    # Rankings
    performans_sirasi: Optional[int] = Field(None, description="Performance ranking among compared funds.")
    risk_sirasi: Optional[int] = Field(None, description="Risk ranking among compared funds.")

class FonKarsilastirmaSonucu(BaseModel):
    """Fund comparison analysis result."""
    karsilastirma_tarihi: datetime.datetime = Field(description="Comparison timestamp.")
    fon_kodlari: List[str] = Field(description="List of fund codes being compared.")
    karsilastirma_tipi: str = Field(description="Comparison type: 'selected' or 'screening'.")
    
    # Comparison results
    fonlar: List[FonKarsilastirmaOgesi] = Field(description="Individual fund comparison data.")
    
    # Summary statistics
    ortalama_getiri_1y: Optional[float] = Field(None, description="Average 1-year return.")
    en_iyi_performans: Optional[str] = Field(None, description="Best performing fund code.")
    en_dusuk_risk: Optional[str] = Field(None, description="Lowest risk fund code.")
    en_buyuk_fon: Optional[str] = Field(None, description="Largest fund by AUM.")
    
    # Response metadata
    response_type: Optional[str] = Field(None, description="API response format: 'period_based' or 'date_range'.")
    toplam_fon_sayisi: int = Field(description="Number of funds compared.")
    api_source: str = Field(default="BindComparisonFundReturns", description="TEFAS API source.")
    
    error_message: Optional[str] = Field(None, description="Error message if comparison failed.")

# --- Fund Screening Models ---

class FonTaramaKriterleri(BaseModel):
    """Fund screening criteria."""
    # Performance criteria
    min_getiri_1y: Optional[float] = Field(None, description="Minimum 1-year return percentage.")
    max_risk: Optional[int] = Field(None, description="Maximum risk level (1-7).")
    min_sharpe: Optional[float] = Field(None, description="Minimum Sharpe ratio.")
    
    # Size criteria
    min_buyukluk: Optional[float] = Field(None, description="Minimum fund size in TL.")
    min_yatirimci: Optional[int] = Field(None, description="Minimum number of investors.")
    
    # Type criteria
    fon_turleri: Optional[List[str]] = Field(None, description="Fund types to include.")
    yonetim_sirketleri: Optional[List[str]] = Field(None, description="Management companies to include.")
    
    # Time-based criteria
    min_gecmis: Optional[int] = Field(None, description="Minimum track record in years.")
    analiz_tarihi: Optional[datetime.date] = Field(None, description="Analysis date for screening.")

class TaranmisFon(BaseModel):
    """Individual fund result from screening."""
    fon_kodu: str = Field(description="Fund code.")
    fon_adi: str = Field(description="Fund name.")
    fon_turu: str = Field(description="Fund type.")
    kurulus: str = Field(description="Management company.")
    risk_degeri: Optional[int] = Field(None, description="Risk level.")
    
    # Performance metrics
    getiri_1y: Optional[float] = Field(None, description="1-year return percentage.")
    getiri_3y: Optional[float] = Field(None, description="3-year return percentage.")
    sharpe_orani: Optional[float] = Field(None, description="Sharpe ratio.")
    volatilite: Optional[float] = Field(None, description="Volatility percentage.")
    max_dusus: Optional[float] = Field(None, description="Maximum drawdown percentage.")
    
    # Size and popularity
    toplam_deger: Optional[float] = Field(None, description="Fund size in TL.")
    yatirimci_sayisi: Optional[int] = Field(None, description="Number of investors.")
    guncel_fiyat: Optional[float] = Field(None, description="Current NAV price.")
    
    # Screening scores
    kalite_skoru: Optional[float] = Field(None, description="Quality score (0-100).")
    performans_skoru: Optional[float] = Field(None, description="Performance score (0-100).")
    genel_skor: Optional[float] = Field(None, description="Overall score (0-100).")

class FonTaramaSonucu(BaseModel):
    """Fund screening analysis result."""
    tarama_tarihi: datetime.datetime = Field(description="Screening timestamp.")
    uygulanan_kriterler: FonTaramaKriterleri = Field(description="Applied screening criteria.")
    
    # Results summary
    toplam_fon_sayisi: int = Field(description="Total funds screened.")
    kriter_uyan_sayisi: int = Field(description="Funds meeting criteria.")
    basari_orani: float = Field(description="Percentage meeting criteria.")
    
    # Screened funds
    bulunan_fonlar: List[TaranmisFon] = Field(description="Funds meeting screening criteria.")
    
    # Analysis summaries
    ortalama_getiri: Optional[float] = Field(None, description="Average return of results.")
    ortalama_risk: Optional[float] = Field(None, description="Average risk level of results.")
    ortalama_sharpe: Optional[float] = Field(None, description="Average Sharpe ratio of results.")
    toplam_aum: Optional[float] = Field(None, description="Total AUM of results.")
    
    # Category breakdown
    kategori_dagilimi: Dict[str, int] = Field(default_factory=dict, description="Fund type distribution.")
    sirket_dagilimi: Dict[str, int] = Field(default_factory=dict, description="Management company distribution.")
    
    # Top performers
    en_yuksek_getiri: Optional[TaranmisFon] = Field(None, description="Highest return fund.")
    en_dusuk_risk: Optional[TaranmisFon] = Field(None, description="Lowest risk fund.")
    en_buyuk_fon: Optional[TaranmisFon] = Field(None, description="Largest fund by AUM.")
    
    error_message: Optional[str] = Field(None, description="Error message if screening failed.")

# --- Investment Strategy Presets ---

class DegerYatirimiKriterleri(BaseModel):
    """Value investing criteria for funds."""
    fon_turleri: List[str] = Field(["Hisse Senedi", "Karma"], description="Equity and mixed funds.")
    min_getiri_1y: float = Field(10.0, description="Minimum 1-year return (10%).")
    max_risk: int = Field(5, description="Maximum risk level.")
    min_buyukluk: float = Field(100_000_000, description="Minimum 100M TL fund size.")
    min_sharpe: float = Field(0.5, description="Minimum Sharpe ratio.")

class TemettuYatirimiKriterleri(BaseModel):
    """Dividend-focused investing criteria."""
    fon_turleri: List[str] = Field(["Hisse Senedi"], description="Equity funds only.")
    min_getiri_1y: float = Field(15.0, description="Minimum 1-year return (15%).")
    max_risk: int = Field(4, description="Low to moderate risk.")
    min_buyukluk: float = Field(250_000_000, description="Minimum 250M TL fund size.")
    min_yatirimci: int = Field(1000, description="Minimum 1000 investors.")

class BuyumeYatirimiKriterleri(BaseModel):
    """Growth investing criteria."""
    fon_turleri: List[str] = Field(["Hisse Senedi", "Teknoloji"], description="Growth-oriented funds.")
    min_getiri_1y: float = Field(20.0, description="Minimum 1-year return (20%).")
    max_risk: int = Field(6, description="Accept higher risk for growth.")
    min_buyukluk: float = Field(50_000_000, description="Minimum 50M TL fund size.")
    min_gecmis: int = Field(2, description="Minimum 2 years track record.")

class MuhafazakarYatirimiKriterleri(BaseModel):
    """Conservative investing criteria."""
    fon_turleri: List[str] = Field(["Borçlanma Araçları", "Para Piyasası"], description="Conservative fund types.")
    min_getiri_1y: float = Field(5.0, description="Minimum 1-year return (5%).")
    max_risk: int = Field(3, description="Low risk tolerance.")
    min_buyukluk: float = Field(500_000_000, description="Minimum 500M TL fund size.")
    min_yatirimci: int = Field(5000, description="Minimum 5000 investors.")

# --- Fund Regulation Model ---

class FonMevzuatSonucu(BaseModel):
    """Fund regulation guide content."""
    baslik: str = Field(description="Regulation guide title.")
    icerik: str = Field(description="Complete regulation content in Turkish.")
    dosya_boyutu: int = Field(description="Content size in characters.")
    son_guncelleme: Optional[str] = Field(None, description="Last update timestamp.")
    kaynak: str = Field(description="Source file or module.")
    error_message: Optional[str] = Field(None, description="Error message if retrieval failed.")