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
    def optimize_list_data(data_list: List[Dict[str, Any]], max_items: int = 50, 
                          sort_key: str = None, sort_reverse: bool = True) -> List[Dict[str, Any]]:
        """
        Optimize list data by limiting items and sorting by relevance.
        
        Args:
            data_list: List of data items
            max_items: Maximum number of items to return
            sort_key: Key to sort by (optional)
            sort_reverse: Sort in reverse order (default: True)
            
        Returns:
            List[Dict]: Optimized list
        """
        if not data_list or len(data_list) <= max_items:
            return data_list
        
        try:
            # Sort if sort_key is provided
            if sort_key:
                sorted_list = sorted(data_list, 
                                   key=lambda x: x.get(sort_key, 0) if isinstance(x.get(sort_key), (int, float)) else 0,
                                   reverse=sort_reverse)
            else:
                sorted_list = data_list
            
            # Limit to max_items
            optimized_list = sorted_list[:max_items]
            
            logger.info(f"Optimized list data: {len(data_list)} -> {len(optimized_list)} items")
            return optimized_list
            
        except Exception as e:
            logger.error(f"Error optimizing list data: {e}")
            return data_list[:max_items]  # Fallback to simple truncation
    
    @staticmethod
    def optimize_crypto_exchange_info(trading_pairs: List[Dict[str, Any]], 
                                     currencies: List[Dict[str, Any]]) -> tuple:
        """
        Optimize crypto exchange info by filtering popular pairs and currencies.
        
        Args:
            trading_pairs: List of trading pairs
            currencies: List of currencies
            
        Returns:
            tuple: (optimized_pairs, optimized_currencies)
        """
        try:
            # Priority currencies (TRY, USDT, USD, EUR, BTC, ETH)
            priority_currencies = {'TRY', 'USDT', 'USD', 'EUR', 'BTC', 'ETH'}
            
            # Filter priority currencies first
            priority_curr_list = [c for c in currencies 
                                if c.get('symbol', '').upper() in priority_currencies]
            
            # Add remaining currencies up to limit
            remaining_currencies = [c for c in currencies 
                                  if c.get('symbol', '').upper() not in priority_currencies]
            
            max_currencies = 30
            optimized_currencies = priority_curr_list + remaining_currencies[:max_currencies-len(priority_curr_list)]
            
            # Filter trading pairs for popular combinations
            popular_pairs = []
            other_pairs = []
            
            for pair in trading_pairs:
                pair_symbol = pair.get('symbol', '').upper()
                
                # Priority pairs (TRY, USDT markets)
                if ('TRY' in pair_symbol or 'USDT' in pair_symbol or 
                    'BTC' in pair_symbol or 'ETH' in pair_symbol):
                    popular_pairs.append(pair)
                else:
                    other_pairs.append(pair)
            
            # Limit popular pairs and add others
            max_pairs = 100
            optimized_pairs = popular_pairs[:max_pairs//2] + other_pairs[:max_pairs//2]
            
            logger.info(f"Optimized crypto exchange info: {len(trading_pairs)} -> {len(optimized_pairs)} pairs, "
                       f"{len(currencies)} -> {len(optimized_currencies)} currencies")
            
            return optimized_pairs, optimized_currencies
            
        except Exception as e:
            logger.error(f"Error optimizing crypto exchange info: {e}")
            return trading_pairs[:100], currencies[:30]  # Fallback limits
    
    @staticmethod
    def optimize_fund_search_results(funds: List[Dict[str, Any]], max_funds: int = 20) -> List[Dict[str, Any]]:
        """
        Optimize fund search results by sorting by performance and limiting results.
        
        Args:
            funds: List of fund data
            max_funds: Maximum number of funds to return
            
        Returns:
            List[Dict]: Optimized fund list
        """
        if not funds or len(funds) <= max_funds:
            return funds
        
        try:
            # Sort by 1-year performance (getiri_1_yil) if available
            def get_performance_key(fund):
                perf = fund.get('getiri_1_yil') or fund.get('getiri_1_y') or 0
                return float(perf) if isinstance(perf, (int, float, str)) and str(perf).replace('.', '').replace('-', '').isdigit() else 0
            
            sorted_funds = sorted(funds, key=get_performance_key, reverse=True)
            optimized_funds = sorted_funds[:max_funds]
            
            logger.info(f"Optimized fund search: {len(funds)} -> {len(optimized_funds)} funds")
            return optimized_funds
            
        except Exception as e:
            logger.error(f"Error optimizing fund search results: {e}")
            return funds[:max_funds]  # Fallback to simple truncation
    
    @staticmethod
    def optimize_news_data(news_items: List[Dict[str, Any]], max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Optimize news data by limiting items and truncating long titles.
        
        Args:
            news_items: List of news items
            max_items: Maximum number of news items
            
        Returns:
            List[Dict]: Optimized news list
        """
        if not news_items or len(news_items) <= max_items:
            return news_items
        
        try:
            # Limit news items
            limited_news = news_items[:max_items]
            
            # Truncate long titles
            MAX_TITLE_LENGTH = 100
            for item in limited_news:
                if 'baslik' in item and len(item['baslik']) > MAX_TITLE_LENGTH:
                    item['baslik'] = item['baslik'][:MAX_TITLE_LENGTH] + '...'
                if 'title' in item and len(item['title']) > MAX_TITLE_LENGTH:
                    item['title'] = item['title'][:MAX_TITLE_LENGTH] + '...'
            
            logger.info(f"Optimized news data: {len(news_items)} -> {len(limited_news)} items")
            return limited_news
            
        except Exception as e:
            logger.error(f"Error optimizing news data: {e}")
            return news_items[:max_items]
    
    @staticmethod
    def optimize_trade_data(trades: List[Dict[str, Any]], max_trades: int = 50) -> List[Dict[str, Any]]:
        """
        Optimize trade data by limiting to most recent trades.
        
        Args:
            trades: List of trade data
            max_trades: Maximum number of trades
            
        Returns:
            List[Dict]: Optimized trade list
        """
        if not trades or len(trades) <= max_trades:
            return trades
        
        try:
            # Sort by timestamp/date (most recent first)
            def get_timestamp_key(trade):
                return (trade.get('timestamp') or trade.get('tarih') or 
                       trade.get('date') or trade.get('time') or 0)
            
            sorted_trades = sorted(trades, key=get_timestamp_key, reverse=True)
            optimized_trades = sorted_trades[:max_trades]
            
            logger.info(f"Optimized trade data: {len(trades)} -> {len(optimized_trades)} trades")
            return optimized_trades
            
        except Exception as e:
            logger.error(f"Error optimizing trade data: {e}")
            return trades[:max_trades]
    
    @staticmethod
    def apply_compact_format(data: Any, format_type: str = "full") -> Any:
        """
        Apply compact JSON format if requested.
        
        Args:
            data: The data structure to potentially compact
            format_type: "full" or "compact"
            
        Returns:
            Compacted data if format_type is "compact", otherwise original data
        """
        if format_type == "compact":
            try:
                from compact_json_optimizer import CompactJSONOptimizer
                return CompactJSONOptimizer.apply_compact_optimizations(data)
            except ImportError:
                logger.warning("CompactJSONOptimizer not available, returning original data")
                return data
        
        return data
    
