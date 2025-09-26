"""
US Markets Provider for S&P 500, NASDAQ, and other US stock data.
Leverages yfinance and optional Alpha Vantage integration.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache
import pandas as pd
import yfinance as yf
import httpx
from models.us_markets_models import (
    USStockInfo, USMarketQuote, USIndexData, USSectorPerformance,
    USMarketMovers, USStockScreener, USOptionsChain, USEarningsCalendar,
    USMarketSentiment, USInsiderTrading, USMarketNews
)

logger = logging.getLogger(__name__)


class USMarketsProvider:
    """Provider for US stock market data (S&P 500, NASDAQ, NYSE)"""

    # Major US indices
    INDICES = {
        "sp500": {"symbol": "^GSPC", "name": "S&P 500"},
        "nasdaq": {"symbol": "^IXIC", "name": "NASDAQ Composite"},
        "dow": {"symbol": "^DJI", "name": "Dow Jones Industrial Average"},
        "russell2000": {"symbol": "^RUT", "name": "Russell 2000"},
        "vix": {"symbol": "^VIX", "name": "CBOE Volatility Index"},
        "nasdaq100": {"symbol": "^NDX", "name": "NASDAQ-100"}
    }

    # S&P 500 sectors ETFs for sector performance
    SECTOR_ETFS = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Communication Services": "XLC",
        "Industrials": "XLI",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Materials": "XLB"
    }

    def __init__(self, alpha_vantage_api_key: Optional[str] = None):
        """
        Initialize US Markets Provider

        Args:
            alpha_vantage_api_key: Optional API key for Alpha Vantage enhanced data
        """
        self.alpha_vantage_key = alpha_vantage_api_key
        self.session = httpx.Client(timeout=30.0)
        self._sp500_tickers: Optional[List[str]] = None
        self._nasdaq_tickers: Optional[List[str]] = None

    @lru_cache(maxsize=1)
    def get_sp500_tickers(self) -> List[str]:
        """Get list of S&P 500 tickers"""
        if self._sp500_tickers:
            return self._sp500_tickers

        try:
            # Get S&P 500 list from Wikipedia
            tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
            df = tables[0]
            self._sp500_tickers = df['Symbol'].tolist()
            return self._sp500_tickers
        except Exception as e:
            logger.error(f"Error fetching S&P 500 list: {e}")
            # Return a subset of well-known S&P 500 stocks as fallback
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
                   "JNJ", "V", "UNH", "NVDA", "PG", "HD", "JPM", "MA"]

    @lru_cache(maxsize=1)
    def get_nasdaq100_tickers(self) -> List[str]:
        """Get list of NASDAQ-100 tickers"""
        try:
            # Get NASDAQ-100 list from Wikipedia
            tables = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')
            df = tables[2]  # The table index might vary
            return df['Ticker'].tolist()
        except Exception as e:
            logger.error(f"Error fetching NASDAQ-100 list: {e}")
            # Return subset of well-known NASDAQ stocks
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA",
                   "NVDA", "INTC", "CSCO", "ADBE", "NFLX", "CMCSA"]

    def search_stocks(self, query: str, limit: int = 20) -> List[USStockInfo]:
        """
        Search for US stocks by ticker or company name

        Args:
            query: Search query (ticker or company name)
            limit: Maximum number of results

        Returns:
            List of matching stocks
        """
        results = []
        query = query.upper()

        # Get S&P 500 and NASDAQ-100 tickers
        sp500 = self.get_sp500_tickers()
        nasdaq100 = self.get_nasdaq100_tickers()

        # First, try exact ticker match
        if len(query) <= 5:  # Likely a ticker symbol
            try:
                ticker = yf.Ticker(query)
                info = ticker.info
                if info.get('symbol'):
                    index_membership = []
                    if query in sp500:
                        index_membership.append("S&P500")
                    if query in nasdaq100:
                        index_membership.append("NASDAQ100")

                    results.append(USStockInfo(
                        ticker=info.get('symbol', query),
                        company_name=info.get('longName', info.get('shortName', '')),
                        exchange=info.get('exchange', ''),
                        market_cap=info.get('marketCap'),
                        sector=info.get('sector'),
                        industry=info.get('industry'),
                        index_membership=index_membership
                    ))
            except Exception as e:
                logger.debug(f"Ticker lookup failed for {query}: {e}")

        # Search in S&P 500 and NASDAQ-100
        for ticker in sp500 + nasdaq100:
            if len(results) >= limit:
                break
            if ticker not in [r.ticker for r in results]:
                if query in ticker:
                    try:
                        t = yf.Ticker(ticker)
                        info = t.info
                        index_membership = []
                        if ticker in sp500:
                            index_membership.append("S&P500")
                        if ticker in nasdaq100:
                            index_membership.append("NASDAQ100")

                        results.append(USStockInfo(
                            ticker=ticker,
                            company_name=info.get('longName', info.get('shortName', '')),
                            exchange=info.get('exchange', ''),
                            market_cap=info.get('marketCap'),
                            sector=info.get('sector'),
                            industry=info.get('industry'),
                            index_membership=index_membership
                        ))
                    except Exception:
                        pass

        return results[:limit]

    def get_quote(self, tickers: List[str]) -> List[USMarketQuote]:
        """
        Get real-time quotes for US stocks

        Args:
            tickers: List of ticker symbols

        Returns:
            List of market quotes
        """
        quotes = []

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # Get current price data
                history = stock.history(period="1d", interval="1m")
                if not history.empty:
                    current_price = history['Close'].iloc[-1]
                else:
                    current_price = info.get('regularMarketPrice', info.get('currentPrice', 0))

                previous_close = info.get('previousClose', 0)
                change = current_price - previous_close if previous_close else 0
                change_percent = (change / previous_close * 100) if previous_close else 0

                quotes.append(USMarketQuote(
                    ticker=ticker,
                    price=current_price,
                    change=change,
                    change_percent=change_percent,
                    volume=info.get('volume', 0),
                    avg_volume=info.get('averageVolume'),
                    market_cap=info.get('marketCap'),
                    pe_ratio=info.get('trailingPE'),
                    week_52_high=info.get('fiftyTwoWeekHigh'),
                    week_52_low=info.get('fiftyTwoWeekLow'),
                    dividend_yield=info.get('dividendYield'),
                    beta=info.get('beta'),
                    timestamp=datetime.now()
                ))
            except Exception as e:
                logger.error(f"Error fetching quote for {ticker}: {e}")

        return quotes

    def get_index_data(self, indices: Optional[List[str]] = None) -> List[USIndexData]:
        """
        Get major US index data

        Args:
            indices: List of index names (sp500, nasdaq, dow) or None for all

        Returns:
            List of index data
        """
        if indices is None:
            indices = list(self.INDICES.keys())

        index_data = []

        for idx_name in indices:
            if idx_name not in self.INDICES:
                continue

            idx_info = self.INDICES[idx_name]
            symbol = idx_info["symbol"]

            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                history = ticker.history(period="1d", interval="1m")

                if not history.empty:
                    current = history['Close'].iloc[-1]
                    open_price = history['Open'].iloc[0]
                    high = history['High'].max()
                    low = history['Low'].min()
                    volume = history['Volume'].sum()
                else:
                    current = info.get('regularMarketPrice', 0)
                    open_price = info.get('regularMarketOpen', 0)
                    high = info.get('regularMarketDayHigh', 0)
                    low = info.get('regularMarketDayLow', 0)
                    volume = info.get('regularMarketVolume')

                previous = info.get('previousClose', 0)
                change = current - previous if previous else 0
                change_percent = (change / previous * 100) if previous else 0

                index_data.append(USIndexData(
                    index_symbol=symbol,
                    index_name=idx_info["name"],
                    value=current,
                    change=change,
                    change_percent=change_percent,
                    previous_close=previous,
                    open=open_price,
                    day_high=high,
                    day_low=low,
                    volume=int(volume) if volume else None,
                    timestamp=datetime.now()
                ))
            except Exception as e:
                logger.error(f"Error fetching index data for {symbol}: {e}")

        return index_data

    def get_sector_performance(self) -> List[USSectorPerformance]:
        """
        Get S&P 500 sector performance

        Returns:
            List of sector performance data
        """
        sector_data = []

        for sector_name, etf_symbol in self.SECTOR_ETFS.items():
            try:
                etf = yf.Ticker(etf_symbol)
                info = etf.info
                history = etf.history(period="1d")

                if not history.empty:
                    current = history['Close'].iloc[-1]
                    previous = info.get('previousClose', current)
                    change_percent = ((current - previous) / previous * 100) if previous else 0
                    volume = history['Volume'].sum()
                else:
                    change_percent = 0
                    volume = 0

                sector_data.append(USSectorPerformance(
                    sector=sector_name,
                    change_percent=change_percent,
                    market_cap=info.get('totalAssets', 0),
                    volume=int(volume),
                    advancing=0,  # Would need more complex calculation
                    declining=0,  # Would need more complex calculation
                    unchanged=0   # Would need more complex calculation
                ))
            except Exception as e:
                logger.error(f"Error fetching sector data for {sector_name}: {e}")

        return sector_data

    def get_market_movers(self) -> Dict[str, USMarketMovers]:
        """
        Get market movers (gainers, losers, most active)

        Returns:
            Dictionary with gainers, losers, and most_active
        """
        movers = {}

        try:
            # Get S&P 500 tickers for analysis
            tickers = self.get_sp500_tickers()[:100]  # Limit to top 100 for performance

            stock_data = []
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    history = stock.history(period="1d")

                    if not history.empty:
                        current = history['Close'].iloc[-1]
                        previous = info.get('previousClose', current)
                        change_percent = ((current - previous) / previous * 100) if previous else 0
                        volume = history['Volume'].sum()

                        stock_data.append({
                            "ticker": ticker,
                            "price": current,
                            "change_percent": change_percent,
                            "volume": int(volume),
                            "company_name": info.get('longName', ticker)
                        })
                except Exception:
                    continue

            # Sort for gainers, losers, and most active
            sorted_by_gain = sorted(stock_data, key=lambda x: x['change_percent'], reverse=True)
            sorted_by_loss = sorted(stock_data, key=lambda x: x['change_percent'])
            sorted_by_volume = sorted(stock_data, key=lambda x: x['volume'], reverse=True)

            movers['gainers'] = USMarketMovers(
                category="gainers",
                stocks=sorted_by_gain[:10],
                timestamp=datetime.now()
            )

            movers['losers'] = USMarketMovers(
                category="losers",
                stocks=sorted_by_loss[:10],
                timestamp=datetime.now()
            )

            movers['most_active'] = USMarketMovers(
                category="most_active",
                stocks=sorted_by_volume[:10],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error fetching market movers: {e}")

        return movers

    def get_options_chain(self, ticker: str) -> Optional[USOptionsChain]:
        """
        Get options chain for a stock

        Args:
            ticker: Stock ticker symbol

        Returns:
            Options chain data or None
        """
        try:
            stock = yf.Ticker(ticker)

            # Get expiration dates
            expirations = stock.options

            if not expirations:
                return None

            # Get options for the nearest expiration
            opt = stock.option_chain(expirations[0])

            calls = opt.calls.to_dict('records')
            puts = opt.puts.to_dict('records')

            # Calculate average IV
            call_iv = opt.calls['impliedVolatility'].mean() if 'impliedVolatility' in opt.calls else None
            put_iv = opt.puts['impliedVolatility'].mean() if 'impliedVolatility' in opt.puts else None
            avg_iv = (call_iv + put_iv) / 2 if call_iv and put_iv else None

            return USOptionsChain(
                ticker=ticker,
                expiration_dates=list(expirations),
                calls=calls[:20],  # Limit to 20 strikes
                puts=puts[:20],     # Limit to 20 strikes
                implied_volatility=avg_iv,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error fetching options chain for {ticker}: {e}")
            return None

    def get_earnings_calendar(self, days_ahead: int = 7) -> USEarningsCalendar:
        """
        Get upcoming earnings calendar

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            Earnings calendar data
        """
        try:
            # Get earnings for S&P 500 companies
            sp500 = self.get_sp500_tickers()[:50]  # Limit for performance

            earnings_data = []
            end_date = datetime.now() + timedelta(days=days_ahead)

            for ticker in sp500:
                try:
                    stock = yf.Ticker(ticker)
                    calendar = stock.calendar

                    if calendar is not None and not calendar.empty:
                        # Check if earnings date is within our range
                        if 'Earnings Date' in calendar.index:
                            earnings_date = calendar.loc['Earnings Date']
                            if isinstance(earnings_date, pd.Timestamp):
                                if earnings_date <= end_date:
                                    earnings_data.append({
                                        "ticker": ticker,
                                        "date": earnings_date.strftime("%Y-%m-%d"),
                                        "company": stock.info.get('longName', ticker)
                                    })
                except Exception:
                    continue

            # Group by date
            grouped_earnings = {}
            for item in earnings_data:
                date = item['date']
                if date not in grouped_earnings:
                    grouped_earnings[date] = []
                grouped_earnings[date].append(item)

            # Return the first date with earnings as example
            if grouped_earnings:
                first_date = min(grouped_earnings.keys())
                return USEarningsCalendar(
                    date=first_date,
                    stocks=grouped_earnings[first_date]
                )
            else:
                return USEarningsCalendar(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    stocks=[]
                )

        except Exception as e:
            logger.error(f"Error fetching earnings calendar: {e}")
            return USEarningsCalendar(
                date=datetime.now().strftime("%Y-%m-%d"),
                stocks=[]
            )

    def get_market_sentiment(self) -> USMarketSentiment:
        """
        Get market sentiment indicators

        Returns:
            Market sentiment data
        """
        try:
            # Get VIX
            vix = yf.Ticker("^VIX")
            vix_info = vix.info
            vix_value = vix_info.get('regularMarketPrice', 0)

            # Get market breadth from S&P 500 sample
            sp500_sample = self.get_sp500_tickers()[:100]

            new_highs = 0
            new_lows = 0
            advancing = 0
            declining = 0

            for ticker in sp500_sample:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info

                    current = info.get('regularMarketPrice', 0)
                    previous = info.get('previousClose', 0)
                    high_52w = info.get('fiftyTwoWeekHigh', 0)
                    low_52w = info.get('fiftyTwoWeekLow', 0)

                    if current > previous:
                        advancing += 1
                    elif current < previous:
                        declining += 1

                    if current >= high_52w * 0.98:  # Within 2% of 52-week high
                        new_highs += 1
                    elif current <= low_52w * 1.02:  # Within 2% of 52-week low
                        new_lows += 1

                except Exception:
                    continue

            # Calculate fear & greed approximation (simplified)
            # Real calculation would be more complex
            if vix_value < 12:
                fear_greed = 75  # Greed
            elif vix_value < 20:
                fear_greed = 50  # Neutral
            else:
                fear_greed = 25  # Fear

            advance_decline = advancing / declining if declining > 0 else advancing

            return USMarketSentiment(
                fear_greed_index=fear_greed,
                vix=vix_value,
                put_call_ratio=None,  # Would need options data
                advance_decline_ratio=advance_decline,
                new_highs=new_highs,
                new_lows=new_lows,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error fetching market sentiment: {e}")
            return USMarketSentiment(
                fear_greed_index=50,
                vix=20,
                new_highs=0,
                new_lows=0,
                timestamp=datetime.now()
            )

    def screen_stocks(self, criteria: Dict[str, Any], limit: int = 50) -> USStockScreener:
        """
        Screen stocks based on criteria

        Args:
            criteria: Screening criteria (market_cap_min, pe_max, etc.)
            limit: Maximum number of results

        Returns:
            Screener results
        """
        results = []

        # Get S&P 500 stocks to screen
        tickers = self.get_sp500_tickers()

        for ticker in tickers[:200]:  # Limit initial pool for performance
            if len(results) >= limit:
                break

            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # Apply criteria
                passes = True

                if 'market_cap_min' in criteria:
                    if info.get('marketCap', 0) < criteria['market_cap_min']:
                        passes = False

                if 'market_cap_max' in criteria:
                    if info.get('marketCap', float('inf')) > criteria['market_cap_max']:
                        passes = False

                if 'pe_min' in criteria:
                    pe = info.get('trailingPE', 0)
                    if pe < criteria['pe_min']:
                        passes = False

                if 'pe_max' in criteria:
                    pe = info.get('trailingPE', float('inf'))
                    if pe > criteria['pe_max']:
                        passes = False

                if 'dividend_yield_min' in criteria:
                    div = info.get('dividendYield', 0)
                    if div < criteria['dividend_yield_min']:
                        passes = False

                if 'sector' in criteria:
                    if info.get('sector', '') != criteria['sector']:
                        passes = False

                if passes:
                    index_membership = []
                    if ticker in self.get_sp500_tickers():
                        index_membership.append("S&P500")
                    if ticker in self.get_nasdaq100_tickers():
                        index_membership.append("NASDAQ100")

                    results.append(USStockInfo(
                        ticker=ticker,
                        company_name=info.get('longName', ticker),
                        exchange=info.get('exchange', ''),
                        market_cap=info.get('marketCap'),
                        sector=info.get('sector'),
                        industry=info.get('industry'),
                        index_membership=index_membership
                    ))

            except Exception:
                continue

        return USStockScreener(
            criteria=criteria,
            results=results,
            count=len(results),
            timestamp=datetime.now()
        )

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'session'):
            self.session.close()