"""
Market Router for unified tools.
Routes requests to appropriate providers based on market type.
Uses BorsaApiClient as the underlying service layer.

NOTE: This module returns raw dicts, not Pydantic models, to avoid validation overhead.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import logging

from models.unified_base import (
    MarketType, StatementType, PeriodType, DataType, RatioSetType, ExchangeType
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
    ) -> Dict[str, Any]:
        """Create unified metadata for responses as raw dict (no Pydantic validation)."""
        if isinstance(symbols, str):
            symbols = [symbols]
        return {
            "market": market.value if hasattr(market, 'value') else str(market),
            "symbols": symbols,
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "successful_count": successful,
            "failed_count": failed,
            "warnings": warnings or []
        }

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
    ) -> Dict[str, Any]:
        """Search for symbols across markets. Returns raw dict (no Pydantic validation)."""
        matches = []
        source = "unknown"

        if market == MarketType.BIST:
            source = "kap"
            result = await self._client.search_companies_from_kap(query)
            if result and result.sonuclar:
                for company in result.sonuclar[:limit]:
                    matches.append({
                        "symbol": company.ticker_kodu,
                        "name": company.sirket_adi,
                        "market": "bist",
                        "asset_type": "stock",
                        "exchange": "BIST"
                    })

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.search_us_stock(query)
            if result and result.get("found") and result.get("info"):
                info = result["info"]
                matches.append({
                    "symbol": info.get("symbol", query.upper()),
                    "name": info.get("name", query.upper()),
                    "market": "us",
                    "asset_type": info.get("quote_type", "equity"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "exchange": info.get("exchange"),
                    "currency": info.get("currency", "USD")
                })

        elif market == MarketType.FUND:
            source = "tefas"
            result = await self._client.search_funds(query, limit=limit)
            if result and result.sonuclar:
                for fund in result.sonuclar[:limit]:
                    matches.append({
                        "symbol": fund.fon_kodu,
                        "name": fund.fon_adi,
                        "market": "fund",
                        "asset_type": "mutual_fund",
                        "currency": "TRY"
                    })

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_exchange_info()
            if result and result.trading_pairs:
                query_upper = query.upper()
                for pair in result.trading_pairs:
                    pair_symbol = pair.symbol or pair.name or ""
                    if query_upper in pair_symbol:
                        matches.append({
                            "symbol": pair_symbol,
                            "name": pair_symbol,
                            "market": "crypto_tr",
                            "asset_type": "crypto",
                            "exchange": "btcturk"
                        })
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
                        matches.append({
                            "symbol": product_id,
                            "name": product.base_name or product_id,
                            "market": "crypto_global",
                            "asset_type": "crypto",
                            "exchange": "coinbase",
                            "currency": product.quote_name
                        })
                        if len(matches) >= limit:
                            break

        return {
            "metadata": self._create_metadata(market, query, source),
            "matches": matches,
            "total_count": len(matches)
        }

    # --- Company Profile ---

    async def get_profile(
        self,
        symbol: str,
        market: MarketType
    ) -> Dict[str, Any]:
        """Get company profile. Returns raw dict (no Pydantic validation)."""
        profile = None
        source = "unknown"

        if market == MarketType.BIST:
            source = "yfinance"
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_sirket_bilgileri_yfinance(ticker)
            if result and result.get("bilgiler"):
                p = result["bilgiler"]
                profile = {
                    "symbol": getattr(p, 'symbol', symbol.upper()),
                    "name": getattr(p, 'longName', None) or symbol.upper(),
                    "market": "bist",
                    "description": getattr(p, 'longBusinessSummary', None),
                    "sector": getattr(p, 'sector', None),
                    "industry": getattr(p, 'industry', None),
                    "country": getattr(p, 'country', None),
                    "website": getattr(p, 'website', None),
                    "employees": getattr(p, 'fullTimeEmployees', None),
                    "market_cap": getattr(p, 'marketCap', None),
                    "currency": getattr(p, 'currency', 'TRY'),
                    "exchange": "BIST",
                    "pe_ratio": getattr(p, 'trailingPE', None),
                    "dividend_yield": getattr(p, 'dividendYield', None),
                    "beta": getattr(p, 'beta', None),
                    "week_52_high": getattr(p, 'fiftyTwoWeekHigh', None),
                    "week_52_low": getattr(p, 'fiftyTwoWeekLow', None)
                }

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_company_profile(symbol)
            if result and result.get("bilgiler"):
                p = result["bilgiler"]
                profile = {
                    "symbol": getattr(p, 'symbol', symbol.upper()),
                    "name": getattr(p, 'longName', None) or symbol.upper(),
                    "market": "us",
                    "description": getattr(p, 'longBusinessSummary', None),
                    "sector": getattr(p, 'sector', None),
                    "industry": getattr(p, 'industry', None),
                    "country": getattr(p, 'country', None),
                    "website": getattr(p, 'website', None),
                    "employees": getattr(p, 'fullTimeEmployees', None),
                    "market_cap": getattr(p, 'marketCap', None),
                    "currency": getattr(p, 'currency', 'USD'),
                    "exchange": "US",
                    "pe_ratio": getattr(p, 'trailingPE', None),
                    "dividend_yield": getattr(p, 'dividendYield', None),
                    "beta": getattr(p, 'beta', None),
                    "week_52_high": getattr(p, 'fiftyTwoWeekHigh', None),
                    "week_52_low": getattr(p, 'fiftyTwoWeekLow', None)
                }

        elif market == MarketType.FUND:
            source = "tefas"
            result = await self._client.get_fund_detail(symbol)
            if result and result.fon:
                f = result.fon
                profile = {
                    "symbol": f.profil.kod if f.profil else symbol,
                    "name": f.profil.ad if f.profil else symbol,
                    "market": "fund",
                    "description": f.profil.kategori if f.profil else None,
                    "currency": "TRY"
                }

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "profile": profile
        }

    # --- Quick Info ---

    async def get_quick_info(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get quick info for single or multiple symbols. Returns raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "unknown"
        results = []
        warnings = []

        if market == MarketType.BIST:
            source = "yfinance"
            if is_multi:
                result = await self._client.get_hizli_bilgi_multi(symbol_list)
                data_list = result.get("data") if isinstance(result, dict) else (result.data if hasattr(result, 'data') else None)
                if result and data_list:
                    for item in data_list:
                        if isinstance(item, dict):
                            b = item.get("hizli_bilgi")
                        else:
                            b = item.hizli_bilgi if hasattr(item, 'hizli_bilgi') else item
                        if b:
                            results.append({
                                "symbol": getattr(b, 'symbol', ''),
                                "name": getattr(b, 'long_name', None) or getattr(b, 'symbol', ''),
                                "market": "bist",
                                "currency": getattr(b, 'currency', 'TRY'),
                                "current_price": getattr(b, 'last_price', None),
                                "change_percent": None,
                                "volume": getattr(b, 'volume', None),
                                "market_cap": getattr(b, 'market_cap', None),
                                "pe_ratio": getattr(b, 'pe_ratio', None),
                                "pb_ratio": getattr(b, 'price_to_book', None),
                                "roe": getattr(b, 'return_on_equity', None),
                                "dividend_yield": getattr(b, 'dividend_yield', None),
                                "week_52_high": getattr(b, 'fifty_two_week_high', None),
                                "week_52_low": getattr(b, 'fifty_two_week_low', None),
                                "avg_volume": getattr(b, 'average_volume', None),
                                "beta": getattr(b, 'beta', None)
                            })
                    warnings = result.get("warnings", []) if isinstance(result, dict) else (result.warnings if hasattr(result, 'warnings') else [])
            else:
                result = await self._client.get_hizli_bilgi(symbol_list[0])
                if result and result.get("hizli_bilgi"):
                    b = result["hizli_bilgi"]
                    results.append({
                        "symbol": getattr(b, 'symbol', symbol_list[0]),
                        "name": getattr(b, 'long_name', None) or getattr(b, 'symbol', symbol_list[0]),
                        "market": "bist",
                        "currency": getattr(b, 'currency', 'TRY'),
                        "current_price": getattr(b, 'last_price', None),
                        "change_percent": None,
                        "volume": getattr(b, 'volume', None),
                        "market_cap": getattr(b, 'market_cap', None),
                        "pe_ratio": getattr(b, 'pe_ratio', None),
                        "pb_ratio": getattr(b, 'price_to_book', None),
                        "roe": getattr(b, 'return_on_equity', None),
                        "dividend_yield": getattr(b, 'dividend_yield', None),
                        "week_52_high": getattr(b, 'fifty_two_week_high', None),
                        "week_52_low": getattr(b, 'fifty_two_week_low', None),
                        "avg_volume": getattr(b, 'average_volume', None),
                        "beta": getattr(b, 'beta', None)
                    })

        elif market == MarketType.US:
            source = "yfinance"
            if is_multi:
                result = await self._client.get_us_quick_info_multi(symbol_list)
                data_list = result.get("data") if isinstance(result, dict) else (result.data if hasattr(result, 'data') else None)
                if result and data_list:
                    for item in data_list:
                        if isinstance(item, dict):
                            i = item.get("bilgiler")
                        else:
                            i = item.bilgiler if hasattr(item, 'bilgiler') else item
                        if i:
                            results.append({
                                "symbol": getattr(i, 'symbol', ''),
                                "name": getattr(i, 'long_name', None) or getattr(i, 'symbol', ''),
                                "market": "us",
                                "currency": getattr(i, 'currency', 'USD'),
                                "current_price": getattr(i, 'last_price', None),
                                "change_percent": None,
                                "volume": getattr(i, 'volume', None),
                                "market_cap": getattr(i, 'market_cap', None),
                                "pe_ratio": getattr(i, 'pe_ratio', None),
                                "pb_ratio": getattr(i, 'price_to_book', None),
                                "ps_ratio": None,
                                "roe": getattr(i, 'return_on_equity', None),
                                "dividend_yield": getattr(i, 'dividend_yield', None),
                                "week_52_high": getattr(i, 'fifty_two_week_high', None),
                                "week_52_low": getattr(i, 'fifty_two_week_low', None),
                                "avg_volume": getattr(i, 'average_volume', None),
                                "beta": getattr(i, 'beta', None)
                            })
                    warnings = result.get("warnings", []) if isinstance(result, dict) else (result.warnings if hasattr(result, 'warnings') else [])
            else:
                result = await self._client.get_us_quick_info(symbol_list[0])
                if result and result.get("bilgiler"):
                    i = result["bilgiler"]
                    results.append({
                        "symbol": getattr(i, 'symbol', symbol_list[0]),
                        "name": getattr(i, 'long_name', None) or getattr(i, 'symbol', symbol_list[0]),
                        "market": "us",
                        "currency": getattr(i, 'currency', 'USD'),
                        "current_price": getattr(i, 'last_price', None),
                        "change_percent": None,
                        "volume": getattr(i, 'volume', None),
                        "market_cap": getattr(i, 'market_cap', None),
                        "pe_ratio": getattr(i, 'pe_ratio', None),
                        "pb_ratio": getattr(i, 'price_to_book', None),
                        "ps_ratio": None,
                        "roe": getattr(i, 'return_on_equity', None),
                        "dividend_yield": getattr(i, 'dividend_yield', None),
                        "week_52_high": getattr(i, 'fifty_two_week_high', None),
                        "week_52_low": getattr(i, 'fifty_two_week_low', None),
                        "avg_volume": getattr(i, 'average_volume', None),
                        "beta": getattr(i, 'beta', None)
                    })

        data = results if is_multi else (results[0] if results else None)
        return {
            "metadata": self._create_metadata(
                market, symbol_list, source,
                successful=len(results),
                failed=len(symbol_list) - len(results),
                warnings=warnings
            ),
            "data": data
        }

    # --- Historical Data ---

    async def get_historical_data(
        self,
        symbol: str,
        market: MarketType,
        period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """Get historical OHLCV data. Returns raw dict."""
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
            if result and result.get("data"):
                for dp in result["data"]:
                    date_val = dp.get("tarih")
                    date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val)
                    data_points.append({
                        "date": date_str,
                        "open": dp.get("acilis") or 0.0,
                        "high": dp.get("en_yuksek") or 0.0,
                        "low": dp.get("en_dusuk") or 0.0,
                        "close": dp.get("kapanis") or 0.0,
                        "volume": int(dp.get("hacim") or 0),
                        "adj_close": None
                    })

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_stock_data(
                symbol,
                period=period or "1mo",
                start_date=start_date,
                end_date=end_date
            )
            if result and result.get("data_points"):
                for dp in result["data_points"]:
                    date_val = dp.get("date")
                    date_str = date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val)
                    data_points.append({
                        "date": date_str,
                        "open": dp.get("open") or 0.0,
                        "high": dp.get("high") or 0.0,
                        "low": dp.get("low") or 0.0,
                        "close": dp.get("close") or 0.0,
                        "volume": dp.get("volume"),
                        "adj_close": dp.get("adj_close")
                    })

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_ohlc(symbol)
            if result and result.ohlc_data:
                for dp in result.ohlc_data:
                    data_points.append({
                        "date": dp.timestamp,
                        "open": dp.open,
                        "high": dp.high,
                        "low": dp.low,
                        "close": dp.close,
                        "volume": int(dp.volume) if dp.volume else None
                    })

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_ohlc(symbol)
            if result and result.candles:
                for dp in result.candles:
                    data_points.append({
                        "date": dp.time,
                        "open": dp.open,
                        "high": dp.high,
                        "low": dp.low,
                        "close": dp.close,
                        "volume": int(dp.volume) if dp.volume else None
                    })

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "symbol": symbol.upper(),
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "data": data_points,
            "data_points": len(data_points)
        }

    # --- Technical Analysis ---

    async def get_technical_analysis(
        self,
        symbol: str,
        market: MarketType,
        timeframe: str = "1d"
    ) -> Dict[str, Any]:
        """Get technical analysis indicators. Returns raw dict."""
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
                if result.get("fiyat_analizi"):
                    current_price = result["fiyat_analizi"].get("guncel_fiyat")
                if result.get("teknik_indiktorler"):
                    ind = result["teknik_indiktorler"]
                    indicators = {
                        "rsi_14": ind.get("rsi_14"),
                        "macd": ind.get("macd"),
                        "macd_signal": ind.get("macd_signal"),
                        "macd_histogram": ind.get("macd_histogram"),
                        "bb_upper": ind.get("bb_upper"),
                        "bb_middle": ind.get("bb_middle"),
                        "bb_lower": ind.get("bb_lower")
                    }
                if result.get("hareketli_ortalamalar"):
                    ma = result["hareketli_ortalamalar"]
                    moving_averages = {
                        "sma_5": ma.get("sma_5"),
                        "sma_10": ma.get("sma_10"),
                        "sma_20": ma.get("sma_20"),
                        "sma_50": ma.get("sma_50"),
                        "sma_200": ma.get("sma_200"),
                        "ema_5": ma.get("ema_5"),
                        "ema_10": ma.get("ema_10"),
                        "ema_20": ma.get("ema_20") or ma.get("ema_12"),
                        "ema_50": ma.get("ema_50") or ma.get("ema_26"),
                        "ema_200": ma.get("ema_200")
                    }
                if result.get("trend_analizi"):
                    t = result["trend_analizi"]
                    signals = {
                        "trend": t.get("kisa_vadeli_trend"),
                        "rsi_signal": result.get("al_sat_sinyali"),
                        "macd_signal": result.get("sinyal_aciklamasi"),
                        "bb_signal": None
                    }

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_technical_analysis(symbol)
            if result and result.get("indicators"):
                ind = result["indicators"]
                current_price = result.get("current_price")
                moving_averages = {
                    "sma_5": ind.get("sma_5"),
                    "sma_10": ind.get("sma_10"),
                    "sma_20": ind.get("sma_20"),
                    "sma_50": ind.get("sma_50"),
                    "sma_200": ind.get("sma_200"),
                    "ema_5": ind.get("ema_5"),
                    "ema_10": ind.get("ema_10"),
                    "ema_20": ind.get("ema_20"),
                    "ema_50": ind.get("ema_50"),
                    "ema_200": ind.get("ema_200")
                }
                indicators = {
                    "rsi_14": ind.get("rsi_14"),
                    "macd": ind.get("macd"),
                    "macd_signal": ind.get("macd_signal"),
                    "macd_histogram": ind.get("macd_histogram"),
                    "bb_upper": ind.get("bb_upper"),
                    "bb_middle": ind.get("bb_middle"),
                    "bb_lower": ind.get("bb_lower")
                }
                if result.get("trend"):
                    t = result["trend"]
                    if isinstance(t, str):
                        signals = {
                            "trend": t,
                            "rsi_signal": None,
                            "macd_signal": None,
                            "bb_signal": None
                        }
                    else:
                        signals = {
                            "trend": t.get("overall_trend"),
                            "rsi_signal": t.get("rsi_signal"),
                            "macd_signal": t.get("macd_signal"),
                            "bb_signal": t.get("bollinger_position")
                        }

        elif market == MarketType.CRYPTO_TR:
            source = "btcturk"
            result = await self._client.get_kripto_teknik_analiz(symbol)
            if result and result.indikatorler:
                ind = result.indikatorler
                current_price = result.guncel_fiyat
                moving_averages = {
                    "sma_5": ind.sma_5,
                    "sma_10": ind.sma_10,
                    "sma_20": ind.sma_20,
                    "sma_50": ind.sma_50,
                    "sma_200": ind.sma_200,
                    "ema_5": ind.ema_5,
                    "ema_10": ind.ema_10,
                    "ema_20": ind.ema_20,
                    "ema_50": ind.ema_50,
                    "ema_200": ind.ema_200
                }
                indicators = {
                    "rsi_14": ind.rsi_14,
                    "macd": ind.macd,
                    "macd_signal": ind.macd_sinyal,
                    "macd_histogram": ind.macd_histogram,
                    "bb_upper": ind.bb_ust,
                    "bb_middle": ind.bb_orta,
                    "bb_lower": ind.bb_alt
                }

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_teknik_analiz(symbol)
            if result and result.indikatorler:
                ind = result.indikatorler
                current_price = result.guncel_fiyat
                moving_averages = {
                    "sma_5": ind.sma_5,
                    "sma_10": ind.sma_10,
                    "sma_20": ind.sma_20,
                    "sma_50": ind.sma_50,
                    "sma_200": ind.sma_200,
                    "ema_5": ind.ema_5,
                    "ema_10": ind.ema_10,
                    "ema_20": ind.ema_20,
                    "ema_50": ind.ema_50,
                    "ema_200": ind.ema_200
                }
                indicators = {
                    "rsi_14": ind.rsi_14,
                    "macd": ind.macd,
                    "macd_signal": ind.macd_sinyal,
                    "macd_histogram": ind.macd_histogram,
                    "bb_upper": ind.bb_ust,
                    "bb_middle": ind.bb_orta,
                    "bb_lower": ind.bb_alt
                }

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "current_price": current_price,
            "moving_averages": moving_averages,
            "indicators": indicators,
            "signals": signals,
            "volume_analysis": volume_analysis
        }

    # --- Pivot Points ---

    async def get_pivot_points(
        self,
        symbol: str,
        market: MarketType
    ) -> Dict[str, Any]:
        """Get pivot points (support/resistance levels). Returns raw dict."""
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
            result = await self._client.get_pivot_points(symbol.upper())
            if result:
                if result.get("mevcut_durum"):
                    md = result["mevcut_durum"]
                    current_price = md.get("mevcut_fiyat")
                    position = md.get("pozisyon")
                    nearest_support = md.get("en_yakin_destek")
                    nearest_resistance = md.get("en_yakin_direnç") or md.get("en_yakin_direnc")
                if result.get("onceki_gun"):
                    og = result["onceki_gun"]
                    prev_high = og.get("yuksek")
                    prev_low = og.get("dusuk")
                    prev_close = og.get("kapanis")
                if result.get("pivot_noktalari"):
                    pn = result["pivot_noktalari"]
                    levels = {
                        "pivot": pn.get("pp"),
                        "r1": pn.get("r1"),
                        "r2": pn.get("r2"),
                        "r3": pn.get("r3"),
                        "s1": pn.get("s1"),
                        "s2": pn.get("s2"),
                        "s3": pn.get("s3")
                    }

        elif market == MarketType.US:
            result = await self._client.get_us_pivot_points(symbol)
            if result:
                current_price = result.get("guncel_fiyat")
                prev_high = result.get("previous_high")
                prev_low = result.get("previous_low")
                prev_close = result.get("previous_close")
                if result.get("pivot_point"):
                    levels = {
                        "pivot": result.get("pivot_point"),
                        "r1": result.get("r1"),
                        "r2": result.get("r2"),
                        "r3": result.get("r3"),
                        "s1": result.get("s1"),
                        "s2": result.get("s2"),
                        "s3": result.get("s3")
                    }
                position = result.get("pozisyon")
                support_level = result.get("en_yakin_destek")
                resist_level = result.get("en_yakin_direnc")
                level_map = {
                    "S1": result.get("s1"), "S2": result.get("s2"), "S3": result.get("s3"),
                    "R1": result.get("r1"), "R2": result.get("r2"), "R3": result.get("r3"),
                    "PP": result.get("pivot_point")
                }
                nearest_support = level_map.get(support_level) if isinstance(support_level, str) else support_level
                nearest_resistance = level_map.get(resist_level) if isinstance(resist_level, str) else resist_level

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "symbol": symbol.upper(),
            "current_price": current_price,
            "previous_high": prev_high,
            "previous_low": prev_low,
            "previous_close": prev_close,
            "levels": levels,
            "position": position,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance
        }

    # --- Analyst Data ---

    async def get_analyst_data(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get analyst ratings and recommendations. Returns raw dict."""
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
                if result.get("tavsiye_ozeti"):
                    s = result["tavsiye_ozeti"]
                    mean_target = None
                    low_target = None
                    high_target = None
                    if result.get("fiyat_hedefleri"):
                        fh = result["fiyat_hedefleri"]
                        if fh and len(fh) > 0:
                            mean_target = getattr(fh[0], 'ortalama', None)
                            low_target = getattr(fh[0], 'dusuk', None)
                            high_target = getattr(fh[0], 'yuksek', None)
                            current_price = getattr(fh[0], 'guncel', None)
                    summary = {
                        "strong_buy": 0,
                        "buy": getattr(s, 'satin_al', 0) or 0,
                        "hold": getattr(s, 'tut', 0) or 0,
                        "sell": getattr(s, 'sat', 0) or 0,
                        "strong_sell": 0,
                        "mean_target": mean_target,
                        "low_target": low_target,
                        "high_target": high_target,
                        "consensus": None
                    }

        elif market == MarketType.US:
            result = await self._client.get_us_analyst_ratings(symbol)
            if result:
                if result.get("fiyat_hedefleri"):
                    fh = result["fiyat_hedefleri"]
                    current_price = getattr(fh, 'guncel', None)
                    mean_target = getattr(fh, 'ortalama', None)
                    low_target = getattr(fh, 'dusuk', None)
                    high_target = getattr(fh, 'yuksek', None)
                    if current_price and mean_target:
                        upside = ((mean_target - current_price) / current_price) * 100
                if result.get("tavsiye_ozeti"):
                    s = result["tavsiye_ozeti"]
                    summary = {
                        "strong_buy": 0,
                        "buy": getattr(s, 'satin_al', 0) + getattr(s, 'fazla_agirlik', 0),
                        "hold": getattr(s, 'tut', 0) or 0,
                        "sell": getattr(s, 'sat', 0) + getattr(s, 'dusuk_agirlik', 0),
                        "strong_sell": 0,
                        "mean_target": mean_target if 'mean_target' in dir() else None,
                        "low_target": low_target if 'low_target' in dir() else None,
                        "high_target": high_target if 'high_target' in dir() else None,
                        "consensus": None
                    }
                if result.get("tavsiyeler"):
                    for r in result["tavsiyeler"][:10]:
                        date_str = getattr(r, 'tarih', None)
                        if hasattr(date_str, 'isoformat'):
                            date_str = date_str.isoformat()
                        ratings.append({
                            "firm": getattr(r, 'firma', None),
                            "rating": getattr(r, 'guncel_derece', None),
                            "price_target": None,
                            "date": str(date_str) if date_str else None
                        })

        return {
            "metadata": self._create_metadata(market, symbol_list, source, warnings=warnings),
            "symbol": symbol.upper(),
            "current_price": current_price,
            "summary": summary,
            "ratings": ratings,
            "upside_potential": upside
        }

    # --- Dividends ---

    async def get_dividends(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get dividend history and information. Returns raw dict."""
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
                if result.get("toplam_temettu_12ay"):
                    annual_dividend = result["toplam_temettu_12ay"]
                if result.get("temettuler"):
                    for t in result["temettuler"]:
                        date_str = t.tarih.isoformat() if hasattr(t.tarih, 'isoformat') else str(t.tarih)
                        dividend_history.append({
                            "ex_date": date_str,
                            "amount": t.miktar,
                            "currency": "TRY"
                        })
                if result.get("bolunmeler"):
                    for s in result["bolunmeler"]:
                        date_str = s.tarih.isoformat() if hasattr(s.tarih, 'isoformat') else str(s.tarih)
                        stock_splits.append({
                            "date": date_str,
                            "ratio": str(s.oran)
                        })

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_dividends(symbol)
            if result:
                if result.get("toplam_temettu_12ay"):
                    annual_dividend = result["toplam_temettu_12ay"]
                if result.get("temettuler"):
                    for t in result["temettuler"]:
                        date_str = t.tarih.isoformat() if hasattr(t.tarih, 'isoformat') else str(t.tarih)
                        dividend_history.append({
                            "ex_date": date_str,
                            "amount": t.miktar,
                            "currency": "USD"
                        })
                if result.get("bolunmeler"):
                    for s in result["bolunmeler"]:
                        date_str = s.tarih.isoformat() if hasattr(s.tarih, 'isoformat') else str(s.tarih)
                        stock_splits.append({
                            "date": date_str,
                            "ratio": str(s.oran)
                        })

        return {
            "metadata": self._create_metadata(market, symbol_list, source),
            "symbol": symbol.upper(),
            "current_yield": current_yield,
            "annual_dividend": annual_dividend,
            "ex_dividend_date": ex_date,
            "payout_ratio": payout_ratio,
            "dividend_history": dividend_history,
            "stock_splits": stock_splits
        }

    # --- Earnings ---

    async def get_earnings(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get earnings calendar and history. Returns raw dict."""
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
                if result.get("kazanc_takvimi"):
                    cal = result["kazanc_takvimi"]
                    if hasattr(cal, 'gelecek_kazanc_tarihi') and cal.gelecek_kazanc_tarihi:
                        next_date = cal.gelecek_kazanc_tarihi.isoformat() if hasattr(cal.gelecek_kazanc_tarihi, 'isoformat') else str(cal.gelecek_kazanc_tarihi)
                elif result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    if hasattr(bv, 'sonraki_kazanc_tarihi') and bv.sonraki_kazanc_tarihi:
                        next_date = bv.sonraki_kazanc_tarihi.isoformat() if hasattr(bv.sonraki_kazanc_tarihi, 'isoformat') else str(bv.sonraki_kazanc_tarihi)
                if result.get("kazanc_tarihleri"):
                    for e in result["kazanc_tarihleri"]:
                        date_str = e.tarih.isoformat() if hasattr(e.tarih, 'isoformat') else str(e.tarih)
                        earnings_history.append({
                            "date": date_str,
                            "eps_estimate": e.eps_tahmini,
                            "eps_actual": e.rapor_edilen_eps,
                            "surprise_percent": e.surpriz_yuzdesi
                        })
                if result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    growth_estimates = {
                        "annual_earnings_growth": getattr(bv, 'yillik_kazanc_buyumesi', None),
                        "quarterly_earnings_growth": getattr(bv, 'ceyreklik_kazanc_buyumesi', None)
                    }

            # Fallback to TradingView if yfinance has no data
            if not next_date and not earnings_history:
                try:
                    from providers.borsapy_scanner_provider import BorsapyScannerProvider
                    scanner = BorsapyScannerProvider()
                    tv_data = await scanner.get_earnings_data(symbol)
                    if tv_data:
                        source = "tradingview"
                        next_date = tv_data.get("earnings_release_next_date")
                        last_date = tv_data.get("earnings_release_date")
                        if last_date:
                            earnings_history.append({
                                "date": last_date,
                                "eps_estimate": tv_data.get("eps_forecast_next_fq"),
                                "eps_actual": tv_data.get("eps_basic_ttm"),
                                "surprise_percent": None
                            })
                        growth_estimates = {
                            "eps_ttm": tv_data.get("eps_basic_ttm"),
                            "eps_diluted_ttm": tv_data.get("eps_diluted_ttm"),
                            "eps_forecast_next_fq": tv_data.get("eps_forecast_next_fq")
                        }
                except Exception as e:
                    logger.warning(f"TradingView earnings fallback failed for {symbol}: {e}")

        elif market == MarketType.US:
            result = await self._client.get_us_earnings(symbol)
            if result:
                if result.get("kazanc_takvimi"):
                    cal = result["kazanc_takvimi"]
                    if hasattr(cal, 'gelecek_kazanc_tarihi') and cal.gelecek_kazanc_tarihi:
                        next_date = cal.gelecek_kazanc_tarihi.isoformat() if hasattr(cal.gelecek_kazanc_tarihi, 'isoformat') else str(cal.gelecek_kazanc_tarihi)
                elif result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    if hasattr(bv, 'sonraki_kazanc_tarihi') and bv.sonraki_kazanc_tarihi:
                        next_date = bv.sonraki_kazanc_tarihi.isoformat() if hasattr(bv.sonraki_kazanc_tarihi, 'isoformat') else str(bv.sonraki_kazanc_tarihi)
                if result.get("kazanc_tarihleri"):
                    for e in result["kazanc_tarihleri"]:
                        date_str = e.tarih.isoformat() if hasattr(e.tarih, 'isoformat') else str(e.tarih)
                        earnings_history.append({
                            "date": date_str,
                            "eps_estimate": e.eps_tahmini,
                            "eps_actual": e.rapor_edilen_eps,
                            "surprise_percent": e.surpriz_yuzdesi
                        })
                if result.get("buyume_verileri"):
                    bv = result["buyume_verileri"]
                    growth_estimates = {
                        "annual_earnings_growth": getattr(bv, 'yillik_kazanc_buyumesi', None),
                        "quarterly_earnings_growth": getattr(bv, 'ceyreklik_kazanc_buyumesi', None)
                    }

        return {
            "metadata": self._create_metadata(market, symbol_list, source),
            "symbol": symbol.upper(),
            "next_earnings_date": next_date,
            "earnings_history": earnings_history,
            "growth_estimates": growth_estimates
        }

    # --- Financial Statements ---

    async def get_financial_statements(
        self,
        symbols: Union[str, List[str]],
        market: MarketType,
        statement_type: StatementType = StatementType.ALL,
        period: PeriodType = PeriodType.ANNUAL
    ) -> Dict[str, Any]:
        """Get financial statements (balance sheet, income, cash flow). Returns raw dict."""
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
                    if result and result.get("tablo"):
                        tablo = result["tablo"]
                        periods_list = []
                        data_dict = {}
                        if tablo:
                            periods_list = sorted([k for k in tablo[0].keys() if k != "Kalem"], reverse=True)
                            for row in tablo:
                                item_name = row.get("Kalem", "Unknown")
                                data_dict[item_name] = [row.get(p) for p in periods_list]
                        statements.append({
                            "symbol": symbol.upper(),
                            "statement_type": stmt_name,
                            "period": period.value if hasattr(period, 'value') else str(period),
                            "periods": periods_list,
                            "data": data_dict,
                            "currency": "TRY"
                        })
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
                    if result and result.get("tablo"):
                        tablo = result["tablo"]
                        periods_list = []
                        data_dict = {}
                        if tablo:
                            periods_list = sorted([k for k in tablo[0].keys() if k != "Kalem"], reverse=True)
                            for row in tablo:
                                item_name = row.get("Kalem", "Unknown")
                                data_dict[item_name] = [row.get(p) for p in periods_list]
                        statements.append({
                            "symbol": symbol.upper(),
                            "statement_type": stmt_name,
                            "period": period.value if hasattr(period, 'value') else str(period),
                            "periods": periods_list,
                            "data": data_dict,
                            "currency": "USD"
                        })
                except Exception as e:
                    warnings.append(f"Failed to fetch {stmt_name}: {str(e)}")

        return {
            "metadata": self._create_metadata(market, symbol_list, source, warnings=warnings),
            "statements": statements
        }

    # --- Financial Ratios ---

    async def get_financial_ratios(
        self,
        symbol: str,
        market: MarketType,
        ratio_set: RatioSetType = RatioSetType.VALUATION
    ) -> Dict[str, Any]:
        """Get financial ratios and analysis. Returns raw dict."""
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
                    if result and not result.get("error"):
                        current_price = result.get("kapanis_fiyati")
                        valuation = {
                            "pe_ratio": result.get("fk_orani"),
                            "pb_ratio": result.get("pd_dd"),
                            "ev_ebitda": result.get("fd_favok"),
                            "ev_sales": result.get("fd_satislar")
                        }
                except Exception as e:
                    ratio_warnings.append(f"Valuation ratios error: {str(e)}")

            if ratio_set in [RatioSetType.BUFFETT, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_buffett_value_analysis(ticker)
                    if result:
                        oe_data = result.get("owner_earnings") or {}
                        oe_yield_data = result.get("oe_yield") or {}
                        dcf_data = result.get("dcf_fisher") or {}
                        sm_data = result.get("safety_margin") or {}

                        oe_value = oe_data.get("owner_earnings") if isinstance(oe_data, dict) else oe_data
                        oe_yield_value = oe_yield_data.get("oe_yield") if isinstance(oe_yield_data, dict) else oe_yield_data
                        dcf_value = dcf_data.get("intrinsic_per_share") if isinstance(dcf_data, dict) else dcf_data
                        sm_value = sm_data.get("safety_margin") if isinstance(sm_data, dict) else sm_data

                        buffett = {
                            "owner_earnings": oe_value,
                            "oe_yield": oe_yield_value,
                            "dcf_intrinsic_value": dcf_value,
                            "safety_margin": sm_value,
                            "buffett_score": result.get("buffett_score")
                        }
                        insights.extend(result.get("key_insights") or [])
                        ratio_warnings.extend(result.get("warnings") or [])
                except Exception as e:
                    ratio_warnings.append(f"Buffett analysis error: {str(e)}")

            if ratio_set in [RatioSetType.CORE_HEALTH, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_core_financial_health(ticker)
                    if result:
                        roe_data = result.get("roe") or {}
                        roic_data = result.get("roic") or {}
                        debt_data = result.get("debt_ratios") or {}
                        fcf_data = result.get("fcf_margin") or {}
                        eq_data = result.get("earnings_quality") or {}

                        roe_value = roe_data.get("roe_percent") / 100.0 if isinstance(roe_data, dict) and roe_data.get("roe_percent") else None
                        roic_value = roic_data.get("roic_percent") / 100.0 if isinstance(roic_data, dict) and roic_data.get("roic_percent") else None
                        d_to_e = debt_data.get("debt_to_equity") if isinstance(debt_data, dict) else None
                        d_to_a = debt_data.get("debt_to_assets") if isinstance(debt_data, dict) else None
                        int_cov = debt_data.get("interest_coverage") if isinstance(debt_data, dict) else None
                        fcf_value = fcf_data.get("fcf_margin_percent") / 100.0 if isinstance(fcf_data, dict) and fcf_data.get("fcf_margin_percent") else None
                        eq_value = eq_data.get("cf_to_earnings_ratio") if isinstance(eq_data, dict) else None

                        core_health = {
                            "roe": roe_value,
                            "roic": roic_value,
                            "debt_to_equity": d_to_e,
                            "debt_to_assets": d_to_a,
                            "interest_coverage": int_cov,
                            "fcf_margin": fcf_value,
                            "earnings_quality": eq_value,
                            "health_score": result.get("overall_health_score")
                        }
                        insights.extend(result.get("strengths") or [])
                        ratio_warnings.extend(result.get("concerns") or [])
                except Exception as e:
                    ratio_warnings.append(f"Core health error: {str(e)}")

            if ratio_set in [RatioSetType.ADVANCED, RatioSetType.COMPREHENSIVE]:
                try:
                    result = await self._client.calculate_advanced_metrics(ticker)
                    if result:
                        advanced = {
                            "altman_z_score": result.get("altman_z_score"),
                            "financial_stability": result.get("financial_stability"),
                            "real_revenue_growth": result.get("real_revenue_growth"),
                            "real_earnings_growth": result.get("real_earnings_growth"),
                            "growth_quality": result.get("growth_quality")
                        }
                except Exception as e:
                    ratio_warnings.append(f"Advanced metrics error: {str(e)}")

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_quick_info(symbol)
            if result and result.get("bilgiler"):
                b = result["bilgiler"]
                current_price = getattr(b, 'last_price', None)
                valuation = {
                    "pe_ratio": getattr(b, 'pe_ratio', None),
                    "pb_ratio": getattr(b, 'price_to_book', None),
                    "ps_ratio": None
                }

        return {
            "metadata": self._create_metadata(market, symbol, source, warnings=ratio_warnings),
            "symbol": symbol.upper(),
            "current_price": current_price,
            "valuation": valuation,
            "buffett": buffett,
            "core_health": core_health,
            "advanced": advanced,
            "insights": insights,
            "warnings": ratio_warnings
        }

    # --- Corporate Actions ---

    async def get_corporate_actions(
        self,
        symbols: Union[str, List[str]],
        market: MarketType = MarketType.BIST,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get corporate actions (capital increases, dividends). Returns raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "isyatirim"
        capital_increases = []
        dividend_history = []

        symbol = symbol_list[0]

        if market == MarketType.BIST:
            try:
                result = await self._client.get_sermaye_artirimlari(symbol, yil=year or 0)
                if result and result.get("sermaye_artirimlari"):
                    for sa in result["sermaye_artirimlari"]:
                        capital_increases.append({
                            "date": sa.get("tarih"),
                            "type_code": sa.get("tip_kodu"),
                            "type_tr": sa.get("tip"),
                            "type_en": sa.get("tip_en"),
                            "rights_issue_rate": sa.get("bedelli_oran"),
                            "rights_issue_amount": sa.get("bedelli_tutar"),
                            "bonus_internal_rate": sa.get("bedelsiz_ic_kaynak_oran"),
                            "bonus_dividend_rate": sa.get("bedelsiz_temettu_oran"),
                            "capital_before": sa.get("onceki_sermaye"),
                            "capital_after": sa.get("sonraki_sermaye")
                        })
            except Exception as e:
                logger.warning(f"Error fetching capital increases: {e}")

            try:
                result = await self._client.get_isyatirim_temettu(symbol, yil=year or 0)
                if result and result.get("temettuler"):
                    for t in result["temettuler"]:
                        dividend_history.append({
                            "ex_date": t.get("tarih"),
                            "amount": t.get("toplam_tutar"),
                            "yield_percent": t.get("brut_oran"),
                            "currency": "TRY",
                            "type": "cash"
                        })
            except Exception as e:
                logger.warning(f"Error fetching dividend history: {e}")

        return {
            "metadata": self._create_metadata(market, symbol_list, source),
            "symbol": symbol.upper(),
            "capital_increases": capital_increases,
            "dividend_history": dividend_history
        }

    # --- News ---

    async def get_news(
        self,
        symbol: Optional[str] = None,
        market: MarketType = MarketType.BIST,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get market news (KAP for BIST). Returns raw dict."""
        source = "unknown"
        news_items = []

        if market == MarketType.BIST and symbol:
            source = "mynet"
            result = await self._client.get_kap_haberleri_mynet(symbol, limit=limit)
            if result and result.get("kap_haberleri"):
                for h in result["kap_haberleri"][:limit]:
                    news_items.append({
                        "id": h.get("haber_id"),
                        "title": h.get("baslik"),
                        "summary": h.get("title_attr"),
                        "source": "KAP",
                        "url": h.get("url"),
                        "published_date": h.get("tarih"),
                        "symbols": [symbol.upper()]
                    })

        return {
            "metadata": self._create_metadata(market, symbol or "market", source),
            "symbol": symbol.upper() if symbol else None,
            "news": news_items
        }

    # --- Screener ---

    async def screen_securities(
        self,
        market: MarketType,
        preset: Optional[str] = None,
        security_type: Optional[str] = None,
        custom_filters: Optional[List[Any]] = None,
        limit: int = 25
    ) -> Dict[str, Any]:
        """Screen securities with presets or custom filters. Returns raw dict."""
        source = "yfscreen"
        stocks = []

        if market == MarketType.BIST:
            result = await self._client.screen_bist_stocks(
                preset=preset,
                custom_filters=custom_filters,
                limit=limit
            )
            if result and result.get("results"):
                for s in result["results"]:
                    stocks.append({
                        "symbol": s.get("ticker"),
                        "name": s.get("name"),
                        "market": "bist",
                        "sector": s.get("sector"),
                        "market_cap": s.get("market_cap"),
                        "price": s.get("price"),
                        "change_percent": s.get("change_percent"),
                        "volume": s.get("volume"),
                        "pe_ratio": s.get("pe_ratio"),
                        "dividend_yield": s.get("dividend_yield"),
                        "additional_data": {}
                    })

        elif market == MarketType.US:
            result = await self._client.screen_us_securities(
                preset=preset,
                security_type=security_type,
                custom_filters=custom_filters,
                limit=limit
            )
            if result and result.get("results"):
                for s in result["results"]:
                    stocks.append({
                        "symbol": s.get("ticker"),
                        "name": s.get("name"),
                        "market": "us",
                        "sector": s.get("sector"),
                        "market_cap": s.get("market_cap"),
                        "price": s.get("price"),
                        "change_percent": s.get("change_percent"),
                        "volume": s.get("volume"),
                        "pe_ratio": s.get("pe_ratio"),
                        "dividend_yield": s.get("dividend_yield"),
                        "additional_data": {}
                    })

        return {
            "metadata": self._create_metadata(market, "screener", source),
            "preset": preset,
            "security_type": security_type,
            "filters_applied": custom_filters,
            "stocks": stocks,
            "total_count": len(stocks)
        }

    # --- Scanner ---

    async def scan_stocks(
        self,
        index: str,
        market: MarketType = MarketType.BIST,
        condition: Optional[str] = None,
        preset: Optional[str] = None,
        timeframe: str = "1d"
    ) -> Dict[str, Any]:
        """Scan stocks by technical conditions. Returns raw dict."""
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
                    stocks.append({
                        "symbol": h.symbol,
                        "name": h.name,
                        "close": h.price,
                        "change": h.change_percent,
                        "volume": h.volume,
                        "rsi": h.rsi,
                        "macd": h.macd,
                        "supertrend_direction": None,
                        "t3": None,
                        "additional_indicators": {}
                    })

        return {
            "metadata": self._create_metadata(market, index, source),
            "index": index,
            "condition": condition,
            "preset": preset,
            "timeframe": timeframe,
            "stocks": stocks,
            "total_count": len(stocks)
        }

    # --- Crypto Market ---

    async def get_crypto_market(
        self,
        symbol: str,
        exchange: ExchangeType,
        data_type: DataType = DataType.TICKER
    ) -> Dict[str, Any]:
        """Get crypto market data. Returns raw dict."""
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
                    t = result.ticker_data[0]
                    ticker = {
                        "symbol": symbol,
                        "pair": t.pair,
                        "exchange": "btcturk",
                        "price": t.last,
                        "bid": t.bid,
                        "ask": t.ask,
                        "volume_24h": t.volume,
                        "change_24h": t.dailyPercent,
                        "high_24h": t.high,
                        "low_24h": t.low,
                        "timestamp": t.timestamp.isoformat() if t.timestamp else None
                    }
            elif data_type == DataType.ORDERBOOK:
                result = await self._client.get_kripto_orderbook(symbol)
                if result and result.orderbook:
                    ob = result.orderbook
                    orderbook = {
                        "symbol": symbol,
                        "pair": symbol,
                        "exchange": "btcturk",
                        "bids": [{"price": b[0], "amount": b[1]} for b in ob.bids[:10]],
                        "asks": [{"price": a[0], "amount": a[1]} for a in ob.asks[:10]],
                        "timestamp": ob.timestamp.isoformat() if ob.timestamp else None
                    }
            elif data_type == DataType.TRADES:
                result = await self._client.get_kripto_trades(symbol)
                if result and result.trades:
                    trades = [
                        {
                            "price": t.price or 0.0,
                            "amount": t.amount or 0.0,
                            "side": "unknown",
                            "timestamp": t.date.isoformat() if t.date else ""
                        }
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
                    t = result.ticker_data[0]
                    ticker = {
                        "symbol": symbol,
                        "pair": t.product_id,
                        "exchange": "coinbase",
                        "price": t.price,
                        "bid": t.bid,
                        "ask": t.ask,
                        "volume_24h": t.volume_24h,
                        "change_24h": t.price_percentage_change_24h,
                        "high_24h": t.high_24h,
                        "low_24h": t.low_24h,
                        "timestamp": None
                    }
            elif data_type == DataType.ORDERBOOK:
                result = await self._client.get_coinbase_orderbook(symbol)
                if result and result.orderbook:
                    ob = result.orderbook
                    orderbook = {
                        "symbol": symbol,
                        "pair": symbol,
                        "exchange": "coinbase",
                        "bids": [{"price": float(b[0]), "amount": float(b[1])} for b in ob.bids[:10]],
                        "asks": [{"price": float(a[0]), "amount": float(a[1])} for a in ob.asks[:10]],
                        "timestamp": None
                    }
            elif data_type == DataType.TRADES:
                result = await self._client.get_coinbase_trades(symbol)
                if result and result.trades:
                    trades = [
                        {
                            "price": t.price or 0.0,
                            "amount": t.size or 0.0,
                            "side": t.side or "unknown",
                            "timestamp": t.time.isoformat() if t.time else ""
                        }
                        for t in result.trades[:20]
                    ]
            elif data_type == DataType.EXCHANGE_INFO:
                result = await self._client.get_coinbase_exchange_info()
                if result:
                    exchange_info = {
                        "products_count": result.total_pairs,
                        "currencies_count": result.total_currencies
                    }

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "data_type": data_type.value if hasattr(data_type, 'value') else str(data_type),
            "ticker": ticker,
            "orderbook": orderbook,
            "trades": trades,
            "exchange_info": exchange_info
        }

    # --- FX Data ---

    async def get_fx_data(
        self,
        symbols: Optional[List[str]] = None,
        category: Optional[str] = None,
        historical: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get foreign exchange rates. Returns raw dict."""
        source = "borsapy"
        rates = []
        historical_data = None

        if historical and symbols and len(symbols) == 1:
            result = await self._client.get_dovizcom_arsiv_veri(
                symbols[0], start_date or "", end_date or ""
            )
            if result and result.ohlc_verileri:
                historical_data = [
                    {
                        "date": v.tarih.isoformat() if v.tarih else "",
                        "open": v.acilis,
                        "high": v.en_yuksek,
                        "low": v.en_dusuk,
                        "close": v.kapanis,
                        "volume": None
                    }
                    for v in result.ohlc_verileri
                ]
        else:
            if symbols:
                for sym in symbols:
                    result = await self._client.get_dovizcom_guncel_kur(sym)
                    if result and result.guncel_deger is not None:
                        ts = result.son_guncelleme
                        timestamp_str = ts.isoformat() if ts else None
                        rates.append({
                            "symbol": sym,
                            "name": result.varlik_adi or sym,
                            "buy": None,
                            "sell": result.guncel_deger,
                            "change": result.degisim,
                            "change_percent": result.degisim_yuzde,
                            "high": None,
                            "low": None,
                            "timestamp": timestamp_str
                        })

        return {
            "metadata": self._create_metadata(MarketType.FX, symbols or ["all"], source),
            "rates": rates,
            "historical_data": historical_data
        }

    # --- Fund Data ---

    async def get_fund_data(
        self,
        symbol: str,
        include_portfolio: bool = False,
        include_performance: bool = False
    ) -> Dict[str, Any]:
        """Get mutual fund data using borsapy. Returns raw dict."""
        import borsapy as bp

        source = "borsapy"
        fund_info = None
        portfolio = None
        performance = None

        try:
            fund = bp.Fund(symbol.upper())
            info = fund.info

            if info:
                fund_info = {
                    "code": info.get("fund_code"),
                    "name": info.get("name"),
                    "category": info.get("category"),
                    "company": info.get("founder"),
                    "price": info.get("price"),
                    "total_assets": info.get("fund_size"),
                    "investor_count": info.get("investor_count"),
                    "daily_return": info.get("daily_return"),
                    "weekly_return": info.get("weekly_return"),
                    "return_1m": info.get("return_1m"),
                    "return_3m": info.get("return_3m"),
                    "return_6m": info.get("return_6m"),
                    "return_ytd": info.get("return_ytd"),
                    "return_1y": info.get("return_1y"),
                    "return_3y": info.get("return_3y"),
                    "return_5y": info.get("return_5y"),
                    "category_rank": info.get("category_rank"),
                    "category_fund_count": info.get("category_fund_count"),
                    "market_share": info.get("market_share"),
                    "isin": info.get("isin"),
                    "kap_link": info.get("kap_link")
                }

                # Portfolio allocation from borsapy
                if include_portfolio and info.get("allocation"):
                    portfolio = [
                        {"asset_type": a.get("asset_type"), "asset_name": a.get("asset_name"), "weight": a.get("weight")}
                        for a in info.get("allocation", [])
                    ]

        except Exception as e:
            logger.warning(f"borsapy fund error for {symbol}: {e}")

        return {
            "metadata": self._create_metadata(MarketType.FUND, symbol, source),
            "fund": fund_info,
            "portfolio": portfolio,
            "performance_history": performance
        }

    # --- Index Data ---

    async def get_index_data(
        self,
        code: str,
        market: MarketType = MarketType.BIST,
        include_components: bool = False
    ) -> Dict[str, Any]:
        """Get stock market index data. Returns raw dict."""
        source = "unknown"
        index_info = None
        components = []

        if market == MarketType.BIST:
            source = "kap"
            result = await self._client.search_indices_from_kap(code)
            if result and result.sonuclar:
                idx = result.sonuclar[0]
                index_info = {
                    "code": idx.endeks_kodu,
                    "name": idx.endeks_adi,
                    "market": "bist"
                }

            if include_components:
                result = await self._client.get_endeks_sirketleri(code)
                if result and result.sirketler:
                    for s in result.sirketler:
                        components.append({
                            "symbol": s.ticker_kodu,
                            "name": s.sirket_adi,
                            "weight": None,
                            "sector": None
                        })

        elif market == MarketType.US:
            source = "yfinance"
            result = await self._client.get_us_index_info(code)
            if result and result.get("index"):
                idx = result["index"]
                index_info = {
                    "code": idx.get("symbol"),
                    "name": idx.get("name"),
                    "market": "us",
                    "value": idx.get("value"),
                    "change": idx.get("change"),
                    "change_percent": idx.get("change_percent"),
                    "components_count": idx.get("components_count")
                }

        return {
            "metadata": self._create_metadata(market, code, source),
            "index": index_info,
            "components": components
        }

    # --- Sector Comparison ---

    async def get_sector_comparison(
        self,
        symbol: str,
        market: MarketType
    ) -> Dict[str, Any]:
        """Get sector comparison for a stock. Returns raw dict."""
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
                sirket_verileri = result.get("sirket_verileri", [])
                if sirket_verileri:
                    first_company = sirket_verileri[0]
                    sector = first_company.get("sektor")

                sektor_ozeti = result.get("sektor_ozeti", {})
                if sektor_ozeti and sector:
                    sector_data = sektor_ozeti.get(sector, {})
                    avg_pe = sector_data.get("ortalama_fk")
                    avg_pb = sector_data.get("ortalama_pd_dd")

                for p in sirket_verileri:
                    ticker_code = p.get("ticker", "").replace(".IS", "")
                    company_name = p.get("sirket_adi") or ticker_code
                    peers.append({
                        "symbol": ticker_code,
                        "name": company_name,
                        "market_cap": p.get("piyasa_degeri"),
                        "pe_ratio": p.get("fk_orani"),
                        "pb_ratio": p.get("pd_dd"),
                        "roe": p.get("roe"),
                        "dividend_yield": None,
                        "change_percent": float(p.get("yillik_getiri")) if p.get("yillik_getiri") else None
                    })

        elif market == MarketType.US:
            result = await self._client.get_us_sector_comparison([symbol])
            if result:
                sector = result.get("sector")
                industry = result.get("industry")
                avg_pe = result.get("sector_avg_pe")
                avg_pb = result.get("sector_avg_pb")
                if result.get("peers"):
                    for p in result["peers"]:
                        peers.append({
                            "symbol": p.get("symbol"),
                            "name": p.get("name"),
                            "market_cap": p.get("market_cap"),
                            "pe_ratio": p.get("pe_ratio"),
                            "pb_ratio": p.get("pb_ratio"),
                            "roe": p.get("roe"),
                            "dividend_yield": p.get("dividend_yield"),
                            "change_percent": p.get("change_percent")
                        })

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "symbol": symbol.upper(),
            "sector": sector,
            "industry": industry,
            "sector_average_pe": avg_pe,
            "sector_average_pb": avg_pb,
            "peers": peers
        }


    # --- News Detail (Phase 2) ---

    async def get_news_detail(
        self,
        news_id: str,
        page: int = 1
    ) -> Dict[str, Any]:
        """Get detailed news content by news ID/URL. Returns raw dict."""
        source = "mynet"

        if news_id.startswith("http"):
            news_url = news_id
        else:
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

        return {
            "metadata": self._create_metadata(MarketType.BIST, news_id, source),
            "news_id": news_id,
            "title": title,
            "content": content,
            "summary": summary,
            "source": "KAP",
            "url": url,
            "published_date": published_date,
            "symbols": symbols,
            "page": page,
            "total_pages": total_pages
        }

    # --- Islamic Finance Compliance (Phase 4) ---

    async def get_islamic_compliance(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """Get Islamic finance (katilim finans) compliance status for a BIST stock. Returns raw dict."""
        result = await self._client.get_katilim_finans_uygunluk(symbol)

        is_compliant = False
        compliance_status = "Bilinmiyor"
        compliance_details = None
        last_updated = None

        if result:
            # Handle both Pydantic model and dict responses
            if hasattr(result, 'katilim_endeksi_dahil'):
                # Pydantic model (KatilimFinansUygunlukSonucu)
                is_compliant = result.katilim_endeksi_dahil if result.katilim_endeksi_dahil else False
                compliance_status = "Uygun" if is_compliant else ("Veri bulunamadı" if not result.veri_bulundu else "Uygun Değil")
                compliance_details = ", ".join(result.katilim_endeksleri) if result.katilim_endeksleri else None
                last_updated = None
            elif hasattr(result, 'get'):
                # Dict response
                is_compliant = result.get("katilim_endeksi_dahil", result.get("uygun", False))
                compliance_status = result.get("durum", "Bilinmiyor")
                compliance_details = result.get("detay", "")
                last_updated = result.get("guncelleme_tarihi", "")

        return {
            "is_compliant": is_compliant,
            "compliance_status": compliance_status,
            "compliance_details": compliance_details,
            "source": "kap",
            "last_updated": last_updated
        }

    # --- Fund Comparison (Phase 5) ---

    async def compare_funds(
        self,
        fund_codes: List[str],
        fund_type: str = "EMK",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare multiple funds side by side. Returns raw dict."""
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
                funds.append({
                    "code": f.get("kod", ""),
                    "name": f.get("ad", ""),
                    "category": f.get("kategori", ""),
                    "company": f.get("kurulus", ""),
                    "price": f.get("fiyat"),
                    "daily_return": f.get("gunluk_getiri"),
                    "weekly_return": f.get("haftalik_getiri"),
                    "monthly_return": f.get("aylik_getiri"),
                    "three_month_return": f.get("uc_aylik_getiri"),
                    "six_month_return": f.get("alti_aylik_getiri"),
                    "ytd_return": f.get("yilbasi_getiri"),
                    "one_year_return": f.get("yillik_getiri"),
                    "total_assets": f.get("toplam_deger")
                })
            comparison_date = result.get("tarih")

        return {
            "metadata": self._create_metadata(MarketType.FUND, fund_codes, source),
            "funds": funds,
            "comparison_date": comparison_date
        }

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
    ) -> Dict[str, Any]:
        """Get Turkish macro economic data. Returns raw dict."""
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

            if result and hasattr(result, 'data') and result.data:
                inflation_data = []
                for d in result.data:
                    inflation_data.append({
                        "date": d.tarih,
                        "rate": d.yillik_enflasyon or 0.0,
                        "change": d.aylik_enflasyon,
                        "cumulative": None
                    })

        elif data_type == "calculate":
            if all([start_year, start_month, end_year, end_month]):
                result = await self._client.calculate_inflation(
                    start_year=start_year,
                    start_month=start_month,
                    end_year=end_year,
                    end_month=end_month,
                    basket_value=basket_value
                )

                if result and hasattr(result, 'yeni_sepet_degeri'):
                    def tr_to_float(s: str) -> float:
                        if not s:
                            return 0.0
                        return float(s.replace('.', '').replace(',', '.'))

                    final_value = tr_to_float(result.yeni_sepet_degeri) if result.yeni_sepet_degeri else basket_value
                    total_change = tr_to_float(result.toplam_degisim) if result.toplam_degisim else 0.0
                    cumulative = (total_change / basket_value) * 100 if basket_value > 0 else 0.0
                    period_months = result.toplam_yil * 12 + result.toplam_ay

                    calculation = {
                        "start_period": f"{start_year}-{start_month:02d}",
                        "end_period": f"{end_year}-{end_month:02d}",
                        "initial_value": basket_value,
                        "final_value": final_value,
                        "cumulative_inflation": cumulative,
                        "period_months": period_months
                    }

        return {
            "metadata": self._create_metadata(MarketType.FX, [data_type], source),
            "data_type": data_type,
            "inflation_type": inflation_type if data_type == "inflation" else None,
            "inflation_data": inflation_data,
            "calculation": calculation
        }

    # --- Screener Help (Phase 7) ---

    async def get_screener_help(
        self,
        market: MarketType
    ) -> Dict[str, Any]:
        """Get screener help with presets and filter documentation. Returns raw dict."""
        source = "yfscreen" if market == MarketType.US else "borsapy"
        presets = []
        filters = []
        operators = ["eq", "gt", "lt", "btwn"]
        examples = []

        if market == MarketType.US:
            preset_result = await self._client.get_us_screener_presets()
            if preset_result and preset_result.get("presets"):
                for p in preset_result["presets"]:
                    presets.append({
                        "name": p.get("name", ""),
                        "description": p.get("description", ""),
                        "filters": p.get("filters"),
                        "security_type": p.get("security_type")
                    })

            filter_result = await self._client.get_us_screener_filter_docs()
            if filter_result and filter_result.get("filters"):
                for f in filter_result["filters"]:
                    filters.append({
                        "field": f.get("field", ""),
                        "description": f.get("description", ""),
                        "operators": f.get("operators", operators),
                        "examples": f.get("examples"),
                        "value_type": f.get("value_type")
                    })

            examples = [
                '[["eq", ["sector", "Technology"]]]',
                '[["gt", ["intradaymarketcap", 10000000000]]]',
                '[["lt", ["pegratio", 1]]]'
            ]

        elif market == MarketType.BIST:
            preset_result = await self._client.get_bist_screener_presets()
            if preset_result and preset_result.get("presets"):
                for p in preset_result["presets"]:
                    presets.append({
                        "name": p.get("name", ""),
                        "description": p.get("description", ""),
                        "filters": p.get("filters")
                    })

            filter_result = await self._client.get_bist_screener_filter_docs()
            if filter_result and filter_result.get("filters"):
                for f in filter_result["filters"]:
                    filters.append({
                        "field": f.get("field", ""),
                        "description": f.get("description", ""),
                        "operators": f.get("operators", operators),
                        "examples": f.get("examples"),
                        "value_type": f.get("value_type")
                    })

            examples = [
                "sector == 'Bankacilik'",
                "market_cap > 10000000000",
                "pe_ratio < 15"
            ]

        return {
            "metadata": self._create_metadata(market, ["help"], source),
            "market": market.value,
            "presets": presets,
            "filters": filters,
            "operators": operators,
            "example_queries": examples
        }

    # --- Scanner Help (Phase 8) ---

    async def get_scanner_help(self) -> Dict[str, Any]:
        """Get BIST scanner help with indicators, operators, and presets. Returns raw dict."""
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
                for category, ind_list in result.indicators.items():
                    for ind_name in ind_list:
                        info = indicator_examples.get(ind_name, (f"{ind_name} indicator", None, None))
                        indicators.append({
                            "name": ind_name,
                            "description": info[0],
                            "range": info[1],
                            "example": info[2]
                        })
            else:
                indicators = [
                    {"name": "RSI", "description": "Relative Strength Index (0-100)", "range": "0-100", "example": "RSI < 30"},
                    {"name": "macd", "description": "MACD histogram", "range": None, "example": "macd > 0"},
                    {"name": "volume", "description": "Trading volume", "range": None, "example": "volume > 10000000"},
                    {"name": "change", "description": "Daily change percentage", "range": None, "example": "change > 3"},
                    {"name": "close", "description": "Closing price", "range": None, "example": "close > sma_50"},
                    {"name": "sma_50", "description": "50-day Simple Moving Average", "range": None, "example": "close > sma_50"},
                    {"name": "ema_20", "description": "20-day Exponential Moving Average", "range": None, "example": "close > ema_20"},
                    {"name": "supertrend_direction", "description": "Supertrend direction (1=bullish, -1=bearish)", "range": "-1 to 1", "example": "supertrend_direction == 1"},
                    {"name": "t3", "description": "Tilson T3 Moving Average", "range": None, "example": "close > t3"},
                    {"name": "bb_upper", "description": "Bollinger Band Upper", "range": None, "example": "close > bb_upper"},
                    {"name": "bb_lower", "description": "Bollinger Band Lower", "range": None, "example": "close < bb_lower"},
                ]

            if hasattr(result, 'presets') and result.presets:
                for p in result.presets:
                    condition = p.condition if hasattr(p, 'condition') else None
                    presets.append({
                        "name": p.name,
                        "description": p.description,
                        "filters": [condition] if condition else None
                    })
            else:
                presets = [
                    {"name": "oversold", "description": "RSI < 30 (Oversold stocks)"},
                    {"name": "overbought", "description": "RSI > 70 (Overbought stocks)"},
                    {"name": "bullish_momentum", "description": "RSI > 50 and MACD > 0"},
                    {"name": "bearish_momentum", "description": "RSI < 50 and MACD < 0"},
                    {"name": "supertrend_bullish", "description": "Supertrend direction = 1 (Bullish)"},
                    {"name": "supertrend_bearish", "description": "Supertrend direction = -1 (Bearish)"},
                    {"name": "t3_bullish", "description": "Price above T3"},
                    {"name": "t3_bearish", "description": "Price below T3"},
                    {"name": "high_volume", "description": "Volume > 10M"},
                    {"name": "big_gainers", "description": "Daily change > 3%"},
                    {"name": "big_losers", "description": "Daily change < -3%"},
                ]

        return {
            "metadata": self._create_metadata(MarketType.BIST, ["help"], source),
            "available_indicators": indicators,
            "available_operators": operators,
            "available_presets": presets,
            "available_indices": indices,
            "available_timeframes": timeframes,
            "example_conditions": examples
        }

    # --- Regulations (Phase 9) ---

    async def get_regulations(
        self,
        regulation_type: str = "fund"
    ) -> Dict[str, Any]:
        """Get Turkish financial regulations. Returns raw dict."""
        source = "mevzuat"
        items = []
        last_updated = None

        if regulation_type == "fund":
            result = await self._client.get_fon_mevzuati()

            if result:
                content = result.icerik if hasattr(result, 'icerik') and result.icerik else ""
                title = result.baslik if hasattr(result, 'baslik') and result.baslik else "Yatirim Fonlarina Iliskin Rehber"
                if content:
                    items.append({
                        "title": title,
                        "content": content[:2000] + "..." if len(content) > 2000 else content,
                        "category": "SPK Fund Regulation"
                    })
                last_updated = result.son_guncelleme if hasattr(result, 'son_guncelleme') else None

        return {
            "metadata": self._create_metadata(MarketType.FUND, [regulation_type], source),
            "regulation_type": regulation_type,
            "items": items,
            "last_updated": last_updated
        }


# Global router instance
market_router = MarketRouter()
