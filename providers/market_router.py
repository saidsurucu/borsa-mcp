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
            # Result is {'bilgiler': SirketProfiliYFinance(...)} - Pydantic model
            if result and result.get("bilgiler"):
                p = result["bilgiler"]  # SirketProfiliYFinance Pydantic model
                profile = CompanyProfile(
                    symbol=getattr(p, 'symbol', symbol.upper()),
                    name=getattr(p, 'longName', None) or symbol.upper(),
                    market=market,
                    description=getattr(p, 'longBusinessSummary', None),
                    sector=getattr(p, 'sector', None),
                    industry=getattr(p, 'industry', None),
                    country=getattr(p, 'country', None),
                    website=getattr(p, 'website', None),
                    employees=getattr(p, 'fullTimeEmployees', None),
                    market_cap=getattr(p, 'marketCap', None),
                    currency=getattr(p, 'currency', 'TRY'),
                    exchange="BIST",
                    pe_ratio=getattr(p, 'trailingPE', None),
                    pb_ratio=None,  # Not in SirketProfiliYFinance
                    dividend_yield=getattr(p, 'dividendYield', None),
                    beta=getattr(p, 'beta', None),
                    current_price=None,  # Not in SirketProfiliYFinance
                    day_high=None,
                    day_low=None,
                    volume=None,
                    avg_volume=None,
                    week_52_high=getattr(p, 'fiftyTwoWeekHigh', None),
                    week_52_low=getattr(p, 'fiftyTwoWeekLow', None)
                )

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_company_profile(symbol)
            # Result is {'bilgiler': SirketProfiliYFinance(...)} - Pydantic model
            if result and result.get("bilgiler"):
                p = result["bilgiler"]  # SirketProfiliYFinance Pydantic model
                profile = CompanyProfile(
                    symbol=getattr(p, 'symbol', symbol.upper()),
                    name=getattr(p, 'longName', None) or symbol.upper(),
                    market=market,
                    description=getattr(p, 'longBusinessSummary', None),
                    sector=getattr(p, 'sector', None),
                    industry=getattr(p, 'industry', None),
                    country=getattr(p, 'country', None),
                    website=getattr(p, 'website', None),
                    employees=getattr(p, 'fullTimeEmployees', None),
                    market_cap=getattr(p, 'marketCap', None),
                    currency=getattr(p, 'currency', 'USD'),
                    exchange="US",
                    pe_ratio=getattr(p, 'trailingPE', None),
                    pb_ratio=None,
                    dividend_yield=getattr(p, 'dividendYield', None),
                    beta=getattr(p, 'beta', None),
                    current_price=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    avg_volume=None,
                    week_52_high=getattr(p, 'fiftyTwoWeekHigh', None),
                    week_52_low=getattr(p, 'fiftyTwoWeekLow', None)
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
                # Multi-ticker returns a dict, not Pydantic model
                data_list = result.get("data") if isinstance(result, dict) else (result.data if hasattr(result, 'data') else None)
                if result and data_list:
                    for item in data_list:
                        # item is dict with hizli_bilgi key or Pydantic model
                        if isinstance(item, dict):
                            b = item.get("hizli_bilgi")
                        else:
                            b = item.hizli_bilgi if hasattr(item, 'hizli_bilgi') else item
                        if b:
                            results.append(QuickInfo(
                                symbol=getattr(b, 'symbol', ''),
                                name=getattr(b, 'long_name', None) or getattr(b, 'symbol', ''),
                                market=market,
                                currency=getattr(b, 'currency', 'TRY'),
                                current_price=getattr(b, 'last_price', None),
                                change_percent=None,
                                volume=getattr(b, 'volume', None),
                                market_cap=getattr(b, 'market_cap', None),
                                pe_ratio=getattr(b, 'pe_ratio', None),
                                pb_ratio=getattr(b, 'price_to_book', None),
                                roe=getattr(b, 'return_on_equity', None),
                                dividend_yield=getattr(b, 'dividend_yield', None),
                                week_52_high=getattr(b, 'fifty_two_week_high', None),
                                week_52_low=getattr(b, 'fifty_two_week_low', None),
                                avg_volume=getattr(b, 'average_volume', None),
                                beta=getattr(b, 'beta', None)
                            ))
                    warnings = result.get("warnings", []) if isinstance(result, dict) else (result.warnings if hasattr(result, 'warnings') else [])
            else:
                result = await self._client.get_hizli_bilgi(symbol_list[0])
                # Result is {'hizli_bilgi': HizliBilgi(...)}
                if result and result.get("hizli_bilgi"):
                    b = result["hizli_bilgi"]  # HizliBilgi Pydantic model
                    results.append(QuickInfo(
                        symbol=getattr(b, 'symbol', symbol_list[0]),
                        name=getattr(b, 'long_name', None) or getattr(b, 'symbol', symbol_list[0]),
                        market=market,
                        currency=getattr(b, 'currency', 'TRY'),
                        current_price=getattr(b, 'last_price', None),
                        change_percent=None,
                        volume=getattr(b, 'volume', None),
                        market_cap=getattr(b, 'market_cap', None),
                        pe_ratio=getattr(b, 'pe_ratio', None),
                        pb_ratio=getattr(b, 'price_to_book', None),
                        roe=getattr(b, 'return_on_equity', None),
                        dividend_yield=getattr(b, 'dividend_yield', None),
                        week_52_high=getattr(b, 'fifty_two_week_high', None),
                        week_52_low=getattr(b, 'fifty_two_week_low', None),
                        avg_volume=getattr(b, 'average_volume', None),
                        beta=getattr(b, 'beta', None)
                    ))

        elif market == MarketType.US:
            source = "yfinance"
            if is_multi:
                result = await self._client.get_us_quick_info_multi(symbol_list)
                # Multi-ticker returns a dict, not Pydantic model
                data_list = result.get("data") if isinstance(result, dict) else (result.data if hasattr(result, 'data') else None)
                if result and data_list:
                    for item in data_list:
                        # item is dict with bilgiler key or Pydantic model
                        if isinstance(item, dict):
                            i = item.get("bilgiler")
                        else:
                            i = item.bilgiler if hasattr(item, 'bilgiler') else item
                        if i:
                            results.append(QuickInfo(
                                symbol=getattr(i, 'symbol', ''),
                                name=getattr(i, 'long_name', None) or getattr(i, 'symbol', ''),
                                market=market,
                                currency=getattr(i, 'currency', 'USD'),
                                current_price=getattr(i, 'last_price', None),
                                change_percent=None,
                                volume=getattr(i, 'volume', None),
                                market_cap=getattr(i, 'market_cap', None),
                                pe_ratio=getattr(i, 'pe_ratio', None),
                                pb_ratio=getattr(i, 'price_to_book', None),
                                ps_ratio=None,
                                roe=getattr(i, 'return_on_equity', None),
                                dividend_yield=getattr(i, 'dividend_yield', None),
                                week_52_high=getattr(i, 'fifty_two_week_high', None),
                                week_52_low=getattr(i, 'fifty_two_week_low', None),
                                avg_volume=getattr(i, 'average_volume', None),
                                beta=getattr(i, 'beta', None)
                            ))
                    warnings = result.get("warnings", []) if isinstance(result, dict) else (result.warnings if hasattr(result, 'warnings') else [])
            else:
                result = await self._client.get_us_quick_info(symbol_list[0])
                # Result is {'bilgiler': HizliBilgi(...), 'ticker': ...}
                if result and result.get("bilgiler"):
                    i = result["bilgiler"]  # HizliBilgi Pydantic model
                    results.append(QuickInfo(
                        symbol=getattr(i, 'symbol', symbol_list[0]),
                        name=getattr(i, 'long_name', None) or getattr(i, 'symbol', symbol_list[0]),
                        market=market,
                        currency=getattr(i, 'currency', 'USD'),
                        current_price=getattr(i, 'last_price', None),
                        change_percent=None,
                        volume=getattr(i, 'volume', None),
                        market_cap=getattr(i, 'market_cap', None),
                        pe_ratio=getattr(i, 'pe_ratio', None),
                        pb_ratio=getattr(i, 'price_to_book', None),
                        ps_ratio=None,
                        roe=getattr(i, 'return_on_equity', None),
                        dividend_yield=getattr(i, 'dividend_yield', None),
                        week_52_high=getattr(i, 'fifty_two_week_high', None),
                        week_52_low=getattr(i, 'fifty_two_week_low', None),
                        avg_volume=getattr(i, 'average_volume', None),
                        beta=getattr(i, 'beta', None)
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
            # Result has 'data' key with list of dicts
            if result and result.get("data"):
                for dp in result["data"]:
                    date_val = dp.get("tarih")
                    date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val)
                    data_points.append(OHLCVData(
                        date=date_str,
                        open=dp.get("acilis") or 0.0,
                        high=dp.get("en_yuksek") or 0.0,
                        low=dp.get("en_dusuk") or 0.0,
                        close=dp.get("kapanis") or 0.0,
                        volume=int(dp.get("hacim") or 0),
                        adj_close=None
                    ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_stock_data(
                symbol,
                period=period or "1mo",
                start_date=start_date,
                end_date=end_date
            )
            # Result has 'data_points' key with list of dicts
            if result and result.get("data_points"):
                for dp in result["data_points"]:
                    date_val = dp.get("date")
                    date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val)
                    data_points.append(OHLCVData(
                        date=date_str,
                        open=dp.get("open") or 0.0,
                        high=dp.get("high") or 0.0,
                        low=dp.get("low") or 0.0,
                        close=dp.get("close") or 0.0,
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
            if result:
                # Get current price from fiyat_analizi
                if result.get("fiyat_analizi"):
                    current_price = result["fiyat_analizi"].get("guncel_fiyat")
                # Get technical indicators from teknik_indiktorler
                if result.get("teknik_indiktorler"):
                    ind = result["teknik_indiktorler"]
                    indicators = TechnicalIndicators(
                        rsi_14=ind.get("rsi_14"),
                        macd=ind.get("macd"),
                        macd_signal=ind.get("macd_signal"),
                        macd_histogram=ind.get("macd_histogram"),
                        bb_upper=ind.get("bb_upper"),
                        bb_middle=ind.get("bb_middle"),
                        bb_lower=ind.get("bb_lower")
                    )
                # Get moving averages from hareketli_ortalamalar
                if result.get("hareketli_ortalamalar"):
                    ma = result["hareketli_ortalamalar"]
                    moving_averages = MovingAverages(
                        sma_5=ma.get("sma_5"),
                        sma_10=ma.get("sma_10"),
                        sma_20=ma.get("sma_20"),
                        sma_50=ma.get("sma_50"),
                        sma_200=ma.get("sma_200"),
                        ema_5=ma.get("ema_5"),
                        ema_10=ma.get("ema_10"),
                        ema_20=ma.get("ema_20") or ma.get("ema_12"),
                        ema_50=ma.get("ema_50") or ma.get("ema_26"),
                        ema_200=ma.get("ema_200")
                    )
                # Get trend analysis from trend_analizi
                if result.get("trend_analizi"):
                    t = result["trend_analizi"]
                    signals = TechnicalSignals(
                        trend=t.get("kisa_vadeli_trend"),
                        rsi_signal=result.get("al_sat_sinyali"),
                        macd_signal=result.get("sinyal_aciklamasi"),
                        bb_signal=None
                    )

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
            # API expects symbol without .IS suffix
            result = await self._client.get_pivot_points(symbol.upper())
            if result:
                # Get current status from mevcut_durum
                if result.get("mevcut_durum"):
                    md = result["mevcut_durum"]
                    current_price = md.get("mevcut_fiyat")
                    position = md.get("pozisyon")
                    nearest_support = md.get("en_yakin_destek")
                    nearest_resistance = md.get("en_yakin_direnç") or md.get("en_yakin_direnc")
                # Get previous day data from onceki_gun
                if result.get("onceki_gun"):
                    og = result["onceki_gun"]
                    prev_high = og.get("yuksek")
                    prev_low = og.get("dusuk")
                    prev_close = og.get("kapanis")
                # Get pivot levels from pivot_noktalari
                if result.get("pivot_noktalari"):
                    pn = result["pivot_noktalari"]
                    levels = PivotLevels(
                        pivot=pn.get("pp"),
                        r1=pn.get("r1"),
                        r2=pn.get("r2"),
                        r3=pn.get("r3"),
                        s1=pn.get("s1"),
                        s2=pn.get("s2"),
                        s3=pn.get("s3")
                    )

        elif market == MarketType.US:
            result = await self._client.get_us_pivot_points(symbol)
            if result:
                current_price = result.get("guncel_fiyat")
                # US API doesn't return previous OHLC separately
                prev_high = result.get("previous_high")
                prev_low = result.get("previous_low")
                prev_close = result.get("previous_close")
                # Pivot levels are at top level
                if result.get("pivot_point"):
                    levels = PivotLevels(
                        pivot=result.get("pivot_point"),
                        r1=result.get("r1"),
                        r2=result.get("r2"),
                        r3=result.get("r3"),
                        s1=result.get("s1"),
                        s2=result.get("s2"),
                        s3=result.get("s3")
                    )
                position = result.get("pozisyon")
                # Convert level names (e.g., "S1") to actual values
                support_level = result.get("en_yakin_destek")
                resist_level = result.get("en_yakin_direnc")
                level_map = {
                    "S1": result.get("s1"), "S2": result.get("s2"), "S3": result.get("s3"),
                    "R1": result.get("r1"), "R2": result.get("r2"), "R3": result.get("r3"),
                    "PP": result.get("pivot_point")
                }
                nearest_support = level_map.get(support_level) if isinstance(support_level, str) else support_level
                nearest_resistance = level_map.get(resist_level) if isinstance(resist_level, str) else resist_level

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
                # tavsiye_ozeti is a Pydantic model TavsiyeOzeti
                if result.get("tavsiye_ozeti"):
                    s = result["tavsiye_ozeti"]
                    # Get price targets from fiyat_hedefleri (list of AnalistFiyatHedefi)
                    mean_target = None
                    low_target = None
                    high_target = None
                    if result.get("fiyat_hedefleri"):
                        fh = result["fiyat_hedefleri"]
                        if fh and len(fh) > 0:
                            # fh[0] is AnalistFiyatHedefi Pydantic model
                            mean_target = getattr(fh[0], 'ortalama', None)
                            low_target = getattr(fh[0], 'dusuk', None)
                            high_target = getattr(fh[0], 'yuksek', None)
                            current_price = getattr(fh[0], 'guncel', None)
                    summary = AnalystSummary(
                        strong_buy=0,  # BIST doesn't have strong_buy/strong_sell
                        buy=getattr(s, 'satin_al', 0) or 0,
                        hold=getattr(s, 'tut', 0) or 0,
                        sell=getattr(s, 'sat', 0) or 0,
                        strong_sell=0,
                        mean_target=mean_target,
                        low_target=low_target,
                        high_target=high_target,
                        consensus=None
                    )

        elif market == MarketType.US:
            result = await self._client.get_us_analyst_ratings(symbol)
            if result:
                # fiyat_hedefleri is a Pydantic model AnalistFiyatHedefi
                if result.get("fiyat_hedefleri"):
                    fh = result["fiyat_hedefleri"]
                    current_price = getattr(fh, 'guncel', None)
                    mean_target = getattr(fh, 'ortalama', None)
                    low_target = getattr(fh, 'dusuk', None)
                    high_target = getattr(fh, 'yuksek', None)
                    # Calculate upside potential
                    if current_price and mean_target:
                        upside = ((mean_target - current_price) / current_price) * 100
                # tavsiye_ozeti is a Pydantic model TavsiyeOzeti
                if result.get("tavsiye_ozeti"):
                    s = result["tavsiye_ozeti"]
                    summary = AnalystSummary(
                        strong_buy=0,  # Not directly available in this API
                        buy=getattr(s, 'satin_al', 0) + getattr(s, 'fazla_agirlik', 0),  # satin_al + fazla_agirlik
                        hold=getattr(s, 'tut', 0) or 0,
                        sell=getattr(s, 'sat', 0) + getattr(s, 'dusuk_agirlik', 0),  # sat + dusuk_agirlik
                        strong_sell=0,
                        mean_target=mean_target if 'mean_target' in dir() else None,
                        low_target=low_target if 'low_target' in dir() else None,
                        high_target=high_target if 'high_target' in dir() else None,
                        consensus=None
                    )
                # tavsiyeler is a list of AnalistTavsiyesi Pydantic models
                if result.get("tavsiyeler"):
                    for r in result["tavsiyeler"][:10]:  # Limit to 10 ratings
                        date_str = getattr(r, 'tarih', None)
                        if hasattr(date_str, 'isoformat'):
                            date_str = date_str.isoformat()
                        ratings.append(AnalystRating(
                            firm=getattr(r, 'firma', None),
                            rating=getattr(r, 'guncel_derece', None),
                            price_target=None,  # Not available in this format
                            date=str(date_str) if date_str else None
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
                # Get dividend yield from 12-month total
                if result.get("toplam_temettu_12ay"):
                    annual_dividend = result["toplam_temettu_12ay"]
                # Process Pydantic Temettu models
                if result.get("temettuler"):
                    for t in result["temettuler"]:
                        date_str = t.tarih.isoformat() if hasattr(t.tarih, 'isoformat') else str(t.tarih)
                        dividend_history.append(DividendInfo(
                            ex_date=date_str,
                            amount=t.miktar,
                            currency="TRY"
                        ))
                # Process Pydantic HisseBolunmesi models
                if result.get("bolunmeler"):
                    for s in result["bolunmeler"]:
                        date_str = s.tarih.isoformat() if hasattr(s.tarih, 'isoformat') else str(s.tarih)
                        stock_splits.append(StockSplitInfo(
                            date=date_str,
                            ratio=str(s.oran)
                        ))

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_dividends(symbol)
            if result:
                # Same structure as BIST - uses temettuler and bolunmeler keys
                if result.get("toplam_temettu_12ay"):
                    annual_dividend = result["toplam_temettu_12ay"]
                # Process Pydantic Temettu models
                if result.get("temettuler"):
                    for t in result["temettuler"]:
                        date_str = t.tarih.isoformat() if hasattr(t.tarih, 'isoformat') else str(t.tarih)
                        dividend_history.append(DividendInfo(
                            ex_date=date_str,
                            amount=t.miktar,
                            currency="USD"
                        ))
                # Process Pydantic HisseBolunmesi models
                if result.get("bolunmeler"):
                    for s in result["bolunmeler"]:
                        date_str = s.tarih.isoformat() if hasattr(s.tarih, 'isoformat') else str(s.tarih)
                        stock_splits.append(StockSplitInfo(
                            date=date_str,
                            ratio=str(s.oran)
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
            if result:
                # Get next earnings date from calendar or growth data
                if result.get("kazanc_takvimi"):
                    cal = result["kazanc_takvimi"]
                    if hasattr(cal, 'gelecek_kazanc_tarihi') and cal.gelecek_kazanc_tarihi:
                        next_date = cal.gelecek_kazanc_tarihi.isoformat() if hasattr(cal.gelecek_kazanc_tarihi, 'isoformat') else str(cal.gelecek_kazanc_tarihi)
                elif result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    if hasattr(bv, 'sonraki_kazanc_tarihi') and bv.sonraki_kazanc_tarihi:
                        next_date = bv.sonraki_kazanc_tarihi.isoformat() if hasattr(bv.sonraki_kazanc_tarihi, 'isoformat') else str(bv.sonraki_kazanc_tarihi)
                # Process Pydantic KazancTarihi models
                if result.get("kazanc_tarihleri"):
                    for e in result["kazanc_tarihleri"]:
                        date_str = e.tarih.isoformat() if hasattr(e.tarih, 'isoformat') else str(e.tarih)
                        earnings_history.append(EarningsEvent(
                            date=date_str,
                            eps_estimate=e.eps_tahmini,
                            eps_actual=e.rapor_edilen_eps,
                            surprise_percent=e.surpriz_yuzdesi
                        ))
                # Get growth estimates from buyume_verileri
                if result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    growth_estimates = {
                        "annual_earnings_growth": getattr(bv, 'yillik_kazanc_buyumesi', None),
                        "quarterly_earnings_growth": getattr(bv, 'ceyreklik_kazanc_buyumesi', None)
                    }

        elif market == MarketType.US:
            result = await self._client.get_us_earnings(symbol)
            if result:
                # Same structure as BIST - uses kazanc_tarihleri and buyume_verileri
                if result.get("kazanc_takvimi"):
                    cal = result["kazanc_takvimi"]
                    if hasattr(cal, 'gelecek_kazanc_tarihi') and cal.gelecek_kazanc_tarihi:
                        next_date = cal.gelecek_kazanc_tarihi.isoformat() if hasattr(cal.gelecek_kazanc_tarihi, 'isoformat') else str(cal.gelecek_kazanc_tarihi)
                elif result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    if hasattr(bv, 'sonraki_kazanc_tarihi') and bv.sonraki_kazanc_tarihi:
                        next_date = bv.sonraki_kazanc_tarihi.isoformat() if hasattr(bv.sonraki_kazanc_tarihi, 'isoformat') else str(bv.sonraki_kazanc_tarihi)
                # Process Pydantic KazancTarihi models
                if result.get("kazanc_tarihleri"):
                    for e in result["kazanc_tarihleri"]:
                        date_str = e.tarih.isoformat() if hasattr(e.tarih, 'isoformat') else str(e.tarih)
                        earnings_history.append(EarningsEvent(
                            date=date_str,
                            eps_estimate=e.eps_tahmini,
                            eps_actual=e.rapor_edilen_eps,
                            surprise_percent=e.surpriz_yuzdesi
                        ))
                # Get growth estimates from buyume_verileri
                if result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    growth_estimates = {
                        "annual_earnings_growth": getattr(bv, 'yillik_kazanc_buyumesi', None),
                        "quarterly_earnings_growth": getattr(bv, 'ceyreklik_kazanc_buyumesi', None)
                    }

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
                    # Return format is {"tablo": [{"Kalem": "...", "2024-09-30": 123, ...}, ...]}
                    if result and result.get("tablo"):
                        tablo = result["tablo"]
                        periods_list = []
                        data_dict = {}
                        if tablo:
                            # Extract and sort periods (newest first)
                            periods_list = sorted([k for k in tablo[0].keys() if k != "Kalem"], reverse=True)
                            # Convert tablo to data dict: {"Current Assets": [123, 456, ...], ...}
                            # Values are lists ordered by periods_list
                            for row in tablo:
                                item_name = row.get("Kalem", "Unknown")
                                data_dict[item_name] = [row.get(p) for p in periods_list]
                        stmt_type = StatementType(stmt_name)
                        statements.append(FinancialStatement(
                            symbol=symbol.upper(),
                            statement_type=stmt_type,
                            period=period,
                            periods=periods_list,
                            data=data_dict,
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
                    # Same format as BIST: {"tablo": [{"Kalem": "...", "2024-09-30": 123, ...}, ...]}
                    if result and result.get("tablo"):
                        tablo = result["tablo"]
                        periods_list = []
                        data_dict = {}
                        if tablo:
                            # Extract and sort periods (newest first)
                            periods_list = sorted([k for k in tablo[0].keys() if k != "Kalem"], reverse=True)
                            # Convert tablo to data dict: {"Current Assets": [123, 456, ...], ...}
                            for row in tablo:
                                item_name = row.get("Kalem", "Unknown")
                                data_dict[item_name] = [row.get(p) for p in periods_list]
                        stmt_type = StatementType(stmt_name)
                        statements.append(FinancialStatement(
                            symbol=symbol.upper(),
                            statement_type=stmt_type,
                            period=period,
                            periods=periods_list,
                            data=data_dict,
                            currency="USD"
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
                    # Ratios are at top level, not nested under "oranlar"
                    if result and not result.get("error"):
                        current_price = result.get("kapanis_fiyati")
                        valuation = ValuationRatios(
                            pe_ratio=result.get("fk_orani"),
                            pb_ratio=result.get("pd_dd"),
                            ev_ebitda=result.get("fd_favok"),
                            ev_sales=result.get("fd_satislar")
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
            # Return format is {"bilgiler": HizliBilgi(...)} - a Pydantic model
            if result and result.get("bilgiler"):
                b = result["bilgiler"]  # HizliBilgi Pydantic model
                current_price = getattr(b, 'last_price', None)
                valuation = ValuationRatios(
                    pe_ratio=getattr(b, 'pe_ratio', None),
                    pb_ratio=getattr(b, 'price_to_book', None),
                    ps_ratio=None  # Not available in HizliBilgi
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
            # Return format is {"kap_haberleri": [...]} not {"haberler": [...]}
            if result and result.get("kap_haberleri"):
                for h in result["kap_haberleri"][:limit]:
                    news_items.append(NewsItem(
                        id=h.get("haber_id"),
                        title=h.get("baslik"),
                        summary=h.get("title_attr"),  # Use title_attr as summary
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
            # Return format is {"results": [...]} with "ticker" field not "symbol"
            if result and result.get("results"):
                for s in result["results"]:
                    stocks.append(ScreenedStock(
                        symbol=s.get("ticker"),
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
            # Return format is {"results": [...]} with "ticker" field not "symbol"
            if result and result.get("results"):
                for s in result["results"]:
                    stocks.append(ScreenedStock(
                        symbol=s.get("ticker"),
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
                        timestamp=t.timestamp.isoformat() if t.timestamp else None
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
        if result and result.fon_kodu:
            # Read from flat fields (provider returns flat structure)
            fund_info = FundInfo(
                code=result.fon_kodu,
                name=result.fon_adi,
                category=result.fon_turu,
                company=result.kurulus,
                price=result.fiyat,
                total_assets=result.toplam_deger,
                investor_count=result.yatirimci_sayisi
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
                # Extract from sirket_verileri (company data list)
                sirket_verileri = result.get("sirket_verileri", [])
                if sirket_verileri:
                    first_company = sirket_verileri[0]
                    sector = first_company.get("sektor")

                # Extract from sektor_ozeti (sector summary)
                sektor_ozeti = result.get("sektor_ozeti", {})
                if sektor_ozeti and sector:
                    sector_data = sektor_ozeti.get(sector, {})
                    avg_pe = sector_data.get("ortalama_fk")
                    avg_pb = sector_data.get("ortalama_pd_dd")

                # Add all companies as peers
                for p in sirket_verileri:
                    ticker_code = p.get("ticker", "").replace(".IS", "")
                    company_name = p.get("sirket_adi") or ticker_code  # Use ticker as fallback
                    peers.append(SectorStock(
                        symbol=ticker_code,
                        name=company_name,
                        market_cap=p.get("piyasa_degeri"),
                        pe_ratio=p.get("fk_orani"),
                        pb_ratio=p.get("pd_dd"),
                        roe=p.get("roe"),
                        dividend_yield=None,
                        change_percent=float(p.get("yillik_getiri")) if p.get("yillik_getiri") else None
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

            if result:
                # FonMevzuatSonucu has icerik (content) as a single string, not maddeler (items)
                content = result.icerik if hasattr(result, 'icerik') and result.icerik else ""
                title = result.baslik if hasattr(result, 'baslik') and result.baslik else "Yatırım Fonlarına İlişkin Rehber"
                if content:
                    items.append(RegulationItem(
                        title=title,
                        content=content[:2000] + "..." if len(content) > 2000 else content,  # Truncate for display
                        category="SPK Fund Regulation"
                    ))
                last_updated = result.son_guncelleme if hasattr(result, 'son_guncelleme') else None

        return RegulationsResult(
            metadata=self._create_metadata(MarketType.FUND, [regulation_type], source),
            regulation_type=regulation_type,
            items=items,
            last_updated=last_updated
        )


# Global router instance
market_router = MarketRouter()
