"""
BtcTurk Provider
This module is responsible for all interactions with the
BtcTurk Kripto API, including fetching cryptocurrency market data.
"""
import httpx
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any, Union
from models import (
    KriptoExchangeInfoSonucu, KriptoTickerSonucu, KriptoOrderbookSonucu,
    KriptoTradesSonucu, KriptoOHLCSonucu, KriptoKlineSonucu, KriptoTeknikAnalizSonucu,
    TradingPair, Currency, CurrencyOperationBlock, KriptoTicker,
    KriptoOrderbook, KriptoTrade, KriptoOHLC, KriptoKline,
    KriptoHareketliOrtalama, KriptoTeknikIndiktorler, KriptoHacimAnalizi,
    KriptoFiyatAnalizi, KriptoTrendAnalizi
)

logger = logging.getLogger(__name__)

class BtcTurkProvider:
    BASE_URL = "https://api.btcturk.com/api/v2"
    GRAPH_API_URL = "https://graph-api.btcturk.com"
    CACHE_DURATION = 60  # 1 minute cache for exchange info
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._exchange_info_cache: Optional[Dict] = None
        self._last_exchange_info_fetch: float = 0
    
    def _convert_resolution_to_minutes(self, resolution: str) -> int:
        """Convert resolution string to minutes for Graph API."""
        resolution = resolution.upper()
        
        if resolution == "1M":
            return 1
        elif resolution == "5M":
            return 5
        elif resolution == "15M":
            return 15
        elif resolution == "30M":
            return 30
        elif resolution == "1H":
            return 60
        elif resolution == "4H":
            return 240
        elif resolution == "1D":
            return 1440
        elif resolution == "1W":
            return 10080
        else:
            # Default to 1 day for unknown resolutions
            return 1440
    
    def _parse_datetime_input(self, date_str: Union[str, int, None]) -> Optional[int]:
        """
        Parse datetime input to Unix timestamp.
        Supports: '2025-01-01', '2025-01-01 15:30:00', '2025-01-01T15:30:00Z', Unix timestamps
        """
        if date_str is None:
            return None
        
        # If already integer (Unix timestamp), return as is
        if isinstance(date_str, int):
            return date_str
        
        try:
            # Try to parse as integer string (Unix timestamp)
            return int(date_str)
        except (ValueError, TypeError):
            pass
        
        # Parse as ISO date string
        try:
            turkey_tz = ZoneInfo("Europe/Istanbul")
            
            # Handle different formats
            date_str = str(date_str).strip()
            
            # ISO format with timezone
            if 'T' in date_str and 'Z' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                dt = dt.astimezone(turkey_tz)
            # ISO format without timezone (assume Turkey time)
            elif 'T' in date_str:
                dt = datetime.fromisoformat(date_str)
                dt = dt.replace(tzinfo=turkey_tz)
            # Date with space-separated time
            elif ' ' in date_str:
                dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=turkey_tz)
            # Date only
            else:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                dt = dt.replace(tzinfo=turkey_tz)
            
            return int(dt.timestamp())
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse datetime '{date_str}': {e}")
            return None
    
    def _format_timestamp_output(self, timestamp: int) -> str:
        """Format Unix timestamp to human-readable Turkey time."""
        try:
            turkey_tz = ZoneInfo("Europe/Istanbul")
            dt = datetime.fromtimestamp(timestamp, tz=turkey_tz)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError, OSError):
            return f"Invalid timestamp: {timestamp}"
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None, use_graph_api: bool = False) -> Dict[str, Any]:
        """Make HTTP request to BtcTurk API with error handling."""
        try:
            # Use Graph API for klines/history endpoint
            base_url = self.GRAPH_API_URL if use_graph_api else self.BASE_URL
            url = f"{base_url}{endpoint}"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'BorsaMCP/1.0'
            }
            
            response = await self._http_client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            
            data = response.json()
            
            # Graph API doesn't have success field, regular API does
            if not use_graph_api and not data.get('success', True):
                raise Exception(f"API Error: {data.get('message', 'Unknown error')}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {endpoint}: {e}")
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error making request to {endpoint}: {e}")
            raise
    
    async def get_exchange_info(self) -> KriptoExchangeInfoSonucu:
        """
        Get detailed information about all trading pairs and currencies on BtcTurk.
        """
        try:
            # Check cache
            current_time = time.time()
            if (self._exchange_info_cache and 
                (current_time - self._last_exchange_info_fetch) < self.CACHE_DURATION):
                data = self._exchange_info_cache
            else:
                data = await self._make_request("/server/exchangeInfo")
                self._exchange_info_cache = data
                self._last_exchange_info_fetch = current_time
            
            # Parse trading pairs
            trading_pairs = []
            symbols_data = data.get('data', {}).get('symbols', [])
            for symbol in symbols_data:
                trading_pair = TradingPair(
                    id=symbol.get('id'),
                    name=symbol.get('name'),
                    name_normalized=symbol.get('nameNormalized'),
                    status=symbol.get('status'),
                    numerator=symbol.get('numerator'),
                    denominator=symbol.get('denominator'),
                    numerator_scale=symbol.get('numeratorScale'),
                    denominator_scale=symbol.get('denominatorScale'),
                    has_fraction=symbol.get('hasFraction'),
                    filters=symbol.get('filters', {}),
                    order_methods=symbol.get('orderMethods', []),
                    display_format=symbol.get('displayFormat'),
                    maximum_limit_order_price=symbol.get('maximumLimitOrderPrice'),
                    minimum_limit_order_price=symbol.get('minimumLimitOrderPrice')
                )
                trading_pairs.append(trading_pair)
            
            # Parse currencies
            currencies = []
            currencies_data = data.get('data', {}).get('currencies', [])
            for currency in currencies_data:
                currency_obj = Currency(
                    id=currency.get('id'),
                    symbol=currency.get('symbol'),
                    min_withdrawal=currency.get('minWithdrawal'),
                    min_deposit=currency.get('minDeposit'),
                    precision=currency.get('precision'),
                    address=currency.get('address', {}),
                    currency_type=currency.get('currencyType'),
                    tag=currency.get('tag', {}),
                    color=currency.get('color'),
                    name=currency.get('name'),
                    is_address_renewable=currency.get('isAddressRenewable'),
                    get_auto_address_disabled=currency.get('getAutoAddressDisabled'),
                    is_partial_withdrawal_enabled=currency.get('isPartialWithdrawalEnabled')
                )
                currencies.append(currency_obj)
            
            # Parse currency operation blocks
            operation_blocks = []
            blocks_data = data.get('data', {}).get('currencyOperationBlocks', [])
            for block in blocks_data:
                operation_block = CurrencyOperationBlock(
                    currency_symbol=block.get('currencySymbol'),
                    withdrawal_disabled=block.get('withdrawalDisabled'),
                    deposit_disabled=block.get('depositDisabled')
                )
                operation_blocks.append(operation_block)
            
            return KriptoExchangeInfoSonucu(
                trading_pairs=trading_pairs,
                currencies=currencies,
                currency_operation_blocks=operation_blocks,
                toplam_cift=len(trading_pairs),
                toplam_para_birimi=len(currencies)
            )
            
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return KriptoExchangeInfoSonucu(
                trading_pairs=[],
                currencies=[],
                currency_operation_blocks=[],
                toplam_cift=0,
                toplam_para_birimi=0,
                error_message=str(e)
            )
    
    async def get_ticker(self, pair_symbol: Optional[str] = None, quote_currency: Optional[str] = None) -> KriptoTickerSonucu:
        """
        Get ticker data for specific trading pair(s) or all pairs.
        """
        try:
            endpoint = "/ticker"
            params = {}
            
            if pair_symbol:
                params['pairSymbol'] = pair_symbol.upper()
            # Note: BtcTurk API doesn't seem to support filtering by quote currency
            # We'll filter the results manually instead
            
            data = await self._make_request(endpoint, params)
            
            # Parse ticker data
            tickers = []
            ticker_data = data.get('data', [])
            if not isinstance(ticker_data, list):
                ticker_data = [ticker_data]
            
            for ticker in ticker_data:
                ticker_obj = KriptoTicker(
                    pair=ticker.get('pair'),
                    pair_normalized=ticker.get('pairNormalized'),
                    timestamp=ticker.get('timestamp'),
                    last=float(ticker.get('last', 0)),
                    high=float(ticker.get('high', 0)),
                    low=float(ticker.get('low', 0)),
                    bid=float(ticker.get('bid', 0)),
                    ask=float(ticker.get('ask', 0)),
                    open=float(ticker.get('open', 0)),
                    volume=float(ticker.get('volume', 0)),
                    average=float(ticker.get('average', 0)),
                    daily=float(ticker.get('daily', 0)),
                    daily_percent=float(ticker.get('dailyPercent', 0)),
                    denominator_symbol=ticker.get('denominatorSymbol'),
                    numerator_symbol=ticker.get('numeratorSymbol')
                )
                tickers.append(ticker_obj)
            
            # Manual filtering by quote currency if requested
            if quote_currency and not pair_symbol:
                quote_upper = quote_currency.upper()
                filtered_tickers = []
                for ticker in tickers:
                    if ticker.denominator_symbol == quote_upper:
                        filtered_tickers.append(ticker)
                tickers = filtered_tickers
            
            return KriptoTickerSonucu(
                tickers=tickers,
                toplam_cift=len(tickers),
                pair_symbol=pair_symbol,
                quote_currency=quote_currency
            )
            
        except Exception as e:
            logger.error(f"Error getting ticker data: {e}")
            return KriptoTickerSonucu(
                tickers=[],
                toplam_cift=0,
                pair_symbol=pair_symbol,
                quote_currency=quote_currency,
                error_message=str(e)
            )
    
    async def get_orderbook(self, pair_symbol: str, limit: int = 100) -> KriptoOrderbookSonucu:
        """
        Get order book data for a specific trading pair.
        """
        try:
            params = {
                'pairSymbol': pair_symbol.upper(),
                'limit': min(limit, 100)
            }
            
            data = await self._make_request("/orderbook", params)
            
            orderbook_data = data.get('data', {})
            timestamp = orderbook_data.get('timestamp')
            bids = orderbook_data.get('bids', [])
            asks = orderbook_data.get('asks', [])
            
            # Convert bids and asks to proper format
            bid_orders = [(float(price), float(quantity)) for price, quantity in bids]
            ask_orders = [(float(price), float(quantity)) for price, quantity in asks]
            
            orderbook = KriptoOrderbook(
                timestamp=timestamp,
                bids=bid_orders,
                asks=ask_orders,
                bid_count=len(bid_orders),
                ask_count=len(ask_orders)
            )
            
            return KriptoOrderbookSonucu(
                pair_symbol=pair_symbol.upper(),
                orderbook=orderbook
            )
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {pair_symbol}: {e}")
            return KriptoOrderbookSonucu(
                pair_symbol=pair_symbol.upper(),
                orderbook=None,
                error_message=str(e)
            )
    
    async def get_trades(self, pair_symbol: str, last: int = 50) -> KriptoTradesSonucu:
        """
        Get recent trades for a specific trading pair.
        """
        try:
            params = {
                'pairSymbol': pair_symbol.upper(),
                'last': min(last, 50)
            }
            
            data = await self._make_request("/trades", params)
            
            # Parse trades data
            trades = []
            trades_data = data.get('data', [])
            
            for trade in trades_data:
                trade_obj = KriptoTrade(
                    pair=trade.get('pair'),
                    pair_normalized=trade.get('pairNormalized'),
                    numerator=trade.get('numerator'),
                    denominator=trade.get('denominator'),
                    date=trade.get('date'),
                    tid=trade.get('tid'),
                    price=float(trade.get('price', 0)),
                    amount=float(trade.get('amount', 0))
                )
                trades.append(trade_obj)
            
            return KriptoTradesSonucu(
                pair_symbol=pair_symbol.upper(),
                trades=trades,
                toplam_islem=len(trades)
            )
            
        except Exception as e:
            logger.error(f"Error getting trades for {pair_symbol}: {e}")
            return KriptoTradesSonucu(
                pair_symbol=pair_symbol.upper(),
                trades=[],
                toplam_islem=0,
                error_message=str(e)
            )
    
    async def get_ohlc(self, pair: str, from_time: Union[str, int, None] = None, to_time: Union[str, int, None] = None) -> KriptoOHLCSonucu:
        """
        Get OHLC data using dedicated Graph API.
        Only uses graph-api.btcturk.com for OHLC data.
        Default: Last 30 days to prevent response size issues.
        Supports human-readable datetime formats.
        """
        try:
            # Parse datetime inputs
            from_timestamp = self._parse_datetime_input(from_time)
            to_timestamp = self._parse_datetime_input(to_time)
            
            # Build Graph API URL directly
            url = f"{self.GRAPH_API_URL}/v1/ohlcs"
            params = {'pair': pair.upper()}
            
            # If no time range specified, default to last 30 days to prevent huge responses
            if not from_timestamp and not to_timestamp:
                import time
                to_timestamp = int(time.time())
                from_timestamp = to_timestamp - (30 * 24 * 60 * 60)  # 30 days ago
            
            if from_timestamp:
                params['from'] = from_timestamp
            if to_timestamp:
                params['to'] = to_timestamp
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'BorsaMCP/1.0'
            }
            
            # Direct Graph API call
            response = await self._http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Graph API returns array directly (no 'data' wrapper)
            # Limit to last 100 records to prevent MCP response size issues
            MAX_RECORDS = 100
            limited_data = data[-MAX_RECORDS:] if len(data) > MAX_RECORDS else data
            
            ohlc_data_list = []
            for ohlc in limited_data:
                timestamp = ohlc.get('time')
                ohlc_obj = KriptoOHLC(
                    pair=ohlc.get('pair') or pair.upper(),  # Fallback to requested pair
                    time=timestamp,
                    formatted_time=self._format_timestamp_output(timestamp) if timestamp else None,
                    open=float(ohlc.get('open', 0)),
                    high=float(ohlc.get('high', 0)),
                    low=float(ohlc.get('low', 0)),
                    close=float(ohlc.get('close', 0)),
                    volume=float(ohlc.get('volume', 0)),
                    total=float(ohlc.get('total', 0)),
                    average=float(ohlc.get('average', 0)),
                    daily_change_amount=float(ohlc.get('dailyChangeAmount', 0)),
                    daily_change_percentage=float(ohlc.get('dailyChangePercentage', 0))
                )
                ohlc_data_list.append(ohlc_obj)
            
            return KriptoOHLCSonucu(
                pair=pair.upper(),
                ohlc_data=ohlc_data_list,
                toplam_veri=len(ohlc_data_list),
                from_time=from_timestamp,
                to_time=to_timestamp
            )
            
        except Exception as e:
            logger.error(f"Error getting OHLC data for {pair}: {e}")
            return KriptoOHLCSonucu(
                pair=pair.upper(),
                ohlc_data=[],
                toplam_veri=0,
                from_time=from_time,
                to_time=to_time,
                error_message=str(e)
            )
    
    async def get_kline(self, symbol: str, resolution: str, from_time: Union[str, int, None] = None, to_time: Union[str, int, None] = None) -> KriptoKlineSonucu:
        """
        Get Kline (candlestick) data using dedicated Graph API.
        Only uses graph-api.btcturk.com for kline data.
        Supports human-readable datetime formats.
        """
        try:
            # Parse datetime inputs
            from_timestamp = self._parse_datetime_input(from_time)
            to_timestamp = self._parse_datetime_input(to_time)
            
            # If no time range specified, default to last 7 days
            if not from_timestamp and not to_timestamp:
                import time
                to_timestamp = int(time.time())
                from_timestamp = to_timestamp - (7 * 24 * 60 * 60)  # 7 days ago
            
            # Convert resolution to minutes for Graph API
            resolution_minutes = self._convert_resolution_to_minutes(resolution)
            
            # Build Graph API URL directly
            url = f"{self.GRAPH_API_URL}/v1/klines/history"
            params = {
                'symbol': symbol.upper(),
                'resolution': resolution_minutes,
                'from': from_timestamp,
                'to': to_timestamp
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'BorsaMCP/1.0'
            }
            
            # Direct Graph API call
            response = await self._http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Graph API returns TradingView format
            status = data.get('s', 'error')
            
            if status != 'ok':
                return KriptoKlineSonucu(
                    symbol=symbol.upper(),
                    resolution=resolution,
                    klines=[],
                    toplam_veri=0,
                    from_time=from_time,
                    to_time=to_time,
                    status=status
                )
            
            # Parse TradingView format arrays
            timestamps = data.get('t', [])
            opens = data.get('o', [])
            highs = data.get('h', [])
            lows = data.get('l', [])
            closes = data.get('c', [])
            volumes = data.get('v', [])
            
            # Create KriptoKline objects with formatted time
            klines = []
            for i in range(len(timestamps)):
                timestamp = timestamps[i] if i < len(timestamps) else 0
                kline = KriptoKline(
                    timestamp=timestamp,
                    formatted_time=self._format_timestamp_output(timestamp) if timestamp else None,
                    open=float(opens[i]) if i < len(opens) else 0.0,
                    high=float(highs[i]) if i < len(highs) else 0.0,
                    low=float(lows[i]) if i < len(lows) else 0.0,
                    close=float(closes[i]) if i < len(closes) else 0.0,
                    volume=float(volumes[i]) if i < len(volumes) else 0.0
                )
                klines.append(kline)
            
            return KriptoKlineSonucu(
                symbol=symbol.upper(),
                resolution=resolution,
                klines=klines,
                toplam_veri=len(klines),
                from_time=from_timestamp,
                to_time=to_timestamp,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error getting Kline data for {symbol}: {e}")
            return KriptoKlineSonucu(
                symbol=symbol.upper(),
                resolution=resolution,
                klines=[],
                toplam_veri=0,
                from_time=from_time,
                to_time=to_time,
                status='error',
                error_message=str(e)
            )
    
    async def get_kripto_teknik_analiz(self, symbol: str, resolution: str = "1D") -> KriptoTeknikAnalizSonucu:
        """
        Comprehensive technical analysis for cryptocurrency pairs using Kline data.
        
        Calculates RSI, MACD, Bollinger Bands, moving averages, and generates trading signals
        specifically optimized for the 24/7 crypto market.
        """
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            current_time = datetime.now().replace(microsecond=0)
            
            # Get 6 months of data for technical analysis (need 200 periods for SMA200)
            to_timestamp = int(time.time())
            from_timestamp = to_timestamp - (180 * 24 * 60 * 60)  # 6 months ago
            
            # Get kline data for analysis
            kline_result = await self.get_kline(symbol, resolution, from_timestamp, to_timestamp)
            
            if kline_result.error_message or not kline_result.klines:
                return KriptoTeknikAnalizSonucu(
                    symbol=symbol.upper(),
                    analiz_tarihi=current_time,
                    resolution=resolution,
                    error_message=f"Could not fetch kline data: {kline_result.error_message or 'No data available'}"
                )
            
            # Convert kline data to pandas DataFrame
            data = []
            for kline in kline_result.klines:
                data.append({
                    'timestamp': kline.timestamp,
                    'open': kline.open,
                    'high': kline.high,
                    'low': kline.low,
                    'close': kline.close,
                    'volume': kline.volume
                })
            
            if len(data) < 50:  # Need minimum data for analysis
                return KriptoTeknikAnalizSonucu(
                    symbol=symbol.upper(),
                    analiz_tarihi=current_time,
                    resolution=resolution,
                    error_message="Insufficient data for technical analysis (minimum 50 periods required)"
                )
            
            df = pd.DataFrame(data)
            df = df.sort_values('timestamp')  # Ensure chronological order
            
            # Initialize result structure
            result = KriptoTeknikAnalizSonucu(
                symbol=symbol.upper(),
                analiz_tarihi=current_time,
                resolution=resolution
            )
            
            # Determine market type based on symbol
            symbol_upper = symbol.upper()
            if 'TRY' in symbol_upper:
                result.piyasa_tipi = 'TRY'
            elif 'USDT' in symbol_upper:
                result.piyasa_tipi = 'USDT'
            elif 'BTC' in symbol_upper and symbol_upper != 'BTCTRY' and symbol_upper != 'BTCUSDT':
                result.piyasa_tipi = 'BTC'
            else:
                result.piyasa_tipi = 'OTHER'
            
            # Price Analysis
            current_price = df['close'].iloc[-1]
            previous_close = df['close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - previous_close
            price_change_pct = (price_change / previous_close * 100) if previous_close != 0 else 0
            
            period_high = df['high'].iloc[-1]
            period_low = df['low'].iloc[-1]
            high_200period = df['high'].rolling(window=min(200, len(df))).max().iloc[-1]
            low_200period = df['low'].rolling(window=min(200, len(df))).min().iloc[-1]
            
            result.fiyat_analizi = KriptoFiyatAnalizi(
                guncel_fiyat=float(current_price),
                onceki_kapanis=float(previous_close),
                degisim_miktari=float(price_change),
                degisim_yuzdesi=float(price_change_pct),
                period_yuksek=float(period_high),
                period_dusuk=float(period_low),
                yuksek_200period=float(high_200period),
                dusuk_200period=float(low_200period),
                yuksek_200period_uzaklik=float((current_price - high_200period) / high_200period * 100),
                dusuk_200period_uzaklik=float((current_price - low_200period) / low_200period * 100)
            )
            
            # Moving Averages
            sma_5 = df['close'].rolling(window=5).mean().iloc[-1] if len(df) >= 5 else None
            sma_10 = df['close'].rolling(window=10).mean().iloc[-1] if len(df) >= 10 else None
            sma_20 = df['close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
            sma_50 = df['close'].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else None
            sma_200 = df['close'].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else None
            
            # Exponential Moving Averages
            ema_12 = df['close'].ewm(span=12).mean().iloc[-1] if len(df) >= 12 else None
            ema_26 = df['close'].ewm(span=26).mean().iloc[-1] if len(df) >= 26 else None
            
            result.hareketli_ortalamalar = KriptoHareketliOrtalama(
                sma_5=float(sma_5) if sma_5 is not None and not pd.isna(sma_5) else None,
                sma_10=float(sma_10) if sma_10 is not None and not pd.isna(sma_10) else None,
                sma_20=float(sma_20) if sma_20 is not None and not pd.isna(sma_20) else None,
                sma_50=float(sma_50) if sma_50 is not None and not pd.isna(sma_50) else None,
                sma_200=float(sma_200) if sma_200 is not None and not pd.isna(sma_200) else None,
                ema_12=float(ema_12) if ema_12 is not None and not pd.isna(ema_12) else None,
                ema_26=float(ema_26) if ema_26 is not None and not pd.isna(ema_26) else None
            )
            
            # Technical Indicators
            
            # RSI calculation
            rsi_14 = None
            if len(df) >= 14:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_14 = rsi.iloc[-1]
            
            # MACD calculation
            macd = None
            macd_signal = None
            macd_histogram = None
            if ema_12 is not None and ema_26 is not None:
                macd = ema_12 - ema_26
                # Calculate MACD signal line (9-period EMA of MACD)
                macd_series = df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()
                macd_signal_series = macd_series.ewm(span=9).mean()
                macd_signal = macd_signal_series.iloc[-1] if not pd.isna(macd_signal_series.iloc[-1]) else None
                macd_histogram = float(macd - macd_signal) if macd_signal is not None else None
                macd = float(macd)
                macd_signal = float(macd_signal) if macd_signal is not None else None
            
            # Bollinger Bands
            bollinger_upper = None
            bollinger_middle = None
            bollinger_lower = None
            if sma_20 is not None and len(df) >= 20:
                std_20 = df['close'].rolling(window=20).std().iloc[-1]
                bollinger_middle = sma_20
                bollinger_upper = sma_20 + (2 * std_20)
                bollinger_lower = sma_20 - (2 * std_20)
            
            # Stochastic Oscillator
            stochastic_k = None
            stochastic_d = None
            if len(df) >= 14:
                low_14 = df['low'].rolling(window=14).min()
                high_14 = df['high'].rolling(window=14).max()
                k_percent = 100 * ((df['close'] - low_14) / (high_14 - low_14))
                stochastic_k = k_percent.iloc[-1] if not pd.isna(k_percent.iloc[-1]) else None
                stochastic_d = k_percent.rolling(window=3).mean().iloc[-1] if len(k_percent) >= 3 else None
            
            result.teknik_indiktorler = KriptoTeknikIndiktorler(
                rsi_14=float(rsi_14) if rsi_14 is not None and not pd.isna(rsi_14) else None,
                macd=macd,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
                bollinger_upper=float(bollinger_upper) if bollinger_upper is not None and not pd.isna(bollinger_upper) else None,
                bollinger_middle=float(bollinger_middle) if bollinger_middle is not None and not pd.isna(bollinger_middle) else None,
                bollinger_lower=float(bollinger_lower) if bollinger_lower is not None and not pd.isna(bollinger_lower) else None,
                stochastic_k=float(stochastic_k) if stochastic_k is not None and not pd.isna(stochastic_k) else None,
                stochastic_d=float(stochastic_d) if stochastic_d is not None and not pd.isna(stochastic_d) else None
            )
            
            # Volume Analysis
            current_volume = float(df['volume'].iloc[-1])
            avg_volume_10 = float(df['volume'].rolling(window=10).mean().iloc[-1]) if len(df) >= 10 else None
            avg_volume_30 = float(df['volume'].rolling(window=30).mean().iloc[-1]) if len(df) >= 30 else None
            volume_ratio = current_volume / avg_volume_10 if avg_volume_10 and avg_volume_10 > 0 else None
            
            volume_trend = "normal"
            if volume_ratio is not None:
                if volume_ratio > 2.0:  # Higher threshold for crypto volatility
                    volume_trend = "yuksek"
                elif volume_ratio < 0.3:  # Lower threshold for crypto
                    volume_trend = "dusuk"
            
            result.hacim_analizi = KriptoHacimAnalizi(
                guncel_hacim=current_volume,
                ortalama_hacim_10period=avg_volume_10,
                ortalama_hacim_30period=avg_volume_30,
                hacim_orani=float(volume_ratio) if volume_ratio is not None else None,
                hacim_trendi=volume_trend
            )
            
            # Trend Analysis
            short_trend = "yatay"  # 5 vs 10 period SMA
            medium_trend = "yatay"  # 20 vs 50 period SMA
            long_trend = "yatay"  # 50 vs 200 period SMA
            
            if sma_5 is not None and sma_10 is not None:
                if sma_5 > sma_10 * 1.001:  # 0.1% threshold
                    short_trend = "yukselis"
                elif sma_5 < sma_10 * 0.999:
                    short_trend = "dusulis"
            
            if sma_20 is not None and sma_50 is not None:
                if sma_20 > sma_50 * 1.002:  # 0.2% threshold
                    medium_trend = "yukselis"
                elif sma_20 < sma_50 * 0.998:
                    medium_trend = "dusulis"
            
            if sma_50 is not None and sma_200 is not None:
                if sma_50 > sma_200 * 1.005:  # 0.5% threshold
                    long_trend = "yukselis"
                elif sma_50 < sma_200 * 0.995:
                    long_trend = "dusulis"
            
            sma50_position = None
            sma200_position = None
            golden_cross = None
            death_cross = None
            
            if sma_50 is not None:
                sma50_position = "ustunde" if current_price > sma_50 else "altinda"
            
            if sma_200 is not None:
                sma200_position = "ustunde" if current_price > sma_200 else "altinda"
            
            if sma_50 is not None and sma_200 is not None:
                golden_cross = sma_50 > sma_200
                death_cross = sma_50 < sma_200
            
            result.trend_analizi = KriptoTrendAnalizi(
                kisa_vadeli_trend=short_trend,
                orta_vadeli_trend=medium_trend,
                uzun_vadeli_trend=long_trend,
                sma50_durumu=sma50_position,
                sma200_durumu=sma200_position,
                golden_cross=golden_cross,
                death_cross=death_cross
            )
            
            # Volatility Analysis
            daily_returns = df['close'].pct_change().dropna()
            if len(daily_returns) > 1:
                volatility = daily_returns.std() * 100  # Convert to percentage
                
                # Crypto-specific volatility thresholds
                if volatility > 8:
                    result.volatilite_seviyesi = "cok_yuksek"
                elif volatility > 5:
                    result.volatilite_seviyesi = "yuksek"
                elif volatility > 2:
                    result.volatilite_seviyesi = "orta"
                else:
                    result.volatilite_seviyesi = "dusuk"
            
            # Overall Signal Generation (crypto-optimized)
            signal_score = 0
            signal_count = 0
            
            # RSI signal (crypto thresholds)
            if rsi_14 is not None:
                if rsi_14 < 25:  # Lower oversold threshold for crypto
                    signal_score += 2
                elif rsi_14 < 45:
                    signal_score += 1
                elif rsi_14 > 75:  # Higher overbought threshold for crypto
                    signal_score -= 2
                elif rsi_14 > 55:
                    signal_score -= 1
                signal_count += 1
            
            # MACD signal
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    signal_score += 1
                else:
                    signal_score -= 1
                signal_count += 1
            
            # Moving average trends
            if short_trend == "yukselis":
                signal_score += 1
            elif short_trend == "dusulis":
                signal_score -= 1
            signal_count += 1
            
            if medium_trend == "yukselis":
                signal_score += 1
            elif medium_trend == "dusulis":
                signal_score -= 1
            signal_count += 1
            
            # Golden/Death cross (stronger weight for crypto)
            if golden_cross is True:
                signal_score += 2
                signal_count += 1
            elif death_cross is True:
                signal_score -= 2
                signal_count += 1
            
            # Volume confirmation
            if volume_trend == "yuksek" and short_trend == "yukselis":
                signal_score += 1
                signal_count += 1
            elif volume_trend == "yuksek" and short_trend == "dusulis":
                signal_score -= 1
                signal_count += 1
            
            # Calculate final signal
            overall_signal = "notr"
            signal_explanation = "Yeterli veri yok"
            
            if signal_count > 0:
                avg_signal = signal_score / signal_count
                
                if avg_signal >= 1.5:
                    overall_signal = "guclu_al"
                    signal_explanation = "Güçlü al sinyali - çoklu kripto indikatör pozitif"
                elif avg_signal >= 0.5:
                    overall_signal = "al"
                    signal_explanation = "Al sinyali - kripto indikatörleri pozitif"
                elif avg_signal <= -1.5:
                    overall_signal = "guclu_sat"
                    signal_explanation = "Güçlü sat sinyali - çoklu kripto indikatör negatif"
                elif avg_signal <= -0.5:
                    overall_signal = "sat"
                    signal_explanation = "Sat sinyali - kripto indikatörleri negatif"
                else:
                    overall_signal = "notr"
                    signal_explanation = "Nötr - karışık kripto sinyaller"
            
            result.al_sat_sinyali = overall_signal
            result.sinyal_aciklamasi = signal_explanation
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in crypto technical analysis for {symbol}")
            return KriptoTeknikAnalizSonucu(
                symbol=symbol.upper(),
                analiz_tarihi=datetime.now().replace(microsecond=0),
                resolution=resolution,
                error_message=str(e)
            )