"""
Token Optimizer for MCP Server
Optimizes data outputs to prevent context window overflow for long time frames.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TokenOptimizer:
    """
    Optimizes financial data outputs based on time frame duration to prevent context window overflow.
    """
    
    # Token limits for different contexts
    MAX_TOKENS_PER_RESPONSE = 8000  # Conservative limit for LLM context
    TOKENS_PER_DATA_POINT = 50      # Estimated tokens per OHLC data point
    
    # Adaptive sampling thresholds (in days)
    DAILY_THRESHOLD = 30      # Up to 30 days: daily data
    WEEKLY_THRESHOLD = 180    # 30-180 days: weekly data  
    MONTHLY_THRESHOLD = 730   # 180-730 days: monthly data
    
    @staticmethod
    def should_optimize(data_points: List[Any], time_frame_days: int) -> bool:
        """
        Determine if data should be optimized based on length and time frame.
        
        Args:
            data_points: List of data points
            time_frame_days: Duration of time frame in days
            
        Returns:
            bool: True if optimization needed
        """
        estimated_tokens = len(data_points) * TokenOptimizer.TOKENS_PER_DATA_POINT
        
        # Optimize if estimated tokens exceed limit or time frame is long
        return (estimated_tokens > TokenOptimizer.MAX_TOKENS_PER_RESPONSE or 
                time_frame_days > TokenOptimizer.DAILY_THRESHOLD)
    
    @staticmethod
    def get_sampling_frequency(time_frame_days: int) -> str:
        """
        Get appropriate sampling frequency based on time frame duration.
        
        Args:
            time_frame_days: Duration in days
            
        Returns:
            str: Sampling frequency ('D', 'W', 'M')
        """
        if time_frame_days <= TokenOptimizer.DAILY_THRESHOLD:
            return 'D'  # Daily
        elif time_frame_days <= TokenOptimizer.WEEKLY_THRESHOLD:
            return 'W'  # Weekly
        elif time_frame_days <= TokenOptimizer.MONTHLY_THRESHOLD:
            return 'M'  # Monthly
        else:
            return 'Q'  # Quarterly for very long periods
    
    @staticmethod
    def optimize_ohlc_data(data_points: List[Dict[str, Any]], time_frame_days: int) -> List[Dict[str, Any]]:
        """
        Optimize OHLC data by consolidating based on time frame.
        
        Args:
            data_points: List of OHLC data points
            time_frame_days: Duration of time frame in days
            
        Returns:
            List[Dict]: Optimized data points
        """
        if not data_points or not TokenOptimizer.should_optimize(data_points, time_frame_days):
            return data_points
        
        try:
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(data_points)
            
            # Ensure we have a datetime column
            if 'tarih' in df.columns:
                df['tarih'] = pd.to_datetime(df['tarih'])
                df.set_index('tarih', inplace=True)
            elif 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            else:
                logger.warning("No date column found, returning original data")
                return data_points
            
            # Get sampling frequency
            freq = TokenOptimizer.get_sampling_frequency(time_frame_days)
            
            # Resample OHLC data
            ohlc_mapping = {
                'acilis': 'first',
                'en_yuksek': 'max',
                'en_dusuk': 'min',
                'kapanis': 'last',
                'hacim': 'sum'
            }
            
            # Handle different column names (Turkish and English)
            available_mapping = {}
            for turkish_col, agg_func in ohlc_mapping.items():
                if turkish_col in df.columns:
                    available_mapping[turkish_col] = agg_func
            
            # English column names fallback
            english_mapping = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            
            for eng_col, agg_func in english_mapping.items():
                if eng_col in df.columns:
                    available_mapping[eng_col] = agg_func
            
            if not available_mapping:
                logger.warning("No OHLC columns found, returning original data")
                return data_points
            
            # Resample data
            resampled_df = df.resample(freq).agg(available_mapping).dropna()
            
            # Convert back to list of dictionaries
            result = []
            for index, row in resampled_df.iterrows():
                data_point = {'tarih': index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index}
                for col, value in row.items():
                    if pd.notna(value):
                        data_point[col] = float(value) if isinstance(value, (int, float)) else value
                result.append(data_point)
            
            logger.info(f"Optimized {len(data_points)} data points to {len(result)} points using {freq} sampling")
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing OHLC data: {e}")
            return data_points
    
    @staticmethod
    def optimize_crypto_data(data_points: List[Dict[str, Any]], time_frame_days: int) -> List[Dict[str, Any]]:
        """
        Optimize cryptocurrency data (kline/OHLC) with crypto-specific considerations.
        
        Args:
            data_points: List of crypto data points
            time_frame_days: Duration of time frame in days
            
        Returns:
            List[Dict]: Optimized data points
        """
        if not data_points or not TokenOptimizer.should_optimize(data_points, time_frame_days):
            return data_points
        
        try:
            # Handle TradingView format {s, t, o, h, l, c, v}
            if isinstance(data_points[0], dict) and 't' in data_points[0]:
                # Convert TradingView format to standard format
                converted_data = []
                for point in data_points:
                    converted_data.append({
                        'timestamp': point.get('t'),
                        'open': point.get('o'),
                        'high': point.get('h'),
                        'low': point.get('l'),
                        'close': point.get('c'),
                        'volume': point.get('v')
                    })
                data_points = converted_data
            
            # Use standard OHLC optimization
            return TokenOptimizer.optimize_ohlc_data(data_points, time_frame_days)
            
        except Exception as e:
            logger.error(f"Error optimizing crypto data: {e}")
            return data_points
    
    @staticmethod
    def optimize_fund_performance(data_points: List[Dict[str, Any]], time_frame_days: int) -> List[Dict[str, Any]]:
        """
        Optimize fund performance data for long time frames.
        
        Args:
            data_points: List of fund performance data points
            time_frame_days: Duration of time frame in days
            
        Returns:
            List[Dict]: Optimized data points
        """
        if not data_points or not TokenOptimizer.should_optimize(data_points, time_frame_days):
            return data_points
        
        try:
            # For fund data, we might want to keep weekly/monthly sampling
            # but with different logic since it's NAV data
            df = pd.DataFrame(data_points)
            
            # Find date column
            date_col = None
            for col in ['tarih', 'date', 'timestamp']:
                if col in df.columns:
                    date_col = col
                    break
            
            if not date_col:
                logger.warning("No date column found in fund data, returning original")
                return data_points
            
            df[date_col] = pd.to_datetime(df[date_col])
            df.set_index(date_col, inplace=True)
            
            # Get sampling frequency
            freq = TokenOptimizer.get_sampling_frequency(time_frame_days)
            
            # For fund data, use last value (NAV) and sum volume if available
            agg_mapping = {}
            for col in df.columns:
                if col in ['fiyat', 'nav', 'price', 'kapanis']:
                    agg_mapping[col] = 'last'
                elif col in ['hacim', 'volume']:
                    agg_mapping[col] = 'sum'
                else:
                    agg_mapping[col] = 'last'  # Default to last value
            
            # Resample
            resampled_df = df.resample(freq).agg(agg_mapping).dropna()
            
            # Convert back to list
            result = []
            for index, row in resampled_df.iterrows():
                data_point = {date_col: index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index}
                for col, value in row.items():
                    if pd.notna(value):
                        data_point[col] = float(value) if isinstance(value, (int, float)) else value
                result.append(data_point)
            
            logger.info(f"Optimized fund data: {len(data_points)} -> {len(result)} points using {freq} sampling")
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing fund performance data: {e}")
            return data_points
    
    @staticmethod
    def calculate_time_frame_days(start_date: str, end_date: str) -> int:
        """
        Calculate number of days between two dates.
        
        Args:
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            
        Returns:
            int: Number of days
        """
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            return (end_dt - start_dt).days
        except Exception as e:
            logger.error(f"Error calculating time frame: {e}")
            return 30  # Default to 30 days
    
    @staticmethod
    def add_optimization_metadata(result: Dict[str, Any], original_count: int, optimized_count: int, 
                                 time_frame_days: int) -> Dict[str, Any]:
        """
        Add optimization metadata to result.
        
        Args:
            result: Original result dictionary
            original_count: Original data point count
            optimized_count: Optimized data point count
            time_frame_days: Time frame duration
            
        Returns:
            Dict: Result with optimization metadata
        """
        if 'optimizasyon_bilgisi' not in result:
            result['optimizasyon_bilgisi'] = {}
        
        result['optimizasyon_bilgisi'].update({
            'optimizasyon_yapildi': original_count != optimized_count,
            'orijinal_veri_sayisi': original_count,
            'optimize_veri_sayisi': optimized_count,
            'zaman_araligi_gun': time_frame_days,
            'ornekleme_frekansi': TokenOptimizer.get_sampling_frequency(time_frame_days),
            'token_tasarrufu_yuzdesi': round(((original_count - optimized_count) / original_count) * 100, 1) if original_count > 0 else 0
        })
        
        return result