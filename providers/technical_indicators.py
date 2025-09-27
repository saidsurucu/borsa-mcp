"""
Technical Indicators Calculator for US Markets
Provides comprehensive technical analysis calculations using pandas and numpy
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for stock price data"""

    @staticmethod
    def calculate_sma(data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average

        Args:
            data: Price series
            period: Number of periods for SMA

        Returns:
            SMA series
        """
        return data.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def calculate_ema(data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average

        Args:
            data: Price series
            period: Number of periods for EMA

        Returns:
            EMA series
        """
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_bollinger_bands(data: pd.Series,
                                 period: int = 20,
                                 std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Args:
            data: Price series
            period: SMA period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Tuple of (middle_band, upper_band, lower_band)
        """
        middle_band = TechnicalIndicators.calculate_sma(data, period)
        std = data.rolling(window=period, min_periods=1).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)

        return middle_band, upper_band, lower_band

    @staticmethod
    def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI)

        Args:
            data: Price series
            period: RSI period (default 14)

        Returns:
            RSI series (0-100)
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Handle division by zero
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # Fill NaN values at the beginning
        rsi = rsi.fillna(50)

        return rsi

    @staticmethod
    def calculate_macd(data: pd.Series,
                      fast_period: int = 12,
                      slow_period: int = 26,
                      signal_period: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        Args:
            data: Price series
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        ema_fast = TechnicalIndicators.calculate_ema(data, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow_period)

        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR)

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period (default 14)

        Returns:
            ATR series
        """
        # Calculate True Range
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR
        atr = true_range.rolling(window=period, min_periods=1).mean()

        return atr

    @staticmethod
    def calculate_stochastic(high: pd.Series,
                           low: pd.Series,
                           close: pd.Series,
                           k_period: int = 14,
                           d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: %K period (default 14)
            d_period: %D period (default 3)

        Returns:
            Tuple of (%K, %D)
        """
        lowest_low = low.rolling(window=k_period, min_periods=1).min()
        highest_high = high.rolling(window=k_period, min_periods=1).max()

        # Calculate %K
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        k_percent = k_percent.fillna(50)

        # Calculate %D (SMA of %K)
        d_percent = k_percent.rolling(window=d_period, min_periods=1).mean()

        return k_percent, d_percent

    @staticmethod
    def calculate_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP)

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            volume: Volume series

        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        cumulative_tpv = (typical_price * volume).cumsum()
        cumulative_volume = volume.cumsum()

        vwap = cumulative_tpv / cumulative_volume.replace(0, np.nan)
        vwap = vwap.ffill()

        return vwap

    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV)

        Args:
            close: Close price series
            volume: Volume series

        Returns:
            OBV series
        """
        # Calculate price direction
        price_diff = close.diff()

        # Initialize OBV
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]

        # Calculate OBV
        for i in range(1, len(close)):
            if price_diff.iloc[i] > 0:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif price_diff.iloc[i] < 0:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]

        return obv

    @staticmethod
    def calculate_relative_volume(volume: pd.Series, avg_volume: float) -> pd.Series:
        """
        Calculate Relative Volume (RVOL)

        Args:
            volume: Current volume series
            avg_volume: Average volume for comparison

        Returns:
            Relative volume series
        """
        return volume / avg_volume if avg_volume > 0 else pd.Series(1, index=volume.index)

    @staticmethod
    def calculate_pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
        """
        Calculate Pivot Points (Classic)

        Args:
            high: Previous day's high
            low: Previous day's low
            close: Previous day's close

        Returns:
            Dictionary with pivot levels
        """
        pivot = (high + low + close) / 3

        r1 = 2 * pivot - low
        s1 = 2 * pivot - high

        r2 = pivot + (high - low)
        s2 = pivot - (high - low)

        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)

        return {
            'pivot': pivot,
            'r1': r1,
            'r2': r2,
            'r3': r3,
            's1': s1,
            's2': s2,
            's3': s3
        }

    @staticmethod
    def calculate_support_resistance(data: pd.Series, window: int = 20) -> Dict[str, List[float]]:
        """
        Calculate Support and Resistance levels

        Args:
            data: Price series
            window: Rolling window for finding local extrema

        Returns:
            Dictionary with support and resistance levels
        """
        # Find local maxima and minima
        rolling_max = data.rolling(window=window, center=True).max()
        rolling_min = data.rolling(window=window, center=True).min()

        # Identify peaks and troughs
        resistance_levels = []
        support_levels = []

        for i in range(len(data)):
            if data.iloc[i] == rolling_max.iloc[i]:
                resistance_levels.append(data.iloc[i])
            if data.iloc[i] == rolling_min.iloc[i]:
                support_levels.append(data.iloc[i])

        # Remove duplicates and sort
        resistance_levels = sorted(list(set(resistance_levels)), reverse=True)[:5]
        support_levels = sorted(list(set(support_levels)), reverse=True)[:5]

        return {
            'resistance': resistance_levels,
            'support': support_levels
        }

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators for a DataFrame

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all indicators added as columns
        """
        result_df = df.copy()

        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning("Missing required OHLCV columns")
            return result_df

        try:
            # Moving Averages
            result_df['SMA_20'] = TechnicalIndicators.calculate_sma(df['Close'], 20)
            result_df['SMA_50'] = TechnicalIndicators.calculate_sma(df['Close'], 50)
            result_df['SMA_200'] = TechnicalIndicators.calculate_sma(df['Close'], 200)
            result_df['EMA_12'] = TechnicalIndicators.calculate_ema(df['Close'], 12)
            result_df['EMA_26'] = TechnicalIndicators.calculate_ema(df['Close'], 26)

            # Bollinger Bands
            bb_middle, bb_upper, bb_lower = TechnicalIndicators.calculate_bollinger_bands(df['Close'])
            result_df['BB_Middle'] = bb_middle
            result_df['BB_Upper'] = bb_upper
            result_df['BB_Lower'] = bb_lower

            # RSI
            result_df['RSI'] = TechnicalIndicators.calculate_rsi(df['Close'])

            # MACD
            macd, signal, histogram = TechnicalIndicators.calculate_macd(df['Close'])
            result_df['MACD'] = macd
            result_df['MACD_Signal'] = signal
            result_df['MACD_Histogram'] = histogram

            # ATR
            result_df['ATR'] = TechnicalIndicators.calculate_atr(df['High'], df['Low'], df['Close'])

            # Stochastic
            k_percent, d_percent = TechnicalIndicators.calculate_stochastic(df['High'], df['Low'], df['Close'])
            result_df['Stoch_K'] = k_percent
            result_df['Stoch_D'] = d_percent

            # VWAP
            result_df['VWAP'] = TechnicalIndicators.calculate_vwap(df['High'], df['Low'], df['Close'], df['Volume'])

            # OBV
            result_df['OBV'] = TechnicalIndicators.calculate_obv(df['Close'], df['Volume'])

            # Relative Volume (using 20-period average)
            avg_volume = df['Volume'].rolling(window=20, min_periods=1).mean()
            result_df['RVOL'] = df['Volume'] / avg_volume.replace(0, np.nan)
            result_df['RVOL'] = result_df['RVOL'].fillna(1)

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")

        return result_df

    @staticmethod
    def get_indicator_signals(df: pd.DataFrame) -> Dict[str, str]:
        """
        Get trading signals based on technical indicators

        Args:
            df: DataFrame with calculated indicators

        Returns:
            Dictionary with signal interpretations
        """
        signals = {}

        try:
            latest = df.iloc[-1] if not df.empty else None

            if latest is not None:
                # RSI Signal
                if 'RSI' in df.columns:
                    rsi = latest['RSI']
                    if rsi > 70:
                        signals['RSI'] = 'Overbought'
                    elif rsi < 30:
                        signals['RSI'] = 'Oversold'
                    else:
                        signals['RSI'] = 'Neutral'

                # MACD Signal
                if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
                    if latest['MACD'] > latest['MACD_Signal']:
                        signals['MACD'] = 'Bullish'
                    else:
                        signals['MACD'] = 'Bearish'

                # Bollinger Bands Signal
                if all(col in df.columns for col in ['BB_Upper', 'BB_Lower', 'Close']):
                    close = latest['Close']
                    if close > latest['BB_Upper']:
                        signals['Bollinger_Bands'] = 'Overbought'
                    elif close < latest['BB_Lower']:
                        signals['Bollinger_Bands'] = 'Oversold'
                    else:
                        signals['Bollinger_Bands'] = 'Neutral'

                # Stochastic Signal
                if 'Stoch_K' in df.columns and 'Stoch_D' in df.columns:
                    k = latest['Stoch_K']
                    if k > 80:
                        signals['Stochastic'] = 'Overbought'
                    elif k < 20:
                        signals['Stochastic'] = 'Oversold'
                    else:
                        signals['Stochastic'] = 'Neutral'

                # Moving Average Signal
                if 'SMA_50' in df.columns and 'SMA_200' in df.columns:
                    if latest['SMA_50'] > latest['SMA_200']:
                        signals['MA_Trend'] = 'Bullish (Golden Cross)'
                    else:
                        signals['MA_Trend'] = 'Bearish (Death Cross)'

        except Exception as e:
            logger.error(f"Error generating signals: {e}")

        return signals