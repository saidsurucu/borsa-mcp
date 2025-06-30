"""
Coinbase Provider
This module is responsible for all interactions with the
Coinbase API, including fetching global cryptocurrency market data.
"""
import httpx
import logging
import time
from typing import List, Optional, Dict, Any
from models import (
    CoinbaseExchangeInfoSonucu, CoinbaseTickerSonucu, CoinbaseOrderbookSonucu,
    CoinbaseTradesSonucu, CoinbaseOHLCSonucu, CoinbaseServerTimeSonucu, CoinbaseTeknikAnalizSonucu,
    CoinbaseProduct, CoinbaseCurrency, CoinbaseTicker,
    CoinbaseOrderbook, CoinbaseTrade, CoinbaseCandle,
    CoinbaseHareketliOrtalama, CoinbaseTeknikIndiktorler, CoinbaseHacimAnalizi,
    CoinbaseFiyatAnalizi, CoinbaseTrendAnalizi
)

logger = logging.getLogger(__name__)

class CoinbaseProvider:
    ADVANCED_TRADE_BASE_URL = "https://api.coinbase.com/api/v3/brokerage"
    APP_BASE_URL = "https://api.coinbase.com/v2"
    CACHE_DURATION = 300  # 5 minutes cache for exchange info
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._exchange_info_cache: Optional[Dict] = None
        self._last_exchange_info_fetch: float = 0
    
    async def _make_request(self, base_url: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to Coinbase API with error handling."""
        try:
            url = f"{base_url}{endpoint}"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'BorsaMCP/1.0'
            }
            
            response = await self._http_client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors in response
            if 'error' in data:
                raise Exception(f"API Error: {data['error']}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {endpoint}: {e}")
            raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Error making request to {endpoint}: {e}")
            raise
    
    async def get_exchange_info(self) -> CoinbaseExchangeInfoSonucu:
        """
        Get detailed information about all trading pairs and currencies on Coinbase.
        """
        try:
            # Check cache
            current_time = time.time()
            if (self._exchange_info_cache and 
                (current_time - self._last_exchange_info_fetch) < self.CACHE_DURATION):
                products_data = self._exchange_info_cache.get('products', [])
                currencies_data = self._exchange_info_cache.get('currencies', [])
            else:
                # Fetch products (trading pairs)
                products_response = await self._make_request(
                    self.ADVANCED_TRADE_BASE_URL, "/market/products"
                )
                products_data = products_response.get('products', [])
                
                # Fetch currencies
                currencies_response = await self._make_request(
                    self.APP_BASE_URL, "/currencies"
                )
                currencies_data = currencies_response.get('data', [])
                
                # Cache the data
                self._exchange_info_cache = {
                    'products': products_data,
                    'currencies': currencies_data
                }
                self._last_exchange_info_fetch = current_time
            
            # Parse trading pairs
            trading_pairs = []
            for product in products_data:
                # Helper function to safely convert to float
                def safe_float(value, default=0.0):
                    if value is None or value == '' or value == 'null':
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                trading_pair = CoinbaseProduct(
                    product_id=product.get('product_id'),
                    price=safe_float(product.get('price')),
                    price_percentage_change_24h=safe_float(product.get('price_percentage_change_24h')),
                    volume_24h=safe_float(product.get('volume_24h')),
                    volume_percentage_change_24h=safe_float(product.get('volume_percentage_change_24h')),
                    base_currency_id=product.get('base_currency_id'),
                    quote_currency_id=product.get('quote_currency_id'),
                    base_display_symbol=product.get('base_display_symbol'),
                    quote_display_symbol=product.get('quote_display_symbol'),
                    base_name=product.get('base_name'),
                    quote_name=product.get('quote_name'),
                    min_market_funds=safe_float(product.get('min_market_funds')),
                    is_disabled=product.get('is_disabled', False),
                    new_listing=product.get('new_listing', False),
                    status=product.get('status'),
                    cancel_only=product.get('cancel_only', False),
                    limit_only=product.get('limit_only', False),
                    post_only=product.get('post_only', False),
                    trading_disabled=product.get('trading_disabled', False),
                    auction_mode=product.get('auction_mode', False),
                    product_type=product.get('product_type'),
                    quote_currency_type=product.get('quote_currency_type'),
                    base_currency_type=product.get('base_currency_type')
                )
                trading_pairs.append(trading_pair)
            
            # Parse currencies
            currencies = []
            for currency in currencies_data:
                currency_obj = CoinbaseCurrency(
                    id=currency.get('id'),
                    name=currency.get('name'),
                    min_size=currency.get('min_size'),
                    status=currency.get('status'),
                    message=currency.get('message'),
                    max_precision=currency.get('max_precision'),
                    convertible_to=currency.get('convertible_to', []),
                    details=currency.get('details', {})
                )
                currencies.append(currency_obj)
            
            return CoinbaseExchangeInfoSonucu(
                trading_pairs=trading_pairs,
                currencies=currencies,
                toplam_cift=len(trading_pairs),
                toplam_para_birimi=len(currencies)
            )
            
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return CoinbaseExchangeInfoSonucu(
                trading_pairs=[],
                currencies=[],
                toplam_cift=0,
                toplam_para_birimi=0,
                error_message=str(e)
            )
    
    async def get_ticker(self, product_id: Optional[str] = None, quote_currency: Optional[str] = None) -> CoinbaseTickerSonucu:
        """
        Get ticker data for specific trading pair(s) or all pairs.
        """
        try:
            tickers = []
            
            if product_id:
                # Get specific product ticker
                endpoint = f"/market/products/{product_id.upper()}/ticker"
                data = await self._make_request(self.ADVANCED_TRADE_BASE_URL, endpoint)
                
                ticker_data = data.get('trades', [])
                if ticker_data:
                    latest_trade = ticker_data[0]  # Most recent trade
                    ticker = CoinbaseTicker(
                        product_id=product_id.upper(),
                        price=float(latest_trade.get('price', 0)),
                        size=float(latest_trade.get('size', 0)),
                        time=latest_trade.get('time'),
                        side=latest_trade.get('side'),
                        bid=0.0,  # Not available in this endpoint
                        ask=0.0,  # Not available in this endpoint
                        volume=0.0  # Not available in this endpoint
                    )
                    tickers.append(ticker)
            else:
                # Get all products and their basic info
                products_response = await self._make_request(
                    self.ADVANCED_TRADE_BASE_URL, "/market/products"
                )
                products_data = products_response.get('products', [])
                
                for product in products_data:
                    # Filter by quote currency if specified
                    if quote_currency and product.get('quote_currency_id', '').upper() != quote_currency.upper():
                        continue
                    
                    ticker = CoinbaseTicker(
                        product_id=product.get('product_id'),
                        price=float(product.get('price', 0)),
                        size=0.0,  # Not available in products endpoint
                        time=None,  # Not available in products endpoint
                        side=None,  # Not available in products endpoint
                        bid=0.0,  # Not available in products endpoint
                        ask=0.0,  # Not available in products endpoint
                        volume=float(product.get('volume_24h', 0))
                    )
                    tickers.append(ticker)
            
            return CoinbaseTickerSonucu(
                tickers=tickers,
                toplam_cift=len(tickers),
                product_id=product_id,
                quote_currency=quote_currency
            )
            
        except Exception as e:
            logger.error(f"Error getting ticker data: {e}")
            return CoinbaseTickerSonucu(
                tickers=[],
                toplam_cift=0,
                product_id=product_id,
                quote_currency=quote_currency,
                error_message=str(e)
            )
    
    async def get_orderbook(self, product_id: str, limit: int = 100) -> CoinbaseOrderbookSonucu:
        """
        Get order book data for a specific trading pair.
        """
        try:
            params = {
                'product_id': product_id.upper(),
                'limit': min(limit, 100)
            }
            
            data = await self._make_request(self.ADVANCED_TRADE_BASE_URL, "/market/product_book", params)
            
            pricebook = data.get('pricebook', {})
            bids_data = pricebook.get('bids', [])
            asks_data = pricebook.get('asks', [])
            time = pricebook.get('time')
            
            # Convert bids and asks to proper format
            bid_orders = [(float(bid.get('price', 0)), float(bid.get('size', 0))) for bid in bids_data]
            ask_orders = [(float(ask.get('price', 0)), float(ask.get('size', 0))) for ask in asks_data]
            
            orderbook = CoinbaseOrderbook(
                time=time,
                bids=bid_orders,
                asks=ask_orders,
                bid_count=len(bid_orders),
                ask_count=len(ask_orders)
            )
            
            return CoinbaseOrderbookSonucu(
                product_id=product_id.upper(),
                orderbook=orderbook
            )
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {product_id}: {e}")
            return CoinbaseOrderbookSonucu(
                product_id=product_id.upper(),
                orderbook=None,
                error_message=str(e)
            )
    
    async def get_trades(self, product_id: str, limit: int = 100) -> CoinbaseTradesSonucu:
        """
        Get recent trades for a specific trading pair.
        """
        try:
            params = {
                'limit': min(limit, 100)
            }
            
            endpoint = f"/market/products/{product_id.upper()}/ticker"
            data = await self._make_request(self.ADVANCED_TRADE_BASE_URL, endpoint, params)
            
            # Parse trades data
            trades = []
            trades_data = data.get('trades', [])
            
            for trade in trades_data:
                trade_obj = CoinbaseTrade(
                    trade_id=trade.get('trade_id'),
                    product_id=product_id.upper(),
                    price=float(trade.get('price', 0)),
                    size=float(trade.get('size', 0)),
                    time=trade.get('time'),
                    side=trade.get('side')
                )
                trades.append(trade_obj)
            
            return CoinbaseTradesSonucu(
                product_id=product_id.upper(),
                trades=trades,
                toplam_islem=len(trades)
            )
            
        except Exception as e:
            logger.error(f"Error getting trades for {product_id}: {e}")
            return CoinbaseTradesSonucu(
                product_id=product_id.upper(),
                trades=[],
                toplam_islem=0,
                error_message=str(e)
            )
    
    async def get_ohlc(self, product_id: str, start: Optional[str] = None, end: Optional[str] = None, granularity: str = "ONE_HOUR") -> CoinbaseOHLCSonucu:
        """
        Get OHLC (candlestick) data for a specific trading pair.
        """
        try:
            params = {
                'granularity': granularity
            }
            
            if start:
                params['start'] = start
            if end:
                params['end'] = end
            
            endpoint = f"/market/products/{product_id.upper()}/candles"
            data = await self._make_request(self.ADVANCED_TRADE_BASE_URL, endpoint, params)
            
            # Parse OHLC data
            ohlc_data_list = []
            candles_data = data.get('candles', [])
            
            for candle in candles_data:
                ohlc_obj = CoinbaseCandle(
                    start=candle.get('start'),
                    low=float(candle.get('low', 0)),
                    high=float(candle.get('high', 0)),
                    open=float(candle.get('open', 0)),
                    close=float(candle.get('close', 0)),
                    volume=float(candle.get('volume', 0))
                )
                ohlc_data_list.append(ohlc_obj)
            
            return CoinbaseOHLCSonucu(
                product_id=product_id.upper(),
                candles=ohlc_data_list,
                toplam_veri=len(ohlc_data_list),
                start=start,
                end=end,
                granularity=granularity
            )
            
        except Exception as e:
            logger.error(f"Error getting OHLC data for {product_id}: {e}")
            return CoinbaseOHLCSonucu(
                product_id=product_id.upper(),
                candles=[],
                toplam_veri=0,
                start=start,
                end=end,
                granularity=granularity,
                error_message=str(e)
            )
    
    async def get_server_time(self) -> CoinbaseServerTimeSonucu:
        """
        Get Coinbase server time and status.
        """
        try:
            data = await self._make_request(self.APP_BASE_URL, "/time")
            
            time_data = data.get('data', {})
            
            return CoinbaseServerTimeSonucu(
                iso=time_data.get('iso'),
                epoch=time_data.get('epoch')
            )
            
        except Exception as e:
            logger.error(f"Error getting server time: {e}")
            return CoinbaseServerTimeSonucu(
                iso=None,
                epoch=None,
                error_message=str(e)
            )
    
    async def get_coinbase_teknik_analiz(self, product_id: str, granularity: str = "ONE_DAY") -> CoinbaseTeknikAnalizSonucu:
        """
        Perform comprehensive technical analysis on Coinbase crypto data.
        
        Implements RSI, MACD, Bollinger Bands, moving averages and generates trading signals
        optimized for global cryptocurrency markets (24/7 trading).
        """
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            # Map user-friendly resolution to Coinbase granularity
            granularity_map = {
                "1M": "ONE_MINUTE",
                "5M": "FIVE_MINUTE", 
                "15M": "FIFTEEN_MINUTE",
                "30M": "THIRTY_MINUTE",
                "1H": "ONE_HOUR",
                "4H": "FOUR_HOUR",
                "6H": "SIX_HOUR",
                "1D": "ONE_DAY"
                # Note: ONE_WEEK is not supported by Coinbase API
            }
            
            coinbase_granularity = granularity_map.get(granularity, granularity)
            
            # Handle unsupported granularity
            if granularity == "1W":
                return CoinbaseTeknikAnalizSonucu(
                    product_id=product_id,
                    analiz_tarihi=datetime.utcnow(),
                    granularity=granularity,
                    error_message="Weekly (1W) granularity is not supported by Coinbase API. Use 1D instead."
                )
            
            # Fetch 6 months of data for technical analysis (need enough for 200-SMA)
            end_time = datetime.utcnow()
            
            # Adjust start time based on granularity (Coinbase has 350 candles limit)
            if granularity in ["1M", "5M"]:
                start_time = end_time - timedelta(days=7)  # 1 week for 1M/5M (max ~2016 candles for 1M)
            elif granularity in ["15M", "30M"]:
                start_time = end_time - timedelta(days=14)  # 2 weeks for 15M/30M 
            elif granularity in ["1H"]:
                start_time = end_time - timedelta(days=14)  # 2 weeks for 1H (~336 candles)
            elif granularity in ["4H", "6H"]:
                start_time = end_time - timedelta(days=60)  # 2 months for 4H/6H (~360 candles for 4H)
            else:
                start_time = end_time - timedelta(days=300)  # ~10 months for daily (~300 candles)
            
            # Convert to Unix timestamps (seconds since epoch) - Coinbase requirement
            start_timestamp = str(int(start_time.timestamp()))
            end_timestamp = str(int(end_time.timestamp()))
            
            # Fetch OHLC data
            ohlc_result = await self.get_ohlc(
                product_id=product_id,
                start=start_timestamp,
                end=end_timestamp,
                granularity=coinbase_granularity
            )
            
            if ohlc_result.error_message or not ohlc_result.candles:
                return CoinbaseTeknikAnalizSonucu(
                    product_id=product_id,
                    analiz_tarihi=datetime.utcnow(),
                    granularity=granularity,
                    error_message=f"Could not fetch OHLC data: {ohlc_result.error_message or 'No data available'}"
                )
            
            # Convert to pandas DataFrame
            data = []
            for candle in ohlc_result.candles:
                data.append({
                    'timestamp': pd.to_datetime(int(candle.start), unit='s', utc=True),
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                })
            
            df = pd.DataFrame(data)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            if len(df) < 50:
                return CoinbaseTeknikAnalizSonucu(
                    product_id=product_id,
                    analiz_tarihi=datetime.utcnow(),
                    granularity=granularity,
                    error_message=f"Insufficient data for analysis: {len(df)} periods (minimum 50 required)"
                )
            
            # === TECHNICAL INDICATOR CALCULATIONS ===
            
            # Moving Averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_100'] = df['close'].rolling(window=100).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # RSI (14-period)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # Get latest values
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else latest
            
            # === ANALYSIS COMPONENTS ===
            
            # Moving Averages Analysis
            hareketli_ortalamalar = CoinbaseHareketliOrtalama(
                sma_20=float(latest['sma_20']) if pd.notna(latest['sma_20']) else None,
                sma_50=float(latest['sma_50']) if pd.notna(latest['sma_50']) else None,
                sma_100=float(latest['sma_100']) if pd.notna(latest['sma_100']) else None,
                sma_200=float(latest['sma_200']) if pd.notna(latest['sma_200']) else None,
                ema_12=float(latest['ema_12']) if pd.notna(latest['ema_12']) else None,
                ema_26=float(latest['ema_26']) if pd.notna(latest['ema_26']) else None
            )
            
            # Technical Indicators
            teknik_indiktorler = CoinbaseTeknikIndiktorler(
                rsi_14=float(latest['rsi']) if pd.notna(latest['rsi']) else None,
                macd=float(latest['macd']) if pd.notna(latest['macd']) else None,
                macd_signal=float(latest['macd_signal']) if pd.notna(latest['macd_signal']) else None,
                macd_histogram=float(latest['macd_histogram']) if pd.notna(latest['macd_histogram']) else None,
                bollinger_ust=float(latest['bb_upper']) if pd.notna(latest['bb_upper']) else None,
                bollinger_orta=float(latest['bb_middle']) if pd.notna(latest['bb_middle']) else None,
                bollinger_alt=float(latest['bb_lower']) if pd.notna(latest['bb_lower']) else None
            )
            
            # Volume Analysis
            volume_ma = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = latest['volume']
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1.0
            
            hacim_analizi = CoinbaseHacimAnalizi(
                guncel_hacim=float(current_volume),
                ortalama_hacim=float(volume_ma) if pd.notna(volume_ma) else None,
                hacim_orani=float(volume_ratio),
                hacim_trendi="yuksek" if volume_ratio > 2.0 else "normal" if volume_ratio > 0.3 else "dusuk"
            )
            
            # Price Analysis
            price_change = ((latest['close'] - previous['close']) / previous['close']) * 100
            high_24h = df['high'].tail(24).max() if len(df) >= 24 else latest['high']
            low_24h = df['low'].tail(24).min() if len(df) >= 24 else latest['low']
            
            fiyat_analizi = CoinbaseFiyatAnalizi(
                guncel_fiyat=float(latest['close']),
                yuksek_24h=float(high_24h),
                dusuk_24h=float(low_24h),
                degisim_yuzdesi=float(price_change),
                destek_seviyesi=float(latest['bb_lower']) if pd.notna(latest['bb_lower']) else None,
                direnc_seviyesi=float(latest['bb_upper']) if pd.notna(latest['bb_upper']) else None
            )
            
            # Trend Analysis
            price_vs_sma20 = "yukari" if pd.notna(latest['sma_20']) and latest['close'] > latest['sma_20'] else "asagi" if pd.notna(latest['sma_20']) else "bilinmiyor"
            price_vs_sma50 = "yukari" if pd.notna(latest['sma_50']) and latest['close'] > latest['sma_50'] else "asagi" if pd.notna(latest['sma_50']) else "bilinmiyor"
            sma20_vs_sma50 = "yukari" if pd.notna(latest['sma_20']) and pd.notna(latest['sma_50']) and latest['sma_20'] > latest['sma_50'] else "asagi" if pd.notna(latest['sma_20']) and pd.notna(latest['sma_50']) else "bilinmiyor"
            
            # Determine overall trends
            if pd.notna(latest['rsi']) and pd.notna(latest['sma_20']):
                kisa_vadeli = "yukselis" if price_vs_sma20 == "yukari" and latest['rsi'] < 80 else "dususlus" if price_vs_sma20 == "asagi" and latest['rsi'] > 20 else "yana"
            else:
                kisa_vadeli = "bilinmiyor"
                
            if pd.notna(latest['sma_20']) and pd.notna(latest['sma_50']):
                uzun_vadeli = "yukselis" if sma20_vs_sma50 == "yukari" and price_vs_sma50 == "yukari" else "dususlus" if sma20_vs_sma50 == "asagi" and price_vs_sma50 == "asagi" else "yana"
            else:
                uzun_vadeli = "bilinmiyor"
            
            trend_analizi = CoinbaseTrendAnalizi(
                kisa_vadeli_trend=kisa_vadeli,
                uzun_vadeli_trend=uzun_vadeli,
                ma_20_50_durumu=sma20_vs_sma50,
                fiyat_ma_durumu=price_vs_sma20
            )
            
            # === SIGNAL GENERATION ===
            
            signals = []
            
            # RSI signals (crypto-optimized thresholds: 25/75 vs stock 30/70)
            if pd.notna(latest['rsi']):
                if latest['rsi'] <= 25:
                    signals.append(("RSI Oversold", 2))  # Strong buy
                elif latest['rsi'] <= 35:
                    signals.append(("RSI Low", 1))  # Buy
                elif latest['rsi'] >= 75:
                    signals.append(("RSI Overbought", -2))  # Strong sell
                elif latest['rsi'] >= 65:
                    signals.append(("RSI High", -1))  # Sell
            
            # MACD signals
            if (pd.notna(latest['macd']) and pd.notna(latest['macd_signal']) and 
                pd.notna(previous['macd']) and pd.notna(previous['macd_signal'])):
                if latest['macd'] > latest['macd_signal'] and previous['macd'] <= previous['macd_signal']:
                    signals.append(("MACD Bullish Cross", 1))
                elif latest['macd'] < latest['macd_signal'] and previous['macd'] >= previous['macd_signal']:
                    signals.append(("MACD Bearish Cross", -1))
            
            # Moving average signals
            if (pd.notna(latest['sma_20']) and pd.notna(latest['sma_50'])):
                if latest['close'] > latest['sma_20'] and latest['sma_20'] > latest['sma_50']:
                    signals.append(("MA Alignment Bullish", 1))
                elif latest['close'] < latest['sma_20'] and latest['sma_20'] < latest['sma_50']:
                    signals.append(("MA Alignment Bearish", -1))
            
            # Bollinger Band signals
            if pd.notna(latest['bb_lower']) and pd.notna(latest['bb_upper']):
                if latest['close'] <= latest['bb_lower']:
                    signals.append(("BB Oversold", 1))
                elif latest['close'] >= latest['bb_upper']:
                    signals.append(("BB Overbought", -1))
            
            # Volume confirmation
            if volume_ratio > 2.0:  # Higher threshold for crypto
                if any(score > 0 for _, score in signals):
                    signals.append(("Volume Confirmation", 1))
                elif any(score < 0 for _, score in signals):
                    signals.append(("Volume Confirmation", -1))
            
            # Calculate total signal score
            total_score = sum(score for _, score in signals)
            signal_strength = len([s for s in signals if s[1] != 0])
            
            # Generate final signal
            if total_score >= 3:
                al_sat_sinyali = "guclu_al"
            elif total_score >= 1:
                al_sat_sinyali = "al"
            elif total_score <= -3:
                al_sat_sinyali = "guclu_sat"
            elif total_score <= -1:
                al_sat_sinyali = "sat"
            else:
                al_sat_sinyali = "notr"
            
            # Create signal explanation
            signal_reasons = [reason for reason, score in signals if score != 0]
            sinyal_aciklamasi = f"Skor: {total_score}, Faktörler: {', '.join(signal_reasons[:3])}" if signal_reasons else "Nötr piyasa koşulları"
            
            # Determine market type based on quote currency
            quote_currency = product_id.split('-')[-1] if '-' in product_id else 'OTHER'
            piyasa_tipi = quote_currency if quote_currency in ['USD', 'EUR', 'GBP', 'BTC', 'ETH'] else 'OTHER'
            
            # Volatility analysis (crypto-specific thresholds)
            if abs(price_change) >= 10:
                volatilite_seviyesi = "cok_yuksek"
            elif abs(price_change) >= 5:
                volatilite_seviyesi = "yuksek"
            elif abs(price_change) >= 2:
                volatilite_seviyesi = "orta"
            else:
                volatilite_seviyesi = "dusuk"
            
            return CoinbaseTeknikAnalizSonucu(
                product_id=product_id,
                analiz_tarihi=datetime.utcnow(),
                granularity=granularity,
                hareketli_ortalamalar=hareketli_ortalamalar,
                teknik_indiktorler=teknik_indiktorler,
                hacim_analizi=hacim_analizi,
                fiyat_analizi=fiyat_analizi,
                trend_analizi=trend_analizi,
                al_sat_sinyali=al_sat_sinyali,
                sinyal_aciklamasi=sinyal_aciklamasi,
                sinyal_gucu=signal_strength,
                piyasa_tipi=piyasa_tipi,
                volatilite_seviyesi=volatilite_seviyesi,
                veri_sayisi=len(df)
            )
            
        except Exception as e:
            logger.error(f"Error in Coinbase technical analysis for {product_id}: {e}")
            return CoinbaseTeknikAnalizSonucu(
                product_id=product_id,
                analiz_tarihi=datetime.utcnow(),
                granularity=granularity,
                error_message=str(e)
            )