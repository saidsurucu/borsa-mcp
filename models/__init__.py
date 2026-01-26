"""
Central models module for Borsa MCP server.
Imports and re-exports all models from provider-specific files
to maintain backward compatibility and provide a single import point.
"""

# Base models and enums
from .base import YFinancePeriodEnum, ZamanAraligiEnum

# Unified base models (new consolidated API)
from .unified_base import (
    # Enums
    MarketType, StatementType, PeriodType, HistoricalPeriod,
    DataType, RatioSetType, ExchangeType, ScreenPresetType,
    SecurityType, ScanPresetType, TimeframeType,
    # Base models
    UnifiedMetadata, UnifiedResult, MultiResult,
    # Symbol search
    SymbolInfo, SymbolSearchResult,
    # Profile
    CompanyProfile, ProfileResult,
    # Quick info
    QuickInfo, QuickInfoResult,
    # Historical data
    OHLCVData, HistoricalDataResult,
    # Technical analysis
    MovingAverages, TechnicalIndicators, TechnicalSignals, TechnicalAnalysisResult,
    # Pivot points
    PivotLevels, PivotPointsResult as UnifiedPivotPointsResult,
    # Analyst data
    AnalystRating as UnifiedAnalystRating, AnalystSummary, AnalystDataResult,
    # Dividends
    DividendInfo, StockSplitInfo, DividendResult,
    # Earnings
    EarningsEvent, EarningsResult,
    # Financial statements
    FinancialStatement, FinancialStatementsResult,
    # Financial ratios
    ValuationRatios, BuffettMetrics, CoreHealthMetrics,
    AdvancedMetrics as UnifiedAdvancedMetrics, FinancialRatiosResult,
    # Corporate actions
    CapitalIncrease, CorporateActionsResult,
    # News
    NewsItem, NewsResult,
    # Screener
    ScreenedStock, ScreenerResult,
    # Scanner
    ScannedStock, ScannerResult,
    # Crypto
    CryptoTicker, CryptoOrderbookLevel, CryptoOrderbook,
    CryptoTrade, CryptoMarketResult,
    # FX
    FXRate, FXResult,
    # Economic calendar
    EconomicEvent, EconomicCalendarResult,
    # Bonds
    BondYield, BondYieldsResult,
    # Funds
    FundInfo, FundPortfolioItem, FundResult,
    # Index
    IndexInfo, IndexComponent, IndexResult,
    # Sector comparison
    SectorStock, SectorComparisonResult,
)

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
    # Pivot points support/resistance models
    PivotPointsSonucu,
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

# Buffett analysis and bond yields models (10 classes)
from .buffett_models import (
    # Bond yields models
    TahvilBilgisi, TahvilFaizleriSonucu,
    # Buffett analysis models
    OwnerEarningsSonucu, OEYieldSonucu,
    ProjectedCashFlow, DCFParameters, DCFFisherSonucu,
    BuffettCriteria, SafetyMarginSonucu,
    # Consolidated Buffett analysis
    BuffettValueAnalysis
)

# Financial ratios models (9 classes: 5 Phase 2 + 2 Phase 3 + 2 Consolidated)
from .financial_ratios_models import (
    RoeSonucu, RoicSonucu, DebtRatiosSonucu,
    FcfMarginSonucu, EarningsQualitySonucu,
    AltmanZScoreSonucu, RealGrowthSonucu,
    CoreFinancialHealthAnalysis, AdvancedFinancialMetrics
)

# Comprehensive analysis models (5 classes: Phase 4)
from .comprehensive_analysis_models import (
    LiquidityMetrics, ProfitabilityMargins, ValuationMetrics,
    CompositeScores, ComprehensiveFinancialAnalysis
)

# Multi-ticker models from borsa_models (Phase 1: Yahoo Finance)
from borsa_models import (
    MultiHizliBilgiSonucu, MultiTemettuVeAksiyonlarSonucu,
    MultiAnalistVerileriSonucu, MultiKazancTakvimSonucu
)

# Multi-ticker models from borsa_models (Phase 2: İş Yatırım Financial Statements)
from borsa_models import (
    MultiFinansalTabloSonucu, MultiKarZararTablosuSonucu,
    MultiNakitAkisiTablosuSonucu
)

# İş Yatırım Financial Ratios Models
from borsa_models import (
    FinansalOranlar, FinansalOranlarSonucu, MultiFinansalOranlarSonucu
)

# İş Yatırım Corporate Actions Models (Sermaye Artırımları & Temettü)
from borsa_models import (
    SermayeArtirimi, SermayeArtirimlariSonucu, MultiSermayeArtirimlariSonucu,
    IsyatirimTemettu, IsyatirimTemettuSonucu, MultiIsyatirimTemettuSonucu
)

# US Stock Models from borsa_models
from borsa_models import (
    # Core US models
    USCompanyInfo, USQuickInfo, USStockDataPoint,
    USDividend, USStockSplit, USAnalystRating, USPriceTarget,
    USEarningsDate, USPivotPoints, USTechnicalIndicators,
    # Result models
    USCompanySearchResult, USQuickInfoResult, USStockDataResult,
    USAnalystResult, USDividendResult, USEarningsResult,
    USTechnicalAnalysisResult, USPivotPointsResult, USSectorInfoResult,
    # Multi-ticker models
    MultiUSQuickInfoResult, MultiUSAnalystResult,
    MultiUSDividendResult, MultiUSEarningsResult,
    # US Financial Statement models
    USBalanceSheetResult, USIncomeStatementResult, USCashFlowResult,
    MultiUSBalanceSheetResult, MultiUSIncomeStatementResult, MultiUSCashFlowResult,
    # US Index models
    USIndexInfo, USIndexSearchResult, USIndexDetailResult
)

# US Stock Screener Models from borsa_models
from borsa_models import (
    SecurityTypeEnum, PresetScreenEnum, ScreenedSecurity,
    USScreenerResult, ScreenerPresetInfo, ScreenerPresetsResult, ScreenerFilterDocumentation
)

# BIST Screener Models from borsa_models
from borsa_models import (
    BistScreenedStock, BistScreenerResult, BistScreenerPresetInfo,
    BistScreenerPresetsResult, BistScreenerFilterDocumentation
)

# BIST Technical Scanner Models (borsapy TradingView integration)
# Note: TaramaSonucu from scanner_models is aliased to avoid conflict with borsa_models.TaramaSonucu
from .scanner_models import (
    TaramaSonucu as ScannerTaramaSonucu, TeknikTaramaSonucu, TaramaPresetInfo, TaramaYardimSonucu
)

# Export all models for backward compatibility
__all__ = [
    # Base enums
    "YFinancePeriodEnum", "ZamanAraligiEnum",

    # Unified base models (new consolidated API)
    "MarketType", "StatementType", "PeriodType", "HistoricalPeriod",
    "DataType", "RatioSetType", "ExchangeType", "ScreenPresetType",
    "SecurityType", "ScanPresetType", "TimeframeType",
    "UnifiedMetadata", "UnifiedResult", "MultiResult",
    "SymbolInfo", "SymbolSearchResult",
    "CompanyProfile", "ProfileResult",
    "QuickInfo", "QuickInfoResult",
    "OHLCVData", "HistoricalDataResult",
    "MovingAverages", "TechnicalIndicators", "TechnicalSignals", "TechnicalAnalysisResult",
    "PivotLevels", "UnifiedPivotPointsResult",
    "UnifiedAnalystRating", "AnalystSummary", "AnalystDataResult",
    "DividendInfo", "StockSplitInfo", "DividendResult",
    "EarningsEvent", "EarningsResult",
    "FinancialStatement", "FinancialStatementsResult",
    "ValuationRatios", "BuffettMetrics", "CoreHealthMetrics",
    "UnifiedAdvancedMetrics", "FinancialRatiosResult",
    "CapitalIncrease", "CorporateActionsResult",
    "NewsItem", "NewsResult",
    "ScreenedStock", "ScreenerResult",
    "ScannedStock", "ScannerResult",
    "CryptoTicker", "CryptoOrderbookLevel", "CryptoOrderbook",
    "CryptoTrade", "CryptoMarketResult",
    "FXRate", "FXResult",
    "EconomicEvent", "EconomicCalendarResult",
    "BondYield", "BondYieldsResult",
    "FundInfo", "FundPortfolioItem", "FundResult",
    "IndexInfo", "IndexComponent", "IndexResult",
    "SectorStock", "SectorComparisonResult",
    
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
    "PivotPointsSonucu",
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
    "FonMevzuatSonucu",

    # Buffett analysis and bond yields models
    "TahvilBilgisi", "TahvilFaizleriSonucu",
    "OwnerEarningsSonucu", "OEYieldSonucu",
    "ProjectedCashFlow", "DCFParameters", "DCFFisherSonucu",
    "BuffettCriteria", "SafetyMarginSonucu",
    "BuffettValueAnalysis",

    # Financial ratios models
    "RoeSonucu", "RoicSonucu", "DebtRatiosSonucu",
    "FcfMarginSonucu", "EarningsQualitySonucu",
    "AltmanZScoreSonucu", "RealGrowthSonucu",
    "CoreFinancialHealthAnalysis", "AdvancedFinancialMetrics",

    # Comprehensive analysis models
    "LiquidityMetrics", "ProfitabilityMargins", "ValuationMetrics",
    "CompositeScores", "ComprehensiveFinancialAnalysis",

    # Multi-ticker models (Phase 1: Yahoo Finance)
    "MultiHizliBilgiSonucu", "MultiTemettuVeAksiyonlarSonucu",
    "MultiAnalistVerileriSonucu", "MultiKazancTakvimSonucu",

    # Multi-ticker models (Phase 2: İş Yatırım Financial Statements)
    "MultiFinansalTabloSonucu", "MultiKarZararTablosuSonucu",
    "MultiNakitAkisiTablosuSonucu",

    # İş Yatırım Financial Ratios Models
    "FinansalOranlar", "FinansalOranlarSonucu", "MultiFinansalOranlarSonucu",

    # İş Yatırım Corporate Actions Models
    "SermayeArtirimi", "SermayeArtirimlariSonucu", "MultiSermayeArtirimlariSonucu",
    "IsyatirimTemettu", "IsyatirimTemettuSonucu", "MultiIsyatirimTemettuSonucu",

    # US Stock Models
    "USCompanyInfo", "USQuickInfo", "USStockDataPoint",
    "USDividend", "USStockSplit", "USAnalystRating", "USPriceTarget",
    "USEarningsDate", "USPivotPoints", "USTechnicalIndicators",
    "USCompanySearchResult", "USQuickInfoResult", "USStockDataResult",
    "USAnalystResult", "USDividendResult", "USEarningsResult",
    "USTechnicalAnalysisResult", "USPivotPointsResult", "USSectorInfoResult",
    "MultiUSQuickInfoResult", "MultiUSAnalystResult",
    "MultiUSDividendResult", "MultiUSEarningsResult",
    # US Financial Statement Models
    "USBalanceSheetResult", "USIncomeStatementResult", "USCashFlowResult",
    "MultiUSBalanceSheetResult", "MultiUSIncomeStatementResult", "MultiUSCashFlowResult",
    # US Index Models
    "USIndexInfo", "USIndexSearchResult", "USIndexDetailResult",
    # US Stock Screener Models
    "SecurityTypeEnum", "PresetScreenEnum", "ScreenedSecurity",
    "USScreenerResult", "ScreenerPresetInfo", "ScreenerPresetsResult", "ScreenerFilterDocumentation",
    # BIST Screener Models
    "BistScreenedStock", "BistScreenerResult", "BistScreenerPresetInfo",
    "BistScreenerPresetsResult", "BistScreenerFilterDocumentation",
    # BIST Technical Scanner Models
    "ScannerTaramaSonucu", "TeknikTaramaSonucu", "TaramaPresetInfo", "TaramaYardimSonucu"
]