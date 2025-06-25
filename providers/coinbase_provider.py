"""
Coinbase Provider
This module is responsible for all interactions with the
Coinbase API, including fetching global cryptocurrency market data.
"""
import httpx
import logging
import time
from typing import List, Optional, Dict, Any
from borsa_models import (
    CoinbaseExchangeInfoSonucu, CoinbaseTickerSonucu, CoinbaseOrderbookSonucu,
    CoinbaseTradesSonucu, CoinbaseOHLCSonucu, CoinbaseServerTimeSonucu,
    CoinbaseProduct, CoinbaseCurrency, CoinbaseTicker,
    CoinbaseOrderbook, CoinbaseTrade, CoinbaseCandle
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