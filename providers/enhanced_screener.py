"""
Enhanced Market Screener using available yfinance features
Uses dynamic discovery without hardcoded ticker lists
"""

import yfinance as yf
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import concurrent.futures
from providers.dynamic_stock_discovery import DynamicStockDiscovery

logger = logging.getLogger(__name__)


class EnhancedScreener:
    """Enhanced screener using yfinance's available features"""

    def __init__(self):
        """Initialize the enhanced screener"""
        self.discovery = DynamicStockDiscovery()
        # Common market sectors for discovery
        self.sector_keywords = [
            'technology', 'finance', 'healthcare', 'energy',
            'consumer', 'industrial', 'retail', 'automotive'
        ]

    def search_trending_stocks(self) -> List[str]:
        """
        Use yfinance Search to find trending stocks

        Returns:
            List of ticker symbols
        """
        tickers = set()

        try:
            from yfinance import Search

            # Search for major market terms
            search_terms = ['stock', 'market', 'trading', 'index', 'etf']

            for term in search_terms:
                try:
                    search = Search(term)
                    results = search.quotes

                    for result in results[:10]:  # Top 10 from each search
                        if 'symbol' in result:
                            symbol = result['symbol']
                            # Filter for US stocks (no dots, reasonable length)
                            if '.' not in symbol and 1 <= len(symbol) <= 5:
                                tickers.add(symbol)
                except:
                    continue

            logger.info(f"Found {len(tickers)} tickers through search")

        except ImportError:
            logger.warning("Search module not available")

        return list(tickers)

    def get_high_volume_stocks(self, limit: int = 50) -> List[Dict]:
        """
        Find high-volume stocks dynamically without hardcoded lists

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of stock dictionaries with ticker, price, volume, change
        """
        # Use dynamic discovery to find high volume stocks
        logger.info(f"Discovering high volume stocks dynamically (limit: {limit})")

        # Get stocks by volume profile
        high_volume = self.discovery.discover_by_volume_profile(
            min_volume=1000000,
            min_price=1.0,
            limit=limit
        )

        # Enrich with additional data if needed
        enriched_stocks = []
        for stock in high_volume:
            try:
                ticker = yf.Ticker(stock['ticker'])
                info = ticker.info

                enriched_stock = {
                    'ticker': stock['ticker'],
                    'price': stock.get('price', info.get('regularMarketPrice', 0)),
                    'volume': stock.get('volume', info.get('regularMarketVolume', 0)),
                    'change_percent': info.get('regularMarketChangePercent', 0),
                    'market_cap': stock.get('market_cap', info.get('marketCap', 0)),
                    'company_name': stock.get('name', info.get('longName', stock['ticker']))
                }
                enriched_stocks.append(enriched_stock)

            except Exception as e:
                logger.debug(f"Could not enrich {stock.get('ticker', 'unknown')}: {e}")
                # Use original data if enrichment fails
                enriched_stocks.append(stock)

        logger.info(f"Found {len(enriched_stocks)} high volume stocks")
        return enriched_stocks[:limit]

    def screen_stocks(self,
                     min_volume: Optional[int] = None,
                     min_market_cap: Optional[float] = None,
                     sector: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Screen stocks based on criteria and return gainers, losers, most active

        Args:
            min_volume: Minimum trading volume
            min_market_cap: Minimum market capitalization
            sector: Specific sector to filter

        Returns:
            Dictionary with 'gainers', 'losers', 'most_active' lists
        """
        # Get high volume stocks
        stocks = self.get_high_volume_stocks(limit=100)

        # Apply filters
        filtered_stocks = []
        for stock in stocks:
            if min_volume and stock.get('volume', 0) < min_volume:
                continue
            if min_market_cap and stock.get('market_cap', 0) < min_market_cap:
                continue

            # If sector filter is specified, check it
            if sector:
                try:
                    ticker = yf.Ticker(stock['ticker'])
                    info = ticker.info
                    if info.get('sector', '').lower() != sector.lower():
                        continue
                except:
                    continue

            filtered_stocks.append(stock)

        # Sort for different categories
        sorted_by_gain = sorted(filtered_stocks,
                               key=lambda x: x.get('change_percent', 0),
                               reverse=True)
        sorted_by_loss = sorted(filtered_stocks,
                               key=lambda x: x.get('change_percent', 0))
        sorted_by_volume = sorted(filtered_stocks,
                                 key=lambda x: x.get('volume', 0),
                                 reverse=True)

        return {
            'gainers': sorted_by_gain[:10],
            'losers': sorted_by_loss[:10],
            'most_active': sorted_by_volume[:10]
        }

    def get_market_movers(self) -> Dict[str, List[Dict]]:
        """
        Get market movers (gainers, losers, most active) without any filters

        Returns:
            Dictionary with categorized market movers
        """
        return self.screen_stocks()