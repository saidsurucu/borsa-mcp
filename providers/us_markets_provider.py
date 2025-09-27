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
from providers.enhanced_screener import EnhancedScreener
from models.us_markets_models import (
    USStockInfo, USMarketQuote, USIndexData, USSectorPerformance,
    USMarketMovers, USStockScreener, USOptionsChain, USEarningsCalendar,
    USMarketSentiment, USInsiderTrading, USMarketNews,
    USTechnicalIndicators, USIntradayLevels, USHistoricalData
)
from providers.technical_indicators import TechnicalIndicators

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
        self.screener = EnhancedScreener()
        self.technical_indicators = TechnicalIndicators()

    def get_sp500_tickers(self) -> List[str]:
        """Get list of S&P 500 tickers dynamically from market data"""
        if self._sp500_tickers:
            return self._sp500_tickers

        try:
            # Use enhanced screener to get active stocks
            logger.info("Fetching S&P 500 tickers dynamically using enhanced screener")

            # Get high volume stocks as proxy for S&P 500
            stocks = self.screener.get_high_volume_stocks(limit=500)

            if stocks:
                self._sp500_tickers = [s['ticker'] for s in stocks]
                logger.info(f"Discovered {len(self._sp500_tickers)} active stock tickers")
            else:
                logger.warning("Could not discover stock tickers dynamically")
                self._sp500_tickers = []

            return self._sp500_tickers

        except Exception as e:
            logger.error(f"Error fetching S&P 500 tickers: {e}")
            return []

    def get_nasdaq100_tickers(self) -> List[str]:
        """Get list of NASDAQ-100 tickers dynamically from market data"""
        try:
            # Use enhanced screener for NASDAQ stocks
            logger.info("Fetching NASDAQ-100 tickers dynamically using enhanced screener")

            # Get high volume stocks with tech focus
            stocks = self.screener.get_high_volume_stocks(limit=100)
            tickers = [s['ticker'] for s in stocks]

            # Filter for NASDAQ characteristics
            nasdaq_tickers = []
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    # NASDAQ stocks often in tech sector or NASDAQ exchange
                    if info.get('exchange') in ['NMS', 'NASDAQ', 'NasdaqGS'] or \
                       info.get('sector') == 'Technology':
                        nasdaq_tickers.append(ticker)
                except:
                    # If we can't verify, include it anyway as it's active
                    nasdaq_tickers.append(ticker)

            return nasdaq_tickers[:100]  # Limit to 100

        except Exception as e:
            logger.error(f"Error fetching NASDAQ-100 tickers: {e}")
            return []

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
            # Use enhanced screener to get market movers
            logger.info("Fetching market movers using enhanced screener")

            # Get market movers from enhanced screener
            screener_results = self.screener.get_market_movers()

            if screener_results:
                # Create USMarketMovers objects from results
                movers['gainers'] = USMarketMovers(
                    category="gainers",
                    stocks=screener_results.get('gainers', []),
                    timestamp=datetime.now()
                )

                movers['losers'] = USMarketMovers(
                    category="losers",
                    stocks=screener_results.get('losers', []),
                    timestamp=datetime.now()
                )

                movers['most_active'] = USMarketMovers(
                    category="most_active",
                    stocks=screener_results.get('most_active', []),
                    timestamp=datetime.now()
                )

                total_stocks = len(screener_results.get('gainers', [])) + \
                               len(screener_results.get('losers', [])) + \
                               len(screener_results.get('most_active', []))
                logger.info(f"Found {total_stocks} market movers")
            else:
                # Return empty movers if no data
                logger.warning("No market movers found")
                movers['gainers'] = USMarketMovers(category="gainers", stocks=[], timestamp=datetime.now())
                movers['losers'] = USMarketMovers(category="losers", stocks=[], timestamp=datetime.now())
                movers['most_active'] = USMarketMovers(category="most_active", stocks=[], timestamp=datetime.now())

        except Exception as e:
            logger.error(f"Error fetching market movers: {e}")
            # Return empty movers on error
            movers['gainers'] = USMarketMovers(category="gainers", stocks=[], timestamp=datetime.now())
            movers['losers'] = USMarketMovers(category="losers", stocks=[], timestamp=datetime.now())
            movers['most_active'] = USMarketMovers(category="most_active", stocks=[], timestamp=datetime.now())

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

    def get_historical_data_with_indicators(self,
                                           ticker: str,
                                           period: str = "1mo",
                                           interval: str = "1d",
                                           extended_hours: bool = False) -> Optional[USHistoricalData]:
        """
        Get historical data with technical indicators

        Args:
            ticker: Stock ticker symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
            extended_hours: Include pre/post market data

        Returns:
            Historical data with technical indicators
        """
        try:
            stock = yf.Ticker(ticker)

            # Fetch historical data
            df = stock.history(
                period=period,
                interval=interval,
                prepost=extended_hours,
                auto_adjust=True,
                back_adjust=False
            )

            if df.empty:
                logger.warning(f"No historical data found for {ticker}")
                return None

            # Calculate all technical indicators
            df_with_indicators = self.technical_indicators.calculate_all_indicators(df)

            # Get latest indicators
            latest = df_with_indicators.iloc[-1]
            indicators = USTechnicalIndicators(
                ticker=ticker,
                timeframe=interval,
                sma_20=latest.get('SMA_20'),
                sma_50=latest.get('SMA_50'),
                sma_200=latest.get('SMA_200'),
                ema_12=latest.get('EMA_12'),
                ema_26=latest.get('EMA_26'),
                bb_upper=latest.get('BB_Upper'),
                bb_middle=latest.get('BB_Middle'),
                bb_lower=latest.get('BB_Lower'),
                rsi=latest.get('RSI'),
                macd=latest.get('MACD'),
                macd_signal=latest.get('MACD_Signal'),
                macd_histogram=latest.get('MACD_Histogram'),
                atr=latest.get('ATR'),
                stoch_k=latest.get('Stoch_K'),
                stoch_d=latest.get('Stoch_D'),
                vwap=latest.get('VWAP'),
                obv=latest.get('OBV'),
                relative_volume=latest.get('RVOL'),
                timestamp=datetime.now()
            )

            # Get trading signals
            signals = self.technical_indicators.get_indicator_signals(df_with_indicators)

            # Convert DataFrame to list of dicts
            data = df_with_indicators.reset_index().to_dict('records')

            # Convert timestamps to strings for JSON serialization
            for record in data:
                if 'Date' in record and hasattr(record['Date'], 'strftime'):
                    record['Date'] = record['Date'].strftime('%Y-%m-%d %H:%M:%S')

            return USHistoricalData(
                ticker=ticker,
                timeframe=interval,
                data=data,
                indicators=indicators,
                signals=signals,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error fetching historical data with indicators for {ticker}: {e}")
            return None

    def get_intraday_levels(self, ticker: str) -> Optional[USIntradayLevels]:
        """
        Calculate intraday pivot points and support/resistance levels

        Args:
            ticker: Stock ticker symbol

        Returns:
            Intraday levels data
        """
        try:
            stock = yf.Ticker(ticker)

            # Get previous day's data for pivot calculation
            history = stock.history(period="5d", interval="1d")

            if history.empty or len(history) < 2:
                logger.warning(f"Insufficient data for pivot calculation for {ticker}")
                return None

            # Use previous day's data
            prev_day = history.iloc[-2]
            high = prev_day['High']
            low = prev_day['Low']
            close = prev_day['Close']

            # Calculate pivot points
            pivot_levels = self.technical_indicators.calculate_pivot_points(high, low, close)

            # Get recent price data for dynamic levels
            recent_data = stock.history(period="1mo", interval="1d")

            if not recent_data.empty:
                # Calculate dynamic support and resistance
                sr_levels = self.technical_indicators.calculate_support_resistance(
                    recent_data['Close'],
                    window=10
                )
            else:
                sr_levels = {'support': [], 'resistance': []}

            return USIntradayLevels(
                ticker=ticker,
                pivot=pivot_levels['pivot'],
                resistance_1=pivot_levels['r1'],
                resistance_2=pivot_levels['r2'],
                resistance_3=pivot_levels['r3'],
                support_1=pivot_levels['s1'],
                support_2=pivot_levels['s2'],
                support_3=pivot_levels['s3'],
                dynamic_resistance=sr_levels['resistance'],
                dynamic_support=sr_levels['support'],
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error calculating intraday levels for {ticker}: {e}")
            return None

    def get_multi_timeframe_data(self, ticker: str, timeframes: Optional[List[str]] = None) -> Dict[str, USHistoricalData]:
        """
        Get data across multiple timeframes for comprehensive analysis

        Args:
            ticker: Stock ticker symbol
            timeframes: List of timeframe specifications or None for default

        Returns:
            Dictionary mapping timeframe to historical data
        """
        if timeframes is None:
            # Default timeframes for different analysis perspectives
            timeframes = [
                ("1d", "1m"),    # Intraday scalping
                ("5d", "5m"),    # Day trading
                ("1mo", "30m"),  # Swing trading
                ("3mo", "1d"),   # Position trading
                ("1y", "1wk"),   # Long-term investing
            ]
        else:
            # Parse user-provided timeframes
            parsed_timeframes = []
            for tf in timeframes:
                if "," in tf:
                    period, interval = tf.split(",")
                    parsed_timeframes.append((period.strip(), interval.strip()))
                else:
                    # Default mapping for common timeframes
                    tf_map = {
                        "1m": ("1d", "1m"),
                        "5m": ("5d", "5m"),
                        "15m": ("5d", "15m"),
                        "30m": ("1mo", "30m"),
                        "1h": ("1mo", "60m"),
                        "4h": ("3mo", "60m"),
                        "daily": ("6mo", "1d"),
                        "weekly": ("2y", "1wk"),
                        "monthly": ("5y", "1mo")
                    }
                    if tf in tf_map:
                        parsed_timeframes.append(tf_map[tf])
                    else:
                        parsed_timeframes.append(("1mo", tf))
            timeframes = parsed_timeframes

        results = {}

        for period, interval in timeframes:
            try:
                data = self.get_historical_data_with_indicators(
                    ticker=ticker,
                    period=period,
                    interval=interval,
                    extended_hours=True
                )
                if data:
                    results[f"{period}_{interval}"] = data
            except Exception as e:
                logger.error(f"Error fetching {period}/{interval} data for {ticker}: {e}")

        return results

    def discover_active_stocks_by_volume(self, min_volume: int = 1000000, limit: int = 100) -> List[str]:
        """
        Discover actively traded stocks dynamically based on volume

        Args:
            min_volume: Minimum volume threshold
            limit: Maximum number of stocks to return

        Returns:
            List of ticker symbols
        """
        active_tickers = []

        try:
            # Use enhanced screener for volume-based discovery
            logger.info(f"Discovering active stocks with volume > {min_volume}")

            # Get high volume stocks from screener
            high_volume = self.screener.get_high_volume_stocks(limit=limit * 2)

            # Filter by minimum volume
            for stock in high_volume:
                if stock.get('volume', 0) >= min_volume:
                    active_tickers.append(stock['ticker'])

                if len(active_tickers) >= limit:
                    break

            # If we need more, try market movers
            if len(active_tickers) < limit:
                movers = self.screener.get_market_movers()
                for category in ['most_active', 'gainers', 'losers']:
                    for stock in movers.get(category, []):
                        ticker = stock.get('ticker')
                        if ticker and ticker not in active_tickers:
                            active_tickers.append(ticker)

                        if len(active_tickers) >= limit:
                            break

            logger.info(f"Discovered {len(active_tickers)} active stocks dynamically")

        except Exception as e:
            logger.error(f"Error discovering active stocks: {e}")

        return active_tickers[:limit]

    def scan_market_for_opportunities(self,
                                     rsi_oversold: float = 30,
                                     rsi_overbought: float = 70,
                                     volume_surge: float = 2.0) -> Dict[str, List[Dict]]:
        """
        Scan market for trading opportunities based on technical conditions

        Args:
            rsi_oversold: RSI level for oversold condition
            rsi_overbought: RSI level for overbought condition
            volume_surge: Volume multiplier for unusual volume

        Returns:
            Dictionary with categorized opportunities
        """
        opportunities = {
            'oversold': [],
            'overbought': [],
            'breakout': [],
            'volume_surge': [],
            'momentum': []
        }

        try:
            # Get active stocks to scan
            active_stocks = self.discover_active_stocks_by_volume(limit=50)

            logger.info(f"Scanning {len(active_stocks)} stocks for opportunities")

            for ticker in active_stocks[:30]:  # Limit for performance
                try:
                    # Get technical data
                    data = self.get_historical_data_with_indicators(
                        ticker=ticker,
                        period="1mo",
                        interval="1d"
                    )

                    if not data or not data.indicators:
                        continue

                    indicators = data.indicators
                    stock_info = {
                        'ticker': ticker,
                        'rsi': indicators.rsi,
                        'relative_volume': indicators.relative_volume
                    }

                    # Check for oversold
                    if indicators.rsi and indicators.rsi < rsi_oversold:
                        opportunities['oversold'].append(stock_info)

                    # Check for overbought
                    if indicators.rsi and indicators.rsi > rsi_overbought:
                        opportunities['overbought'].append(stock_info)

                    # Check for volume surge
                    if indicators.relative_volume and indicators.relative_volume > volume_surge:
                        opportunities['volume_surge'].append(stock_info)

                    # Check for momentum (MACD bullish crossover)
                    if indicators.macd and indicators.macd_signal:
                        if indicators.macd > indicators.macd_signal:
                            opportunities['momentum'].append(stock_info)

                    # Check for breakout (price above upper Bollinger Band)
                    if data.data:
                        latest = data.data[-1]
                        if 'Close' in latest and 'BB_Upper' in latest:
                            if latest['Close'] > latest['BB_Upper']:
                                opportunities['breakout'].append(stock_info)

                except Exception as e:
                    logger.debug(f"Error scanning {ticker}: {e}")
                    continue

            logger.info(f"Found {sum(len(v) for v in opportunities.values())} total opportunities")

        except Exception as e:
            logger.error(f"Error scanning market: {e}")

        return opportunities

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'session'):
            self.session.close()