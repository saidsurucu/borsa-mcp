"""
Central models module for Borsa MCP server.
Imports and re-exports all models from provider-specific files
to maintain backward compatibility and provide a single import point.
"""

# Base models and enums
from .base import YFinancePeriodEnum, ZamanAraligiEnum

# KAP models (8 classes)
from .kap_models import (
    SirketInfo, SirketAramaSonucu,
    KatilimFinansUygunlukBilgisi, KatilimFinansUygunlukSonucu,
    EndeksBilgisi, EndeksAramaSonucu, EndeksAramaOgesi, EndeksKoduAramaSonucu,
    EndeksSirketDetayi, EndeksSirketleriSonucu
)

# Yahoo Finance models (15+ classes)
from .yfinance_models import (
    # Company profile models
    SirketProfiliYFinance, SirketProfiliSonucu,
    # Financial statement models
    FinansalTabloSonucu, FinansalVeriNoktasi, FinansalVeriSonucu,
    # Analyst data models
    AnalistTavsiyesi, AnalistFiyatHedefi, TavsiyeOzeti, AnalistVerileriSonucu,
    # Dividend models
    Temettu, HisseBolunmesi, KurumsalAksiyon, TemettuVeAksiyonlarSonucu,
    # Fast info models
    HizliBilgi, HizliBilgiSonucu,
    # Earnings calendar models
    KazancTarihi, KazancTakvimi, KazancBuyumeVerileri, KazancTakvimSonucu,
    # Technical analysis models
    HareketliOrtalama, TeknikIndiktorler, HacimAnalizi, FiyatAnalizi,
    TrendAnalizi, AnalistTavsiyeOzeti, TeknikAnalizSonucu,
    # Sector analysis models
    SektorBilgisi, SirketSektorBilgisi, SektorPerformansOzeti, SektorKarsilastirmaSonucu,
    # Stock screening models
    TaramaKriterleri, TaranmisHisse, TaramaSonucu,
    # Strategy preset models
    DegerYatirimiKriterleri, TemettuYatirimiKriterleri, 
    BuyumeYatirimiKriterleri, MuhafazakarYatirimiKriterleri
)

# TEFAS models (20+ classes)
from .tefas_models import (
    # Core fund models
    FonBilgisi, FonAramaSonucu,
    # Detailed fund information
    FonProfil, FonPortfoyDagilimi, FonFiyatGecmisi, FonDetayBilgisi,
    # Performance analysis
    FonFiyatNoktasi, FonPerformansSonucu,
    # Portfolio analysis
    PortfoyVarlik, VarlikGrubu, PortfoyTarihselVeri, FonPortfoySonucu,
    # Fund comparison
    FonKarsilastirmaOgesi, FonKarsilastirmaSonucu,
    # Fund screening
    FonTaramaKriterleri, TaranmisFon, FonTaramaSonucu
)

# Mynet models (15 classes)
from .mynet_models import (
    # Company detail models
    HisseDetay, Yonetici, Ortak, Istirak, PiyasaDegeri, SirketGenelBilgileri,
    # Financial statement models (legacy)
    BilancoKalemi, KarZararKalemi, MevcutDonem,
    # KAP news models
    KapHaberi, KapHaberleriSonucu, KapHaberDetayi, KapHaberSayfasi
)

# BtcTurk crypto models (18 classes: 12 + 6 technical analysis)
from .btcturk_models import (
    # Exchange models
    TradingPair, Currency, CurrencyOperationBlock, KriptoExchangeInfoSonucu,
    # Market data models
    KriptoTicker, KriptoTickerSonucu, KriptoOrderbook, KriptoOrderbookSonucu,
    KriptoTrade, KriptoTradesSonucu, KriptoOHLC, KriptoOHLCSonucu,
    KriptoKline, KriptoKlineSonucu,
    # Technical analysis models
    KriptoHareketliOrtalama, KriptoTeknikIndiktorler, KriptoHacimAnalizi,
    KriptoFiyatAnalizi, KriptoTrendAnalizi, KriptoTeknikAnalizSonucu
)

# Coinbase global crypto models (21 classes: 15 + 6 technical analysis)
from .coinbase_models import (
    # Exchange models
    CoinbaseProduct, CoinbaseCurrency, CoinbaseExchangeInfoSonucu,
    # Market data models
    CoinbaseTicker, CoinbaseTickerSonucu, CoinbaseOrderbook, CoinbaseOrderbookSonucu,
    CoinbaseTrade, CoinbaseTradesSonucu, CoinbaseCandle, CoinbaseOHLCSonucu,
    CoinbaseServerTimeSonucu,
    # Technical analysis models
    CoinbaseHareketliOrtalama, CoinbaseTeknikIndiktorler, CoinbaseHacimAnalizi,
    CoinbaseFiyatAnalizi, CoinbaseTrendAnalizi, CoinbaseTeknikAnalizSonucu
)

# Dovizcom currency & commodities models (6 classes)
from .dovizcom_models import (
    DovizcomVarligi, DovizcomOHLCVarligi, DovizcomGuncelSonucu,
    DovizcomDakikalikSonucu, DovizcomArsivSonucu
)

# Economic calendar models (4 classes)
from .calendar_models import (
    EkonomikOlayDetayi, EkonomikOlay, EkonomikTakvimSonucu
)

# Fund regulation models (1 class)
from .regulation_models import (
    FonMevzuatSonucu
)

# Export all models for backward compatibility
__all__ = [
    # Base enums
    "YFinancePeriodEnum", "ZamanAraligiEnum",
    
    # KAP models
    "SirketInfo", "SirketAramaSonucu",
    "KatilimFinansUygunlukBilgisi", "KatilimFinansUygunlukSonucu",
    "EndeksBilgisi", "EndeksAramaSonucu", "EndeksAramaOgesi", "EndeksKoduAramaSonucu",
    "EndeksSirketDetayi", "EndeksSirketleriSonucu",
    
    # Yahoo Finance models
    "SirketProfiliYFinance", "SirketProfiliSonucu",
    "FinansalTabloSonucu", "FinansalVeriNoktasi", "FinansalVeriSonucu",
    "AnalistTavsiyesi", "AnalistFiyatHedefi", "TavsiyeOzeti", "AnalistVerileriSonucu",
    "Temettu", "HisseBolunmesi", "KurumsalAksiyon", "TemettuVeAksiyonlarSonucu",
    "HizliBilgi", "HizliBilgiSonucu",
    "KazancTarihi", "KazancTakvimi", "KazancBuyumeVerileri", "KazancTakvimSonucu",
    "HareketliOrtalama", "TeknikIndiktorler", "HacimAnalizi", "FiyatAnalizi",
    "TrendAnalizi", "AnalistTavsiyeOzeti", "TeknikAnalizSonucu",
    "SektorBilgisi", "SirketSektorBilgisi", "SektorPerformansOzeti", "SektorKarsilastirmaSonucu",
    "TaramaKriterleri", "TaranmisHisse", "TaramaSonucu",
    "DegerYatirimiKriterleri", "TemettuYatirimiKriterleri", 
    "BuyumeYatirimiKriterleri", "MuhafazakarYatirimiKriterleri",
    
    # TEFAS models
    "FonBilgisi", "FonAramaSonucu",
    "FonProfil", "FonPortfoyDagilimi", "FonFiyatGecmisi", "FonDetayBilgisi",
    "FonFiyatNoktasi", "FonPerformansSonucu",
    "PortfoyVarlik", "VarlikGrubu", "PortfoyTarihselVeri", "FonPortfoySonucu",
    "FonKarsilastirmaOgesi", "FonKarsilastirmaSonucu",
    "FonTaramaKriterleri", "TaranmisFon", "FonTaramaSonucu",
    
    # Mynet models
    "HisseDetay", "Yonetici", "Ortak", "Istirak", "PiyasaDegeri", "SirketGenelBilgileri",
    "BilancoKalemi", "KarZararKalemi", "MevcutDonem",
    "KapHaberi", "KapHaberleriSonucu", "KapHaberDetayi", "KapHaberSayfasi",
    
    # BtcTurk crypto models
    "TradingPair", "Currency", "CurrencyOperationBlock", "KriptoExchangeInfoSonucu",
    "KriptoTicker", "KriptoTickerSonucu", "KriptoOrderbook", "KriptoOrderbookSonucu",
    "KriptoTrade", "KriptoTradesSonucu", "KriptoOHLC", "KriptoOHLCSonucu",
    "KriptoKline", "KriptoKlineSonucu",
    "KriptoHareketliOrtalama", "KriptoTeknikIndiktorler", "KriptoHacimAnalizi",
    "KriptoFiyatAnalizi", "KriptoTrendAnalizi", "KriptoTeknikAnalizSonucu",
    
    # Coinbase global crypto models
    "CoinbaseProduct", "CoinbaseCurrency", "CoinbaseExchangeInfoSonucu",
    "CoinbaseTicker", "CoinbaseTickerSonucu", "CoinbaseOrderbook", "CoinbaseOrderbookSonucu",
    "CoinbaseTrade", "CoinbaseTradesSonucu", "CoinbaseCandle", "CoinbaseOHLCSonucu",
    "CoinbaseServerTimeSonucu",
    "CoinbaseHareketliOrtalama", "CoinbaseTeknikIndiktorler", "CoinbaseHacimAnalizi",
    "CoinbaseFiyatAnalizi", "CoinbaseTrendAnalizi", "CoinbaseTeknikAnalizSonucu",
    
    # Dovizcom currency & commodities models
    "DovizcomVarligi", "DovizcomOHLCVarligi", "DovizcomGuncelSonucu",
    "DovizcomDakikalikSonucu", "DovizcomArsivSonucu",
    
    # Economic calendar models
    "EkonomikOlayDetayi", "EkonomikOlay", "EkonomikTakvimSonucu",
    
    # Fund regulation models
    "FonMevzuatSonucu"
]