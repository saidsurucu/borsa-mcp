"""
Dynamic Ticker Discovery Module
Fetches real-time stock tickers from web sources without hardcoding
"""

import logging
import yfinance as yf
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DynamicTickerDiscovery:
    """Discovers stock tickers dynamically from various sources"""

    def __init__(self):
        self.session = httpx.Client(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )

    def get_trending_tickers(self) -> List[str]:
        """
        Get trending/most active tickers from Yahoo Finance

        Returns:
            List of trending ticker symbols
        """
        try:
            # Try Yahoo Finance trending tickers page
            url = "https://finance.yahoo.com/trending-tickers"
            response = self.session.get(url)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for ticker symbols in the page
                tickers = []

                # Find links that look like tickers
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    if '/quote/' in href:
                        # Extract ticker from URL like /quote/AAPL
                        parts = href.split('/quote/')
                        if len(parts) > 1:
                            ticker = parts[1].split('?')[0].split('/')[0]
                            if ticker and len(ticker) <= 5 and ticker.isalpha():
                                if ticker not in tickers:
                                    tickers.append(ticker.upper())

                logger.info(f"Found {len(tickers)} trending tickers")
                return tickers[:50]  # Return top 50

        except Exception as e:
            logger.error(f"Error fetching trending tickers: {e}")

        return []

    def get_most_active_from_yahoo(self) -> List[str]:
        """
        Get most active stocks from Yahoo Finance screener

        Returns:
            List of most active ticker symbols
        """
        try:
            # Yahoo Finance most active stocks
            url = "https://finance.yahoo.com/most-active"
            response = self.session.get(url)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for ticker symbols
                tickers = []

                # Find table rows or ticker links
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    if '/quote/' in href:
                        parts = href.split('/quote/')
                        if len(parts) > 1:
                            ticker = parts[1].split('?')[0].split('/')[0]
                            if ticker and len(ticker) <= 5 and ticker.isalpha():
                                if ticker not in tickers:
                                    tickers.append(ticker.upper())

                logger.info(f"Found {len(tickers)} most active tickers")
                return tickers[:100]

        except Exception as e:
            logger.error(f"Error fetching most active stocks: {e}")

        return []

    def verify_tickers(self, tickers: List[str]) -> List[str]:
        """
        Verify that tickers are valid by checking with yfinance

        Args:
            tickers: List of ticker symbols to verify

        Returns:
            List of valid ticker symbols
        """
        valid_tickers = []

        for ticker in tickers[:50]:  # Limit to avoid too many requests
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                if info and info.get('symbol'):
                    valid_tickers.append(ticker)
            except:
                continue

        logger.info(f"Verified {len(valid_tickers)} valid tickers")
        return valid_tickers

    def get_dynamic_stock_list(self, limit: int = 30) -> List[str]:
        """
        Get a dynamic list of active stock tickers

        Args:
            limit: Maximum number of tickers to return

        Returns:
            List of stock ticker symbols
        """
        all_tickers = []

        # Try multiple sources
        trending = self.get_trending_tickers()
        if trending:
            all_tickers.extend(trending)

        most_active = self.get_most_active_from_yahoo()
        if most_active:
            for ticker in most_active:
                if ticker not in all_tickers:
                    all_tickers.append(ticker)

        # Verify and return
        if all_tickers:
            valid = self.verify_tickers(all_tickers)
            return valid[:limit]

        return []

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'session'):
            self.session.close()