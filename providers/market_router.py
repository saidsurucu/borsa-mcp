"""
Market Router for unified tools.
Routes requests to appropriate providers based on market type.
Uses BorsaApiClient as the underlying service layer.
"""
from datetime import datetime
from typing import Any, List, Optional, Union
import logging

from models.unified_base import (
    MarketType, StatementType, PeriodType, DataType, RatioSetType, ExchangeType, UnifiedMetadata, SymbolInfo, SymbolSearchResult,
    CompanyProfile, ProfileResult, QuickInfo, QuickInfoResult,
    OHLCVData, HistoricalDataResult, TechnicalAnalysisResult,
    PivotPointsResult, AnalystDataResult, DividendResult,
    EarningsResult, FinancialStatementsResult, FinancialRatiosResult,
    CorporateActionsResult, NewsResult, NewsDetailResult, ScreenerResult, ScannerResult,
    CryptoMarketResult, FXResult, FundResult, IndexResult,
    SectorComparisonResult, MovingAverages, TechnicalIndicators,
    TechnicalSignals, PivotLevels, AnalystRating, AnalystSummary,
    DividendInfo, StockSplitInfo, EarningsEvent, FinancialStatement,
    ValuationRatios, BuffettMetrics, CoreHealthMetrics, AdvancedMetrics,
    CapitalIncrease, NewsItem, ScreenedStock, ScannedStock,
    CryptoTicker, CryptoOrderbook, CryptoOrderbookLevel, CryptoTrade, FXRate, FundInfo,
    IndexInfo, IndexComponent, SectorStock,
    # New models for expanded features
    IslamicComplianceInfo, FundComparisonItem, FundComparisonResult,
    InflationData, InflationCalculation, MacroDataResult,
    PresetInfo, FilterInfo, ScreenerHelpResult,
    IndicatorInfo, ScannerHelpResult,
    RegulationItem, RegulationsResult
)

logger = logging.getLogger(__name__)


class MarketRouter:
    """Routes unified tool requests to appropriate market-specific providers."""

    def __init__(self):
        """Initialize the market router with borsa_client as the underlying service layer."""
        from borsa_client import BorsaApiClient
        self._client = BorsaApiClient()

    # --- Helper Methods ---

    def _create_metadata(
        self,
        market: MarketType,
        symbols: Union[str, List[str]],
        source: str,
        successful: int = 1,
        failed: int = 0,
        warnings: List[str] = None
    ) -> UnifiedMetadata:
        """Create unified metadata for responses."""
        if isinstance(symbols, str):
            symbols = [symbols]
        return UnifiedMetadata(
            market=market,
            symbols=symbols,
            timestamp=datetime.now(),
            source=source,
            successful_count=successful,
            failed_count=failed,
            warnings=warnings or []
        )

    def _get_ticker_with_suffix(self, symbol: str, market: MarketType) -> str:
        """Get ticker with appropriate suffix for market."""
        symbol = symbol.upper()
        if market == MarketType.BIST and not symbol.endswith('.IS'):
            return f"{symbol}.IS"
        return symbol

    # --- Symbol Search ---

    async def search_symbol(
        self,
        query: str,
        market: MarketType,
        limit: int = 10
    ) -> SymbolSearchResult:
        """Search for symbols across markets."""
        matches = []
        source = "unknown"

        if market == MarketType.BIST:
            source = "kap"
            result = await self._client.search_companies_from_kap(query)
            if result and result.sonuclar:
                for company in result.sonuclar[:limit]:
                    matches.append(SymbolInfo(
                        symbol=company.ticker_kodu,
                        name=company.sirket_adi,
                        market=MarketType.BIST,
                        asset_type="stock",
                        exchange="BIST"
                    ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.search_us_stock(query)
            if result and result.get("found") and result.get("info"):
                info = result["info"]
                matches.append(SymbolInfo(
                    symbol=info.get("symbol", query.upper()),
                    name=info.get("name", query.upper()),
                    market=MarketType.US,
                    asset_type=info.get("quote_type", "equity"),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    exchange=info.get("exchange"),
                    currency=info.get("currency", "USD")
                ))

        elif market == MarketType.FUND:
            source = "tefas"
            result = await self._client.search_funds(query, limit=limit)
            if result and result.sonuclar:
                for fund in result.sonuclar[:limit]:
                    matches.append(SymbolInfo(
                        symbol=fund.fon_kodu,
                        name=fund.fon_adi,
                        market=MarketType.FUND,
                        asset_type="mutual_fund",
                        currency="TRY"
                    ))

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_exchange_info()
            if result and result.trading_pairs:
                query_upper = query.upper()
                for pair in result.trading_pairs:
                    pair_symbol = pair.symbol or pair.name or ""
                    if query_upper in pair_symbol:
                        matches.append(SymbolInfo(
                            symbol=pair_symbol,
                            name=pair_symbol,
                            market=MarketType.CRYPTO_TR,
                            asset_type="crypto",
                            exchange="btcturk"
                        ))
                        if len(matches) >= limit:
                            break

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_exchange_info()
            if result and result.trading_pairs:
                query_upper = query.upper()
                for product in result.trading_pairs:
                    product_id = product.product_id or ""
                    if query_upper in product_id:
                        matches.append(SymbolInfo(
                            symbol=product_id,
                            name=product.base_name or product_id,
                            market=MarketType.CRYPTO_GLOBAL,
                            asset_type="crypto",
                            exchange="coinbase",
                            currency=product.quote_name
                        ))
                        if len(matches) >= limit:
                            break

        return SymbolSearchResult(
            metadata=self._create_metadata(market, query, source),
            matches=matches,
            total_count=len(matches)
        )

    # --- Company Profile ---

    async def get_profile(
        self,
        symbol: str,
        market: MarketType
    ) -> ProfileResult:
        """Get company profile."""
        profile = None
        source = "unknown"

        if market == MarketType.BIST:
            source = "yfinance"
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_sirket_bilgileri_yfinance(ticker)
            if result and result.get("profil"):
                p = result["profil"]
                profile = CompanyProfile(
                    symbol=symbol.upper(),
                    name=p.get("uzun_ad") or p.get("kisa_ad") or symbol,
                    market=market,
                    description=p.get("ozet"),
                    sector=p.get("sektor"),
                    industry=p.get("sanayi"),
                    country=p.get("ulke"),
                    website=p.get("web_sitesi"),
                    employees=p.get("calisan_sayisi"),
                    market_cap=p.get("piyasa_degeri"),
                    currency=p.get("para_birimi", "TRY"),
                    exchange=p.get("borsa", "BIST"),
                    pe_ratio=p.get("takip_eden_fk"),
                    pb_ratio=p.get("pd_dd"),
                    dividend_yield=p.get("temettu_orani"),
                    beta=p.get("beta"),
                    current_price=p.get("guncel_fiyat"),
                    day_high=p.get("gun_yuksek"),
                    day_low=p.get("gun_dusuk"),
                    volume=p.get("hacim"),
                    avg_volume=p.get("ortalama_hacim"),
                    week_52_high=p.get("elli_iki_hafta_yuksek"),
                    week_52_low=p.get("elli_iki_hafta_dusuk")
                )

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_company_profile(symbol)
            if result and result.get("info"):
                p = result["info"]
                profile = CompanyProfile(
                    symbol=p.get("symbol", symbol.upper()),
                    name=p.get("name", symbol.upper()),
                    market=market,
                    description=p.get("description"),
                    sector=p.get("sector"),
                    industry=p.get("industry"),
                    country=p.get("country"),
                    website=p.get("website"),
                    employees=p.get("employees"),
                    market_cap=p.get("market_cap"),
                    currency=p.get("currency", "USD"),
                    exchange=p.get("exchange"),
                    pe_ratio=p.get("pe_ratio"),
                    pb_ratio=p.get("pb_ratio"),
                    dividend_yield=p.get("dividend_yield"),
                    beta=p.get("beta"),
                    current_price=p.get("current_price"),
                    day_high=p.get("day_high"),
                    day_low=p.get("day_low"),
                    volume=p.get("volume"),
                    avg_volume=p.get("avg_volume"),
                    week_52_high=p.get("week_52_high"),
                    week_52_low=p.get("week_52_low")
                )

        elif market == MarketType.FUND:
            source = "tefas"
            result = await self._client.get_fund_detail(symbol)
            if result and result.fon:
                f = result.fon
                profile = CompanyProfile(
                    symbol=f.profil.kod if f.profil else symbol,
                    name=f.profil.ad if f.profil else symbol,
                    market=market,
                    description=f.profil.kategori if f.profil else None,
                    currency="TRY"
                )

        return ProfileResult(
            metadata=self._create_metadata(market, symbol, source),
            profile=profile
        )

    # --- Quick Info ---

    async def get_quick_info(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> QuickInfoResult:
        """Get quick info for single or multiple symbols."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "unknown"
        results = []
        warnings = []

        if market == MarketType.BIST:
            source = "yfinance"
            if is_multi:
                result = await self._client.get_hizli_bilgi_multi(symbol_list)
                if result and result.get("data"):
                    for item in result["data"]:
                        if item.get("bilgi"):
                            b = item["bilgi"]
                            results.append(QuickInfo(
                                symbol=b.get("sembol", ""),
                                name=b.get("sirket_adi") or b.get("sembol", ""),
                                market=market,
                                currency="TRY",
                                current_price=b.get("guncel_fiyat"),
                                change_percent=b.get("degisim_yuzdesi"),
                                volume=b.get("hacim"),
                                market_cap=b.get("piyasa_degeri"),
                                pe_ratio=b.get("fk_orani"),
                                pb_ratio=b.get("pd_dd"),
                                roe=b.get("oz_sermaye_karliligi"),
                                dividend_yield=b.get("temettu_verimi"),
                                week_52_high=b.get("elli_iki_hafta_yuksek"),
                                week_52_low=b.get("elli_iki_hafta_dusuk"),
                                avg_volume=b.get("ortalama_hacim"),
                                beta=b.get("beta")
                            ))
                    warnings = result.get("warnings", [])
            else:
                result = await self._client.get_hizli_bilgi(symbol_list[0])
                if result and result.get("bilgi"):
                    b = result["bilgi"]
                    results.append(QuickInfo(
                        symbol=b.get("sembol", symbol_list[0]),
                        name=b.get("sirket_adi") or b.get("sembol", symbol_list[0]),
                        market=market,
                        currency="TRY",
                        current_price=b.get("guncel_fiyat"),
                        change_percent=b.get("degisim_yuzdesi"),
                        volume=b.get("hacim"),
                        market_cap=b.get("piyasa_degeri"),
                        pe_ratio=b.get("fk_orani"),
                        pb_ratio=b.get("pd_dd"),
                        roe=b.get("oz_sermaye_karliligi"),
                        dividend_yield=b.get("temettu_verimi"),
                        week_52_high=b.get("elli_iki_hafta_yuksek"),
                        week_52_low=b.get("elli_iki_hafta_dusuk"),
                        avg_volume=b.get("ortalama_hacim"),
                        beta=b.get("beta")
                    ))

        elif market == MarketType.US:
            source = "yfinance"
            if is_multi:
                result = await self._client.get_us_quick_info_multi(symbol_list)
                if result and result.get("data"):
                    for item in result["data"]:
                        if item.get("info"):
                            i = item["info"]
                            results.append(QuickInfo(
                                symbol=i.get("symbol", ""),
                                name=i.get("name") or i.get("symbol", ""),
                                market=market,
                                currency=i.get("currency", "USD"),
                                current_price=i.get("current_price"),
                                change_percent=i.get("change_percent"),
                                volume=i.get("volume"),
                                market_cap=i.get("market_cap"),
                                pe_ratio=i.get("pe_ratio"),
                                pb_ratio=i.get("pb_ratio"),
                                ps_ratio=i.get("ps_ratio"),
                                roe=i.get("roe"),
                                dividend_yield=i.get("dividend_yield"),
                                week_52_high=i.get("week_52_high"),
                                week_52_low=i.get("week_52_low"),
                                avg_volume=i.get("avg_volume"),
                                beta=i.get("beta")
                            ))
                    warnings = result.get("warnings", [])
            else:
                result = await self._client.get_us_quick_info(symbol_list[0])
                if result and result.get("info"):
                    i = result["info"]
                    results.append(QuickInfo(
                        symbol=i.get("symbol", symbol_list[0]),
                        name=i.get("name") or i.get("symbol", symbol_list[0]),
                        market=market,
                        currency=i.get("currency", "USD"),
                        current_price=i.get("current_price"),
                        change_percent=i.get("change_percent"),
                        volume=i.get("volume"),
                        market_cap=i.get("market_cap"),
                        pe_ratio=i.get("pe_ratio"),
                        pb_ratio=i.get("pb_ratio"),
                        ps_ratio=i.get("ps_ratio"),
                        roe=i.get("roe"),
                        dividend_yield=i.get("dividend_yield"),
                        week_52_high=i.get("week_52_high"),
                        week_52_low=i.get("week_52_low"),
                        avg_volume=i.get("avg_volume"),
                        beta=i.get("beta")
                    ))

        data = results if is_multi else (results[0] if results else None)
        return QuickInfoResult(
            metadata=self._create_metadata(
                market, symbol_list, source,
                successful=len(results),
                failed=len(symbol_list) - len(results),
                warnings=warnings
            ),
            data=data
        )

    # --- Historical Data ---

    async def get_historical_data(
        self,
        symbol: str,
        market: MarketType,
        period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d"
    ) -> HistoricalDataResult:
        """Get historical OHLCV data."""
        source = "unknown"
        data_points = []

        if market == MarketType.BIST:
            source = "yfinance"
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_finansal_veri(
                ticker,
                zaman_araligi=period or "1mo",
                start_date=start_date,
                end_date=end_date
            )
            if result and result.get("veri_noktalari"):
                for dp in result["veri_noktalari"]:
                    data_points.append(OHLCVData(
                        date=dp.get("tarih"),
                        open=dp.get("acilis"),
                        high=dp.get("yuksek"),
                        low=dp.get("dusuk"),
                        close=dp.get("kapanis"),
                        volume=dp.get("hacim"),
                        adj_close=dp.get("duzeltilmis_kapanis")
                    ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_stock_data(
                symbol,
                period=period or "1mo",
                start_date=start_date,
                end_date=end_date
            )
            if result and result.get("data"):
                for dp in result["data"]:
                    data_points.append(OHLCVData(
                        date=dp.get("date"),
                        open=dp.get("open"),
                        high=dp.get("high"),
                        low=dp.get("low"),
                        close=dp.get("close"),
                        volume=dp.get("volume"),
                        adj_close=dp.get("adj_close")
                    ))

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_ohlc(symbol)
            if result and result.ohlc_data:
                for dp in result.ohlc_data:
                    data_points.append(OHLCVData(
                        date=dp.timestamp,
                        open=dp.open,
                        high=dp.high,
                        low=dp.low,
                        close=dp.close,
                        volume=int(dp.volume) if dp.volume else None
                    ))

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_ohlc(symbol)
            if result and result.candles:
                for dp in result.candles:
                    data_points.append(OHLCVData(
                        date=dp.time,
                        open=dp.open,
                        high=dp.high,
                        low=dp.low,
                        close=dp.close,
                        volume=int(dp.volume) if dp.volume else None
                    ))

        return HistoricalDataResult(
            metadata=self._create_metadata(market, symbol, source),
            symbol=symbol.upper(),
            period=period,
            start_date=start_date,
            end_date=end_date,
            data=data_points,
            data_points=len(data_points)
        )

    # --- Technical Analysis ---

    async def get_technical_analysis(
        self,
        symbol: str,
        market: MarketType,
        timeframe: str = "1d"
    ) -> TechnicalAnalysisResult:
        """Get technical analysis indicators."""
        source = "unknown"
        moving_averages = None
        indicators = None
        signals = None
        current_price = None
        volume_analysis = None

        if market == MarketType.BIST:
            source = "yfinance"
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_teknik_analiz_yfinance(ticker)
            if result and result.get("indikatorler"):
                ind = result["indikatorler"]
                current_price = result.get("guncel_fiyat")
                moving_averages = MovingAverages(
                    sma_5=ind.get("sma_5"),
                    sma_10=ind.get("sma_10"),
                    sma_20=ind.get("sma_20"),
                    sma_50=ind.get("sma_50"),
                    sma_200=ind.get("sma_200"),
                    ema_5=ind.get("ema_5"),
                    ema_10=ind.get("ema_10"),
                    ema_20=ind.get("ema_20"),
                    ema_50=ind.get("ema_50"),
                    ema_200=ind.get("ema_200")
                )
                indicators = TechnicalIndicators(
                    rsi_14=ind.get("rsi_14"),
                    macd=ind.get("macd"),
                    macd_signal=ind.get("macd_sinyal"),
                    macd_histogram=ind.get("macd_histogram"),
                    bb_upper=ind.get("bb_ust"),
                    bb_middle=ind.get("bb_orta"),
                    bb_lower=ind.get("bb_alt")
                )
                if result.get("trend"):
                    t = result["trend"]
                    signals = TechnicalSignals(
                        trend=t.get("genel_trend"),
                        rsi_signal=t.get("rsi_sinyal"),
                        macd_signal=t.get("macd_sinyal"),
                        bb_signal=t.get("bollinger_pozisyonu")
                    )
                if result.get("hacim"):
                    h = result["hacim"]
                    volume_analysis = {
                        "current_volume": h.get("guncel_hacim"),
                        "average_volume": h.get("ortalama_hacim"),
                        "volume_ratio": h.get("hacim_orani"),
                        "volume_trend": h.get("hacim_trendi")
                    }

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_technical_analysis(symbol)
            if result and result.get("indicators"):
                ind = result["indicators"]
                current_price = result.get("current_price")
                moving_averages = MovingAverages(
                    sma_5=ind.get("sma_5"),
                    sma_10=ind.get("sma_10"),
                    sma_20=ind.get("sma_20"),
                    sma_50=ind.get("sma_50"),
                    sma_200=ind.get("sma_200"),
                    ema_5=ind.get("ema_5"),
                    ema_10=ind.get("ema_10"),
                    ema_20=ind.get("ema_20"),
                    ema_50=ind.get("ema_50"),
                    ema_200=ind.get("ema_200")
                )
                indicators = TechnicalIndicators(
                    rsi_14=ind.get("rsi_14"),
                    macd=ind.get("macd"),
                    macd_signal=ind.get("macd_signal"),
                    macd_histogram=ind.get("macd_histogram"),
                    bb_upper=ind.get("bb_upper"),
                    bb_middle=ind.get("bb_middle"),
                    bb_lower=ind.get("bb_lower")
                )
                if result.get("trend"):
                    t = result["trend"]
                    # US technical analysis returns trend as a string directly
                    if isinstance(t, str):
                        signals = TechnicalSignals(
                            trend=t,
                            rsi_signal=None,
                            macd_signal=None,
                            bb_signal=None
                        )
                    else:
                        signals = TechnicalSignals(
                            trend=t.get("overall_trend"),
                            rsi_signal=t.get("rsi_signal"),
                            macd_signal=t.get("macd_signal"),
                            bb_signal=t.get("bollinger_position")
                        )

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_teknik_analiz(symbol)
            if result and result.indikatorler:
                ind = result.indikatorler
                current_price = result.guncel_fiyat
                moving_averages = MovingAverages(
                    sma_5=ind.sma_5,
                    sma_10=ind.sma_10,
                    sma_20=ind.sma_20,
                    sma_50=ind.sma_50,
                    sma_200=ind.sma_200,
                    ema_5=ind.ema_5,
                    ema_10=ind.ema_10,
                    ema_20=ind.ema_20,
                    ema_50=ind.ema_50,
                    ema_200=ind.ema_200
                )
                indicators = TechnicalIndicators(
                    rsi_14=ind.rsi_14,
                    macd=ind.macd,
                    macd_signal=ind.macd_sinyal,
                    macd_histogram=ind.macd_histogram,
                    bb_upper=ind.bb_ust,
                    bb_middle=ind.bb_orta,
                    bb_lower=ind.bb_alt
                )

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_teknik_analiz(symbol)
            if result and result.indikatorler:
                ind = result.indikatorler
                current_price = result.guncel_fiyat
                moving_averages = MovingAverages(
                    sma_5=ind.sma_5,
                    sma_10=ind.sma_10,
                    sma_20=ind.sma_20,
                    sma_50=ind.sma_50,
                    sma_200=ind.sma_200,
                    ema_5=ind.ema_5,
                    ema_10=ind.ema_10,
                    ema_20=ind.ema_20,
                    ema_50=ind.ema_50,
                    ema_200=ind.ema_200
                )
                indicators = TechnicalIndicators(
                    rsi_14=ind.rsi_14,
                    macd=ind.macd,
                    macd_signal=ind.macd_sinyal,
                    macd_histogram=ind.macd_histogram,
                    bb_upper=ind.bb_ust,
                    bb_middle=ind.bb_orta,
                    bb_lower=ind.bb_alt
                )

        return TechnicalAnalysisResult(
            metadata=self._create_metadata(market, symbol, source),
            symbol=symbol.upper(),
            timeframe=timeframe,
            current_price=current_price,
            moving_averages=moving_averages,
            indicators=indicators,
            signals=signals,
            volume_analysis=volume_analysis
        )

    # --- Pivot Points ---

    async def get_pivot_points(
        self,
        symbol: str,
        market: MarketType
    ) -> PivotPointsResult:
        """Get pivot points (support/resistance levels)."""
        source = "yfinance"
        levels = None
        current_price = None
        prev_high = None
        prev_low = None
        prev_close = None
        position = None
        nearest_support = None
        nearest_resistance = None

        if market == MarketType.BIST:
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_pivot_points(ticker)
            if result:
                current_price = result.get("guncel_fiyat")
                prev_high = result.get("onceki_yuksek")
                prev_low = result.get("onceki_dusuk")
                prev_close = result.get("onceki_kapanis")
                if result.get("pivot"):
                    levels = PivotLevels(
                        pivot=result.get("pivot"),
                        r1=result.get("r1"),
                        r2=result.get("r2"),
                        r3=result.get("r3"),
                        s1=result.get("s1"),
                        s2=result.get("s2"),
                        s3=result.get("s3")
                    )
                position = result.get("pozisyon")
                nearest_support = result.get("en_yakin_destek")
                nearest_resistance = result.get("en_yakin_direnc")

        elif market == MarketType.US:
            result = await self._client.get_us_pivot_points(symbol)
            if result:
                current_price = result.get("current_price")
                prev_high = result.get("previous_high")
                prev_low = result.get("previous_low")
                prev_close = result.get("previous_close")
                if result.get("pivot"):
                    levels = PivotLevels(
                        pivot=result.get("pivot"),
                        r1=result.get("r1"),
                        r2=result.get("r2"),
                        r3=result.get("r3"),
                        s1=result.get("s1"),
                        s2=result.get("s2"),
                        s3=result.get("s3")
                    )
                position = result.get("position")
                nearest_support = result.get("nearest_support")
                nearest_resistance = result.get("nearest_resistance")

        return PivotPointsResult(
            metadata=self._create_metadata(market, symbol, source),
            symbol=symbol.upper(),
            current_price=current_price,
            previous_high=prev_high,
            previous_low=prev_low,
            previous_close=prev_close,
            levels=levels,
            position=position,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance
        )

    # --- Analyst Data ---

    async def get_analyst_data(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> AnalystDataResult:
        """Get analyst ratings and recommendations."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "yfinance"
        warnings = []
        symbol = symbol_list[0]
        summary = None
        ratings = []
        current_price = None
        upside = None

        if market == MarketType.BIST:
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_analist_verileri_yfinance(ticker)
            if result:
                current_price = result.get("guncel_fiyat")
                if result.get("ozet"):
                    s = result["ozet"]
                    summary = AnalystSummary(
                        strong_buy=s.get("guclu_al") or 0,
                        buy=s.get("al") or 0,
                        hold=s.get("tut") or 0,
                        sell=s.get("sat") or 0,
                        strong_sell=s.get("guclu_sat") or 0,
                        mean_target=result.get("ortalama_hedef_fiyat"),
                        low_target=result.get("en_dusuk_hedef_fiyat"),
                        high_target=result.get("en_yuksek_hedef_fiyat"),
                        consensus=s.get("genel_tavsiye")
                    )
                upside = result.get("yukselis_potansiyeli")

        elif market == MarketType.US:
            result = await self._client.get_us_analyst_ratings(symbol)
            if result:
                current_price = result.get("current_price")
                if result.get("summary"):
                    s = result["summary"]
                    summary = AnalystSummary(
                        strong_buy=s.get("strong_buy") or 0,
                        buy=s.get("buy") or 0,
                        hold=s.get("hold") or 0,
                        sell=s.get("sell") or 0,
                        strong_sell=s.get("strong_sell") or 0,
                        mean_target=result.get("mean_target"),
                        low_target=result.get("low_target"),
                        high_target=result.get("high_target"),
                        consensus=s.get("consensus")
                    )
                upside = result.get("upside_potential")
                if result.get("ratings"):
                    for r in result["ratings"]:
                        ratings.append(AnalystRating(
                            firm=r.get("firm"),
                            rating=r.get("rating"),
                            price_target=r.get("price_target"),
                            date=r.get("date")
                        ))

        return AnalystDataResult(
            metadata=self._create_metadata(market, symbol_list, source, warnings=warnings),
            symbol=symbol.upper(),
            current_price=current_price,
            summary=summary,
            ratings=ratings,
            upside_potential=upside
        )

    # --- Dividends ---

    async def get_dividends(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> DividendResult:
        """Get dividend history and information."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "unknown"
        symbol = symbol_list[0]
        dividend_history = []
        stock_splits = []
        current_yield = None
        annual_dividend = None
        ex_date = None
        payout_ratio = None

        if market == MarketType.BIST:
            source = "yfinance"
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_temettu_ve_aksiyonlar_yfinance(ticker)
            if result:
                current_yield = result.get("temettu_verimi")
                if result.get("temettuler"):
                    for t in result["temettuler"]:
                        dividend_history.append(DividendInfo(
                            ex_date=t.get("tarih"),
                            amount=t.get("miktar"),
                            currency="TRY"
                        ))
                if result.get("bolunmeler"):
                    for s in result["bolunmeler"]:
                        stock_splits.append(StockSplitInfo(
                            date=s.get("tarih"),
                            ratio=s.get("oran")
                        ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_dividends(symbol)
            if result:
                current_yield = result.get("current_yield")
                annual_dividend = result.get("annual_dividend")
                ex_date = result.get("ex_dividend_date")
                payout_ratio = result.get("payout_ratio")
                if result.get("dividend_history"):
                    for d in result["dividend_history"]:
                        dividend_history.append(DividendInfo(
                            ex_date=d.get("ex_date"),
                            payment_date=d.get("payment_date"),
                            amount=d.get("amount"),
                            currency=d.get("currency")
                        ))
                if result.get("stock_splits"):
                    for s in result["stock_splits"]:
                        stock_splits.append(StockSplitInfo(
                            date=s.get("date"),
                            ratio=s.get("ratio")
                        ))

        return DividendResult(
            metadata=self._create_metadata(market, symbol_list, source),
            symbol=symbol.upper(),
            current_yield=current_yield,
            annual_dividend=annual_dividend,
            ex_dividend_date=ex_date,
            payout_ratio=payout_ratio,
            dividend_history=dividend_history,
            stock_splits=stock_splits
        )

    # --- Earnings ---

    async def get_earnings(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> EarningsResult:
        """Get earnings calendar and history."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "yfinance"
        symbol = symbol_list[0]
        next_date = None
        earnings_history = []
        growth_estimates = None

        if market == MarketType.BIST:
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_kazanc_takvimi_yfinance(ticker)
            if result and result.get("takvim"):
                t = result["takvim"]
                next_date = t.get("sonraki_kazanc_tarihi")
                if t.get("gecmis_kazanclar"):
                    for e in t["gecmis_kazanclar"]:
                        earnings_history.append(EarningsEvent(
                            date=e.get("tarih"),
                            eps_estimate=e.get("beklenen_hbk"),
                            eps_actual=e.get("gerceklesen_hbk"),
                            surprise_percent=e.get("surpriz_yuzdesi")
                        ))
                if t.get("buyume_verileri"):
                    g = t["buyume_verileri"]
                    growth_estimates = {
                        "current_qtr": g.get("mevcut_ceyrek"),
                        "next_qtr": g.get("sonraki_ceyrek"),
                        "current_year": g.get("mevcut_yil"),
                        "next_year": g.get("sonraki_yil")
                    }

        elif market == MarketType.US:
            result = await self._client.get_us_earnings(symbol)
            if result:
                next_date = result.get("next_earnings_date")
                if result.get("earnings_history"):
                    for e in result["earnings_history"]:
                        earnings_history.append(EarningsEvent(
                            date=e.get("date"),
                            eps_estimate=e.get("eps_estimate"),
                            eps_actual=e.get("eps_actual"),
                            revenue_estimate=e.get("revenue_estimate"),
                            revenue_actual=e.get("revenue_actual"),
                            surprise_percent=e.get("surprise_percent")
                        ))
                if result.get("growth_estimates"):
                    growth_estimates = result["growth_estimates"]

        return EarningsResult(
            metadata=self._create_metadata(market, symbol_list, source),
            symbol=symbol.upper(),
            next_earnings_date=next_date,
            earnings_history=earnings_history,
            growth_estimates=growth_estimates
        )

    # --- Financial Statements ---

    async def get_financial_statements(
        self,
        symbols: Union[str, List[str]],
        market: MarketType,
        statement_type: StatementType = StatementType.ALL,
        period: PeriodType = PeriodType.ANNUAL
    ) -> FinancialStatementsResult:
        """Get financial statements (balance sheet, income, cash flow)."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "unknown"
        statements = []
        warnings = []

        symbol = symbol_list[0]
        period_str = "annual" if period == PeriodType.ANNUAL else "quarterly"

        if market == MarketType.BIST:
            source = "isyatirim"
            types_to_fetch = []
            if statement_type in [StatementType.BALANCE, StatementType.ALL]:
                types_to_fetch.append(("balance", self._client.get_bilanco))
            if statement_type in [StatementType.INCOME, StatementType.ALL]:
                types_to_fetch.append(("income", self._client.get_kar_zarar))
            if statement_type in [StatementType.CASHFLOW, StatementType.ALL]:
                types_to_fetch.append(("cashflow", self._client.get_nakit_akisi))

            for stmt_name, fetch_func in types_to_fetch:
                try:
                    result = await fetch_func(symbol, period_str)
                    if result and result.get("donemler"):
                        stmt_type = StatementType(stmt_name)
                        statements.append(FinancialStatement(
                            symbol=symbol.upper(),
                            statement_type=stmt_type,
                            period=period,
                            periods=result["donemler"],
                            data=result.get("kalemler") or {},
                            currency="TRY"
                        ))
                except Exception as e:
                    warnings.append(f"Failed to fetch {stmt_name}: {str(e)}")

        elif market == MarketType.US:
            source = "yfinance"
            types_to_fetch = []
            if statement_type in [StatementType.BALANCE, StatementType.ALL]:
                types_to_fetch.append(("balance", self._client.get_us_balance_sheet))
            if statement_type in [StatementType.INCOME, StatementType.ALL]:
                types_to_fetch.append(("income", self._client.get_us_income_statement))
            if statement_type in [StatementType.CASHFLOW, StatementType.ALL]:
                types_to_fetch.append(("cashflow", self._client.get_us_cash_flow))

            for stmt_name, fetch_func in types_to_fetch:
                try:
                    result = await fetch_func(symbol, period_str)
                    if result and result.get("periods"):
                        stmt_type = StatementType(stmt_name)
                        statements.append(FinancialStatement(
                            symbol=symbol.upper(),
                            statement_type=stmt_type,
                            period=period,
                            periods=result["periods"],
                            data=result.get("data") or {},
                            currency=result.get("currency", "USD")
                        ))
                except Exception as e:
                    warnings.append(f"Failed to fetch {stmt_name}: {str(e)}")

        return FinancialStatementsResult(
            metadata=self._create_metadata(market, symbol_list, source, warnings=warnings),
            statements=statements
        )

    # --- Financial Ratios ---

    async def get_financial_ratios(
        self,
        symbol: str,
        market: MarketType,
        ratio_set: RatioSetType = RatioSetType.VALUATION
    ) -> FinancialRatiosResult:
        """Get financial ratios and analysis."""
        source = "unknown"
        valuation = None
        buffett = None
        core_health = None
        advanced = None
        insights = []
        ratio_warnings = []
        current_price = None

        if market == MarketType.BIST:
            source = "isyatirim"
            ticker = self._get_ticker_with_suffix(symbol, market)

            if ratio_set in [RatioSetType.VALUATION, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.get_finansal_oranlar(symbol)
                    if result and result.get("oranlar"):
                        o = result["oranlar"]
                        valuation = ValuationRatios(
                            pe_ratio=o.get("fk_orani"),
                            pb_ratio=o.get("pd_dd"),
                            ev_ebitda=o.get("fd_favok"),
                            ev_sales=o.get("fd_satislar")
                        )
                except Exception as e:
                    ratio_warnings.append(f"Valuation ratios error: {str(e)}")

            if ratio_set in [RatioSetType.BUFFETT, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_buffett_value_analysis(ticker)
                    if result:
                        buffett = BuffettMetrics(
                            owner_earnings=result.get("owner_earnings"),
                            oe_yield=result.get("oe_yield"),
                            dcf_intrinsic_value=result.get("dcf_fisher"),
                            safety_margin=result.get("safety_margin"),
                            buffett_score=result.get("buffett_score")
                        )
                        insights.extend(result.get("insights") or [])
                        ratio_warnings.extend(result.get("warnings") or [])
                except Exception as e:
                    ratio_warnings.append(f"Buffett analysis error: {str(e)}")

            if ratio_set in [RatioSetType.CORE_HEALTH, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_core_financial_health(ticker)
                    if result:
                        core_health = CoreHealthMetrics(
                            roe=result.get("roe"),
                            roic=result.get("roic"),
                            debt_to_equity=result.get("debt_to_equity"),
                            debt_to_assets=result.get("debt_to_assets"),
                            interest_coverage=result.get("interest_coverage"),
                            fcf_margin=result.get("fcf_margin"),
                            earnings_quality=result.get("earnings_quality"),
                            health_score=result.get("health_score")
                        )
                        insights.extend(result.get("insights") or [])
                except Exception as e:
                    ratio_warnings.append(f"Core health error: {str(e)}")

            if ratio_set in [RatioSetType.ADVANCED, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_advanced_metrics(ticker)
                    if result:
                        advanced = AdvancedMetrics(
                            altman_z_score=result.get("altman_z_score"),
                            financial_stability=result.get("financial_stability"),
                            real_revenue_growth=result.get("real_revenue_growth"),
                            real_earnings_growth=result.get("real_earnings_growth"),
                            growth_quality=result.get("growth_quality")
                        )
                except Exception as e:
                    ratio_warnings.append(f"Advanced metrics error: {str(e)}")

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_quick_info(symbol)
            if result and result.get("info"):
                i = result["info"]
                current_price = i.get("current_price")
                valuation = ValuationRatios(
                    pe_ratio=i.get("pe_ratio"),
                    pb_ratio=i.get("pb_ratio"),
                    ps_ratio=i.get("ps_ratio")
                )

        return FinancialRatiosResult(
            metadata=self._create_metadata(market, symbol, source, warnings=ratio_warnings),
            symbol=symbol.upper(),
            current_price=current_price,
            valuation=valuation,
            buffett=buffett,
            core_health=core_health,
            advanced=advanced,
            insights=insights,
            warnings=ratio_warnings
        )

    # --- Corporate Actions ---

    async def get_corporate_actions(
        self,
        symbols: Union[str, List[str]],
        market: MarketType = MarketType.BIST,
        year: Optional[int] = None
    ) -> CorporateActionsResult:
        """Get corporate actions (capital increases, dividends)."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "isyatirim"
        capital_increases = []
        dividend_history = []

        symbol = symbol_list[0]

        if market == MarketType.BIST:
            # Capital increases
            try:
                result = await self._client.get_sermaye_artirimlari(symbol, yil=year or 0)
                if result and result.get("sermaye_artirimlari"):
                    for sa in result["sermaye_artirimlari"]:
                        capital_increases.append(CapitalIncrease(
                            date=sa.get("tarih"),
                            type_code=sa.get("tip_kodu"),
                            type_tr=sa.get("tip"),
                            type_en=sa.get("tip_en"),
                            rights_issue_rate=sa.get("bedelli_oran"),
                            rights_issue_amount=sa.get("bedelli_tutar"),
                            bonus_internal_rate=sa.get("bedelsiz_ic_kaynak_oran"),
                            bonus_dividend_rate=sa.get("bedelsiz_temettu_oran"),
                            capital_before=sa.get("onceki_sermaye"),
                            capital_after=sa.get("sonraki_sermaye")
                        ))
            except Exception as e:
                logger.warning(f"Error fetching capital increases: {e}")

            # Dividend history from İş Yatırım
            try:
                result = await self._client.get_isyatirim_temettu(symbol, yil=year or 0)
                if result and result.get("temettuler"):
                    for t in result["temettuler"]:
                        dividend_history.append(DividendInfo(
                            ex_date=t.get("tarih"),
                            amount=t.get("toplam_tutar"),
                            yield_percent=t.get("brut_oran"),
                            currency="TRY",
                            type="cash"
                        ))
            except Exception as e:
                logger.warning(f"Error fetching dividend history: {e}")

        return CorporateActionsResult(
            metadata=self._create_metadata(market, symbol_list, source),
            symbol=symbol.upper(),
            capital_increases=capital_increases,
            dividend_history=dividend_history
        )

    # --- News ---

    async def get_news(
        self,
        symbol: Optional[str] = None,
        market: MarketType = MarketType.BIST,
        limit: int = 10
    ) -> NewsResult:
        """Get market news (KAP for BIST)."""
        source = "unknown"
        news_items = []

        if market == MarketType.BIST and symbol:
            source = "mynet"
            result = await self._client.get_kap_haberleri_mynet(symbol, limit=limit)
            if result and result.get("haberler"):
                for h in result["haberler"][:limit]:
                    news_items.append(NewsItem(
                        id=h.get("id"),
                        title=h.get("baslik"),
                        summary=h.get("ozet"),
                        source="KAP",
                        url=h.get("url"),
                        published_date=h.get("tarih"),
                        symbols=[symbol.upper()]
                    ))

        return NewsResult(
            metadata=self._create_metadata(market, symbol or "market", source),
            symbol=symbol.upper() if symbol else None,
            news=news_items
        )

    # --- Screener ---

    async def screen_securities(
        self,
        market: MarketType,
        preset: Optional[str] = None,
        security_type: Optional[str] = None,
        custom_filters: Optional[List[Any]] = None,
        limit: int = 25
    ) -> ScreenerResult:
        """Screen securities with presets or custom filters."""
        source = "yfscreen"
        stocks = []

        if market == MarketType.BIST:
            result = await self._client.screen_bist_stocks(
                preset=preset,
                custom_filters=custom_filters,
                limit=limit
            )
            if result and result.get("stocks"):
                for s in result["stocks"]:
                    stocks.append(ScreenedStock(
                        symbol=s.get("symbol"),
                        name=s.get("name"),
                        market=market,
                        sector=s.get("sector"),
                        market_cap=s.get("market_cap"),
                        price=s.get("price"),
                        change_percent=s.get("change_percent"),
                        volume=s.get("volume"),
                        pe_ratio=s.get("pe_ratio"),
                        dividend_yield=s.get("dividend_yield"),
                        additional_data={}
                    ))

        elif market == MarketType.US:
            result = await self._client.screen_us_securities(
                preset=preset,
                security_type=security_type,
                custom_filters=custom_filters,
                limit=limit
            )
            if result and result.get("stocks"):
                for s in result["stocks"]:
                    stocks.append(ScreenedStock(
                        symbol=s.get("symbol"),
                        name=s.get("name"),
                        market=market,
                        sector=s.get("sector"),
                        market_cap=s.get("market_cap"),
                        price=s.get("price"),
                        change_percent=s.get("change_percent"),
                        volume=s.get("volume"),
                        pe_ratio=s.get("pe_ratio"),
                        dividend_yield=s.get("dividend_yield"),
                        additional_data={}
                    ))

        return ScreenerResult(
            metadata=self._create_metadata(market, "screener", source),
            preset=preset,
            security_type=security_type,
            filters_applied=custom_filters,
            stocks=stocks,
            total_count=len(stocks)
        )

    # --- Scanner ---

    async def scan_stocks(
        self,
        index: str,
        market: MarketType = MarketType.BIST,
        condition: Optional[str] = None,
        preset: Optional[str] = None,
        timeframe: str = "1d"
    ) -> ScannerResult:
        """Scan stocks by technical conditions."""
        source = "borsapy"
        stocks = []

        if market == MarketType.BIST:
            if condition:
                result = await self._client.scan_bist_teknik(index, condition, timeframe)
            elif preset:
                result = await self._client.scan_bist_preset(index, preset, timeframe)
            else:
                result = await self._client.scan_bist_preset(index, "oversold", timeframe)

            if result and result.results:
                for h in result.results:
                    stocks.append(ScannedStock(
                        symbol=h.symbol,
                        name=h.name,
                        close=h.price,
                        change=h.change_percent,
                        volume=h.volume,
                        rsi=h.rsi,
                        macd=h.macd,
                        supertrend_direction=None,  # Not in TaramaSonucu model
                        t3=None,  # Not in TaramaSonucu model
                        additional_indicators={}
                    ))

        return ScannerResult(
            metadata=self._create_metadata(market, index, source),
            index=index,
            condition=condition,
            preset=preset,
            timeframe=timeframe,
            stocks=stocks,
            total_count=len(stocks)
        )

    # --- Crypto Market ---

    async def get_crypto_market(
        self,
        symbol: str,
        exchange: ExchangeType,
        data_type: DataType = DataType.TICKER
    ) -> CryptoMarketResult:
        """Get crypto market data."""
        market = MarketType.CRYPTO_TR if exchange == ExchangeType.BTCTURK else MarketType.CRYPTO_GLOBAL
        source = exchange.value
        ticker = None
        orderbook = None
        trades = None
        exchange_info = None

        if exchange == ExchangeType.BTCTURK:
            if data_type == DataType.TICKER:
                result = await self._client.get_kripto_ticker(pair_symbol=symbol)
                if result and result.ticker_data:
                    t = result.ticker_data[0]  # Get first ticker from list
                    ticker = CryptoTicker(
                        symbol=symbol,
                        pair=t.pair,
                        exchange=exchange,
                        price=t.last,
                        bid=t.bid,
                        ask=t.ask,
                        volume_24h=t.volume,
                        change_24h=t.dailyPercent,  # Correct attribute name
                        high_24h=t.high,
                        low_24h=t.low,
                        timestamp=t.timestamp
                    )
            elif data_type == DataType.ORDERBOOK:
                result = await self._client.get_kripto_orderbook(symbol)
                if result and result.orderbook:
                    ob = result.orderbook
                    orderbook = CryptoOrderbook(
                        symbol=symbol,
                        pair=symbol,
                        exchange=exchange,
                        bids=[CryptoOrderbookLevel(price=b[0], amount=b[1]) for b in ob.bids[:10]],
                        asks=[CryptoOrderbookLevel(price=a[0], amount=a[1]) for a in ob.asks[:10]],
                        timestamp=ob.timestamp.isoformat() if ob.timestamp else None
                    )
            elif data_type == DataType.TRADES:
                result = await self._client.get_kripto_trades(symbol)
                if result and result.trades:
                    trades = [
                        CryptoTrade(
                            price=t.price or 0.0,
                            amount=t.amount or 0.0,
                            side="unknown",  # BtcTurk doesn't provide side info
                            timestamp=t.date.isoformat() if t.date else ""
                        )
                        for t in result.trades[:20]
                    ]
            elif data_type == DataType.EXCHANGE_INFO:
                result = await self._client.get_kripto_exchange_info()
                if result:
                    exchange_info = {
                        "pairs_count": result.total_pairs,
                        "currencies_count": result.total_currencies
                    }

        elif exchange == ExchangeType.COINBASE:
            if data_type == DataType.TICKER:
                result = await self._client.get_coinbase_ticker(product_id=symbol)
                if result and result.ticker_data:
                    t = result.ticker_data[0]  # Get first ticker from list
                    ticker = CryptoTicker(
                        symbol=symbol,
                        pair=t.product_id,
                        exchange=exchange,
                        price=t.price,
                        bid=t.bid,
                        ask=t.ask,
                        volume_24h=t.volume_24h,
                        change_24h=t.price_percentage_change_24h,
                        high_24h=t.high_24h,
                        low_24h=t.low_24h,
                        timestamp=None  # CoinbaseTicker doesn't have time field
                    )
            elif data_type == DataType.ORDERBOOK:
                result = await self._client.get_coinbase_orderbook(symbol)
                if result and result.orderbook:
                    ob = result.orderbook
                    orderbook = CryptoOrderbook(
                        symbol=symbol,
                        pair=symbol,
                        exchange=exchange,
                        bids=[CryptoOrderbookLevel(price=float(b[0]), amount=float(b[1])) for b in ob.bids[:10]],
                        asks=[CryptoOrderbookLevel(price=float(a[0]), amount=float(a[1])) for a in ob.asks[:10]],
                        timestamp=None  # Coinbase orderbook doesn't have timestamp
                    )
            elif data_type == DataType.TRADES:
                result = await self._client.get_coinbase_trades(symbol)
                if result and result.trades:
                    trades = [
                        CryptoTrade(
                            price=t.price or 0.0,
                            amount=t.size or 0.0,
                            side=t.side or "unknown",
                            timestamp=t.time.isoformat() if t.time else ""
                        )
                        for t in result.trades[:20]
                    ]
            elif data_type == DataType.EXCHANGE_INFO:
                result = await self._client.get_coinbase_exchange_info()
                if result:
                    exchange_info = {
                        "products_count": result.total_pairs,
                        "currencies_count": result.total_currencies
                    }

        return CryptoMarketResult(
            metadata=self._create_metadata(market, symbol, source),
            data_type=data_type,
            ticker=ticker,
            orderbook=orderbook,
            trades=trades,
            exchange_info=exchange_info
        )

    # --- FX Data ---

    async def get_fx_data(
        self,
        symbols: Optional[List[str]] = None,
        category: Optional[str] = None,
        historical: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> FXResult:
        """Get foreign exchange rates."""
        source = "borsapy"
        rates = []
        historical_data = None

        if historical and symbols and len(symbols) == 1:
            result = await self._client.get_dovizcom_arsiv_veri(
                symbols[0], start_date or "", end_date or ""
            )
            if result and result.ohlc_verileri:
                historical_data = [
                    OHLCVData(
                        date=v.tarih.isoformat() if v.tarih else "",
                        open=v.acilis,
                        high=v.en_yuksek,
                        low=v.en_dusuk,
                        close=v.kapanis,
                        volume=None
                    )
                    for v in result.ohlc_verileri
                ]
        else:
            # Get current rates for specified symbols or all
            if symbols:
                for sym in symbols:
                    result = await self._client.get_dovizcom_guncel_kur(sym)
                    if result and result.guncel_deger is not None:
                        # Convert datetime to string if present
                        ts = result.son_guncelleme
                        timestamp_str = ts.isoformat() if ts else None
                        rates.append(FXRate(
                            symbol=sym,
                            name=result.varlik_adi or sym,
                            buy=None,  # Not available in current model
                            sell=result.guncel_deger,
                            change=result.degisim,
                            change_percent=result.degisim_yuzde,
                            high=None,  # Not available in current model
                            low=None,  # Not available in current model
                            timestamp=timestamp_str
                        ))

        return FXResult(
            metadata=self._create_metadata(MarketType.FX, symbols or ["all"], source),
            rates=rates,
            historical_data=historical_data
        )

    # --- Fund Data ---

    async def get_fund_data(
        self,
        symbol: str,
        include_portfolio: bool = False,
        include_performance: bool = False
    ) -> FundResult:
        """Get mutual fund data."""
        source = "tefas"
        fund_info = None
        portfolio = None
        performance = None

        result = await self._client.get_fund_detail(symbol)
        if result and result.fon_bilgisi:
            f = result.fon_bilgisi
            fund_info = FundInfo(
                code=f.fon_kodu,
                name=f.fon_adi,
                category=f.fon_turu,
                company=f.kurulus,
                price=f.fiyat,
                total_assets=f.toplam_deger,
                investor_count=f.yatirimci_sayisi
            )

        if include_portfolio:
            result = await self._client.get_fund_portfolio(symbol)
            if result and result.varlik_gruplari:
                portfolio = [
                    {"asset_type": g.grup_adi, "weight": g.yuzde, "value": g.deger}
                    for g in result.varlik_gruplari
                ]

        if include_performance:
            result = await self._client.get_fund_performance(symbol)
            if result and result.fiyat_noktalari:
                performance = [
                    {"date": p.tarih, "price": p.fiyat, "portfolio_size": p.portfoy_buyuklugu}
                    for p in result.fiyat_noktalari
                ]

        return FundResult(
            metadata=self._create_metadata(MarketType.FUND, symbol, source),
            fund=fund_info,
            portfolio=portfolio,
            performance_history=performance
        )

    # --- Index Data ---

    async def get_index_data(
        self,
        code: str,
        market: MarketType = MarketType.BIST,
        include_components: bool = False
    ) -> IndexResult:
        """Get stock market index data."""
        source = "unknown"
        index_info = None
        components = []

        if market == MarketType.BIST:
            source = "kap"
            result = await self._client.search_indices_from_kap(code)
            if result and result.sonuclar:
                idx = result.sonuclar[0]
                index_info = IndexInfo(
                    code=idx.endeks_kodu,
                    name=idx.endeks_adi,
                    market=market
                )

            if include_components:
                result = await self._client.get_endeks_sirketleri(code)
                if result and result.sirketler:
                    for s in result.sirketler:
                        components.append(IndexComponent(
                            symbol=s.ticker_kodu,
                            name=s.sirket_adi,
                            weight=None,  # Not available in model
                            sector=None   # Not available in model
                        ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_index_info(code)
            if result and result.get("index"):
                idx = result["index"]
                index_info = IndexInfo(
                    code=idx.get("symbol"),
                    name=idx.get("name"),
                    market=market,
                    value=idx.get("value"),
                    change=idx.get("change"),
                    change_percent=idx.get("change_percent"),
                    components_count=idx.get("components_count")
                )

        return IndexResult(
            metadata=self._create_metadata(market, code, source),
            index=index_info,
            components=components
        )

    # --- Sector Comparison ---

    async def get_sector_comparison(
        self,
        symbol: str,
        market: MarketType
    ) -> SectorComparisonResult:
        """Get sector comparison for a stock."""
        source = "yfinance"
        sector = None
        industry = None
        peers = []
        avg_pe = None
        avg_pb = None

        if market == MarketType.BIST:
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_sektor_karsilastirmasi_yfinance([ticker])
            if result:
                sector = result.get("sektor")
                industry = result.get("sanayi")
                avg_pe = result.get("sektor_ortalama_fk")
                avg_pb = result.get("sektor_ortalama_pddd")
                if result.get("rakipler"):
                    for p in result["rakipler"]:
                        peers.append(SectorStock(
                            symbol=p.get("sembol"),
                            name=p.get("ad"),
                            market_cap=p.get("piyasa_degeri"),
                            pe_ratio=p.get("fk_orani"),
                            pb_ratio=p.get("pd_dd"),
                            dividend_yield=p.get("temettu_verimi"),
                            change_percent=p.get("degisim_yuzdesi")
                        ))

        elif market == MarketType.US:
            result = await self._client.get_us_sector_comparison([symbol])
            if result:
                sector = result.get("sector")
                industry = result.get("industry")
                avg_pe = result.get("sector_avg_pe")
                avg_pb = result.get("sector_avg_pb")
                if result.get("peers"):
                    for p in result["peers"]:
                        peers.append(SectorStock(
                            symbol=p.get("symbol"),
                            name=p.get("name"),
                            market_cap=p.get("market_cap"),
                            pe_ratio=p.get("pe_ratio"),
                            pb_ratio=p.get("pb_ratio"),
                            roe=p.get("roe"),
                            dividend_yield=p.get("dividend_yield"),
                            change_percent=p.get("change_percent")
                        ))

        return SectorComparisonResult(
            metadata=self._create_metadata(market, symbol, source),
            symbol=symbol.upper(),
            sector=sector,
            industry=industry,
            sector_average_pe=avg_pe,
            sector_average_pb=avg_pb,
            peers=peers
        )


    # --- News Detail (Phase 2) ---

    async def get_news_detail(
        self,
        news_id: str,
        page: int = 1
    ) -> NewsDetailResult:
        """Get detailed news content by news ID/URL."""
        source = "mynet"

        # If news_id is just an ID (not a full URL), construct the full URL
        if news_id.startswith("http"):
            news_url = news_id
        else:
            # Mynet URL format: https://finans.mynet.com/borsa/haberdetay/{news_id}/
            news_url = f"https://finans.mynet.com/borsa/haberdetay/{news_id}/"

        result = await self._client.get_kap_haber_detayi_mynet(news_url, page)

        title = ""
        content = None
        summary = None
        url = None
        published_date = None
        symbols = []
        total_pages = None

        if result:
            title = result.get("baslik", "")
            content = result.get("icerik", "")
            summary = result.get("ozet", "")
            url = result.get("url", news_id)
            published_date = result.get("tarih", "")
            symbols = result.get("semboller", [])
            total_pages = result.get("toplam_sayfa", 1)

        return NewsDetailResult(
            metadata=self._create_metadata(MarketType.BIST, news_id, source),
            news_id=news_id,
            title=title,
            content=content,
            summary=summary,
            source="KAP",
            url=url,
            published_date=published_date,
            symbols=symbols,
            page=page,
            total_pages=total_pages
        )

    # --- Islamic Finance Compliance (Phase 4) ---

    async def get_islamic_compliance(
        self,
        symbol: str
    ) -> IslamicComplianceInfo:
        """Get Islamic finance (katılım finans) compliance status for a BIST stock."""
        result = await self._client.get_katilim_finans_uygunluk(symbol)

        is_compliant = False
        compliance_status = "Bilinmiyor"
        compliance_details = None
        last_updated = None

        if result:
            is_compliant = result.get("uygun", False)
            compliance_status = result.get("durum", "Bilinmiyor")
            compliance_details = result.get("detay", "")
            last_updated = result.get("guncelleme_tarihi", "")

        return IslamicComplianceInfo(
            is_compliant=is_compliant,
            compliance_status=compliance_status,
            compliance_details=compliance_details,
            source="kap",
            last_updated=last_updated
        )

    # --- Fund Comparison (Phase 5) ---

    async def compare_funds(
        self,
        fund_codes: List[str],
        fund_type: str = "EMK",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> FundComparisonResult:
        """Compare multiple funds side by side."""
        source = "tefas"

        result = await self._client.compare_funds_advanced(
            fund_codes=fund_codes,
            fund_type=fund_type,
            start_date=start_date,
            end_date=end_date
        )

        funds = []
        comparison_date = None

        if result and result.get("funds"):
            for f in result["funds"]:
                funds.append(FundComparisonItem(
                    code=f.get("kod", ""),
                    name=f.get("ad", ""),
                    category=f.get("kategori", ""),
                    company=f.get("kurulus", ""),
                    price=f.get("fiyat"),
                    daily_return=f.get("gunluk_getiri"),
                    weekly_return=f.get("haftalik_getiri"),
                    monthly_return=f.get("aylik_getiri"),
                    three_month_return=f.get("uc_aylik_getiri"),
                    six_month_return=f.get("alti_aylik_getiri"),
                    ytd_return=f.get("yilbasi_getiri"),
                    one_year_return=f.get("yillik_getiri"),
                    total_assets=f.get("toplam_deger")
                ))
            comparison_date = result.get("tarih")

        return FundComparisonResult(
            metadata=self._create_metadata(MarketType.FUND, fund_codes, source),
            funds=funds,
            comparison_date=comparison_date
        )

    # --- Macro Data (Phase 6) ---

    async def get_macro_data(
        self,
        data_type: str,  # inflation, calculate
        inflation_type: Optional[str] = "tufe",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        basket_value: float = 100.0,
        limit: Optional[int] = None
    ) -> MacroDataResult:
        """Get Turkish macro economic data."""
        source = "tcmb"
        inflation_data = None
        calculation = None

        if data_type == "inflation":
            result = await self._client.get_turkiye_enflasyon(
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )

            # Result is TcmbEnflasyonSonucu Pydantic model
            if result and hasattr(result, 'data') and result.data:
                inflation_data = []
                for d in result.data:
                    # d is EnflasyonVerisi Pydantic model
                    inflation_data.append(InflationData(
                        date=d.tarih,
                        rate=d.yillik_enflasyon or 0.0,
                        change=d.aylik_enflasyon,
                        cumulative=None  # Not available in TCMB data
                    ))

        elif data_type == "calculate":
            if all([start_year, start_month, end_year, end_month]):
                result = await self._client.calculate_inflation(
                    start_year=start_year,
                    start_month=start_month,
                    end_year=end_year,
                    end_month=end_month,
                    basket_value=basket_value
                )

                # Result is EnflasyonHesaplamaSonucu Pydantic model
                if result and hasattr(result, 'yeni_sepet_degeri'):
                    # Parse Turkish formatted string values to float
                    # Turkish format: thousands separator is ".", decimal is ","
                    # Example: "6.013,10" = 6013.10
                    def tr_to_float(s: str) -> float:
                        if not s:
                            return 0.0
                        # Remove thousands separator (.) then replace decimal (,) with (.)
                        return float(s.replace('.', '').replace(',', '.'))

                    final_value = tr_to_float(result.yeni_sepet_degeri) if result.yeni_sepet_degeri else basket_value
                    total_change = tr_to_float(result.toplam_degisim) if result.toplam_degisim else 0.0
                    cumulative = (total_change / basket_value) * 100 if basket_value > 0 else 0.0
                    period_months = result.toplam_yil * 12 + result.toplam_ay

                    calculation = InflationCalculation(
                        start_period=f"{start_year}-{start_month:02d}",
                        end_period=f"{end_year}-{end_month:02d}",
                        initial_value=basket_value,
                        final_value=final_value,
                        cumulative_inflation=cumulative,
                        period_months=period_months
                    )

        return MacroDataResult(
            metadata=self._create_metadata(MarketType.FX, [data_type], source),
            data_type=data_type,
            inflation_type=inflation_type if data_type == "inflation" else None,
            inflation_data=inflation_data,
            calculation=calculation
        )

    # --- Screener Help (Phase 7) ---

    async def get_screener_help(
        self,
        market: MarketType
    ) -> ScreenerHelpResult:
        """Get screener help with presets and filter documentation."""
        source = "yfscreen" if market == MarketType.US else "borsapy"
        presets = []
        filters = []
        operators = ["eq", "gt", "lt", "btwn"]
        examples = []

        if market == MarketType.US:
            # US market - yfscreen
            preset_result = await self._client.get_us_screener_presets()
            if preset_result and preset_result.get("presets"):
                for p in preset_result["presets"]:
                    presets.append(PresetInfo(
                        name=p.get("name", ""),
                        description=p.get("description", ""),
                        filters=p.get("filters"),
                        security_type=p.get("security_type")
                    ))

            # Filter documentation
            filter_result = await self._client.get_us_screener_filter_docs()
            if filter_result and filter_result.get("filters"):
                for f in filter_result["filters"]:
                    filters.append(FilterInfo(
                        field=f.get("field", ""),
                        description=f.get("description", ""),
                        operators=f.get("operators", operators),
                        examples=f.get("examples"),
                        value_type=f.get("value_type")
                    ))

            examples = [
                '[["eq", ["sector", "Technology"]]]',
                '[["gt", ["intradaymarketcap", 10000000000]]]',
                '[["lt", ["pegratio", 1]]]'
            ]

        elif market == MarketType.BIST:
            # BIST market - borsapy
            preset_result = await self._client.get_bist_screener_presets()
            if preset_result and preset_result.get("presets"):
                for p in preset_result["presets"]:
                    presets.append(PresetInfo(
                        name=p.get("name", ""),
                        description=p.get("description", ""),
                        filters=p.get("filters")
                    ))

            filter_result = await self._client.get_bist_screener_filter_docs()
            if filter_result and filter_result.get("filters"):
                for f in filter_result["filters"]:
                    filters.append(FilterInfo(
                        field=f.get("field", ""),
                        description=f.get("description", ""),
                        operators=f.get("operators", operators),
                        examples=f.get("examples"),
                        value_type=f.get("value_type")
                    ))

            examples = [
                "sector == 'Bankacılık'",
                "market_cap > 10000000000",
                "pe_ratio < 15"
            ]

        return ScreenerHelpResult(
            metadata=self._create_metadata(market, ["help"], source),
            market=market.value,
            presets=presets,
            filters=filters,
            operators=operators,
            example_queries=examples
        )

    # --- Scanner Help (Phase 8) ---

    async def get_scanner_help(self) -> ScannerHelpResult:
        """Get BIST scanner help with indicators, operators, and presets."""
        source = "borsapy"

        result = await self._client.get_scan_yardim()

        indicators = []
        operators = [">", "<", ">=", "<=", "==", "and", "or"]
        presets = []
        indices = ["XU030", "XU100", "XBANK", "XUSIN", "XUMAL", "XUHIZ", "XUTEK",
                   "XHOLD", "XGIDA", "XELKT", "XILTM", "XK100", "XK050", "XK030"]
        timeframes = ["1d", "1h", "4h", "1W"]
        examples = [
            "RSI < 30",
            "RSI > 70",
            "supertrend_direction == 1",
            "close > t3 and RSI > 50",
            "macd > 0 and volume > 10000000"
        ]

        if result:
            # Parse indicators from result (TaramaYardimSonucu model)
            # indicators is Dict[str, List[str]] - flatten to IndicatorInfo list
            if hasattr(result, 'indicators') and result.indicators:
                indicator_examples = {
                    "RSI": ("Relative Strength Index (0-100)", "0-100", "RSI < 30"),
                    "macd": ("MACD histogram", None, "macd > 0"),
                    "volume": ("Trading volume", None, "volume > 10000000"),
                    "change": ("Daily change percentage", None, "change > 3"),
                    "close": ("Closing price", None, "close > sma_50"),
                    "SMA": ("Simple Moving Average (sma_50, sma_200)", None, "close > sma_50"),
                    "EMA": ("Exponential Moving Average (ema_20)", None, "close > ema_20"),
                    "market_cap": ("Market capitalization", None, "market_cap > 10000000000"),
                    "supertrend_direction": ("Supertrend direction (1=bullish, -1=bearish)", "-1 to 1", "supertrend_direction == 1"),
                    "t3": ("Tilson T3 Moving Average", None, "close > t3"),
                }
                # Flatten dict to list
                for category, ind_list in result.indicators.items():
                    for ind_name in ind_list:
                        info = indicator_examples.get(ind_name, (f"{ind_name} indicator", None, None))
                        indicators.append(IndicatorInfo(
                            name=ind_name,
                            description=info[0],
                            range=info[1],
                            example=info[2]
                        ))
            else:
                # Fallback to known indicators
                indicators = [
                    IndicatorInfo(name="RSI", description="Relative Strength Index (0-100)", range="0-100", example="RSI < 30"),
                    IndicatorInfo(name="macd", description="MACD histogram", range=None, example="macd > 0"),
                    IndicatorInfo(name="volume", description="Trading volume", range=None, example="volume > 10000000"),
                    IndicatorInfo(name="change", description="Daily change percentage", range=None, example="change > 3"),
                    IndicatorInfo(name="close", description="Closing price", range=None, example="close > sma_50"),
                    IndicatorInfo(name="sma_50", description="50-day Simple Moving Average", range=None, example="close > sma_50"),
                    IndicatorInfo(name="ema_20", description="20-day Exponential Moving Average", range=None, example="close > ema_20"),
                    IndicatorInfo(name="supertrend_direction", description="Supertrend direction (1=bullish, -1=bearish)", range="-1 to 1", example="supertrend_direction == 1"),
                    IndicatorInfo(name="t3", description="Tilson T3 Moving Average", range=None, example="close > t3"),
                    IndicatorInfo(name="bb_upper", description="Bollinger Band Upper", range=None, example="close > bb_upper"),
                    IndicatorInfo(name="bb_lower", description="Bollinger Band Lower", range=None, example="close < bb_lower"),
                ]

            # Parse presets from result (List[TaramaPresetInfo] - Pydantic models)
            if hasattr(result, 'presets') and result.presets:
                for p in result.presets:
                    # p is TaramaPresetInfo Pydantic model - use attribute access
                    # filters expects List[str], condition is a single string
                    condition = p.condition if hasattr(p, 'condition') else None
                    presets.append(PresetInfo(
                        name=p.name,
                        description=p.description,
                        filters=[condition] if condition else None
                    ))
            else:
                # Fallback to known presets
                presets = [
                    PresetInfo(name="oversold", description="RSI < 30 (Oversold stocks)"),
                    PresetInfo(name="overbought", description="RSI > 70 (Overbought stocks)"),
                    PresetInfo(name="bullish_momentum", description="RSI > 50 and MACD > 0"),
                    PresetInfo(name="bearish_momentum", description="RSI < 50 and MACD < 0"),
                    PresetInfo(name="supertrend_bullish", description="Supertrend direction = 1 (Bullish)"),
                    PresetInfo(name="supertrend_bearish", description="Supertrend direction = -1 (Bearish)"),
                    PresetInfo(name="t3_bullish", description="Price above T3"),
                    PresetInfo(name="t3_bearish", description="Price below T3"),
                    PresetInfo(name="high_volume", description="Volume > 10M"),
                    PresetInfo(name="big_gainers", description="Daily change > 3%"),
                    PresetInfo(name="big_losers", description="Daily change < -3%"),
                ]

        return ScannerHelpResult(
            metadata=self._create_metadata(MarketType.BIST, ["help"], source),
            available_indicators=indicators,
            available_operators=operators,
            available_presets=presets,
            available_indices=indices,
            available_timeframes=timeframes,
            example_conditions=examples
        )

    # --- Regulations (Phase 9) ---

    async def get_regulations(
        self,
        regulation_type: str = "fund"
    ) -> RegulationsResult:
        """Get Turkish financial regulations."""
        source = "mevzuat"
        items = []
        last_updated = None

        if regulation_type == "fund":
            result = await self._client.get_fon_mevzuati()

            if result and hasattr(result, 'maddeler'):
                for m in result.maddeler:
                    items.append(RegulationItem(
                        title=m.baslik if hasattr(m, 'baslik') else "",
                        content=m.icerik if hasattr(m, 'icerik') else "",
                        category=m.kategori if hasattr(m, 'kategori') else None
                    ))
                last_updated = result.guncelleme_tarihi if hasattr(result, 'guncelleme_tarihi') else None

        return RegulationsResult(
            metadata=self._create_metadata(MarketType.FUND, [regulation_type], source),
            regulation_type=regulation_type,
            items=items,
            last_updated=last_updated
        )


# Global router instance
market_router = MarketRouter()
