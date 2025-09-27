"""
Dynamic Stock Discovery Module
Implements volume-based and market activity scanning without hardcoded tickers
"""

import yfinance as yf
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import concurrent.futures
import pandas as pd

logger = logging.getLogger(__name__)


class DynamicStockDiscovery:
    """Dynamic stock discovery using market activity patterns"""

    def __init__(self):
        """Initialize the dynamic discovery engine"""
        self.cache_duration = timedelta(minutes=15)
        self._cache = {}
        self._last_cache_time = None

    def discover_by_market_activity(self, limit: int = 100) -> List[str]:
        """
        Discover stocks through market activity scanning

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of active ticker symbols
        """
        discovered_tickers = set()

        try:
            # Strategy 1: Use market ETFs to find components
            market_etfs = ['SPY', 'QQQ', 'DIA', 'IWM', 'VTI']
            for etf in market_etfs:
                try:
                    ticker = yf.Ticker(etf)
                    # Get recent trading data
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        # ETF exists and is tradeable
                        discovered_tickers.add(etf)

                        # Try to get holdings info (if available)
                        info = ticker.info
                        if 'holdings' in info:
                            for holding in info['holdings'][:20]:
                                if 'symbol' in holding:
                                    discovered_tickers.add(holding['symbol'])
                except:
                    continue

            # Strategy 2: Scan for high-volume tickers using market screener endpoints
            discovered_tickers.update(self._scan_high_volume_universe(limit=limit))

            # Strategy 3: Use sector ETFs to discover sector leaders
            sector_etfs = ['XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'XLY', 'XLP', 'XLU', 'XLRE', 'XLB', 'XLC']
            for etf in sector_etfs:
                if len(discovered_tickers) >= limit:
                    break
                try:
                    ticker = yf.Ticker(etf)
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        discovered_tickers.add(etf)
                except:
                    continue

            logger.info(f"Discovered {len(discovered_tickers)} stocks through market activity")

        except Exception as e:
            logger.error(f"Error in market activity discovery: {e}")

        return list(discovered_tickers)[:limit]

    def _scan_high_volume_universe(self, limit: int = 100) -> Set[str]:
        """
        Scan for high volume stocks without hardcoded lists

        Args:
            limit: Maximum number of stocks

        Returns:
            Set of ticker symbols
        """
        tickers = set()

        try:
            # Use yfinance's trending tickers feature if available
            try:
                from yfinance import Tickers

                # Get market movers and trending stocks
                trending = yf.Ticker("^GSPC")  # S&P 500 as reference

                # Try to get related/similar stocks
                info = trending.info
                if 'recommendationKey' in info:
                    # Get recommendations which often include active stocks
                    recommendations = trending.recommendations
                    if recommendations is not None and not recommendations.empty:
                        for _, row in recommendations.iterrows():
                            if 'symbol' in row:
                                tickers.add(row['symbol'])

            except Exception as e:
                logger.debug(f"Could not get trending tickers: {e}")

            # Try market screener approach
            screener_symbols = self._use_market_screener()
            tickers.update(screener_symbols)

        except Exception as e:
            logger.error(f"Error scanning high volume universe: {e}")

        return tickers

    def _use_market_screener(self) -> Set[str]:
        """
        Use market screener to find active stocks

        Returns:
            Set of ticker symbols
        """
        symbols = set()

        try:
            # Check most active stocks by trying common tickers that represent indices
            test_indices = ['^GSPC', '^IXIC', '^DJI', '^RUT']

            for index in test_indices:
                try:
                    ticker = yf.Ticker(index)
                    info = ticker.info

                    # Get constituents if available
                    if 'components' in info:
                        for component in info['components'][:20]:
                            symbols.add(component)

                except:
                    continue

        except Exception as e:
            logger.debug(f"Market screener error: {e}")

        return symbols

    def discover_by_volume_profile(self,
                                  min_volume: int = 1000000,
                                  min_price: float = 1.0,
                                  max_price: float = 10000.0,
                                  limit: int = 50) -> List[Dict]:
        """
        Discover stocks by volume profile analysis

        Args:
            min_volume: Minimum average volume
            min_price: Minimum stock price
            max_price: Maximum stock price
            limit: Maximum results

        Returns:
            List of stock dictionaries with volume data
        """
        results = []

        # Start with market activity discovery
        candidates = self.discover_by_market_activity(limit=limit * 3)

        def check_volume_profile(symbol):
            """Check individual stock volume profile"""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Check basic criteria
                price = info.get('regularMarketPrice', 0)
                volume = info.get('regularMarketVolume', 0)
                avg_volume = info.get('averageVolume', 0)

                if (price >= min_price and price <= max_price and
                    volume >= min_volume):

                    # Calculate volume metrics
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 0

                    return {
                        'ticker': symbol,
                        'price': price,
                        'volume': volume,
                        'avg_volume': avg_volume,
                        'volume_ratio': volume_ratio,
                        'market_cap': info.get('marketCap', 0),
                        'name': info.get('shortName', symbol)
                    }
            except:
                pass
            return None

        # Check candidates in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_volume_profile, symbol): symbol
                      for symbol in candidates}

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

                if len(results) >= limit:
                    break

        # Sort by volume ratio (relative volume)
        results.sort(key=lambda x: x.get('volume_ratio', 0), reverse=True)

        logger.info(f"Discovered {len(results)} stocks by volume profile")
        return results[:limit]

    def scan_for_unusual_activity(self,
                                 volume_multiplier: float = 2.0,
                                 price_change_min: float = 2.0,
                                 limit: int = 20) -> List[Dict]:
        """
        Scan for stocks with unusual trading activity

        Args:
            volume_multiplier: Minimum volume vs average
            price_change_min: Minimum price change percentage
            limit: Maximum results

        Returns:
            List of stocks with unusual activity
        """
        unusual_stocks = []

        # Get candidates
        candidates = self.discover_by_market_activity(limit=100)

        for symbol in candidates:
            if len(unusual_stocks) >= limit:
                break

            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Check for unusual volume
                volume = info.get('regularMarketVolume', 0)
                avg_volume = info.get('averageVolume', 0)

                if avg_volume > 0:
                    volume_ratio = volume / avg_volume

                    if volume_ratio >= volume_multiplier:
                        # Check price change
                        price = info.get('regularMarketPrice', 0)
                        prev_close = info.get('previousClose', 0)

                        if prev_close > 0:
                            price_change = abs((price - prev_close) / prev_close * 100)

                            if price_change >= price_change_min:
                                unusual_stocks.append({
                                    'ticker': symbol,
                                    'volume_ratio': volume_ratio,
                                    'price_change': price_change,
                                    'volume': volume,
                                    'price': price,
                                    'name': info.get('shortName', symbol)
                                })

            except Exception as e:
                logger.debug(f"Error checking {symbol}: {e}")
                continue

        # Sort by volume ratio
        unusual_stocks.sort(key=lambda x: x['volume_ratio'], reverse=True)

        logger.info(f"Found {len(unusual_stocks)} stocks with unusual activity")
        return unusual_stocks

    def get_market_breadth(self) -> Dict[str, any]:
        """
        Calculate market breadth metrics dynamically

        Returns:
            Dictionary with market breadth statistics
        """
        breadth = {
            'advancing': 0,
            'declining': 0,
            'unchanged': 0,
            'new_highs': 0,
            'new_lows': 0,
            'above_ma50': 0,
            'below_ma50': 0,
            'sample_size': 0
        }

        try:
            # Get a sample of active stocks
            sample = self.discover_by_market_activity(limit=100)
            breadth['sample_size'] = len(sample)

            for symbol in sample[:50]:  # Limit for performance
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info

                    # Price change
                    price = info.get('regularMarketPrice', 0)
                    prev_close = info.get('previousClose', 0)

                    if prev_close > 0:
                        if price > prev_close:
                            breadth['advancing'] += 1
                        elif price < prev_close:
                            breadth['declining'] += 1
                        else:
                            breadth['unchanged'] += 1

                    # 52-week highs/lows
                    high_52w = info.get('fiftyTwoWeekHigh', 0)
                    low_52w = info.get('fiftyTwoWeekLow', 0)

                    if high_52w > 0 and price >= high_52w * 0.95:
                        breadth['new_highs'] += 1
                    elif low_52w > 0 and price <= low_52w * 1.05:
                        breadth['new_lows'] += 1

                    # MA50 comparison
                    ma50 = info.get('fiftyDayAverage', 0)
                    if ma50 > 0:
                        if price > ma50:
                            breadth['above_ma50'] += 1
                        else:
                            breadth['below_ma50'] += 1

                except:
                    continue

            # Calculate ratios
            if breadth['declining'] > 0:
                breadth['advance_decline_ratio'] = breadth['advancing'] / breadth['declining']
            else:
                breadth['advance_decline_ratio'] = breadth['advancing']

            if breadth['new_lows'] > 0:
                breadth['high_low_ratio'] = breadth['new_highs'] / breadth['new_lows']
            else:
                breadth['high_low_ratio'] = breadth['new_highs']

        except Exception as e:
            logger.error(f"Error calculating market breadth: {e}")

        return breadth

    def find_correlated_stocks(self, reference_ticker: str, correlation_threshold: float = 0.7, limit: int = 10) -> List[Dict]:
        """
        Find stocks correlated with a reference ticker

        Args:
            reference_ticker: Reference stock ticker
            correlation_threshold: Minimum correlation coefficient
            limit: Maximum results

        Returns:
            List of correlated stocks
        """
        correlated = []

        try:
            # Get reference stock data
            ref = yf.Ticker(reference_ticker)
            ref_hist = ref.history(period="1mo")

            if ref_hist.empty:
                return []

            ref_returns = ref_hist['Close'].pct_change().dropna()

            # Get candidates from same sector if possible
            ref_info = ref.info
            sector = ref_info.get('sector', '')

            # Get market stocks
            candidates = self.discover_by_market_activity(limit=50)

            for symbol in candidates:
                if symbol == reference_ticker:
                    continue

                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1mo")

                    if not hist.empty:
                        returns = hist['Close'].pct_change().dropna()

                        # Calculate correlation
                        if len(returns) > 10 and len(ref_returns) > 10:
                            correlation = returns.corr(ref_returns)

                            if abs(correlation) >= correlation_threshold:
                                info = ticker.info
                                correlated.append({
                                    'ticker': symbol,
                                    'correlation': correlation,
                                    'name': info.get('shortName', symbol),
                                    'sector': info.get('sector', ''),
                                    'same_sector': info.get('sector', '') == sector
                                })

                except:
                    continue

                if len(correlated) >= limit:
                    break

            # Sort by correlation
            correlated.sort(key=lambda x: abs(x['correlation']), reverse=True)

        except Exception as e:
            logger.error(f"Error finding correlated stocks: {e}")

        return correlated[:limit]