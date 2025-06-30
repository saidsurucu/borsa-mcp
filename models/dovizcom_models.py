"""
Dovizcom currency and commodities models.
Contains models for Turkish and international currency/commodity data
including real-time rates, historical data, and market analysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# --- Dovizcom Currency & Commodities Models ---

class DovizcomVarligi(BaseModel):
    """Single data point for doviz.com asset data."""
    tarih: datetime.datetime = Field(description="Data timestamp.")
    deger: float = Field(description="Asset value/price.")
    degisim: Optional[float] = Field(None, description="Change amount from previous period.")
    degisim_yuzde: Optional[float] = Field(None, description="Change percentage from previous period.")

class DovizcomOHLCVarligi(BaseModel):
    """OHLC data point for historical archive data."""
    tarih: datetime.date = Field(description="Date for this OHLC data.")
    acilis: float = Field(description="Opening price.")
    en_yuksek: float = Field(description="Highest price.")
    en_dusuk: float = Field(description="Lowest price.")
    kapanis: float = Field(description="Closing price.")

class DovizcomGuncelSonucu(BaseModel):
    """Current exchange rate or commodity price result."""
    varlik_adi: Optional[str] = Field(None, description="Asset name (e.g., 'USD', 'gram-altin', 'BRENT').")
    guncel_deger: Optional[float] = Field(None, description="Current rate/price.")
    son_guncelleme: Optional[datetime.datetime] = Field(None, description="Last update timestamp.")
    degisim: Optional[float] = Field(None, description="Change from previous value.")
    degisim_yuzde: Optional[float] = Field(None, description="Percentage change.")
    birim: Optional[str] = Field(None, description="Unit of measurement (TRY, USD, etc.).")
    kategori: Optional[str] = Field(None, description="Asset category: 'doviz', 'emtia', 'yakit'.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class DovizcomDakikalikSonucu(BaseModel):
    """Minute-by-minute data result for real-time monitoring."""
    varlik_adi: Optional[str] = Field(None, description="Asset name.")
    zaman_araligi: Optional[str] = Field(None, description="Time range for the data.")
    veri_noktalari: List[DovizcomVarligi] = Field(default_factory=list, description="List of minute-by-minute data points.")
    veri_sayisi: Optional[int] = Field(None, description="Number of data points returned.")
    baslangic_tarihi: Optional[datetime.datetime] = Field(None, description="Data start timestamp.")
    bitis_tarihi: Optional[datetime.datetime] = Field(None, description="Data end timestamp.")
    
    # Analysis metrics
    en_yuksek_deger: Optional[float] = Field(None, description="Highest value in the period.")
    en_dusuk_deger: Optional[float] = Field(None, description="Lowest value in the period.")
    ortalama_deger: Optional[float] = Field(None, description="Average value in the period.")
    volatilite: Optional[float] = Field(None, description="Price volatility (standard deviation).")
    
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class DovizcomArsivSonucu(BaseModel):
    """Historical OHLC archive data result for technical analysis."""
    varlik_adi: Optional[str] = Field(None, description="Asset name.")
    baslangic_tarihi: Optional[datetime.date] = Field(None, description="Data start date.")
    bitis_tarihi: Optional[datetime.date] = Field(None, description="Data end date.")
    ohlc_verileri: List[DovizcomOHLCVarligi] = Field(default_factory=list, description="Historical OHLC data points.")
    veri_sayisi: Optional[int] = Field(None, description="Number of OHLC data points.")
    
    # Technical analysis metrics
    trend_yonu: Optional[str] = Field(None, description="Overall trend direction: 'yukselis', 'dusulis', 'yatay'.")
    en_yuksek_fiyat: Optional[float] = Field(None, description="Highest price in the period.")
    en_dusuk_fiyat: Optional[float] = Field(None, description="Lowest price in the period.")
    toplam_getiri: Optional[float] = Field(None, description="Total return percentage for the period.")
    volatilite_seviyesi: Optional[str] = Field(None, description="Volatility level: 'dusuk', 'orta', 'yuksek'.")
    
    # Market context
    piyasa_tipi: Optional[str] = Field(None, description="Market type: 'doviz', 'kiymetli_maden', 'enerji', 'yakit'.")
    referans_para_birimi: Optional[str] = Field(None, description="Reference currency (usually TRY for Turkish markets).")
    
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")