"""
BtcTurk Provider
This module is responsible for all interactions with the
BtcTurk Kripto API, including fetching cryptocurrency market data.
"""
import httpx
import logging
import time
from typing import List, Optional, Dict, Any
from borsa_models import (
    KriptoExchangeInfoSonucu, KriptoTickerSonucu, KriptoOrderbookSonucu,
    KriptoTradesSonucu, KriptoOHLCSonucu, KriptoKlineSonucu,
    TradingPair, Currency, CurrencyOperationBlock, KriptoTicker,
    KriptoOrderbook, KriptoTrade, KriptoOHLC, KriptoKline
)

logger = logging.getLogger(__name__)

class BtcTurkProvider:
    BASE_URL = "https://api.btcturk.com/api/v2"
    CACHE_DURATION = 60  # 1 minute cache for exchange info
    
    def __init__(self, client: httpx.AsyncClient):
        self._http_client = client
        self._exchange_info_cache: Optional[Dict] = None
        self._last_exchange_info_fetch: float = 0
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to BtcTurk API with error handling."""
        try:
            url = f"{self.BASE_URL}{endpoint}"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'BorsaMCP/1.0'
            }
            
            response = await self._http_client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            
            data = response.json()
            if not data.get('success', True):
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
    
    async def get_ohlc(self, pair: str, from_time: Optional[int] = None, to_time: Optional[int] = None) -> KriptoOHLCSonucu:
        """
        Get OHLC data for a specific trading pair.
        """
        try:
            params = {'pair': pair.upper()}
            
            if from_time:
                params['from'] = from_time
            if to_time:
                params['to'] = to_time
            
            data = await self._make_request("/ohlc", params)
            
            # Parse OHLC data
            ohlc_data_list = []
            ohlc_data = data.get('data', [])
            
            for ohlc in ohlc_data:
                ohlc_obj = KriptoOHLC(
                    pair=ohlc.get('pair'),
                    time=ohlc.get('time'),
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
                from_time=from_time,
                to_time=to_time
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
    
    async def get_kline(self, symbol: str, resolution: str, from_time: int, to_time: int) -> KriptoKlineSonucu:
        """
        Get Kline (candlestick) data for a specific symbol.
        """
        try:
            params = {
                'symbol': symbol.upper(),
                'resolution': resolution,
                'from': from_time,
                'to': to_time
            }
            
            data = await self._make_request("/kline", params)
            
            kline_data = data.get('data', {})
            status = kline_data.get('s', 'error')
            
            if status != 'ok':
                raise Exception(f"Kline data error: {status}")
            
            # Parse arrays
            timestamps = kline_data.get('t', [])
            highs = kline_data.get('h', [])
            opens = kline_data.get('o', [])
            lows = kline_data.get('l', [])
            closes = kline_data.get('c', [])
            volumes = kline_data.get('v', [])
            
            # Create KriptoKline objects
            klines = []
            for i in range(len(timestamps)):
                kline = KriptoKline(
                    timestamp=timestamps[i],
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
                from_time=from_time,
                to_time=to_time,
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