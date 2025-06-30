"""
Pydantic models for the Borsa MCP server. Defines data structures for
company information from KAP and financial data from Yahoo Finance.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import datetime

# --- Enums ---
class YFinancePeriodEnum(str, Enum):
    """Enum for yfinance historical data periods."""
    P1D = "1d"
    P5D = "5d"
    P1MO = "1mo"
    P3MO = "3mo"
    P6MO = "6mo"
    P1Y = "1y"
    P2Y = "2y"
    P5Y = "5y"
    YTD = "ytd"
    MAX = "max"

class ZamanAraligiEnum(str, Enum):
    """Enum for Mynet time periods."""
    GUNLUK = "1d"
    HAFTALIK = "1w"
    AYLIK = "1mo"
    UC_AYLIK = "3mo"
    ALTI_AYLIK = "6mo"
    YILLIK = "1y"
    UC_YILLIK = "3y"
    BES_YILLIK = "5y"
    TUMU = "max"

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

# --- Yahoo Finance Models ---

class SirketProfiliYFinance(BaseModel):
    """Represents detailed company profile information from Yahoo Finance."""
    symbol: Optional[str] = Field(None, description="The stock ticker symbol.")
    longName: Optional[str] = Field(None, description="The full name of the company.")
    sector: Optional[str] = Field(None, description="The sector the company belongs to.")
    industry: Optional[str] = Field(None, description="The industry the company belongs to.")
    fullTimeEmployees: Optional[int] = Field(None, description="The number of full-time employees.")
    longBusinessSummary: Optional[str] = Field(None, description="A detailed summary of the company's business.")
    city: Optional[str] = Field(None, description="The city where the company is headquartered.")
    country: Optional[str] = Field(None, description="The country where the company is headquartered.")
    website: Optional[str] = Field(None, description="The official website of the company.")
    marketCap: Optional[float] = Field(None, description="The market capitalization of the company.")
    fiftyTwoWeekLow: Optional[float] = Field(None, description="The lowest stock price in the last 52 weeks.")
    fiftyTwoWeekHigh: Optional[float] = Field(None, description="The highest stock price in the last 52 weeks.")
    beta: Optional[float] = Field(None, description="A measure of the stock's volatility in relation to the market.")
    trailingPE: Optional[float] = Field(None, description="The trailing Price-to-Earnings ratio.")
    forwardPE: Optional[float] = Field(None, description="The forward Price-to-Earnings ratio.")
    dividendYield: Optional[float] = Field(None, description="The dividend yield of the stock.")
    currency: Optional[str] = Field(None, description="The currency in which the financial data is reported.")

class SirketProfiliSonucu(BaseModel):
    """The result of a company profile query supporting both Yahoo Finance and hybrid data sources."""
    ticker_kodu: str
    bilgiler: Optional[SirketProfiliYFinance] = Field(None, description="Yahoo Finance company profile data")
    mynet_bilgileri: Optional[Any] = Field(None, description="Mynet Finans company details (when using hybrid mode)")
    veri_kalitesi: Optional[Dict[str, Any]] = Field(None, description="Data quality metrics for hybrid sources")
    kaynak: Optional[str] = Field("yahoo", description="Data source: 'yahoo', 'mynet', or 'hibrit'")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class FinansalTabloSonucu(BaseModel):
    """Represents a financial statement (Balance Sheet, Income Statement, or Cash Flow) from yfinance."""
    ticker_kodu: str
    period_type: str = Field(description="The type of period ('annual' or 'quarterly').")
    tablo: List[Dict[str, Any]] = Field(description="The financial statement data as a list of records.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class FinansalVeriNoktasi(BaseModel):
    """Represents a single data point in a time series (OHLCV)."""
    tarih: datetime.datetime = Field(description="The timestamp for this data point.")
    acilis: float = Field(description="Opening price.")
    en_yuksek: float = Field(description="Highest price.")
    en_dusuk: float = Field(description="Lowest price.")
    kapanis: float = Field(description="Closing price.")
    hacim: float = Field(description="Trading volume.")

class FinansalVeriSonucu(BaseModel):
    """The result of a historical financial data query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    zaman_araligi: YFinancePeriodEnum = Field(description="The time range requested for the data.")
    veri_noktalari: List[FinansalVeriNoktasi] = Field(description="The list of historical data points.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Analyst Data Models ---
class AnalistTavsiyesi(BaseModel):
    """Represents a single analyst recommendation."""
    tarih: datetime.datetime = Field(description="Date of the recommendation.")
    firma: str = Field(description="Name of the analyst firm.")
    guncel_derece: str = Field(description="Current rating (e.g., Buy, Hold, Sell).")
    onceki_derece: Optional[str] = Field(None, description="Previous rating if this is an upgrade/downgrade.")
    aksiyon: Optional[str] = Field(None, description="Action taken (e.g., upgrade, downgrade, init, reiterate).")

class AnalistFiyatHedefi(BaseModel):
    """Represents analyst price target data."""
    guncel: Optional[float] = Field(None, description="Current stock price.")
    ortalama: Optional[float] = Field(None, description="Average analyst price target.")
    dusuk: Optional[float] = Field(None, description="Lowest analyst price target.")
    yuksek: Optional[float] = Field(None, description="Highest analyst price target.")
    analist_sayisi: Optional[int] = Field(None, description="Number of analysts providing targets.")

class TavsiyeOzeti(BaseModel):
    """Summary of analyst recommendations."""
    satin_al: int = Field(0, description="Number of Buy recommendations.")
    fazla_agirlik: int = Field(0, description="Number of Overweight recommendations.")
    tut: int = Field(0, description="Number of Hold recommendations.")
    dusuk_agirlik: int = Field(0, description="Number of Underweight recommendations.")
    sat: int = Field(0, description="Number of Sell recommendations.")

class AnalistVerileriSonucu(BaseModel):
    """The result of analyst data query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    fiyat_hedefleri: Optional[AnalistFiyatHedefi] = Field(None, description="Analyst price targets.")
    tavsiyeler: List[AnalistTavsiyesi] = Field(default_factory=list, description="List of analyst recommendations.")
    tavsiye_ozeti: Optional[TavsiyeOzeti] = Field(None, description="Summary of recommendations.")
    tavsiye_trendi: Optional[List[Dict[str, Any]]] = Field(None, description="Recommendation trend data over time.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Dividend and Corporate Actions Models ---
class Temettu(BaseModel):
    """Represents a single dividend payment."""
    tarih: datetime.datetime = Field(description="Dividend payment date.")
    miktar: float = Field(description="Dividend amount per share.")

class HisseBolunmesi(BaseModel):
    """Represents a stock split event."""
    tarih: datetime.datetime = Field(description="Stock split date.")
    oran: float = Field(description="Split ratio (e.g., 2.0 for 2:1 split).")

class KurumsalAksiyon(BaseModel):
    """Represents a corporate action (dividend or split)."""
    tarih: datetime.datetime = Field(description="Action date.")
    tip: str = Field(description="Type of action: 'Temettü' or 'Bölünme'.")
    deger: float = Field(description="Value (dividend amount or split ratio).")

class TemettuVeAksiyonlarSonucu(BaseModel):
    """The result of dividends and corporate actions query."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    temettuler: List[Temettu] = Field(default_factory=list, description="List of dividend payments.")
    bolunmeler: List[HisseBolunmesi] = Field(default_factory=list, description="List of stock splits.")
    tum_aksiyonlar: List[KurumsalAksiyon] = Field(default_factory=list, description="All corporate actions combined.")
    toplam_temettu_12ay: Optional[float] = Field(None, description="Total dividends paid in last 12 months.")
    son_temettu: Optional[Temettu] = Field(None, description="Most recent dividend payment.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Fast Info Models ---
class HizliBilgi(BaseModel):
    """Fast access to key company metrics without heavy data processing."""
    symbol: Optional[str] = Field(None, description="Stock ticker symbol.")
    long_name: Optional[str] = Field(None, description="Company full name.")
    currency: Optional[str] = Field(None, description="Currency of the stock.")
    exchange: Optional[str] = Field(None, description="Exchange where stock is traded.")
    
    # Price Info
    last_price: Optional[float] = Field(None, description="Current/last trading price.")
    previous_close: Optional[float] = Field(None, description="Previous day's closing price.")
    open_price: Optional[float] = Field(None, description="Today's opening price.")
    day_high: Optional[float] = Field(None, description="Today's highest price.")
    day_low: Optional[float] = Field(None, description="Today's lowest price.")
    
    # 52-week range
    fifty_two_week_high: Optional[float] = Field(None, description="52-week highest price.")
    fifty_two_week_low: Optional[float] = Field(None, description="52-week lowest price.")
    
    # Volume and Market Data
    volume: Optional[int] = Field(None, description="Today's trading volume.")
    average_volume: Optional[int] = Field(None, description="Average daily volume.")
    market_cap: Optional[float] = Field(None, description="Market capitalization.")
    shares_outstanding: Optional[float] = Field(None, description="Number of shares outstanding.")
    
    # Valuation Metrics
    pe_ratio: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio.")
    peg_ratio: Optional[float] = Field(None, description="Price/Earnings to Growth ratio.")
    price_to_book: Optional[float] = Field(None, description="Price-to-Book ratio.")
    
    # Financial Health
    debt_to_equity: Optional[float] = Field(None, description="Debt-to-Equity ratio.")
    return_on_equity: Optional[float] = Field(None, description="Return on Equity.")
    return_on_assets: Optional[float] = Field(None, description="Return on Assets.")
    
    # Dividend Info
    dividend_yield: Optional[float] = Field(None, description="Annual dividend yield.")
    payout_ratio: Optional[float] = Field(None, description="Dividend payout ratio.")
    
    # Growth Metrics
    earnings_growth: Optional[float] = Field(None, description="Earnings growth rate.")
    revenue_growth: Optional[float] = Field(None, description="Revenue growth rate.")
    
    # Risk Metrics
    beta: Optional[float] = Field(None, description="Beta coefficient (volatility vs market).")

class HizliBilgiSonucu(BaseModel):
    """The result of fast info query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    bilgiler: Optional[HizliBilgi] = Field(None, description="Fast info data.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Earnings Calendar Models ---
class KazancTarihi(BaseModel):
    """Represents a single earnings date entry."""
    tarih: datetime.datetime = Field(description="Earnings announcement date.")
    eps_tahmini: Optional[float] = Field(None, description="EPS estimate.")
    rapor_edilen_eps: Optional[float] = Field(None, description="Actual reported EPS.")
    surpriz_yuzdesi: Optional[float] = Field(None, description="Surprise percentage.")
    durum: str = Field(description="Status: 'gelecek', 'gecmis'")

class KazancTakvimi(BaseModel):
    """Earnings calendar summary from ticker.calendar."""
    gelecek_kazanc_tarihi: Optional[datetime.date] = Field(None, description="Next earnings date.")
    ex_temettu_tarihi: Optional[datetime.date] = Field(None, description="Ex-dividend date.")
    eps_tahmini_yuksek: Optional[float] = Field(None, description="EPS estimate high.")
    eps_tahmini_dusuk: Optional[float] = Field(None, description="EPS estimate low.")
    eps_tahmini_ortalama: Optional[float] = Field(None, description="EPS estimate average.")
    gelir_tahmini_yuksek: Optional[float] = Field(None, description="Revenue estimate high.")
    gelir_tahmini_dusuk: Optional[float] = Field(None, description="Revenue estimate low.")
    gelir_tahmini_ortalama: Optional[float] = Field(None, description="Revenue estimate average.")

class KazancBuyumeVerileri(BaseModel):
    """Earnings growth data from info."""
    yillik_kazanc_buyumesi: Optional[float] = Field(None, description="Annual earnings growth rate.")
    ceyreklik_kazanc_buyumesi: Optional[float] = Field(None, description="Quarterly earnings growth rate.")
    sonraki_kazanc_tarihi: Optional[datetime.datetime] = Field(None, description="Next earnings timestamp.")
    tarih_tahmini_mi: Optional[bool] = Field(None, description="Is the earnings date an estimate.")

class KazancTakvimSonucu(BaseModel):
    """The result of earnings calendar query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    kazanc_tarihleri: List[KazancTarihi] = Field(default_factory=list, description="List of earnings dates.")
    kazanc_takvimi: Optional[KazancTakvimi] = Field(None, description="Earnings calendar summary.")
    buyume_verileri: Optional[KazancBuyumeVerileri] = Field(None, description="Earnings growth data.")
    gelecek_kazanc_sayisi: int = Field(0, description="Number of upcoming earnings dates.")
    gecmis_kazanc_sayisi: int = Field(0, description="Number of historical earnings dates.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Technical Analysis Models ---
class HareketliOrtalama(BaseModel):
    """Moving averages data."""
    sma_5: Optional[float] = Field(None, description="5-day Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-day Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-day Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-day Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-day Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-day Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-day Exponential Moving Average.")

class TeknikIndiktorler(BaseModel):
    """Technical indicators calculated from price data."""
    rsi_14: Optional[float] = Field(None, description="14-day Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-day SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")
    stochastic_k: Optional[float] = Field(None, description="Stochastic %K.")
    stochastic_d: Optional[float] = Field(None, description="Stochastic %D.")

class HacimAnalizi(BaseModel):
    """Volume analysis metrics."""
    gunluk_hacim: Optional[int] = Field(None, description="Current day's trading volume.")
    ortalama_hacim_10gun: Optional[int] = Field(None, description="10-day average volume.")
    ortalama_hacim_30gun: Optional[int] = Field(None, description="30-day average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")

class FiyatAnalizi(BaseModel):
    """Price analysis and trends."""
    guncel_fiyat: Optional[float] = Field(None, description="Current stock price.")
    onceki_kapanis: Optional[float] = Field(None, description="Previous closing price.")
    degisim_miktari: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzdesi: Optional[float] = Field(None, description="Price change percentage.")
    gunluk_yuksek: Optional[float] = Field(None, description="Daily high price.")
    gunluk_dusuk: Optional[float] = Field(None, description="Daily low price.")
    yillik_yuksek: Optional[float] = Field(None, description="52-week high price.")
    yillik_dusuk: Optional[float] = Field(None, description="52-week low price.")
    yillik_yuksek_uzaklik: Optional[float] = Field(None, description="Distance from 52-week high (%).")
    yillik_dusuk_uzaklik: Optional[float] = Field(None, description="Distance from 52-week low (%).")

class TrendAnalizi(BaseModel):
    """Trend analysis based on moving averages."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-day SMA: 'ustunde', 'altinda'.")
    sma200_durumu: Optional[str] = Field(None, description="Position vs 200-day SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA50 > SMA200).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA50 < SMA200).")

class AnalistTavsiyeOzeti(BaseModel):
    """Summary of analyst recommendations from yfinance."""
    guclu_al: int = Field(0, description="Strong Buy recommendations count.")
    al: int = Field(0, description="Buy recommendations count.")
    tut: int = Field(0, description="Hold recommendations count.")
    sat: int = Field(0, description="Sell recommendations count.")
    guclu_sat: int = Field(0, description="Strong Sell recommendations count.")
    toplam_analist: int = Field(0, description="Total number of analysts.")
    ortalama_derece: Optional[float] = Field(None, description="Average recommendation score (1=Strong Buy, 5=Strong Sell).")
    ortalama_derece_aciklama: Optional[str] = Field(None, description="Average rating description.")

class TeknikAnalizSonucu(BaseModel):
    """Comprehensive technical analysis result."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    analiz_tarihi: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    
    # Price and trend analysis
    fiyat_analizi: Optional[FiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[TrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[HareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[TeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis
    hacim_analizi: Optional[HacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Analyst recommendations
    analist_tavsiyeleri: Optional[AnalistTavsiyeOzeti] = Field(None, description="Analyst recommendations summary.")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Sector Analysis Models ---
class SektorBilgisi(BaseModel):
    """Basic sector/industry information."""
    sektor_adi: Optional[str] = Field(None, description="Sector name.")
    sektor_kodu: Optional[str] = Field(None, description="Sector key/code.")
    endustri_adi: Optional[str] = Field(None, description="Industry name.")
    endustri_kodu: Optional[str] = Field(None, description="Industry key/code.")

class SirketSektorBilgisi(BaseModel):
    """Company's sector information with key metrics."""
    ticker_kodu: str = Field(description="Stock ticker code.")
    sirket_adi: Optional[str] = Field(None, description="Company name.")
    sektor_bilgisi: Optional[SektorBilgisi] = Field(None, description="Sector/industry classification.")
    
    # Financial metrics
    piyasa_degeri: Optional[float] = Field(None, description="Market capitalization.")
    pe_orani: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    pb_orani: Optional[float] = Field(None, description="Price-to-Book ratio.")
    roe: Optional[float] = Field(None, description="Return on Equity.")
    borclanma_orani: Optional[float] = Field(None, description="Debt-to-Equity ratio.")
    kar_marji: Optional[float] = Field(None, description="Profit margin.")
    
    # Performance metrics
    yillik_getiri: Optional[float] = Field(None, description="1-year return percentage.")
    volatilite: Optional[float] = Field(None, description="Annualized volatility percentage.")
    ortalama_hacim: Optional[float] = Field(None, description="Average daily volume.")

class SektorPerformansOzeti(BaseModel):
    """Sector performance summary statistics."""
    sektor_adi: str = Field(description="Sector name.")
    sirket_sayisi: int = Field(description="Number of companies in sector.")
    sirket_listesi: List[str] = Field(default_factory=list, description="List of ticker codes in sector.")
    
    # Financial metrics averages
    ortalama_pe: Optional[float] = Field(None, description="Average P/E ratio for sector.")
    ortalama_pb: Optional[float] = Field(None, description="Average P/B ratio for sector.")
    ortalama_roe: Optional[float] = Field(None, description="Average ROE for sector.")
    ortalama_borclanma: Optional[float] = Field(None, description="Average debt-to-equity for sector.")
    ortalama_kar_marji: Optional[float] = Field(None, description="Average profit margin for sector.")
    
    # Performance metrics
    ortalama_yillik_getiri: Optional[float] = Field(None, description="Average 1-year return for sector.")
    ortalama_volatilite: Optional[float] = Field(None, description="Average volatility for sector.")
    toplam_piyasa_degeri: Optional[float] = Field(None, description="Total market cap for sector.")
    
    # Range information
    en_yuksek_getiri: Optional[float] = Field(None, description="Highest return in sector.")
    en_dusuk_getiri: Optional[float] = Field(None, description="Lowest return in sector.")
    en_yuksek_pe: Optional[float] = Field(None, description="Highest P/E in sector.")
    en_dusuk_pe: Optional[float] = Field(None, description="Lowest P/E in sector.")

class SektorKarsilastirmaSonucu(BaseModel):
    """Complete sector analysis and comparison result."""
    analiz_tarihi: datetime.datetime = Field(description="Analysis timestamp.")
    toplam_sirket_sayisi: int = Field(description="Total number of companies analyzed.")
    sektor_sayisi: int = Field(description="Number of sectors found.")
    
    # Individual company data
    sirket_verileri: List[SirketSektorBilgisi] = Field(default_factory=list, description="Individual company sector data.")
    
    # Sector summaries
    sektor_ozetleri: List[SektorPerformansOzeti] = Field(default_factory=list, description="Sector performance summaries.")
    
    # Market overview
    en_iyi_performans_sektor: Optional[str] = Field(None, description="Best performing sector by average return.")
    en_dusuk_risk_sektor: Optional[str] = Field(None, description="Lowest risk sector by volatility.")
    en_buyuk_sektor: Optional[str] = Field(None, description="Largest sector by market cap.")
    
    # Overall market metrics
    genel_piyasa_degeri: Optional[float] = Field(None, description="Total market cap of analyzed companies.")
    genel_ortalama_getiri: Optional[float] = Field(None, description="Overall average return.")
    genel_ortalama_volatilite: Optional[float] = Field(None, description="Overall average volatility.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Stock Screening Models ---
class TaramaKriterleri(BaseModel):
    """Stock screening criteria for filtering."""
    # Valuation criteria
    min_pe_ratio: Optional[float] = Field(None, description="Minimum P/E ratio.")
    max_pe_ratio: Optional[float] = Field(None, description="Maximum P/E ratio.")
    min_pb_ratio: Optional[float] = Field(None, description="Minimum P/B ratio.")
    max_pb_ratio: Optional[float] = Field(None, description="Maximum P/B ratio.")
    
    # Market size criteria
    min_market_cap: Optional[float] = Field(None, description="Minimum market capitalization in TL.")
    max_market_cap: Optional[float] = Field(None, description="Maximum market capitalization in TL.")
    
    # Financial health criteria
    min_roe: Optional[float] = Field(None, description="Minimum Return on Equity (as decimal).")
    max_debt_to_equity: Optional[float] = Field(None, description="Maximum debt-to-equity ratio.")
    min_current_ratio: Optional[float] = Field(None, description="Minimum current ratio.")
    
    # Dividend criteria
    min_dividend_yield: Optional[float] = Field(None, description="Minimum dividend yield (as decimal).")
    max_payout_ratio: Optional[float] = Field(None, description="Maximum payout ratio (as decimal).")
    
    # Growth criteria
    min_revenue_growth: Optional[float] = Field(None, description="Minimum revenue growth (as decimal).")
    min_earnings_growth: Optional[float] = Field(None, description="Minimum earnings growth (as decimal).")
    
    # Risk criteria
    max_beta: Optional[float] = Field(None, description="Maximum beta coefficient.")
    
    # Price criteria
    min_price: Optional[float] = Field(None, description="Minimum stock price in TL.")
    max_price: Optional[float] = Field(None, description="Maximum stock price in TL.")
    
    # Volume criteria
    min_avg_volume: Optional[float] = Field(None, description="Minimum average daily volume.")
    
    # Sector filtering
    sectors: Optional[List[str]] = Field(None, description="List of sectors to include.")
    exclude_sectors: Optional[List[str]] = Field(None, description="List of sectors to exclude.")

class TaranmisHisse(BaseModel):
    """Individual stock result from screening."""
    ticker_kodu: str = Field(description="Stock ticker code.")
    sirket_adi: str = Field(description="Company name.")
    sehir: Optional[str] = Field(None, description="Company city.")
    sektor: Optional[str] = Field(None, description="Company sector.")
    endustri: Optional[str] = Field(None, description="Company industry.")
    
    # Price and market data
    guncel_fiyat: Optional[float] = Field(None, description="Current stock price.")
    piyasa_degeri: Optional[float] = Field(None, description="Market capitalization.")
    hacim: Optional[float] = Field(None, description="Current trading volume.")
    ortalama_hacim: Optional[float] = Field(None, description="Average daily volume.")
    
    # Valuation metrics
    pe_orani: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    pb_orani: Optional[float] = Field(None, description="Price-to-Book ratio.")
    peg_orani: Optional[float] = Field(None, description="Price-to-Earnings-Growth ratio.")
    
    # Financial health
    borclanma_orani: Optional[float] = Field(None, description="Debt-to-equity ratio.")
    roe: Optional[float] = Field(None, description="Return on Equity.")
    roa: Optional[float] = Field(None, description="Return on Assets.")
    cari_oran: Optional[float] = Field(None, description="Current ratio.")
    
    # Profitability
    kar_marji: Optional[float] = Field(None, description="Profit margin.")
    gelir_buyumesi: Optional[float] = Field(None, description="Revenue growth rate.")
    kazanc_buyumesi: Optional[float] = Field(None, description="Earnings growth rate.")
    
    # Dividend
    temettu_getirisi: Optional[float] = Field(None, description="Dividend yield.")
    odeme_orani: Optional[float] = Field(None, description="Payout ratio.")
    
    # Risk metrics
    beta: Optional[float] = Field(None, description="Beta coefficient.")
    volatilite: Optional[float] = Field(None, description="Price volatility.")
    
    # Performance
    yillik_getiri: Optional[float] = Field(None, description="1-year return percentage.")
    hafta_52_yuksek: Optional[float] = Field(None, description="52-week high price.")
    hafta_52_dusuk: Optional[float] = Field(None, description="52-week low price.")
    
    # Ranking scores
    deger_skoru: Optional[float] = Field(None, description="Value investing score (0-100).")
    kalite_skoru: Optional[float] = Field(None, description="Quality score (0-100).")
    buyume_skoru: Optional[float] = Field(None, description="Growth score (0-100).")
    genel_skor: Optional[float] = Field(None, description="Overall investment score (0-100).")

class TaramaSonucu(BaseModel):
    """Complete stock screening result."""
    tarama_tarihi: datetime.datetime = Field(description="Screening timestamp.")
    uygulanan_kriterler: TaramaKriterleri = Field(description="Applied screening criteria.")
    
    # Summary statistics
    toplam_sirket_sayisi: int = Field(description="Total number of companies screened.")
    kriter_uyan_sayisi: int = Field(description="Number of companies meeting criteria.")
    basari_orani: float = Field(description="Percentage of companies meeting criteria.")
    
    # Results
    bulunan_hisseler: List[TaranmisHisse] = Field(default_factory=list, description="List of stocks meeting criteria.")
    
    # Analysis summaries
    ortalama_pe: Optional[float] = Field(None, description="Average P/E ratio of results.")
    ortalama_pb: Optional[float] = Field(None, description="Average P/B ratio of results.")
    ortalama_roe: Optional[float] = Field(None, description="Average ROE of results.")
    ortalama_temettu: Optional[float] = Field(None, description="Average dividend yield of results.")
    toplam_piyasa_degeri: Optional[float] = Field(None, description="Total market cap of results.")
    
    # Sector breakdown
    sektor_dagilimi: Dict[str, int] = Field(default_factory=dict, description="Sector distribution of results.")
    
    # Top performers
    en_yuksek_pe: Optional[TaranmisHisse] = Field(None, description="Stock with highest P/E.")
    en_dusuk_pe: Optional[TaranmisHisse] = Field(None, description="Stock with lowest P/E.")
    en_yuksek_temettu: Optional[TaranmisHisse] = Field(None, description="Stock with highest dividend yield.")
    en_buyuk_sirket: Optional[TaranmisHisse] = Field(None, description="Largest company by market cap.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- TEFAS Fund Models ---
class FonBilgisi(BaseModel):
    """Basic fund information from TEFAS."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    fon_adi: str = Field(description="Full name of the fund.")
    fon_turu: Optional[str] = Field(None, description="Fund type (e.g., HSF, DEF, HBF).")
    kurulus: Optional[str] = Field(None, description="Fund founder/issuer company.")
    yonetici: Optional[str] = Field(None, description="Fund management company.")
    risk_degeri: Optional[int] = Field(None, description="Risk score (1-7, where 7 is highest risk).")
    tarih: Optional[str] = Field(None, description="Data date.")
    
    # Performance metrics from advanced API
    getiri_1_ay: Optional[float] = Field(None, description="1-month return (%).")
    getiri_3_ay: Optional[float] = Field(None, description="3-month return (%).")
    getiri_6_ay: Optional[float] = Field(None, description="6-month return (%).")
    getiri_1_yil: Optional[float] = Field(None, description="1-year return (%).")
    getiri_yil_basi: Optional[float] = Field(None, description="Year-to-date return (%).")
    getiri_3_yil: Optional[float] = Field(None, description="3-year return (%).")
    getiri_5_yil: Optional[float] = Field(None, description="5-year return (%).")
    api_source: Optional[str] = Field(None, description="Source API used for data.")

class FonAramaSonucu(BaseModel):
    """Result of fund search operation."""
    arama_terimi: str = Field(description="Search term used.")
    sonuclar: List[FonBilgisi] = Field(description="List of funds matching search criteria.")
    sonuc_sayisi: int = Field(description="Number of results found.")
    
    # Advanced search fields
    toplam_bulunan: Optional[int] = Field(None, description="Total number of funds found before limit.")
    kaynak: Optional[str] = Field(None, description="Data source used for search.")
    fund_type: Optional[str] = Field(None, description="Fund type filter applied.")
    fund_category: Optional[str] = Field(None, description="Fund category filter applied.")
    category_code: Optional[str] = Field(None, description="TEFAS category code used.")
    tarih: Optional[str] = Field(None, description="Search date.")
    performans_dahil: Optional[bool] = Field(None, description="Whether performance data is included.")
    
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class FonProfil(BaseModel):
    """Fund profile and technical information from fundProfile."""
    isin_kod: Optional[str] = Field(None, description="ISIN code (ISINKOD).")
    son_islem_saati: Optional[str] = Field(None, description="Last trading time (SONISSAAT).")
    min_alis: Optional[float] = Field(None, description="Minimum purchase amount (MINALIS).")
    min_satis: Optional[float] = Field(None, description="Minimum sale amount (MINSATIS).")
    max_alis: Optional[float] = Field(None, description="Maximum purchase amount (MAXALIS).")
    max_satis: Optional[float] = Field(None, description="Maximum sale amount (MAXSATIS).")
    kap_link: Optional[str] = Field(None, description="KAP disclosure link (KAPLINK).")
    tefas_durum: Optional[str] = Field(None, description="TEFAS trading status (TEFASDURUM).")
    cikis_komisyonu: Optional[float] = Field(None, description="Exit commission (CIKISKOMISYONU).")
    giris_komisyonu: Optional[float] = Field(None, description="Entry commission (GIRISKOMISYONU).")
    basis_saat: Optional[str] = Field(None, description="Pricing time (BASISSAAT).")
    fon_satis_valor: Optional[int] = Field(None, description="Fund sale valor (FONSATISVALOR).")
    fon_geri_alis_valor: Optional[int] = Field(None, description="Fund redemption valor (FONGERIALISVALOR).")
    faiz_icerigi: Optional[str] = Field(None, description="Interest content (FAIZICERIGI).")

class FonPortfoyDagilimi(BaseModel):
    """Fund portfolio allocation breakdown from fundAllocation."""
    kiymet_tip: str = Field(description="Asset type (KIYMETTIP).")
    portfoy_orani: float = Field(description="Portfolio percentage (PORTFOYORANI).")

class FonFiyatGecmisi(BaseModel):
    """Historical price data point with category ranking."""
    tarih: str = Field(description="Date (YYYY-MM-DD format).")
    fiyat: float = Field(description="Fund price on this date.")
    kategori_derece: Optional[int] = Field(None, description="Category ranking (KATEGORIDERECE).")
    kategori_fon_sayisi: Optional[int] = Field(None, description="Number of funds in category (KATEGORIFONSAY).")

class FonDetayBilgisi(BaseModel):
    """Comprehensive fund information including all available data from GetAllFundAnalyzeData API."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    fon_adi: str = Field(description="Full name of the fund.")
    tarih: str = Field(description="Data date.")
    fiyat: float = Field(description="Current fund price/NAV.")
    tedavuldeki_pay_sayisi: float = Field(description="Outstanding shares.")
    toplam_deger: float = Field(description="Total fund value (AUM).")
    birim_pay_degeri: float = Field(description="Net asset value per share.")
    yatirimci_sayisi: int = Field(description="Number of investors.")
    kurulus: str = Field(description="Fund founder/issuer.")
    yonetici: str = Field(description="Fund manager.")
    fon_turu: str = Field(description="Fund type.")
    risk_degeri: int = Field(description="Risk score (1-7).")
    
    # Performance metrics
    getiri_1_ay: Optional[float] = Field(None, description="1-month return (%).")
    getiri_3_ay: Optional[float] = Field(None, description="3-month return (%).")
    getiri_6_ay: Optional[float] = Field(None, description="6-month return (%).")
    getiri_yil_basi: Optional[float] = Field(None, description="Year-to-date return (%).")
    getiri_1_yil: Optional[float] = Field(None, description="1-year return (%).")
    getiri_3_yil: Optional[float] = Field(None, description="3-year return (%).")
    getiri_5_yil: Optional[float] = Field(None, description="5-year return (%).")
    
    # Risk metrics
    standart_sapma: Optional[float] = Field(None, description="Standard deviation.")
    sharpe_orani: Optional[float] = Field(None, description="Sharpe ratio.")
    alpha: Optional[float] = Field(None, description="Alpha coefficient.")
    beta: Optional[float] = Field(None, description="Beta coefficient.")
    tracking_error: Optional[float] = Field(None, description="Tracking error.")
    
    # Enhanced metrics from widget approach
    gunluk_getiri: Optional[float] = Field(None, description="Daily return percentage.")
    haftalik_getiri: Optional[float] = Field(None, description="Weekly return percentage.")
    gunluk_degisim_miktar: Optional[float] = Field(None, description="Daily change amount in fund price.")
    onceki_gun_fiyat: Optional[float] = Field(None, description="Previous day's closing price.")
    
    # New comprehensive data from API
    fon_kategori: Optional[str] = Field(None, description="Fund category (FONKATEGORI).")
    kategori_derece: Optional[str] = Field(None, description="Ranking in category (KATEGORIDERECE).")
    kategori_fon_sayisi: Optional[int] = Field(None, description="Total funds in category (KATEGORIFONSAY).")
    pazar_payi: Optional[float] = Field(None, description="Market share percentage (PAZARPAYI).")
    kategori_derece_birlesik: Optional[str] = Field(None, description="Combined ranking display (KATEGORIDERECEBIRLESIK).")
    
    # Fund profile information
    fon_profil: Optional[FonProfil] = Field(None, description="Technical fund profile data.")
    
    # Portfolio allocation
    portfoy_dagilimi: Optional[List[FonPortfoyDagilimi]] = Field(None, description="Portfolio allocation breakdown by asset type.")
    
    # Price history metadata
    fiyat_gecmisi_1ay_sayisi: Optional[int] = Field(None, description="Number of price points available for last month.")
    fiyat_gecmisi_1ay_mevcut: Optional[bool] = Field(None, description="Whether 1-month price history is available.")
    
    # Optional detailed price history (on request)
    fiyat_gecmisi_1hafta: Optional[List[FonFiyatGecmisi]] = Field(None, description="1-week price history (fundPrices1H) - optional.")
    fiyat_gecmisi_1ay: Optional[List[FonFiyatGecmisi]] = Field(None, description="1-month price history (fundPrices1A) - optional.")
    fiyat_gecmisi_3ay: Optional[List[FonFiyatGecmisi]] = Field(None, description="3-month price history (fundPrices3A) - optional.")
    fiyat_gecmisi_6ay: Optional[List[FonFiyatGecmisi]] = Field(None, description="6-month price history (fundPrices6A) - optional.")
    
    # API and data quality information
    api_source: Optional[str] = Field(None, description="Source API used for data retrieval.")
    veri_kalitesi: Optional[Dict[str, Any]] = Field(None, description="Data quality metrics and completeness scores.")
    
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class FonFiyatNoktasi(BaseModel):
    """Single price point in fund history from TEFAS BindHistoryInfo API."""
    tarih: str = Field(description="Date of the price point (YYYY-MM-DD format).")
    fiyat: float = Field(description="Fund NAV on this date.")
    tedavuldeki_pay_sayisi: float = Field(description="Outstanding shares (TEDPAYSAYISI).")
    toplam_deger: float = Field(description="Total portfolio value (PORTFOYBUYUKLUK).")
    yatirimci_sayisi: int = Field(description="Number of investors (KISISAYISI).")
    fon_unvan: Optional[str] = Field(None, description="Full fund name (FONUNVAN).")
    borsa_bulten_fiyat: Optional[str] = Field(None, description="Stock exchange bulletin price (BORSABULTENFIYAT).")

class FonPerformansSonucu(BaseModel):
    """Fund performance history result from official TEFAS BindHistoryInfo API."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    baslangic_tarihi: str = Field(description="Start date of the period.")
    bitis_tarihi: str = Field(description="End date of the period.")
    fiyat_geçmisi: List[FonFiyatNoktasi] = Field(description="Historical price data with timestamps.")
    toplam_getiri: Optional[float] = Field(None, description="Total return for the period (%).")
    yillik_getiri: Optional[float] = Field(None, description="Annualized return (%).")
    veri_sayisi: int = Field(description="Number of data points.")
    kaynak: Optional[str] = Field(None, description="Data source API used.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class PortfoyVarlik(BaseModel):
    """Single asset in fund portfolio."""
    varlik_turu: str = Field(description="Asset type (e.g., Hisse Senedi, Tahvil).")
    alt_varlik_turu: str = Field(description="Sub-asset type.")
    tutar: float = Field(description="Amount in TRY.")
    oran: float = Field(description="Percentage of portfolio.")
    detay: str = Field(description="Additional details.")

class VarlikGrubu(BaseModel):
    """Grouped assets by type."""
    tutar: float = Field(description="Total amount for this asset type.")
    oran: float = Field(description="Total percentage for this asset type.")
    alt_kalemler: List[PortfoyVarlik] = Field(description="Individual items in this group.")

class PortfoyTarihselVeri(BaseModel):
    """Single date's portfolio allocation data from TEFAS BindHistoryAllocation API."""
    tarih: str = Field(description="Date of the allocation data (YYYY-MM-DD format).")
    fon_kodu: str = Field(description="TEFAS fund code.")
    fon_unvan: str = Field(description="Full fund name.")
    portfoy_dagilimi: Dict[str, float] = Field(description="Asset allocation percentages by category.")
    bil_fiyat: str = Field(description="Pricing information.")

class FonPortfoySonucu(BaseModel):
    """Fund portfolio allocation history result from official TEFAS BindHistoryAllocation API."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    baslangic_tarihi: str = Field(description="Start date of the period.")
    bitis_tarihi: str = Field(description="End date of the period.")
    portfoy_geçmisi: List[PortfoyTarihselVeri] = Field(description="Historical allocation data over time.")
    son_portfoy_dagilimi: Dict[str, float] = Field(description="Latest portfolio allocation percentages.")
    veri_sayisi: int = Field(description="Number of data points.")
    kaynak: Optional[str] = Field(None, description="Data source API used.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class FonKarsilastirmaOgesi(BaseModel):
    """Single fund in comparison."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    fon_adi: str = Field(description="Fund name.")
    fon_turu: str = Field(description="Fund type.")
    risk_degeri: int = Field(description="Risk score.")
    fiyat: float = Field(description="Current NAV.")
    getiri_1_ay: float = Field(description="1-month return.")
    getiri_3_ay: float = Field(description="3-month return.")
    getiri_1_yil: float = Field(description="1-year return.")
    sharpe_orani: float = Field(description="Sharpe ratio.")
    standart_sapma: float = Field(description="Standard deviation.")
    toplam_deger: float = Field(description="Total AUM.")
    yatirimci_sayisi: int = Field(description="Number of investors.")
    getiri_siralamasi: Optional[int] = Field(None, description="Ranking by return.")
    risk_ayarli_getiri_siralamasi: Optional[int] = Field(None, description="Ranking by risk-adjusted return.")
    buyukluk_siralamasi: Optional[int] = Field(None, description="Ranking by size.")
    
    # Enhanced fields from widget approach
    gunluk_getiri: Optional[float] = Field(None, description="Daily return percentage.")
    gunluk_degisim_miktar: Optional[float] = Field(None, description="Daily change amount.")
    onceki_gun_fiyat: Optional[float] = Field(None, description="Previous day's price.")
    veri_kalitesi_skoru: Optional[float] = Field(None, description="Data completeness score (0.0-1.0).")
    api_source: Optional[str] = Field(None, description="Source API used for data.")

class FonKarsilastirmaSonucu(BaseModel):
    """Fund comparison result."""
    karsilastirilan_fonlar: List[str] = Field(description="List of compared fund codes.")
    karsilastirma_verileri: List[FonKarsilastirmaOgesi] = Field(description="Comparison data for each fund.")
    fon_sayisi: int = Field(description="Number of funds compared.")
    tarih: str = Field(description="Comparison date.")
    
    # Enhanced summary statistics from widget approach
    basari_orani: Optional[float] = Field(None, description="Success rate of data retrieval (0.0-1.0).")
    basarili_fon_sayisi: Optional[int] = Field(None, description="Number of funds with successful data retrieval.")
    basarisiz_fon_sayisi: Optional[int] = Field(None, description="Number of funds with failed data retrieval.")
    toplam_fon_degeri: Optional[float] = Field(None, description="Total value of all compared funds.")
    ortalama_gunluk_getiri: Optional[float] = Field(None, description="Average daily return of compared funds.")
    veri_kalitesi_ozeti: Optional[Dict[str, Any]] = Field(None, description="Summary of data quality metrics.")
    
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class FonTaramaKriterleri(BaseModel):
    """Fund screening criteria."""
    fund_type: Optional[str] = Field(None, description="Fund type filter (e.g., HSF, DEF, HBF).")
    min_return_1y: Optional[float] = Field(None, description="Minimum 1-year return (%).")
    max_risk: Optional[int] = Field(None, description="Maximum risk score (1-7).")
    min_sharpe: Optional[float] = Field(None, description="Minimum Sharpe ratio.")
    min_size: Optional[float] = Field(None, description="Minimum fund size (TRY).")
    founder: Optional[str] = Field(None, description="Specific founder/company name.")

class TaranmisFon(BaseModel):
    """Screened fund result."""
    fon_kodu: str = Field(description="TEFAS fund code.")
    fon_adi: str = Field(description="Fund name.")
    fon_turu: str = Field(description="Fund type.")
    kurulus: str = Field(description="Fund founder.")
    risk_degeri: int = Field(description="Risk score.")
    getiri_1_yil: float = Field(description="1-year return (%).")
    sharpe_orani: float = Field(description="Sharpe ratio.")
    toplam_deger: float = Field(description="Total AUM.")
    fiyat: float = Field(description="Current NAV.")

class FonTaramaSonucu(BaseModel):
    """Fund screening result."""
    tarama_kriterleri: FonTaramaKriterleri = Field(description="Criteria used for screening.")
    bulunan_fonlar: List[TaranmisFon] = Field(description="Funds matching criteria.")
    toplam_sonuc: int = Field(description="Total number of matching funds.")
    tarih: str = Field(description="Screening date.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# Pre-defined screening strategies
class DegerYatirimiKriterleri(BaseModel):
    """Value investing criteria preset."""
    max_pe_ratio: float = Field(15.0, description="Maximum P/E ratio for value stocks.")
    max_pb_ratio: float = Field(2.0, description="Maximum P/B ratio for value stocks.")
    min_roe: float = Field(0.05, description="Minimum ROE (5%).")
    max_debt_to_equity: float = Field(1.0, description="Maximum debt-to-equity ratio.")
    min_market_cap: float = Field(1_000_000_000, description="Minimum market cap (1B TL).")

class TemettuYatirimiKriterleri(BaseModel):
    """Dividend investing criteria preset."""
    min_dividend_yield: float = Field(0.03, description="Minimum dividend yield (3%).")
    max_payout_ratio: float = Field(0.8, description="Maximum payout ratio (80%).")
    min_roe: float = Field(0.08, description="Minimum ROE (8%).")
    max_debt_to_equity: float = Field(0.6, description="Maximum debt-to-equity ratio.")
    min_market_cap: float = Field(5_000_000_000, description="Minimum market cap (5B TL).")

class BuyumeYatirimiKriterleri(BaseModel):
    """Growth investing criteria preset."""
    min_revenue_growth: float = Field(0.15, description="Minimum revenue growth (15%).")
    min_earnings_growth: float = Field(0.10, description="Minimum earnings growth (10%).")
    max_pe_ratio: float = Field(30.0, description="Maximum P/E ratio for growth stocks.")
    min_roe: float = Field(0.15, description="Minimum ROE (15%).")
    min_market_cap: float = Field(2_000_000_000, description="Minimum market cap (2B TL).")

class MuhafazakarYatirimiKriterleri(BaseModel):
    """Conservative investing criteria preset."""
    max_beta: float = Field(0.8, description="Maximum beta for defensive stocks.")
    max_debt_to_equity: float = Field(0.3, description="Maximum debt-to-equity ratio.")
    min_dividend_yield: float = Field(0.02, description="Minimum dividend yield (2%).")
    min_current_ratio: float = Field(1.5, description="Minimum current ratio.")
    min_market_cap: float = Field(10_000_000_000, description="Minimum market cap (10B TL).")

# --- Mynet Provider Models ---

class HisseDetay(BaseModel):
    """Detailed stock information from Mynet Finans."""
    mynet_url: Optional[str] = Field(None, description="Mynet page URL.")
    ilk_islem_tarihi: Optional[str] = Field(None, description="First trading date.")
    son_islem_fiyati: Optional[float] = Field(None, description="Last trading price.")
    alis: Optional[float] = Field(None, description="Bid price.")
    satis: Optional[float] = Field(None, description="Ask price.")
    gunluk_degisim: Optional[float] = Field(None, description="Daily change amount.")
    gunluk_degisim_yuzde: Optional[float] = Field(None, description="Daily change percentage.")
    gunluk_hacim_lot: Optional[int] = Field(None, description="Daily volume in lots.")
    gunluk_hacim_tl: Optional[float] = Field(None, description="Daily volume in TL.")
    gunluk_ortalama: Optional[float] = Field(None, description="Daily average price.")
    gun_ici_en_dusuk: Optional[float] = Field(None, description="Intraday low.")
    gun_ici_en_yuksek: Optional[float] = Field(None, description="Intraday high.")
    acilis_fiyati: Optional[float] = Field(None, description="Opening price.")
    fiyat_adimi: Optional[float] = Field(None, description="Price step.")
    onceki_kapanis_fiyati: Optional[float] = Field(None, description="Previous closing price.")
    alt_marj_fiyati: Optional[float] = Field(None, description="Lower price limit.")
    ust_marj_fiyati: Optional[float] = Field(None, description="Upper price limit.")
    haftalik_en_dusuk: Optional[float] = Field(None, description="Weekly low.")
    haftalik_en_yuksek: Optional[float] = Field(None, description="Weekly high.")
    aylik_en_dusuk: Optional[float] = Field(None, description="Monthly low.")
    aylik_en_yuksek: Optional[float] = Field(None, description="Monthly high.")
    yillik_en_dusuk: Optional[float] = Field(None, description="Yearly low.")
    yillik_en_yuksek: Optional[float] = Field(None, description="Yearly high.")
    baz_fiyat: Optional[float] = Field(None, description="Base price.")

class Yonetici(BaseModel):
    """Company executive information."""
    isim: str = Field(description="Executive name.")

class Ortak(BaseModel):
    """Shareholder information."""
    isim: str = Field(description="Shareholder name.")
    sermaye_tutari: Optional[str] = Field(None, description="Capital amount.")
    sermaye_orani: Optional[str] = Field(None, description="Capital percentage.")

class Istirak(BaseModel):
    """Subsidiary/affiliate information."""
    isim: str = Field(description="Subsidiary name.")
    sermaye: Optional[str] = Field(None, description="Capital amount.")
    pay_orani: Optional[str] = Field(None, description="Ownership percentage.")

class PiyasaDegeri(BaseModel):
    """Market value and currency position information."""
    doviz_varliklari_tl: Optional[str] = Field(None, description="FX assets in TL.")
    doviz_yukumlulukleri_tl: Optional[str] = Field(None, description="FX liabilities in TL.")
    net_doviz_pozisyonu_tl: Optional[str] = Field(None, description="Net FX position in TL.")
    turev_enstrumanlar_net_pozisyonu_tl: Optional[str] = Field(None, description="Derivative instruments net position in TL.")

class SirketGenelBilgileri(BaseModel):
    """General company information from Mynet."""
    bist_kodu: Optional[str] = Field(None, description="BIST ticker code.")
    halka_acilma_tarihi: Optional[str] = Field(None, description="IPO date.")
    kurulus_tarihi: Optional[str] = Field(None, description="Establishment date.")
    faaliyet_alani: Optional[str] = Field(None, description="Business field.")
    sermaye: Optional[str] = Field(None, description="Capital.")
    genel_mudur: Optional[str] = Field(None, description="General manager.")
    personel_sayisi: Optional[int] = Field(None, description="Number of employees.")
    web_adresi: Optional[str] = Field(None, description="Website URL.")
    sirket_unvani: Optional[str] = Field(None, description="Company title.")
    yonetim_kurulu: Optional[List[Yonetici]] = Field(None, description="Board of directors.")
    istirakler: Optional[List[Istirak]] = Field(None, description="Subsidiaries.")
    ortaklar: Optional[List[Ortak]] = Field(None, description="Shareholders.")
    piyasa_degeri: Optional[PiyasaDegeri] = Field(None, description="Market value info.")

class BilancoKalemi(BaseModel):
    """Balance sheet line item."""
    kalem: str = Field(description="Line item name.")
    deger: str = Field(description="Line item value.")

class KarZararKalemi(BaseModel):
    """Income statement line item."""
    kalem: str = Field(description="Line item name.")
    deger: str = Field(description="Line item value.")

class MevcutDonem(BaseModel):
    """Available financial period."""
    yil: int = Field(description="Year.")
    donem: int = Field(description="Period (quarter).")
    aciklama: str = Field(description="Period description.")

class KapHaberi(BaseModel):
    """Individual KAP news item."""
    baslik: str = Field(description="News headline.")
    tarih: str = Field(description="News date and time.")
    url: Optional[str] = Field(None, description="Full URL to news detail.")
    haber_id: Optional[str] = Field(None, description="Unique news ID.")
    title_attr: Optional[str] = Field(None, description="Full title attribute.")

class KapHaberleriSonucu(BaseModel):
    """Result of KAP news query."""
    ticker_kodu: str = Field(description="Stock ticker code.")
    kap_haberleri: List[KapHaberi] = Field(default_factory=list, description="List of KAP news items.")
    toplam_haber: int = Field(0, description="Total number of news items returned.")
    kaynak_url: Optional[str] = Field(None, description="Source URL from Mynet.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KapHaberDetayi(BaseModel):
    """Detailed KAP news content with automatic pagination for large documents."""
    baslik: str = Field(description="News headline.")
    belge_turu: Optional[str] = Field(None, description="Document type (e.g., Şirket Genel Bilgi Formu).")
    markdown_icerik: str = Field(description="News content formatted as markdown. For large documents (>5000 chars), this contains the first page.")
    toplam_karakter: int = Field(description="Total character count of the full document.")
    sayfa_numarasi: int = Field(1, description="Current page number (1-based).")
    toplam_sayfa: int = Field(description="Total number of pages.")
    sonraki_sayfa_var: bool = Field(description="Whether there is a next page available.")
    sayfa_boyutu: int = Field(5000, description="Characters per page.")
    haber_url: Optional[str] = Field(None, description="Original news URL for pagination.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KapHaberSayfasi(BaseModel):
    """Paginated KAP news content page."""
    baslik: str = Field(description="News headline.")
    sayfa_icerik: str = Field(description="Markdown content for this specific page.")
    sayfa_numarasi: int = Field(description="Current page number (1-based).")
    toplam_sayfa: int = Field(description="Total number of pages.")
    sonraki_sayfa_var: bool = Field(description="Whether there is a next page available.")
    onceki_sayfa_var: bool = Field(description="Whether there is a previous page available.")
    toplam_karakter: int = Field(description="Total character count of the full document.")
    sayfa_boyutu: int = Field(5000, description="Characters per page.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Fon Mevzuat Models ---
class FonMevzuatSonucu(BaseModel):
    """Yatırım fonları mevzuat rehber içeriği."""
    mevzuat_adi: str = Field(description="Mevzuat dokümanının adı.")
    icerik: str = Field(description="Fon mevzuat rehberinin tam içeriği markdown formatında.")
    karakter_sayisi: int = Field(description="İçeriğin toplam karakter sayısı.")
    kaynak_dosya: str = Field(description="Kaynak dosya adı.")
    guncelleme_tarihi: Optional[str] = Field(None, description="Dosyanın son güncellenme tarihi.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- BtcTurk Kripto Models ---

class TradingPair(BaseModel):
    """Trading pair information from BtcTurk."""
    id: Optional[int] = Field(None, description="Trading pair ID.")
    name: str = Field(description="Trading pair name (e.g., BTCTRY).")
    name_normalized: Optional[str] = Field(None, description="Normalized trading pair name.")
    status: str = Field(description="Trading pair status.")
    numerator: str = Field(description="Base currency symbol.")
    denominator: str = Field(description="Quote currency symbol.")
    numerator_scale: Optional[int] = Field(None, description="Base currency decimal precision.")
    denominator_scale: Optional[int] = Field(None, description="Quote currency decimal precision.")
    has_fraction: Optional[bool] = Field(None, description="Whether fractional trading is supported.")
    filters: Optional[List[Dict[str, Any]]] = Field(None, description="Trading filters and limits.")
    order_methods: Optional[List[str]] = Field(None, description="Supported order methods.")
    display_format: Optional[str] = Field(None, description="Display format.")
    maximum_limit_order_price: Optional[float] = Field(None, description="Maximum limit order price.")
    minimum_limit_order_price: Optional[float] = Field(None, description="Minimum limit order price.")

class Currency(BaseModel):
    """Currency information from BtcTurk."""
    id: Optional[int] = Field(None, description="Currency ID.")
    symbol: str = Field(description="Currency symbol (e.g., BTC, TRY).")
    min_withdrawal: Optional[float] = Field(None, description="Minimum withdrawal amount.")
    min_deposit: Optional[float] = Field(None, description="Minimum deposit amount.")
    precision: Optional[int] = Field(None, description="Currency precision.")
    address: Optional[Dict[str, Any]] = Field(None, description="Address information.")
    currency_type: Optional[str] = Field(None, description="Currency type (FIAT or CRYPTO).")
    tag: Optional[Dict[str, Any]] = Field(None, description="Tag information.")
    color: Optional[str] = Field(None, description="Currency color code.")
    name: Optional[str] = Field(None, description="Full currency name.")
    is_address_renewable: Optional[bool] = Field(None, description="Whether address is renewable.")
    get_auto_address_disabled: Optional[bool] = Field(None, description="Whether auto address generation is disabled.")
    is_partial_withdrawal_enabled: Optional[bool] = Field(None, description="Whether partial withdrawals are enabled.")

class CurrencyOperationBlock(BaseModel):
    """Currency operation block status."""
    currency_symbol: str = Field(description="Currency symbol.")
    withdrawal_disabled: Optional[bool] = Field(None, description="Whether withdrawals are disabled.")
    deposit_disabled: Optional[bool] = Field(None, description="Whether deposits are disabled.")

class KriptoExchangeInfoSonucu(BaseModel):
    """Exchange information result from BtcTurk."""
    trading_pairs: List[TradingPair] = Field(description="List of all trading pairs.")
    currencies: List[Currency] = Field(description="List of all currencies.")
    currency_operation_blocks: List[CurrencyOperationBlock] = Field(description="Currency operation status.")
    toplam_cift: int = Field(description="Total number of trading pairs.")
    toplam_para_birimi: int = Field(description="Total number of currencies.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoTicker(BaseModel):
    """Ticker data for a trading pair."""
    pair: str = Field(description="Trading pair symbol.")
    pair_normalized: Optional[str] = Field(None, description="Normalized pair symbol.")
    timestamp: Optional[int] = Field(None, description="Data timestamp.")
    last: float = Field(description="Last trade price.")
    high: float = Field(description="24h highest price.")
    low: float = Field(description="24h lowest price.")
    bid: float = Field(description="Best bid price.")
    ask: float = Field(description="Best ask price.")
    open: float = Field(description="24h opening price.")
    volume: float = Field(description="24h trading volume.")
    average: float = Field(description="24h average price.")
    daily: float = Field(description="24h price change amount.")
    daily_percent: float = Field(description="24h price change percentage.")
    denominator_symbol: Optional[str] = Field(None, description="Quote currency symbol.")
    numerator_symbol: Optional[str] = Field(None, description="Base currency symbol.")

class KriptoTickerSonucu(BaseModel):
    """Ticker data result."""
    tickers: List[KriptoTicker] = Field(description="List of ticker data.")
    toplam_cift: int = Field(description="Total number of trading pairs.")
    pair_symbol: Optional[str] = Field(None, description="Specific pair symbol if requested.")
    quote_currency: Optional[str] = Field(None, description="Quote currency if requested.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoOrderbook(BaseModel):
    """Order book data for a trading pair."""
    timestamp: Optional[int] = Field(None, description="Data timestamp.")
    bids: List[tuple] = Field(description="List of bid orders (price, quantity).")
    asks: List[tuple] = Field(description="List of ask orders (price, quantity).")
    bid_count: int = Field(description="Number of bid orders.")
    ask_count: int = Field(description="Number of ask orders.")

class KriptoOrderbookSonucu(BaseModel):
    """Order book result."""
    pair_symbol: str = Field(description="Trading pair symbol.")
    orderbook: Optional[KriptoOrderbook] = Field(None, description="Order book data.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoTrade(BaseModel):
    """Individual trade data."""
    pair: str = Field(description="Trading pair symbol.")
    pair_normalized: Optional[str] = Field(None, description="Normalized pair symbol.")
    numerator: Optional[str] = Field(None, description="Base currency.")
    denominator: Optional[str] = Field(None, description="Quote currency.")
    date: Optional[int] = Field(None, description="Trade timestamp.")
    tid: Optional[str] = Field(None, description="Trade ID.")
    price: float = Field(description="Trade price.")
    amount: float = Field(description="Trade amount.")

class KriptoTradesSonucu(BaseModel):
    """Recent trades result."""
    pair_symbol: str = Field(description="Trading pair symbol.")
    trades: List[KriptoTrade] = Field(description="List of recent trades.")
    toplam_islem: int = Field(description="Total number of trades.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoOHLC(BaseModel):
    """OHLC data for a time period."""
    pair: Optional[str] = Field(None, description="Trading pair symbol.")
    time: Optional[int] = Field(None, description="Period timestamp (Unix timestamp).")
    formatted_time: Optional[str] = Field(None, description="Human-readable time in Turkey timezone (YYYY-MM-DD HH:MM:SS).")
    open: float = Field(description="Opening price.")
    high: float = Field(description="Highest price.")
    low: float = Field(description="Lowest price.")
    close: float = Field(description="Closing price.")
    volume: float = Field(description="Trading volume.")
    total: float = Field(description="Total trade value.")
    average: float = Field(description="Average price.")
    daily_change_amount: float = Field(description="Daily change amount.")
    daily_change_percentage: float = Field(description="Daily change percentage.")

class KriptoOHLCSonucu(BaseModel):
    """OHLC data result."""
    pair: str = Field(description="Trading pair symbol.")
    ohlc_data: List[KriptoOHLC] = Field(description="List of OHLC data.")
    toplam_veri: int = Field(description="Total number of data points.")
    from_time: Optional[int] = Field(None, description="Start time filter.")
    to_time: Optional[int] = Field(None, description="End time filter.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoKline(BaseModel):
    """Kline (candlestick) data."""
    timestamp: int = Field(description="Candlestick timestamp (Unix timestamp).")
    formatted_time: Optional[str] = Field(None, description="Human-readable time in Turkey timezone (YYYY-MM-DD HH:MM:SS).")
    open: float = Field(description="Opening price.")
    high: float = Field(description="Highest price.")
    low: float = Field(description="Lowest price.")
    close: float = Field(description="Closing price.")
    volume: float = Field(description="Trading volume.")

class KriptoKlineSonucu(BaseModel):
    """Kline data result."""
    symbol: str = Field(description="Trading symbol.")
    resolution: str = Field(description="Candlestick resolution.")
    klines: List[KriptoKline] = Field(description="List of kline data.")
    toplam_veri: int = Field(description="Total number of data points.")
    from_time: Optional[int] = Field(None, description="Start time.")
    to_time: Optional[int] = Field(None, description="End time.")
    status: str = Field(description="API response status.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Crypto Technical Analysis Models ---
class KriptoHareketliOrtalama(BaseModel):
    """Crypto moving averages data."""
    sma_5: Optional[float] = Field(None, description="5-period Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-period Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-period Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-period Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-period Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-period Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-period Exponential Moving Average.")

class KriptoTeknikIndiktorler(BaseModel):
    """Crypto technical indicators calculated from price data."""
    rsi_14: Optional[float] = Field(None, description="14-period Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-period SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")
    stochastic_k: Optional[float] = Field(None, description="Stochastic %K.")
    stochastic_d: Optional[float] = Field(None, description="Stochastic %D.")

class KriptoHacimAnalizi(BaseModel):
    """Crypto volume analysis metrics (24/7 market considerations)."""
    guncel_hacim: Optional[float] = Field(None, description="Current period's trading volume.")
    ortalama_hacim_10period: Optional[float] = Field(None, description="10-period average volume.")
    ortalama_hacim_30period: Optional[float] = Field(None, description="30-period average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")

class KriptoFiyatAnalizi(BaseModel):
    """Crypto price analysis and trends."""
    guncel_fiyat: Optional[float] = Field(None, description="Current crypto price.")
    onceki_kapanis: Optional[float] = Field(None, description="Previous closing price.")
    degisim_miktari: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzdesi: Optional[float] = Field(None, description="Price change percentage.")
    period_yuksek: Optional[float] = Field(None, description="Period high price.")
    period_dusuk: Optional[float] = Field(None, description="Period low price.")
    yuksek_200period: Optional[float] = Field(None, description="200-period high price.")
    dusuk_200period: Optional[float] = Field(None, description="200-period low price.")
    yuksek_200period_uzaklik: Optional[float] = Field(None, description="Distance from 200-period high (%).")
    dusuk_200period_uzaklik: Optional[float] = Field(None, description="Distance from 200-period low (%).")

class KriptoTrendAnalizi(BaseModel):
    """Crypto trend analysis based on moving averages."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-period SMA: 'ustunde', 'altinda'.")
    sma200_durumu: Optional[str] = Field(None, description="Position vs 200-period SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA50 > SMA200).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA50 < SMA200).")

class KriptoTeknikAnalizSonucu(BaseModel):
    """Comprehensive crypto technical analysis result."""
    symbol: str = Field(description="The crypto trading symbol (e.g., BTCTRY, ETHUSDT).")
    analiz_tarihi: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    resolution: str = Field(description="Chart resolution used for analysis.")
    
    # Price and trend analysis
    fiyat_analizi: Optional[KriptoFiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[KriptoTrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[KriptoHareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[KriptoTeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis  
    hacim_analizi: Optional[KriptoHacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    
    # Crypto-specific data
    piyasa_tipi: Optional[str] = Field(None, description="Market type: 'TRY', 'USDT', 'BTC' based on quote currency.")
    volatilite_seviyesi: Optional[str] = Field(None, description="Volatility level: 'dusuk', 'orta', 'yuksek', 'cok_yuksek'.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Coinbase Crypto Models ---

class CoinbaseProduct(BaseModel):
    """Trading pair information from Coinbase."""
    product_id: str = Field(description="Product identifier (e.g., BTC-USD).")
    price: float = Field(description="Current price.")
    price_percentage_change_24h: float = Field(description="24h price change percentage.")
    volume_24h: float = Field(description="24h trading volume.")
    volume_percentage_change_24h: float = Field(description="24h volume change percentage.")
    base_currency_id: str = Field(description="Base currency symbol.")
    quote_currency_id: str = Field(description="Quote currency symbol.")
    base_display_symbol: Optional[str] = Field(None, description="Base currency display symbol.")
    quote_display_symbol: Optional[str] = Field(None, description="Quote currency display symbol.")
    base_name: Optional[str] = Field(None, description="Base currency name.")
    quote_name: Optional[str] = Field(None, description="Quote currency name.")
    min_market_funds: float = Field(description="Minimum market order funds.")
    is_disabled: bool = Field(description="Whether trading is disabled.")
    new_listing: bool = Field(description="Whether this is a new listing.")
    status: Optional[str] = Field(None, description="Product status.")
    cancel_only: bool = Field(description="Whether only cancellations are allowed.")
    limit_only: bool = Field(description="Whether only limit orders are allowed.")
    post_only: bool = Field(description="Whether only post-only orders are allowed.")
    trading_disabled: bool = Field(description="Whether trading is disabled.")
    auction_mode: bool = Field(description="Whether in auction mode.")
    product_type: Optional[str] = Field(None, description="Product type.")
    quote_currency_type: Optional[str] = Field(None, description="Quote currency type.")
    base_currency_type: Optional[str] = Field(None, description="Base currency type.")

class CoinbaseCurrency(BaseModel):
    """Currency information from Coinbase."""
    id: str = Field(description="Currency identifier.")
    name: str = Field(description="Currency name.")
    min_size: Optional[str] = Field(None, description="Minimum transaction size.")
    status: Optional[str] = Field(None, description="Currency status.")
    message: Optional[str] = Field(None, description="Status message.")
    max_precision: Optional[int] = Field(None, description="Maximum decimal precision.")
    convertible_to: List[str] = Field(description="Currencies this can be converted to.")
    details: Dict[str, Any] = Field(description="Additional currency details.")

class CoinbaseExchangeInfoSonucu(BaseModel):
    """Exchange information result from Coinbase."""
    trading_pairs: List[CoinbaseProduct] = Field(description="List of trading pairs.")
    currencies: List[CoinbaseCurrency] = Field(description="List of supported currencies.")
    toplam_cift: int = Field(description="Total number of trading pairs.")
    toplam_para_birimi: int = Field(description="Total number of currencies.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseTicker(BaseModel):
    """Ticker data for a trading pair from Coinbase."""
    product_id: str = Field(description="Product identifier.")
    price: float = Field(description="Current price.")
    size: float = Field(description="Trade size.")
    time: Optional[str] = Field(None, description="Trade timestamp.")
    side: Optional[str] = Field(None, description="Trade side (buy/sell).")
    bid: float = Field(description="Best bid price.")
    ask: float = Field(description="Best ask price.")
    volume: float = Field(description="24h trading volume.")

class CoinbaseTickerSonucu(BaseModel):
    """Ticker data result from Coinbase."""
    tickers: List[CoinbaseTicker] = Field(description="List of ticker data.")
    toplam_cift: int = Field(description="Total number of trading pairs.")
    product_id: Optional[str] = Field(None, description="Specific product ID if requested.")
    quote_currency: Optional[str] = Field(None, description="Quote currency if requested.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseOrderbook(BaseModel):
    """Order book data for a trading pair from Coinbase."""
    time: Optional[str] = Field(None, description="Order book timestamp.")
    bids: List[tuple] = Field(description="List of bid orders (price, size).")
    asks: List[tuple] = Field(description="List of ask orders (price, size).")
    bid_count: int = Field(description="Number of bid orders.")
    ask_count: int = Field(description="Number of ask orders.")

class CoinbaseOrderbookSonucu(BaseModel):
    """Order book result from Coinbase."""
    product_id: str = Field(description="Product identifier.")
    orderbook: Optional[CoinbaseOrderbook] = Field(None, description="Order book data.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseTrade(BaseModel):
    """Individual trade data from Coinbase."""
    trade_id: Optional[str] = Field(None, description="Trade identifier.")
    product_id: str = Field(description="Product identifier.")
    price: float = Field(description="Trade price.")
    size: float = Field(description="Trade size.")
    time: Optional[str] = Field(None, description="Trade timestamp.")
    side: Optional[str] = Field(None, description="Trade side (buy/sell).")

class CoinbaseTradesSonucu(BaseModel):
    """Recent trades result from Coinbase."""
    product_id: str = Field(description="Product identifier.")
    trades: List[CoinbaseTrade] = Field(description="List of recent trades.")
    toplam_islem: int = Field(description="Total number of trades.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseCandle(BaseModel):
    """OHLC candlestick data from Coinbase."""
    start: Optional[str] = Field(None, description="Candle start time.")
    low: float = Field(description="Lowest price.")
    high: float = Field(description="Highest price.")
    open: float = Field(description="Opening price.")
    close: float = Field(description="Closing price.")
    volume: float = Field(description="Trading volume.")

class CoinbaseOHLCSonucu(BaseModel):
    """OHLC data result from Coinbase."""
    product_id: str = Field(description="Product identifier.")
    candles: List[CoinbaseCandle] = Field(description="List of candle data.")
    toplam_veri: int = Field(description="Total number of data points.")
    start: Optional[str] = Field(None, description="Start time filter.")
    end: Optional[str] = Field(None, description="End time filter.")
    granularity: str = Field(description="Candle granularity.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseServerTimeSonucu(BaseModel):
    """Server time result from Coinbase."""
    iso: Optional[str] = Field(None, description="ISO timestamp.")
    epoch: Optional[int] = Field(None, description="Unix timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Coinbase Technical Analysis Models ---
class CoinbaseHareketliOrtalama(BaseModel):
    """Coinbase moving averages data for global crypto markets."""
    sma_5: Optional[float] = Field(None, description="5-period Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-period Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-period Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-period Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-period Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-period Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-period Exponential Moving Average.")

class CoinbaseTeknikIndiktorler(BaseModel):
    """Coinbase technical indicators for global crypto analysis."""
    rsi_14: Optional[float] = Field(None, description="14-period Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-period SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")
    stochastic_k: Optional[float] = Field(None, description="Stochastic %K.")
    stochastic_d: Optional[float] = Field(None, description="Stochastic %D.")

class CoinbaseHacimAnalizi(BaseModel):
    """Coinbase volume analysis for global institutional crypto markets."""
    guncel_hacim: Optional[float] = Field(None, description="Current period's trading volume.")
    ortalama_hacim_10period: Optional[float] = Field(None, description="10-period average volume.")
    ortalama_hacim_30period: Optional[float] = Field(None, description="30-period average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")

class CoinbaseFiyatAnalizi(BaseModel):
    """Coinbase price analysis for global crypto markets."""
    guncel_fiyat: Optional[float] = Field(None, description="Current crypto price in quote currency.")
    onceki_kapanis: Optional[float] = Field(None, description="Previous closing price.")
    degisim_miktari: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzdesi: Optional[float] = Field(None, description="Price change percentage.")
    period_yuksek: Optional[float] = Field(None, description="Period high price.")
    period_dusuk: Optional[float] = Field(None, description="Period low price.")
    yuksek_200period: Optional[float] = Field(None, description="200-period high price.")
    dusuk_200period: Optional[float] = Field(None, description="200-period low price.")
    yuksek_200period_uzaklik: Optional[float] = Field(None, description="Distance from 200-period high (%).")
    dusuk_200period_uzaklik: Optional[float] = Field(None, description="Distance from 200-period low (%).")

class CoinbaseTrendAnalizi(BaseModel):
    """Coinbase trend analysis for global crypto markets."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-period SMA: 'ustunde', 'altinda'.")
    sma200_durumu: Optional[str] = Field(None, description="Position vs 200-period SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA50 > SMA200).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA50 < SMA200).")

class CoinbaseTeknikAnalizSonucu(BaseModel):
    """Comprehensive Coinbase technical analysis result for global crypto markets."""
    product_id: str = Field(description="The crypto product ID (e.g., BTC-USD, ETH-EUR).")
    analiz_tarihi: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    granularity: str = Field(description="Chart granularity used for analysis.")
    
    # Price and trend analysis
    fiyat_analizi: Optional[CoinbaseFiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[CoinbaseTrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[CoinbaseHareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[CoinbaseTeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis  
    hacim_analizi: Optional[CoinbaseHacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    
    # Global crypto-specific data
    piyasa_tipi: Optional[str] = Field(None, description="Market type: 'USD', 'EUR', 'GBP', 'USDC' based on quote currency.")
    volatilite_seviyesi: Optional[str] = Field(None, description="Volatility level: 'dusuk', 'orta', 'yuksek', 'cok_yuksek'.")
    likidite_seviyesi: Optional[str] = Field(None, description="Liquidity level: 'dusuk', 'orta', 'yuksek' (global markets).")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Dovizcom Models ---
class DovizcomVarligi(BaseModel):
    """Single data point for doviz.com asset data."""
    close: float = Field(description="Closing price/rate of the asset.")
    update_date: Optional[datetime.datetime] = Field(None, description="Last update timestamp.")

class DovizcomOHLCVarligi(BaseModel):
    """OHLC data point for doviz.com historical archive data."""
    update_date: Optional[datetime.datetime] = Field(None, description="Date/time of the data point.")
    open: float = Field(description="Opening price/rate.")
    high: float = Field(description="Highest price/rate.")
    low: float = Field(description="Lowest price/rate.")
    close: float = Field(description="Closing price/rate.")
    close_try: float = Field(description="Closing price in TRY.")
    close_usd: float = Field(description="Closing price in USD.")
    volume: float = Field(description="Trading volume.")

class DovizcomGuncelSonucu(BaseModel):
    """Current exchange rate or commodity price result from doviz.com."""
    asset: str = Field(description="Asset symbol (e.g., USD, EUR, gram-altin, BRENT).")
    guncel_deger: Optional[float] = Field(None, description="Current rate/price of the asset.")
    guncelleme_tarihi: Optional[datetime.datetime] = Field(None, description="Last update timestamp.")
    cached: bool = Field(False, description="Whether the data is from cache.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class DovizcomDakikalikSonucu(BaseModel):
    """Minute-by-minute data result from doviz.com."""
    asset: str = Field(description="Asset symbol (e.g., USD, EUR, gram-altin, BRENT).")
    veri_noktalari: List[DovizcomVarligi] = Field(description="List of minute-by-minute data points.")
    toplam_veri: int = Field(description="Total number of data points returned.")
    limit: int = Field(description="Requested data limit.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class DovizcomArsivSonucu(BaseModel):
    """Historical OHLC archive data result from doviz.com."""
    asset: str = Field(description="Asset symbol (e.g., USD, EUR, gram-altin, BRENT).")
    ohlc_verileri: List[DovizcomOHLCVarligi] = Field(description="List of OHLC data points.")
    toplam_veri: int = Field(description="Total number of data points returned.")
    start_date: str = Field(description="Start date of the data range.")
    end_date: str = Field(description="End date of the data range.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Yahoo Finance Economic Calendar Models ---
class EkonomikOlayDetayi(BaseModel):
    """Details of a single economic event."""
    event_name: str = Field(description="Name of the economic event (e.g., 'GDP YY', 'Industrial Output YY').")
    country_code: str = Field(description="Country code (e.g., 'US', 'GB', 'JP').")
    country_name: str = Field(description="Full country name (e.g., 'United States', 'United Kingdom').")
    event_time: datetime.datetime = Field(description="Exact time of the event.")
    period: str = Field(description="Time period the data refers to (e.g., 'Q1', 'May').")
    actual: Optional[str] = Field(None, description="Actual value reported.")
    prior: Optional[str] = Field(None, description="Previous period's value.")
    forecast: Optional[str] = Field(None, description="Forecasted value.")
    revised_from: Optional[str] = Field(None, description="Revised from previous estimate.")
    description: str = Field(description="Detailed description of the economic indicator.")

class EkonomikOlay(BaseModel):
    """Economic events for a single day."""
    date: datetime.date = Field(description="Date of the economic events.")
    timezone: str = Field(description="Timezone of the events (e.g., 'America/New_York').")
    event_count: int = Field(description="Number of events on this date.")
    events: List[EkonomikOlayDetayi] = Field(description="List of economic events for this date.")

class EkonomikTakvimSonucu(BaseModel):
    """Result of economic calendar query."""
    start_date: str = Field(description="Start date of the query (YYYY-MM-DD).")
    end_date: str = Field(description="End date of the query (YYYY-MM-DD).")
    economic_events: List[EkonomikOlay] = Field(description="List of economic events by date.")
    total_events: int = Field(description="Total number of economic events found.")
    high_importance_only: bool = Field(description="Whether only high importance events were included.")
    country_filter: Optional[str] = Field(None, description="Country filter applied (comma-separated codes).")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")
    # Additional fields for enhanced economic calendar
    total_days: Optional[int] = Field(None, description="Number of days with events.")
    countries_covered: Optional[List[str]] = Field(None, description="List of countries covered in the results.")
    high_impact_events: Optional[int] = Field(None, description="Number of high impact events.")
    major_releases: Optional[List[str]] = Field(None, description="List of major economic releases.")
    market_moving_events: Optional[List[str]] = Field(None, description="List of market-moving events.")
    query_timestamp: Optional[datetime.datetime] = Field(None, description="When the query was executed.")
    data_source: Optional[str] = Field(None, description="Source of the economic data.")
    api_endpoint: Optional[str] = Field(None, description="API endpoint used for the query.")

# --- TCMB Inflation Models ---
class EnflasyonVerisi(BaseModel):
    """Single inflation data point from TCMB."""
    tarih: str = Field(description="Date in YYYY-MM-DD format")
    ay_yil: str = Field(description="Month-year in MM-YYYY format from TCMB")
    yillik_enflasyon: Optional[float] = Field(None, description="Annual inflation rate percentage")
    aylik_enflasyon: Optional[float] = Field(None, description="Monthly inflation rate percentage")

class TcmbEnflasyonSonucu(BaseModel):
    """Result from TCMB inflation data request."""
    inflation_type: str = Field(description="Type of inflation data: 'tufe' or 'ufe'")
    start_date: Optional[str] = Field(None, description="Start date filter applied (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date filter applied (YYYY-MM-DD)")
    data: List[EnflasyonVerisi] = Field(description="List of inflation data points")
    total_records: int = Field(description="Number of records returned after filtering")
    total_available_records: Optional[int] = Field(None, description="Total records available before filtering")
    date_range: Optional[Dict[str, str]] = Field(None, description="Available date range in source data")
    statistics: Optional[Dict[str, Optional[float]]] = Field(None, description="Statistical summary of the data")
    data_source: str = Field(description="Source of the data")
    query_timestamp: datetime.datetime = Field(description="When the query was executed")
    error_message: Optional[str] = Field(None, description="Error message if operation failed")

