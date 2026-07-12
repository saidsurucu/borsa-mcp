"""
Market Router for unified tools.
Routes requests to appropriate providers based on market type.
Uses BorsaApiClient as the underlying service layer.

NOTE: This module returns raw dicts, not Pydantic models, to avoid validation overhead.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

from borsapy.exceptions import DataNotAvailableError

from models.unified_base import (
    MarketType, StatementType, PeriodType, DataType, RatioSetType, ExchangeType
)

logger = logging.getLogger(__name__)

# Coinbase's Advanced Trade API rejects any request for more than 350 candles,
# whatever the granularity. Verified live: 350 -> OK, 351 -> HTTP 400
# ("number of candles requested should be less than 350").
COINBASE_MAX_CANDLES = 350


def parse_tcmb_number(value: Optional[str]) -> Optional[float]:
    """Parse a number from TCMB's calculator API.

    TCMB serves invariant-culture numbers ('601.31', '2,684.55000'), but an
    earlier implementation assumed the Turkish convention (dot groups thousands,
    comma is decimal) and stripped the decimal point -- inflating every value by
    ~100x, so the tool claimed 100 TL in 2020-01 was worth 60,131 TL in 2024-12.

    Resolving by the LAST separator is correct under either convention: whichever
    of ',' or '.' appears last is the decimal point.

    Raises ValueError on an unparseable string rather than defaulting to 0.0,
    which would read as "inflation was zero".
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    last_comma = text.rfind(',')
    last_dot = text.rfind('.')

    if last_comma > last_dot:          # Turkish: 2.684,55
        text = text.replace('.', '').replace(',', '.')
    else:                              # Invariant: 2,684.55 (and plain '601.31')
        text = text.replace(',', '')

    try:
        return float(text)
    except ValueError as e:
        raise ValueError(f"Could not parse TCMB number {value!r}: {e}")


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
            if result:
                # FonDetayBilgisi has flat structure (fon_kodu, fon_adi, etc.)
                profile = {
                    "symbol": result.fon_kodu or symbol,
                    "name": result.fon_adi or symbol,
                    "market": "fund",
                    "description": result.fon_turu,
                    "currency": "TRY",
                    "company": result.kurulus,
                    "manager": result.yonetici,
                    "risk_level": result.risk_degeri,
                    "total_assets": result.toplam_deger,
                    "investor_count": result.yatirimci_sayisi,
                    "price": result.fiyat
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
        interval: str = "1d",
        adjust: bool = True
    ) -> Dict[str, Any]:
        """Get historical OHLCV data. Returns raw dict.

        One adjustment basis across every market (design doc §3.3, "Decision A"):
        **splits adjusted everywhere, dividends nowhere.**

        BIST used to default to raw prices while US returned a split- AND
        dividend-adjusted series. Each was internally consistent; putting them in one
        table was nonsense. BIMAS's 100% bonus issue took the BIST series
        813.00 -> 414.00, so any window spanning 2026-05-14 reported -49% for a
        company that had merely split.

        `adjust=False` is still honoured for BIST when a caller genuinely wants the
        prices printed on the exchange that day — but it is no longer the default,
        because a return computed from it is wrong.
        """
        source = "unknown"
        data_points = []

        bar_interval = None
        raw_count = None

        if market == MarketType.BIST:
            source = "borsapy"
            ticker = self._get_ticker_with_suffix(symbol, market)

            # borsapy's `period` is a BAR COUNT, not a calendar span: period="1y" asks
            # for 365 *trading* bars, and a year holds only ~250 of them — so "1y"
            # came back with roughly 18 calendar months, and "6mo" with 9. borsapy
            # adopted yfinance's period names without yfinance's semantics. Resolve
            # the period to explicit dates ourselves; _clamp_to_window then holds the
            # span to what was asked for.
            if period and not (start_date or end_date):
                win_start, win_end = self._resolve_window(period, None, None)
                if win_start and win_end:
                    start_date = win_start.strftime("%Y-%m-%d")
                    end_date = win_end.strftime("%Y-%m-%d")
                    period = None

            result = await self._client.get_finansal_veri(
                ticker,
                zaman_araligi=period or "1mo",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            # get_finansal_veri reports upstream failures as {"error": ...}. Falling
            # through would return an empty-but-successful payload, which reads as
            # "this ticker has no price history".
            if result and result.get("error"):
                raise RuntimeError(result["error"])
            if result and result.get("optimizasyon_uygulandı"):
                raw_count = result.get("ham_veri_sayisi")
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
            # auto_adjust=False gives Yahoo's `Close`: split-adjusted but NOT
            # dividend-adjusted — the same basis as BIST's adjusted frame. yfinance
            # 1.1.0 defaults it to True, which folds dividends in and quietly makes
            # the two markets incomparable. The `adjust` flag was accepted here and
            # never forwarded at all.
            result = await self._client.get_us_stock_data(
                symbol,
                period=period or "1mo",
                start_date=start_date,
                end_date=end_date,
                auto_adjust=False,
            )
            if result and result.get("optimizasyon_uygulandı"):
                raw_count = result.get("ham_veri_sayisi")
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
            # BtcTurk's graph API takes a unix-second window. The requested window
            # used to be dropped here entirely: the call was get_kripto_ohlc(symbol).
            win_start, win_end = self._resolve_window(period, start_date, end_date)
            result = await self._client.get_kripto_ohlc(
                symbol,
                from_time=int(win_start.timestamp()) if win_start else None,
                to_time=int(win_end.timestamp()) if win_end else None,
            )
            if result and result.ohlc_data:
                for dp in result.ohlc_data:
                    data_points.append({
                        "date": dp.time,  # KriptoOHLC uses 'time' not 'timestamp'
                        "open": dp.open,
                        "high": dp.high,
                        "low": dp.low,
                        "close": dp.close,
                        # float, not int: 6.779 BTC is not 6 BTC.
                        "volume": float(dp.volume) if dp.volume is not None else None,
                    })

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            # Same bug as CRYPTO_TR: the window was never forwarded. Coinbase's
            # Advanced Trade API wants unix seconds as strings — an ISO date earns
            # an HTTP 400 ("Invalid start timestamp") that the provider swallows
            # into an empty candle list.
            win_start, win_end = self._resolve_window(period, start_date, end_date)

            # Coinbase caps at 350 candles per request. Over that it answers HTTP 400,
            # the provider swallows it into an empty candle list, and the caller was
            # told "no data" — when the truth is the window is too wide. A 1-year
            # daily request (365 candles) hits this every time.
            if win_start and win_end:
                span_days = (win_end - win_start).days
                if span_days > COINBASE_MAX_CANDLES:
                    raise ValueError(
                        f"Coinbase serves at most {COINBASE_MAX_CANDLES} candles per "
                        f"request; {span_days} days of {interval} bars were asked for. "
                        f"Narrow the window, or use market='crypto_tr' (BtcTurk), "
                        f"which has no such cap."
                    )

            result = await self._client.get_coinbase_ohlc(
                symbol,
                start=str(int(win_start.timestamp())) if win_start else None,
                end=str(int(win_end.timestamp())) if win_end else None,
                granularity=self._coinbase_granularity(interval),
            )
            if result and result.candles:
                for dp in result.candles:
                    data_points.append({
                        "date": dp.start,  # CoinbaseCandle uses 'start' not 'time'
                        "open": dp.open,
                        "high": dp.high,
                        "low": dp.low,
                        "close": dp.close,
                        # float, not int: 6.779 BTC is not 6 BTC.
                        "volume": float(dp.volume) if dp.volume is not None else None,
                    })
            # Coinbase returns candles newest-first; every other market here ascends.
            # Normalize rather than propagate the inconsistency — data[-1] must mean
            # the same thing in every market (CLAUDE.md #6).
            data_points.sort(key=lambda row: str(row["date"]))

        elif market == MarketType.FX:
            import borsapy as bp
            from providers.canonical_series import resolve_fx_asset
            source = "borsapy"
            try:
                # Resolve through the same registry get_fx_data uses. This branch used
                # to pass the symbol straight to bp.FX(), so `XPT-USD` returned the
                # USD platinum ounce here and the TRY platinum gram there — two assets,
                # two currencies, one name. `gumus` and `ons` had no historical path
                # at all because only the other tool applied the mapping.
                fx = bp.FX(resolve_fx_asset(symbol).provider_symbol)
                hist = fx.history(period=period or "1mo", start=start_date, end=end_date)
                if hist is not None and len(hist) > 0:
                    for idx, row in hist.iterrows():
                        date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
                        data_points.append({
                            "date": date_str,
                            "open": row.get('Open'),
                            "high": row.get('High'),
                            "low": row.get('Low'),
                            "close": row.get('Close'),
                            "volume": None
                        })
            except Exception as e:
                logger.warning(f"FX historical data error for {symbol}: {e}")

        # Forwarding the window to the provider is not enough: BtcTurk's graph API is
        # handed from/to and still answers with a superset (a 07-01..07-10 request came
        # back 06-30..07-12). Clamp to what was actually asked for. Providers that do
        # honour the window are unaffected.
        if start_date or end_date:
            data_points = self._clamp_to_window(data_points, start_date, end_date)

        if not data_points:
            # An empty-but-successful payload tells the model "this asset exists and
            # has no history here", which is a far stronger claim than "the fetch
            # failed" — and it is usually the false one. See CLAUDE.md #7. Coinbase's
            # HTTP 400 used to arrive here as a cheerful empty series.
            window = (
                f"{start_date or 'start'}..{end_date or 'now'}"
                if (start_date or end_date) else (period or "default period")
            )
            raise DataNotAvailableError(
                f"No historical data for '{symbol}' ({market.value}) over {window}"
            )

        result_dict = {
            "metadata": self._create_metadata(market, symbol, source),
            # FX asset names are genuinely lower-case (gram-altin, ons-altin); upper-
            # casing them is lossy. Tickers are upper-case by convention.
            "symbol": symbol if market == MarketType.FX else symbol.upper(),
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "data": data_points,
            "data_points": len(data_points)
        }

        # Ranges longer than a month are resampled to weekly/monthly bars to bound
        # response size. Without saying so, rows spaced 7 or 30 days apart look like
        # daily candles with gaps, and any indicator computed off them is wrong.
        if raw_count and len(data_points) < raw_count:
            bar_interval = self._infer_bar_interval(data_points)
            result_dict["bar_interval"] = bar_interval
            result_dict["warnings"] = [
                f"Resampled from {raw_count} daily bars to {len(data_points)} "
                f"{bar_interval} bars to bound response size. These are NOT daily "
                f"candles. For daily bars, request a period of 1mo or shorter, or pass "
                f"an explicit start_date/end_date range."
            ]

        return result_dict

    @staticmethod
    def _clamp_to_window(
        rows: List[Dict[str, Any]],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Drop rows outside [start_date, end_date]. Both bounds are inclusive.

        Row dates may carry a time component or a timezone; only the date part is
        compared. A row whose date cannot be parsed is kept, so a format change
        upstream degrades to "too much data" rather than to silence.
        """
        def in_window(row: Dict[str, Any]) -> bool:
            raw = str(row.get("date", ""))[:10]
            if len(raw) != 10:
                return True
            if start_date and raw < start_date:
                return False
            if end_date and raw > end_date:
                return False
            return True

        return [row for row in rows if in_window(row)]

    # Calendar spans for the period vocabulary, used to turn a period into an explicit
    # window for providers that take dates (the crypto exchanges) or that misread the
    # period keyword (borsapy treats it as a bar count).
    #
    # These MUST match yfinance_provider's own period->days map, because both feed
    # TokenOptimizer, whose weekly/monthly threshold sits exactly at 180 days. A "6mo"
    # of 183 here against 180 there put the two markets on opposite sides of it: BIST
    # answered with 7 monthly bars and US with 26 weekly ones, for the same request.
    _PERIOD_DAYS = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825,
    }

    @staticmethod
    def _resolve_window(
        period: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Resolve (period | start/end) into an explicit datetime window.

        Explicit dates win. A period is measured back from now. Returns (None, None)
        when neither is given, letting the provider apply its own default.
        """
        if start_date or end_date:
            start = datetime.fromisoformat(start_date) if start_date else None
            end = datetime.fromisoformat(end_date) if end_date else datetime.now()
            return start, end

        if period:
            days = MarketRouter._PERIOD_DAYS.get(period)
            if days is None:
                # "ytd" / "max" have no fixed span; let the provider default.
                if period == "ytd":
                    now = datetime.now()
                    return datetime(now.year, 1, 1), now
                return None, None
            end = datetime.now()
            return end - timedelta(days=days), end

        return None, None

    @staticmethod
    def _coinbase_granularity(interval: str) -> str:
        """Map the interval vocabulary onto Coinbase's granularity keywords."""
        return {
            "1m": "ONE_MINUTE",
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "1h": "ONE_HOUR",
            "6h": "SIX_HOUR",
            "1d": "ONE_DAY",
        }.get(interval, "ONE_DAY")

    @staticmethod
    def _infer_bar_interval(data_points: List[Dict[str, Any]]) -> str:
        """Infer bar spacing from the MEDIAN gap between bars.

        This used to read the final two bars alone. The last bucket of a resampled
        series is almost always partial — a month that is only twelve days old — so a
        monthly series announced itself as `weekly`. `bar_interval` is the single
        field telling the caller these are not daily candles; getting it wrong defeats
        the warning it belongs to.
        """
        if len(data_points) < 2:
            return "unknown"
        try:
            dates = sorted(
                datetime.fromisoformat(str(dp["date"])[:10]) for dp in data_points
            )
        except Exception:
            return "unknown"

        gaps = sorted((dates[i + 1] - dates[i]).days for i in range(len(dates) - 1))
        if not gaps:
            return "unknown"
        gap = gaps[len(gaps) // 2]

        if gap <= 3:
            return "daily"
        if gap <= 10:
            return "weekly"
        if gap <= 45:
            return "monthly"
        return "quarterly"

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
            if result and result.teknik_indiktorler:
                ind = result.teknik_indiktorler
                ma = result.hareketli_ortalamalar
                if result.fiyat_analizi:
                    current_price = result.fiyat_analizi.guncel_fiyat
                if ma:
                    moving_averages = {
                        "sma_5": ma.sma_5,
                        "sma_10": ma.sma_10,
                        "sma_20": ma.sma_20,
                        "sma_50": ma.sma_50,
                        "sma_200": ma.sma_200,
                        "ema_12": ma.ema_12,
                        "ema_26": ma.ema_26
                    }
                indicators = {
                    "rsi_14": ind.rsi_14,
                    "macd": ind.macd,
                    "macd_signal": ind.macd_signal,
                    "macd_histogram": ind.macd_histogram,
                    "bb_upper": ind.bollinger_upper,
                    "bb_middle": ind.bollinger_middle,
                    "bb_lower": ind.bollinger_lower
                }

        elif market == MarketType.CRYPTO_GLOBAL:
            source = "coinbase"
            result = await self._client.get_coinbase_teknik_analiz(symbol)
            if result and result.teknik_indiktorler:
                ind = result.teknik_indiktorler
                ma = result.hareketli_ortalamalar
                if result.fiyat_analizi:
                    current_price = result.fiyat_analizi.guncel_fiyat
                if ma:
                    moving_averages = {
                        "sma_5": ma.sma_5,
                        "sma_10": ma.sma_10,
                        "sma_20": ma.sma_20,
                        "sma_50": ma.sma_50,
                        "sma_200": ma.sma_200,
                        "ema_12": ma.ema_12,
                        "ema_26": ma.ema_26
                    }
                indicators = {
                    "rsi_14": ind.rsi_14,
                    "macd": ind.macd,
                    "macd_signal": ind.macd_signal,
                    "macd_histogram": ind.macd_histogram,
                    "bb_upper": ind.bollinger_upper,
                    "bb_middle": ind.bollinger_middle,
                    "bb_lower": ind.bollinger_lower
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

    def _derive_consensus(self, summary: Dict[str, Any]) -> Optional[str]:
        """Derive consensus from buy/hold/sell counts."""
        if not summary:
            return None
        buy = (summary.get("strong_buy", 0) or 0) + (summary.get("buy", 0) or 0)
        hold = summary.get("hold", 0) or 0
        sell = (summary.get("sell", 0) or 0) + (summary.get("strong_sell", 0) or 0)
        total = buy + hold + sell
        if total == 0:
            return None
        if buy > hold + sell:
            return "Buy"
        elif sell > buy + hold:
            return "Sell"
        else:
            return "Hold"

    async def _get_analyst_single(self, symbol: str, market: MarketType) -> Dict[str, Any]:
        """Get analyst data for a single symbol."""
        summary = None
        ratings = []
        current_price = None
        upside = None
        mean_target = None
        low_target = None
        high_target = None

        if market == MarketType.BIST:
            ticker = self._get_ticker_with_suffix(symbol, market)
            result = await self._client.get_analist_verileri_yfinance(ticker)
            if result:
                if result.get("fiyat_hedefleri"):
                    fh = result["fiyat_hedefleri"]
                    if fh and len(fh) > 0:
                        mean_target = getattr(fh[0], 'ortalama', None)
                        low_target = getattr(fh[0], 'dusuk', None)
                        high_target = getattr(fh[0], 'yuksek', None)
                        current_price = getattr(fh[0], 'guncel', None)
                if result.get("tavsiye_ozeti"):
                    s = result["tavsiye_ozeti"]
                    summary = {
                        "strong_buy": 0,
                        "buy": getattr(s, 'satin_al', 0) or 0,
                        "hold": getattr(s, 'tut', 0) or 0,
                        "sell": getattr(s, 'sat', 0) or 0,
                        "strong_sell": 0,
                        "mean_target": mean_target,
                        "low_target": low_target,
                        "high_target": high_target,
                    }
                    if current_price and mean_target:
                        upside = ((mean_target - current_price) / current_price) * 100
                    summary["consensus"] = self._derive_consensus(summary)

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
                        "mean_target": mean_target,
                        "low_target": low_target,
                        "high_target": high_target,
                    }
                    summary["consensus"] = self._derive_consensus(summary)
                if result.get("tavsiyeler"):
                    for r in result["tavsiyeler"][:10]:
                        date_str = getattr(r, 'tarih', None)
                        if hasattr(date_str, 'isoformat'):
                            date_str = date_str.isoformat()
                        ratings.append({
                            "firm": getattr(r, 'firma', None),
                            "rating": getattr(r, 'guncel_derece', None),
                            "previous_rating": getattr(r, 'onceki_derece', None),
                            "action": getattr(r, 'aksiyon', None),
                            "price_target": getattr(r, 'fiyat_hedefi', None),
                            "date": str(date_str) if date_str else None
                        })

        return {
            "symbol": symbol.upper(),
            "current_price": current_price,
            "summary": summary,
            "ratings": ratings,
            "upside_potential": upside
        }

    async def get_analyst_data(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get analyst ratings and recommendations. Returns raw dict."""
        import asyncio
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "yfinance"
        warnings = []

        if not is_multi or len(symbol_list) == 1:
            symbol = symbol_list[0]
            single_result = await self._get_analyst_single(symbol, market)
            single_result["metadata"] = self._create_metadata(market, symbol_list, source, warnings=warnings)
            return single_result

        # Multi-ticker: fetch all in parallel
        tasks = [self._get_analyst_single(s, market) for s in symbol_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                warnings.append(f"{symbol_list[i]}: {str(r)}")
            else:
                data.append(r)

        return {
            "metadata": self._create_metadata(market, symbol_list, source, warnings=warnings),
            "tickers": [s.upper() for s in symbol_list],
            "data": data,
            "successful_count": len(data),
            "failed_count": len(symbol_list) - len(data),
            "warnings": warnings
        }

    # --- Multi-ticker fan-out ---

    async def _fan_out_multi(
        self,
        symbol_list: List[str],
        market: MarketType,
        source: str,
        fetch_one,
        warnings: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run a per-symbol fetch in parallel and build the multi-ticker envelope."""
        warnings = warnings if warnings is not None else []
        results = await asyncio.gather(
            *(fetch_one(s) for s in symbol_list), return_exceptions=True
        )
        data = []
        for sym, r in zip(symbol_list, results):
            if isinstance(r, Exception):
                warnings.append(f"{sym}: {r}")
            else:
                data.append(r)
        return {
            "metadata": self._create_metadata(
                market, symbol_list, source,
                successful=len(data),
                failed=len(symbol_list) - len(data),
                warnings=warnings
            ),
            "tickers": [s.upper() for s in symbol_list],
            "data": data,
            "successful_count": len(data),
            "failed_count": len(symbol_list) - len(data),
            "warnings": warnings
        }

    # --- Dividends ---

    async def _get_dividends_single(self, symbol: str, market: MarketType) -> Dict[str, Any]:
        """Get dividend history for a single symbol (no metadata)."""
        dividend_history = []
        stock_splits = []
        current_yield = None
        annual_dividend = None
        ex_date = None
        payout_ratio = None

        if market == MarketType.BIST:
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
            "symbol": symbol.upper(),
            "current_yield": current_yield,
            "annual_dividend": annual_dividend,
            "ex_dividend_date": ex_date,
            "payout_ratio": payout_ratio,
            "dividend_history": dividend_history,
            "stock_splits": stock_splits
        }

    async def get_dividends(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get dividend history and information. Returns raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "yfinance"

        if not is_multi or len(symbol_list) == 1:
            single_result = await self._get_dividends_single(symbol_list[0], market)
            return {
                "metadata": self._create_metadata(market, symbol_list, source),
                **single_result
            }

        return await self._fan_out_multi(
            symbol_list, market, source,
            lambda s: self._get_dividends_single(s, market)
        )

    # --- Earnings ---

    async def _get_earnings_single(self, symbol: str, market: MarketType) -> Dict[str, Any]:
        """Get earnings data for a single symbol (no metadata). "_source" is popped by the caller."""
        source = "yfinance"
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
            "_source": source,
            "symbol": symbol.upper(),
            "next_earnings_date": next_date,
            "earnings_history": earnings_history,
            "growth_estimates": growth_estimates
        }

    async def get_earnings(
        self,
        symbols: Union[str, List[str]],
        market: MarketType
    ) -> Dict[str, Any]:
        """Get earnings calendar and history. Returns raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]

        if not is_multi or len(symbol_list) == 1:
            single_result = await self._get_earnings_single(symbol_list[0], market)
            source = single_result.pop("_source")
            return {
                "metadata": self._create_metadata(market, symbol_list, source),
                **single_result
            }

        async def fetch_one(sym):
            result = await self._get_earnings_single(sym, market)
            result.pop("_source")
            return result

        return await self._fan_out_multi(symbol_list, market, "yfinance", fetch_one)

    # --- Financial Statements ---

    async def _get_financial_statements_single(
        self,
        symbol: str,
        market: MarketType,
        statement_type: StatementType,
        period: PeriodType,
        last_n: int = None
    ) -> Dict[str, Any]:
        """Get financial statements for a single symbol (no metadata)."""
        statements = []
        warnings = []
        period_str = "annual" if period == PeriodType.ANNUAL else "quarterly"

        if market == MarketType.BIST:
            types_to_fetch = []
            if statement_type in [StatementType.BALANCE, StatementType.ALL]:
                types_to_fetch.append(("balance", self._client.get_bilanco))
            if statement_type in [StatementType.INCOME, StatementType.ALL]:
                types_to_fetch.append(("income", self._client.get_kar_zarar))
            if statement_type in [StatementType.CASHFLOW, StatementType.ALL]:
                types_to_fetch.append(("cashflow", self._client.get_nakit_akisi))

            for stmt_name, fetch_func in types_to_fetch:
                try:
                    result = await fetch_func(symbol, period_str, last_n)
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
            "symbol": symbol.upper(),
            "statements": statements,
            "warnings": warnings
        }

    async def get_financial_statements(
        self,
        symbols: Union[str, List[str]],
        market: MarketType,
        statement_type: StatementType = StatementType.ALL,
        period: PeriodType = PeriodType.ANNUAL,
        last_n: int = None
    ) -> Dict[str, Any]:
        """Get financial statements (balance sheet, income, cash flow). Returns raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        source = "borsapy" if market == MarketType.BIST else "yfinance"

        if not is_multi or len(symbol_list) == 1:
            single_result = await self._get_financial_statements_single(
                symbol_list[0], market, statement_type, period, last_n
            )
            return {
                "metadata": self._create_metadata(
                    market, symbol_list, source, warnings=single_result["warnings"]
                ),
                "statements": single_result["statements"]
            }

        warnings = []

        async def fetch_one(sym):
            result = await self._get_financial_statements_single(
                sym, market, statement_type, period, last_n
            )
            for w in result.pop("warnings"):
                warnings.append(f"{sym}: {w}")
            return result

        return await self._fan_out_multi(symbol_list, market, source, fetch_one, warnings=warnings)

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

                        # Fallback: borsapy/İş Yatırım frequently omits trailingPE for
                        # BIST names (e.g. ASELS), which then gets null-stripped from the
                        # response and looks like missing data. İş Yatırım's own net
                        # income (netProceeds) is parent-only/solo, so deriving P/E from
                        # it is misleading; yfinance reports a consolidated trailing P/E,
                        # so backfill F/K from there instead of leaving it absent.
                        if valuation.get("pe_ratio") is None:
                            try:
                                yf_result = await self._client.yfinance_provider.get_hizli_bilgi(symbol, market="BIST")
                                bilgi = yf_result.get("bilgiler") if yf_result else None
                                yf_pe = getattr(bilgi, "pe_ratio", None) if bilgi else None
                                if yf_pe:
                                    valuation["pe_ratio"] = round(float(yf_pe), 2)
                                    ratio_warnings.append(
                                        "F/K (P/E) not provided by İş Yatırım; sourced from Yahoo Finance (consolidated trailing P/E)."
                                    )
                                    if current_price is None:
                                        current_price = getattr(bilgi, "last_price", None)
                            except Exception as fallback_err:
                                logger.debug(f"yfinance P/E fallback failed for {symbol}: {fallback_err}")
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

    # A blue chip can carry 60 years of quarterly dividends. Keep the recent ones.
    _MAX_DIVIDEND_ROWS = 24

    async def _get_corporate_actions_single(
        self,
        symbol: str,
        market: MarketType,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get corporate actions for a single symbol (no metadata)."""
        capital_increases = []
        dividend_history = []

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
                            "total_amount": t.get("toplam_tutar"),
                            "gross_rate_percent": t.get("brut_oran"),
                            "currency": "TRY",
                        })
            except Exception as e:
                logger.warning(f"Error fetching dividend rates: {e}")

        # get_dividends used to be its own tool. It covered BIST *and* US and carried
        # stock splits, while corporate actions were BIST-only — so absorbing it
        # without merging would have dropped every US dividend and every split.
        #
        # The two dividend sources are genuinely different data and keep different
        # names: `dividends` are per-share cash amounts from yfinance, `dividend_rates`
        # are İş Yatırım's gross percentages of nominal. Collapsing them into one list
        # called `dividend_history` (as both tools did, separately) would have silently
        # mixed lira-per-share with percent-of-nominal.
        payout = await self._get_dividends_single(symbol, market)

        # KO has paid a dividend every quarter since 1962 — 258 of them, ~9.7k
        # characters of ancient history nobody asked for. Keep the recent ones and say
        # how many were dropped; a silent truncation reads as "this is all of them".
        dividends = payout.get("dividend_history") or []
        total_dividends = len(dividends)
        warnings: List[str] = []
        if total_dividends > self._MAX_DIVIDEND_ROWS:
            dividends = dividends[-self._MAX_DIVIDEND_ROWS:]
            warnings.append(
                f"Showing the {self._MAX_DIVIDEND_ROWS} most recent of "
                f"{total_dividends} dividends. The full history goes back to "
                f"{payout['dividend_history'][0].get('ex_date', 'inception')}."
            )

        merged = {
            "symbol": symbol.upper(),
            "current_yield": payout.get("current_yield"),
            "annual_dividend": payout.get("annual_dividend"),
            "ex_dividend_date": payout.get("ex_dividend_date"),
            "payout_ratio": payout.get("payout_ratio"),
            "dividends": dividends,
            "dividends_total_count": total_dividends,
            "stock_splits": payout.get("stock_splits") or [],
        }
        if market == MarketType.BIST:
            merged["capital_increases"] = capital_increases
            merged["dividend_rates"] = dividend_history
        if warnings:
            merged["warnings"] = warnings
        return merged

    async def get_corporate_actions(
        self,
        symbols: Union[str, List[str]],
        market: MarketType = MarketType.BIST,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get corporate actions (dividends, splits, capital increases). Raw dict."""
        is_multi = isinstance(symbols, list)
        symbol_list = symbols if is_multi else [symbols]
        # BIST capital increases come from İş Yatırım; everything else is yfinance.
        # Reporting "isyatirim" for a US ticker was simply false.
        source = "isyatirim+yfinance" if market == MarketType.BIST else "yfinance"

        if not is_multi or len(symbol_list) == 1:
            single_result = await self._get_corporate_actions_single(symbol_list[0], market, year)
            return {
                "metadata": self._create_metadata(market, symbol_list, source),
                **single_result
            }

        return await self._fan_out_multi(
            symbol_list, market, source,
            lambda s: self._get_corporate_actions_single(s, market, year)
        )

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
        ohlc = None

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
            elif data_type == DataType.OHLC:
                result = await self._client.get_kripto_ohlc(symbol)
                if result and result.ohlc_data:
                    ohlc = [
                        {
                            "date": c.time.isoformat() if c.time else None,
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "close": c.close,
                            "volume": c.volume,
                        }
                        for c in result.ohlc_data
                    ]

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
            elif data_type == DataType.OHLC:
                result = await self._client.get_coinbase_ohlc(symbol, granularity="ONE_DAY")
                if result and result.candles:
                    ohlc = [
                        {
                            "date": c.start.isoformat() if c.start else None,
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "close": c.close,
                            "volume": c.volume,
                        }
                        for c in result.candles
                    ]

        # BtcTurk returns candles oldest-first, Coinbase newest-first. Normalize to
        # chronological order before capping, so the cap keeps the most recent bars.
        if ohlc:
            ohlc.sort(key=lambda c: c["date"] or "")
            ohlc = ohlc[-100:]

        return {
            "metadata": self._create_metadata(market, symbol, source),
            "data_type": data_type.value if hasattr(data_type, 'value') else str(data_type),
            "ticker": ticker,
            "orderbook": orderbook,
            "trades": trades,
            "exchange_info": exchange_info,
            "ohlc": ohlc
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
        """Get foreign exchange rates. Returns raw dict.

        The payload is mode-specific: historical mode carries 'historical_data' and
        current mode carries 'rates'. It used to always carry both, so a historical
        request shipped an empty 'rates' list, which the markdown renderer then
        announced as "rates: Sonuç bulunamadı." right next to perfectly good data.
        """
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
            if not historical_data:
                # An empty-but-successful payload reads to an LLM as "this asset
                # exists and has no history", which is a far stronger claim than
                # "the fetch failed". See CLAUDE.md "Common Issues" #7.
                raise DataNotAvailableError(
                    f"No historical FX data for '{symbols[0]}' between "
                    f"{start_date or 'start'} and {end_date or 'now'}"
                )
            return {
                "metadata": self._create_metadata(MarketType.FX, symbols, source),
                "historical_data": historical_data,
            }
        else:
            failed: List[str] = []
            if symbols:
                # Fetch all symbols concurrently instead of serially; each
                # get_dovizcom_guncel_kur is an independent network round-trip.
                results = await asyncio.gather(
                    *(self._client.get_dovizcom_guncel_kur(sym) for sym in symbols),
                    return_exceptions=True
                )
                for sym, result in zip(symbols, results):
                    if isinstance(result, Exception):
                        logger.warning(f"FX fetch failed for {sym}: {result}")
                        failed.append(f"{sym}: {result}")
                        continue
                    if result is None or result.guncel_deger is None:
                        # borsapy's get_current asks canlidoviz for a 5-day window;
                        # some items (gram-platin, ons-altin) answer with an empty
                        # body and the provider swallows it into guncel_deger=None.
                        # Dropping the row silently shipped `successful_count: 1`
                        # with no data at all.
                        logger.warning(f"FX quote unavailable for {sym}")
                        failed.append(f"{sym}: no current quote available")
                        continue
                    ts = result.son_guncelleme
                    rates.append({
                        "symbol": sym,
                        "name": result.varlik_adi or sym,
                        "buy": None,
                        "sell": result.guncel_deger,
                        "change": result.degisim,
                        "change_percent": result.degisim_yuzde,
                        "high": None,
                        "low": None,
                        "timestamp": ts.isoformat() if ts else None,
                    })

            if not rates:
                raise DataNotAvailableError(
                    "No current FX quotes for "
                    f"{', '.join(symbols or ['all'])}. " + "; ".join(failed)
                )

        payload = {
            "metadata": self._create_metadata(MarketType.FX, symbols or ["all"], source),
            "rates": rates,
        }
        # A partial batch keeps its good rows, but never silently: one dead symbol
        # among five must not read as five healthy quotes.
        if failed:
            payload["warnings"] = [f"No current quote for {f}" for f in failed]
        return payload

    # --- Fund Data ---

    # A window this wide around each endpoint stays under TokenOptimizer's 30-day
    # daily/weekly threshold, so the bars we price from are real daily closes.
    #
    # Fetching the WHOLE comparison window instead would be the obvious thing and the
    # wrong one: a 6-month span comes back resampled to weekly bars, and
    # first_on_or_after(start) would then land on some Monday's bucket rather than the
    # close on the day actually requested.
    _ENDPOINT_PAD_DAYS = 12

    async def _canonical_window(self, ref, start_date: str, end_date: str):
        """Fetch just enough of an asset's history to price both endpoints."""
        from providers.canonical_series import to_canonical

        pad = timedelta(days=self._ENDPOINT_PAD_DAYS)
        s = datetime.fromisoformat(start_date)
        e = datetime.fromisoformat(end_date)

        # One fetch if the padded endpoint windows would meet anyway; two if not.
        if (e - s).days <= 2 * self._ENDPOINT_PAD_DAYS:
            windows = [((s - pad).strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"))]
        else:
            windows = [
                ((s - pad).strftime("%Y-%m-%d"), (s + pad).strftime("%Y-%m-%d")),
                ((e - pad).strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")),
            ]

        merged = []
        for w_start, w_end in windows:
            if ref.market == "fund":
                raw = await self.get_fund_price_series(ref.symbol, w_start, w_end)
            else:
                raw = await self.get_historical_data(
                    ref.symbol, MarketType(ref.market),
                    start_date=w_start, end_date=w_end,
                )
            merged.append(to_canonical(raw, market=ref.market))

        if len(merged) == 1:
            return merged[0]

        # Same asset, two windows: one series, deduplicated by date.
        seen = {}
        for series in merged:
            for bar in series.bars:
                seen[bar.date] = bar
        from providers.canonical_series import CanonicalSeries
        return CanonicalSeries(meta=merged[0].meta, bars=list(seen.values()))

    async def get_quote(
        self,
        symbol: Union[str, List[str]],
        market: MarketType,
    ) -> Dict[str, Any]:
        """"What is it worth right now" — for a stock, a currency, a metal or a coin.

        Absorbs get_quick_info (equity metrics), get_fx_data's current mode, and
        get_crypto_market's ticker mode. They asked one question through three shapes.

        Each market answers with what it actually has: equities carry P/E, P/B and the
        52-week range; FX carries a dealer quote; crypto carries bid/ask and 24h volume.
        The skeleton is shared, the payload is not padded with nulls to pretend
        otherwise.
        """
        if market in (MarketType.BIST, MarketType.US):
            return await self.get_quick_info(symbol, market)

        symbols = symbol if isinstance(symbol, list) else [symbol]

        if market == MarketType.FX:
            return await self.get_fx_data(symbols=symbols, historical=False)

        if market in (MarketType.CRYPTO_TR, MarketType.CRYPTO_GLOBAL):
            exchange = (ExchangeType.BTCTURK if market == MarketType.CRYPTO_TR
                        else ExchangeType.COINBASE)
            quotes = []
            for sym in symbols:
                raw = await self.get_crypto_market(sym, exchange, DataType.TICKER)
                ticker = raw.get("ticker") or {}
                if not ticker:
                    raise DataNotAvailableError(
                        f"No current quote for '{sym}' on "
                        f"{'BtcTurk' if market == MarketType.CRYPTO_TR else 'Coinbase'}"
                    )
                quotes.append({"symbol": sym, **ticker})
            return {
                "metadata": self._create_metadata(market, symbols, "exchange"),
                "quotes": quotes,
            }

        raise ValueError(
            f"get_quote does not serve market '{market.value}'. "
            "Supported: bist, us, fx, crypto_tr, crypto_global."
        )

    async def compare_assets(
        self,
        assets: List[Any],
        start_date: str,
        end_date: Optional[str] = None,
        base_currency: str = "TRY",
        initial_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compare period returns across markets, in TRY and USD.

        The whole reason this exists: answering "ASELS mi altın mı?" took six tool
        calls and left the currency conversion and the window alignment to the model.
        """
        from providers.asset_resolver import AssetResolver
        from providers.compare import AssetWindow, compute_comparison

        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        if start_date >= end_date:
            raise ValueError(
                f"start_date ({start_date}) must be before end_date ({end_date})"
            )

        if not hasattr(self, "_asset_resolver"):
            self._asset_resolver = AssetResolver(self._client)

        refs = [await self._asset_resolver.resolve(a) for a in assets]

        # USDTRY is fetched over the same padded windows and read at each asset's own
        # endpoint dates, so a fund converting a day earlier than a stock uses the rate
        # that applied on the day it actually traded.
        from providers.asset_resolver import AssetRef
        usdtry = await self._canonical_window(
            AssetRef("USD", "fx"), start_date, end_date
        )

        series = await asyncio.gather(
            *(self._canonical_window(r, start_date, end_date) for r in refs)
        )

        rows = compute_comparison(
            [AssetWindow(s) for s in series],
            usdtry,
            start_date=start_date,
            end_date=end_date,
            initial_amount=initial_amount,
        )

        warnings = [
            "Returns are PRICE returns and exclude dividends. Splits are adjusted.",
        ]
        for row in rows:
            for w in row.pop("warnings", []):
                if w not in warnings:
                    warnings.append(f"{row['asset']}: {w}")

        return {
            "metadata": {
                "window": f"{start_date} .. {end_date}",
                "base_currency": base_currency,
                "fx_series": "USD (borsapy/canlidoviz)",
                "initial_amount": initial_amount,
                "resolved": [f"{r.symbol}={r.market}" for r in refs],
            },
            "comparison": rows,
            "warnings": warnings,
        }

    async def get_fund_price_series(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """A fund's full NAV series, for the canonical layer.

        `get_fund_data` calls fund.history() but only ever emits 7 rows of
        `recent_prices`, so there was no path to a fund's price history at all.

        TEFAS is close-only: no OHLC, no volume. The v2 API accepts only fixed period
        buckets (5 years is the maximum); borsapy serves an arbitrary window by
        fetching the smallest covering bucket and filtering client-side.

        The `published_date` here is TEFAS's `tarih`. It is NOT the date the NAV is
        marked to — see canonical_series.fund_valuation_date, which shifts it back a
        trading day. Callers must go through to_canonical() rather than reading these
        dates as session dates.
        """
        import borsapy as bp

        fund = bp.Fund(symbol.upper())
        hist = await asyncio.get_running_loop().run_in_executor(
            None, lambda: fund.history(start=start_date, end=end_date)
        )
        if hist is None or len(hist) == 0:
            raise DataNotAvailableError(
                f"No NAV history for fund '{symbol}' between "
                f"{start_date or 'start'} and {end_date or 'now'}"
            )

        rows = [
            {"published_date": idx.strftime("%Y-%m-%d"), "close": float(row["Price"])}
            for idx, row in hist.iterrows()
        ]
        return {
            "symbol": symbol.upper(),
            "currency": "TRY",
            "source": "tefas",
            "data": rows,
        }

    async def get_fund_data(
        self,
        symbol: str,
        include_portfolio: bool = False,
        include_performance: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get mutual fund data using borsapy. Returns raw dict.

        Args:
            symbol: Fund code (e.g., TPC, IPB)
            include_portfolio: Include portfolio allocation
            include_performance: Include performance history
            start_date: Custom range start (YYYY-MM-DD) for calculating custom_return
            end_date: Custom range end (YYYY-MM-DD) for calculating custom_return
        """
        import borsapy as bp
        from datetime import datetime, timedelta

        source = "borsapy"
        fund_info = None
        portfolio = None
        performance = None
        custom_return = None
        recent_prices = None
        warnings = []

        loop = asyncio.get_event_loop()
        try:
            fund = await loop.run_in_executor(None, bp.Fund, symbol.upper())
            info = await loop.run_in_executor(None, lambda: fund.info)

            if not info:
                raise ValueError(
                    f"No data for fund: {symbol.upper()}. The code may be delisted or "
                    f"misspelled - use search_symbol(market='fund') to find valid codes."
                )

            if info:
                # Calculate weekly return from history if not provided
                weekly_return = info.get("weekly_return")
                if weekly_return is None:
                    try:
                        week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                        hist = await loop.run_in_executor(None, lambda: fund.history(start=week_start))
                        if hist is not None and len(hist) >= 2:
                            first_price = hist['Price'].iloc[0]
                            last_price = hist['Price'].iloc[-1]
                            weekly_return = round(((last_price / first_price) - 1) * 100, 2)
                    except Exception as e:
                        logger.debug(f"Could not calculate weekly return for {symbol}: {e}")

                # Calculate custom range return if dates provided.
                # TEFAS publishes prices at 6-decimal precision; keep that here so
                # callers can read the actual announced price instead of deriving it
                # from a rounded percentage.
                if start_date:
                    try:
                        hist = await loop.run_in_executor(None, lambda: fund.history(start=start_date, end=end_date))
                        if hist is not None and len(hist) >= 1:
                            first_price = float(hist['Price'].iloc[0])
                            last_price = float(hist['Price'].iloc[-1])
                            actual_start = str(hist.index[0])[:10]
                            actual_end = str(hist.index[-1])[:10]
                            custom_return = {
                                "start_date": actual_start,
                                "end_date": actual_end,
                                "start_price": round(first_price, 6),
                                "end_price": round(last_price, 6),
                                "return_percent": (
                                    round(((last_price / first_price) - 1) * 100, 4)
                                    if len(hist) >= 2 and first_price else None
                                ),
                                "days": len(hist),
                                "requested_start": start_date,
                                "requested_end": end_date or datetime.now().strftime('%Y-%m-%d'),
                            }
                    except Exception as e:
                        logger.debug(f"Could not calculate custom return for {symbol}: {e}")

                # Recent trading-day prices (actual announced prices, 6-decimal).
                # Lets callers read "yesterday"/last announced price directly from
                # the list instead of back-calculating from a rounded daily_return.
                # history() already returns trading days only, so holidays/weekends
                # are skipped automatically: recent_prices[0] is the last announced
                # price, recent_prices[1] the prior trading day, and so on.
                try:
                    rp_start = (datetime.now() - timedelta(days=16)).strftime('%Y-%m-%d')
                    rp_hist = await loop.run_in_executor(None, lambda: fund.history(start=rp_start))
                    if rp_hist is not None and len(rp_hist) >= 1:
                        recent_rows = []
                        for date_idx, price in rp_hist['Price'].items():
                            recent_rows.append({
                                "date": str(date_idx)[:10],
                                "price": round(float(price), 6),
                            })
                        # Newest first, keep last ~7 trading days
                        recent_rows.sort(key=lambda r: r["date"], reverse=True)
                        recent_prices = recent_rows[:7]
                except Exception as e:
                    logger.debug(f"Could not build recent_prices for {symbol}: {e}")

                fund_info = {
                    "code": info.get("fund_code"),
                    "name": info.get("name"),
                    "category": info.get("category"),
                    "company": info.get("founder"),
                    "price": info.get("price"),
                    "total_assets": info.get("fund_size"),
                    "investor_count": info.get("investor_count"),
                    "daily_return": info.get("daily_return"),
                    "weekly_return": weekly_return,
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

                # Portfolio allocation from borsapy.
                # NOTE: TEFAS migrated (2026-04) to an Akamai-protected Next.js
                # SSR site, so info["allocation"] is no longer populated by the
                # JSON path and comes back None for every fund. Surface an
                # actionable warning instead of silently returning portfolio=null.
                if include_portfolio:
                    allocation = info.get("allocation")
                    if allocation:
                        portfolio = [
                            {"asset_type": a.get("asset_type"), "asset_name": a.get("asset_name"), "weight": a.get("weight")}
                            for a in allocation
                        ]
                    else:
                        warnings.append(
                            "Portfolio allocation is unavailable from the TEFAS JSON "
                            "feed since the 2026-04 TEFAS migration to an Akamai-protected "
                            "SSR site. To enable asset-type breakdown install the "
                            "borsapy[allocation] extra (Scrapling + chromium); for "
                            "individual holdings use borsapy Fund.get_holdings() with an "
                            "OpenRouter API key."
                        )

        except Exception as e:
            # Do not swallow: an unknown/delisted fund code makes borsapy raise
            # DataNotAvailableError, and returning an empty-but-successful payload
            # here reads to a caller as "fund exists, has no data".
            logger.warning(f"borsapy fund error for {symbol}: {e}")
            raise

        result = {
            "metadata": self._create_metadata(MarketType.FUND, symbol, source),
            "fund": fund_info,
            "portfolio": portfolio,
            "performance_history": performance,
            "custom_return": custom_return,
            "recent_prices": recent_prices
        }
        if warnings:
            result["warnings"] = warnings
        return result

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
            # borsapy is the only source here that carries the index *level*. KAP's
            # index search returns the code/name only, which is why this tool used
            # to answer without a price at all.
            source = "borsapy"
            import borsapy as bp
            loop = asyncio.get_event_loop()
            idx_code = code.upper().strip()

            index_obj = await loop.run_in_executor(None, bp.Index, idx_code)
            info = await loop.run_in_executor(None, lambda: index_obj.info)

            if not info:
                raise ValueError(
                    f"No data for index: {idx_code}. Use a BIST index code such as "
                    f"XU100, XU030, or XBANK."
                )

            index_info = {
                "code": info.get("symbol") or idx_code,
                "name": info.get("name") or info.get("description"),
                "market": "bist",
                "value": info.get("last"),
                "change": info.get("change"),
                "change_percent": info.get("change_percent"),
                "open": info.get("open"),
                "high": info.get("high"),
                "low": info.get("low"),
                "previous_close": info.get("prev_close"),
                "volume": info.get("volume"),
            }

            if include_components:
                symbols = await loop.run_in_executor(None, lambda: index_obj.component_symbols)

                # Enrich with company names from KAP's cached list (borsapy returns
                # bare tickers). Names are a nicety; a KAP miss must not drop the row.
                names = {}
                try:
                    companies = await self._client.kap_provider.get_all_companies()
                    names = {c.ticker_kodu: c.sirket_adi for c in companies}
                except Exception as e:
                    logger.warning(f"Could not load KAP names for index components: {e}")

                for s in (symbols or []):
                    components.append({
                        "symbol": s,
                        "name": names.get(s),
                        "weight": None,
                        "sector": None
                    })
                index_info["components_count"] = len(components)

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

    # BIST sector indices, narrowest first so a bank resolves to XBANK (12 members)
    # rather than the broad XUMAL (150). XILTM is tiny but still the right bucket.
    _SECTOR_INDICES = [
        "XILTM", "XBANK", "XELKT", "XUTEK", "XGIDA",
        "XHOLD", "XUHIZ", "XUMAL", "XUSIN",
    ]
    _MAX_PEERS = 24

    async def _bist_sector_peers(self, target: str) -> tuple:
        """Resolve a BIST ticker to its sector index and that index's other members."""
        import borsapy as bp
        loop = asyncio.get_event_loop()

        if not getattr(self, "_sector_membership", None):
            def load(ix):
                try:
                    return ix, list(bp.Index(ix).component_symbols or [])
                except Exception as e:
                    logger.warning(f"Could not load components for {ix}: {e}")
                    return ix, []

            pairs = await asyncio.gather(
                *(loop.run_in_executor(None, load, ix) for ix in self._SECTOR_INDICES)
            )
            self._sector_membership = dict(pairs)

        membership = self._sector_membership
        sector_index = next(
            (ix for ix in self._SECTOR_INDICES if target in membership.get(ix, [])),
            None
        )
        if not sector_index:
            return [], None

        peers = [s for s in membership[sector_index] if s != target]

        # Broad indices (XUSIN has 246 members) would be neither useful nor cheap to
        # price, so narrow them to the liquid BIST-100 names before capping.
        if len(peers) > self._MAX_PEERS:
            try:
                xu100 = set(
                    await loop.run_in_executor(
                        None, lambda: bp.Index("XU100").component_symbols or []
                    )
                )
                liquid = [s for s in peers if s in xu100]
                if liquid:
                    peers = liquid
            except Exception as e:
                logger.warning(f"Could not narrow peers by XU100: {e}")

        return peers[: self._MAX_PEERS], sector_index

    # borsapy's screener returns one column per requested filter, with a stable id
    # per criterion. Asking for all three gives every BIST stock's valuation in a
    # single request -- fanning out Ticker.info per peer instead took ~50s.
    _SCREENER_MARKET_CAP = "criteria_8"   # million TRY
    _SCREENER_PE = "criteria_28"
    _SCREENER_PB = "criteria_30"

    async def _fetch_bist_metrics(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch valuation metrics for BIST tickers via one bulk screener call."""
        import borsapy as bp
        loop = asyncio.get_event_loop()

        df = await loop.run_in_executor(
            None,
            lambda: bp.screen_stocks(pe_min=0, pb_min=0, market_cap_min=0)
        )
        if df is None or df.empty:
            return {}

        wanted = set(symbols)
        metrics = {}
        for _, row in df.iterrows():
            sym = row.get("symbol")
            if sym not in wanted:
                continue
            mcap = row.get(self._SCREENER_MARKET_CAP)
            metrics[sym] = {
                "name": row.get("name"),
                "market_cap": float(mcap) * 1_000_000 if mcap else None,
                "pe_ratio": row.get(self._SCREENER_PE),
                "pb_ratio": row.get(self._SCREENER_PB),
            }
        return metrics

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
            source = "borsapy"
            target = symbol.upper().strip()

            # Peers come from the BIST sector index the stock actually belongs to.
            # This used to pass [symbol] into a multi-stock comparison helper, so the
            # "sector average" was just the stock's own P/E and it had no peers.
            peer_symbols, sector_index = await self._bist_sector_peers(target)
            sector = sector_index

            metrics = await self._fetch_bist_metrics([target] + peer_symbols)

            for sym, m in metrics.items():
                peers.append({
                    "symbol": sym,
                    "name": m.get("name") or sym,
                    "market_cap": m.get("market_cap"),
                    "pe_ratio": m.get("pe_ratio"),
                    "pb_ratio": m.get("pb_ratio"),
                    "is_target": sym == target,
                })

            peers.sort(key=lambda p: p.get("market_cap") or 0, reverse=True)

            # Median, not mean. A sector index routinely contains one peer trading at
            # a P/E in the thousands (post-loss recovery), and a mean over that is not
            # a number anyone should compare against.
            import statistics

            pes = [p["pe_ratio"] for p in peers if p.get("pe_ratio") and p["pe_ratio"] > 0]
            pbs = [p["pb_ratio"] for p in peers if p.get("pb_ratio") and p["pb_ratio"] > 0]
            avg_pe = round(statistics.median(pes), 2) if pes else None
            avg_pb = round(statistics.median(pbs), 2) if pbs else None

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
            "sector_median_pe": avg_pe,
            "sector_median_pb": avg_pb,
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
            content = result.get("markdown_icerik", "")
            summary = result.get("belge_turu", "")
            url = result.get("haber_url", news_id)
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
        """Compare multiple funds side by side using borsapy. Returns raw dict."""
        import borsapy as bp
        from datetime import datetime, timedelta

        source = "borsapy"
        funds = []
        comparison_date = datetime.now().strftime('%Y-%m-%d')
        warnings = []

        for fund_code in fund_codes[:10]:  # Max 10 funds
            try:
                fund = bp.Fund(fund_code.upper())
                info = fund.info

                if info:
                    # Calculate weekly return from history if not provided
                    weekly_return = info.get("weekly_return")
                    if weekly_return is None:
                        try:
                            week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                            hist = fund.history(start=week_start)
                            if hist is not None and len(hist) >= 2:
                                first_price = hist['Price'].iloc[0]
                                last_price = hist['Price'].iloc[-1]
                                weekly_return = round(((last_price / first_price) - 1) * 100, 2)
                        except Exception:
                            pass

                    # Calculate custom range return if dates provided
                    custom_return = None
                    if start_date:
                        try:
                            hist = fund.history(start=start_date, end=end_date)
                            if hist is not None and len(hist) >= 2:
                                first_price = hist['Price'].iloc[0]
                                last_price = hist['Price'].iloc[-1]
                                custom_return = round(((last_price / first_price) - 1) * 100, 2)
                        except Exception:
                            pass

                    funds.append({
                        "code": info.get("fund_code"),
                        "name": info.get("name"),
                        "category": info.get("category"),
                        "company": info.get("founder"),
                        "price": info.get("price"),
                        "daily_return": info.get("daily_return"),
                        "weekly_return": weekly_return,
                        "monthly_return": info.get("return_1m"),
                        "three_month_return": info.get("return_3m"),
                        "six_month_return": info.get("return_6m"),
                        "ytd_return": info.get("return_ytd"),
                        "one_year_return": info.get("return_1y"),
                        "three_year_return": info.get("return_3y"),
                        "five_year_return": info.get("return_5y"),
                        "total_assets": info.get("fund_size"),
                        "investor_count": info.get("investor_count"),
                        "custom_return": custom_return
                    })
            except Exception as e:
                warnings.append(f"{fund_code}: {str(e)}")
                logger.warning(f"Error fetching fund {fund_code}: {e}")

        return {
            "metadata": self._create_metadata(
                MarketType.FUND, fund_codes, source,
                successful=len(funds), failed=len(fund_codes) - len(funds),
                warnings=warnings
            ),
            "funds": funds,
            "comparison_date": comparison_date
        }

    # --- Macro Data (Phase 6) ---

    async def get_macro_data(
        self,
        data_type: str,  # inflation, calculate
        inflation_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        basket_value: float = 100.0,
        limit: Optional[int] = None,
        *,
        region: str = "tr",
    ) -> Dict[str, Any]:
        """Inflation data for Turkey, the US, or the euro area. Returns raw dict.

        `region` is keyword-only on purpose: adding it positionally would
        reinterpret an existing get_macro_data("inflation", "ufe") call.
        """
        if region not in ("tr", "us", "eu"):
            raise ValueError(f"Unknown region '{region}'. Supported: tr, us, eu.")

        if region in ("us", "eu"):
            return await self._get_macro_data_global(
                region=region,
                data_type=data_type,
                inflation_type=inflation_type,
                start_date=start_date,
                end_date=end_date,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value,
                limit=limit,
            )

        return await self._get_macro_data_tr(
            data_type=data_type,
            inflation_type=inflation_type or "tufe",
            start_date=start_date,
            end_date=end_date,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            basket_value=basket_value,
            limit=limit,
        )

    async def _get_macro_data_global(
        self,
        region: str,
        data_type: str,
        inflation_type: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        start_year: Optional[int],
        start_month: Optional[int],
        end_year: Optional[int],
        end_month: Optional[int],
        basket_value: float,
        limit: Optional[int],
    ) -> Dict[str, Any]:
        """US CPI-U / euro-area HICP via FredCpiProvider."""
        from providers.fred_cpi_provider import FredCpiProvider

        if not hasattr(self, "_fred_provider"):
            self._fred_provider = FredCpiProvider()
        p = self._fred_provider

        # Rejected, not ignored: US/EU publish only a headline index, and a caller
        # who asked for PPI should learn they did not get it.
        if inflation_type is not None:
            raise ValueError(
                f"inflation_type is not supported for region='{region}': only a "
                f"headline consumer price index is published "
                f"({'CPI-U' if region == 'us' else 'HICP'}). Omit the parameter, "
                f"or use region='tr' for the TÜFE/ÜFE distinction."
            )

        spec = FredCpiProvider.SERIES[region]
        for year in (start_year, end_year):
            if year is not None and year < spec.start_year:
                raise ValueError(
                    f"The {region.upper()} series starts in {spec.start_year}; "
                    f"{year} is before it."
                )

        if data_type == "inflation":
            payload = await p.get_inflation_data(
                region=region,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            payload["calculation"] = None
        elif data_type == "calculate":
            if not all([start_year, start_month, end_year, end_month]):
                raise ValueError(
                    "calculate mode requires start_year, start_month, end_year "
                    "and end_month."
                )
            payload = await p.calculate_inflation(
                region=region,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value,
            )
            payload["inflation_data"] = None
        else:
            raise ValueError(
                f"Unknown data_type '{data_type}'. Supported: inflation, calculate."
            )

        payload["metadata"] = self._create_metadata(
            MarketType.FX, [data_type], payload["source"]
        )
        payload["data_type"] = data_type
        payload["inflation_type"] = None
        return payload

    async def _get_macro_data_tr(
        self,
        data_type: str,
        inflation_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
        start_year: Optional[int],
        start_month: Optional[int],
        end_year: Optional[int],
        end_month: Optional[int],
        basket_value: float,
        limit: Optional[int],
    ) -> Dict[str, Any]:
        """Turkish TÜFE/ÜFE via TCMB. Returns raw dict."""
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

            # TcmbProvider swallows exceptions into an error-bearing object.
            # Reporting that as a successful empty response would tell the caller
            # "TÜFE exists and has no data", which is false.
            if result is None or getattr(result, "error_message", None):
                raise DataNotAvailableError(
                    f"TCMB inflation data unavailable: "
                    f"{getattr(result, 'error_message', 'no response')}"
                )
            if not getattr(result, "data", None):
                raise DataNotAvailableError(
                    "TCMB returned no inflation rows for the requested range."
                )

            inflation_data = []
            for d in result.data:
                inflation_data.append({
                    "date": d.tarih,
                    "rate": d.yillik_enflasyon or 0.0,
                    "change": d.aylik_enflasyon,
                    "cumulative": None
                })

        elif data_type == "calculate":
            if not all([start_year, start_month, end_year, end_month]):
                raise ValueError(
                    "calculate mode requires start_year, start_month, end_year "
                    "and end_month."
                )
            if basket_value <= 0:
                raise ValueError("basket_value must be greater than 0.")

            result = await self._client.calculate_inflation(
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                basket_value=basket_value
            )

            # The error object still carries a `yeni_sepet_degeri` attribute (an
            # empty string), so a hasattr check passes and the falsy value
            # silently becomes "prices did not move". Check the error field.
            if result is None or getattr(result, "error_message", None):
                raise DataNotAvailableError(
                    f"TCMB inflation calculation failed: "
                    f"{getattr(result, 'error_message', 'no response')}"
                )
            if not result.yeni_sepet_degeri:
                raise DataNotAvailableError(
                    "TCMB returned an empty calculation for the requested period."
                )

            final_value = parse_tcmb_number(result.yeni_sepet_degeri)
            total_change = parse_tcmb_number(result.toplam_degisim) or 0.0
            cumulative = (total_change / basket_value) * 100
            period_months = result.toplam_yil * 12 + result.toplam_ay

            calculation = {
                "start_period": f"{start_year}-{start_month:02d}",
                "end_period": f"{end_year}-{end_month:02d}",
                "initial_value": basket_value,
                "final_value": final_value,
                "cumulative_inflation": cumulative,
                "period_months": period_months,
                "start_index": parse_tcmb_number(result.ilk_yil_tufe),
                "end_index": parse_tcmb_number(result.son_yil_tufe),
                "annualized_compound_change": parse_tcmb_number(
                    result.ortalama_yillik_enflasyon
                ),
            }

        return {
            "metadata": self._create_metadata(MarketType.FX, [data_type], source),
            "data_type": data_type,
            "region": "tr",
            "currency": "TRY",
            "source": "TCMB",
            "inflation_type": inflation_type if data_type == "inflation" else None,
            "inflation_data": inflation_data,
            "calculation": calculation
        }

    # --- TCMB EVDS (Elektronik Veri Dağıtım Sistemi) ---

    async def get_evds_data(
        self,
        action: str,
        category_id: Optional[int] = None,
        datagroup_code: Optional[str] = None,
        keyword: Optional[str] = None,
        scope: Optional[str] = "all",
        lang: Optional[str] = "TR",
        series_code: Optional[str] = None,
        series_codes: Optional[List[str]] = None,
        period: Optional[str] = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None,
        aggregation: Optional[str] = None,
        formula: Optional[str] = "level",
        decimals: Optional[int] = None,
        dashboard_name: Optional[str] = None,
        dashboard_id: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> Dict[str, Any]:
        """Route a get_evds_data call to BorsapyEVDSProvider. Returns raw dict."""
        from providers.borsapy_evds_provider import BorsapyEVDSProvider

        if not hasattr(self, "_evds_provider"):
            self._evds_provider = BorsapyEVDSProvider()
        p = self._evds_provider

        if action == "categories":
            payload = await p.get_categories()
        elif action == "datagroups":
            if category_id is None:
                raise ValueError("category_id is required for action='datagroups'")
            payload = await p.get_datagroups(category_id)
        elif action == "series_list":
            if not datagroup_code:
                raise ValueError("datagroup_code is required for action='series_list'")
            payload = await p.get_series_list(datagroup_code)
        elif action == "search":
            if not keyword:
                raise ValueError("keyword is required for action='search'")
            payload = await p.search(keyword, scope=scope or "all", lang=lang or "TR", limit=limit or 200)
        elif action == "search_server":
            if not keyword:
                raise ValueError("keyword is required for action='search_server'")
            payload = await p.search_server(keyword, limit=limit or 100)
        elif action == "series_info":
            if not series_code:
                raise ValueError("series_code is required for action='series_info'")
            payload = await p.get_series_info(series_code)
        elif action == "dashboards":
            payload = await p.list_dashboards()
        elif action == "dashboard":
            payload = await p.get_dashboard(name=dashboard_name, dashboard_id=dashboard_id)
        elif action == "series":
            if not series_code:
                raise ValueError("series_code is required for action='series'")
            payload = await p.get_series(
                series_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                aggregation=aggregation,
                formula=formula,
                decimals=decimals,
                limit=limit,
            )
        elif action == "multi_series":
            if not series_codes:
                raise ValueError("series_codes is required for action='multi_series'")
            payload = await p.get_multi_series(
                series_codes,
                period=period,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                aggregation=aggregation,
                formula=formula,
                decimals=decimals,
                limit=limit,
            )
        elif action == "datagroup_data":
            if not datagroup_code:
                raise ValueError("datagroup_code is required for action='datagroup_data'")
            payload = await p.get_datagroup_data(
                datagroup_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                aggregation=aggregation,
                formula=formula,
                limit=limit,
            )
        else:
            raise ValueError(f"Unknown EVDS action: {action}")

        return {
            "metadata": self._create_metadata(MarketType.FX, [action], "tcmb_evds"),
            "action": action,
            **payload,
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
