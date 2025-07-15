"""
Array Format Optimizer
Converts OHLCV data to ultra-compact array format for maximum token efficiency.
Achieves 60-70% token savings compared to object format.
"""

from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ArrayFormatOptimizer:
    """
    Optimizes OHLCV data by converting to array format for maximum token efficiency.
    
    Standard array format: [date, open, high, low, close, volume]
    """
    
    @staticmethod
    def ohlcv_to_array(ohlcv_data: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        Convert OHLCV objects to array format.
        
        Args:
            ohlcv_data: List of OHLCV dictionaries or Pydantic objects
            
        Returns:
            List of arrays in format [date, open, high, low, close, volume]
        """
        if not ohlcv_data:
            return []
        
        arrays = []
        for point in ohlcv_data:
            try:
                # Convert Pydantic model to dict if needed
                if hasattr(point, 'model_dump'):
                    point_dict = point.model_dump()
                elif hasattr(point, 'dict'):
                    point_dict = point.dict()
                else:
                    point_dict = point
                
                # Handle different field name variations
                date_val = (point_dict.get('tarih') or point_dict.get('date') or 
                           point_dict.get('timestamp') or point_dict.get('formatted_time'))
                
                # Convert datetime to string if needed
                if isinstance(date_val, datetime):
                    date_val = date_val.strftime('%Y-%m-%d')
                elif isinstance(date_val, int):
                    # Unix timestamp to date
                    date_val = datetime.fromtimestamp(date_val).strftime('%Y-%m-%d')
                
                # Get OHLCV values with fallbacks
                open_val = float(point_dict.get('acilis') or point_dict.get('open') or 0)
                high_val = float(point_dict.get('en_yuksek') or point_dict.get('high') or 0)
                low_val = float(point_dict.get('en_dusuk') or point_dict.get('low') or 0)
                close_val = float(point_dict.get('kapanis') or point_dict.get('close') or 0)
                volume_val = int(point_dict.get('hacim') or point_dict.get('volume') or 0)
                
                # Round to 2 decimal places for price data
                array_point = [
                    date_val,
                    round(open_val, 2),
                    round(high_val, 2),
                    round(low_val, 2),
                    round(close_val, 2),
                    volume_val
                ]
                arrays.append(array_point)
                
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error converting OHLCV point to array: {e}")
                continue
        
        return arrays
    
    @staticmethod
    def array_to_ohlcv(array_data: List[List[Any]], field_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Convert array format back to OHLCV objects.
        
        Args:
            array_data: List of arrays in format [date, open, high, low, close, volume]
            field_names: Optional field names to use (defaults to Turkish names)
            
        Returns:
            List of OHLCV dictionaries
        """
        if not array_data:
            return []
        
        # Default field names (Turkish)
        if field_names is None:
            field_names = ['tarih', 'acilis', 'en_yuksek', 'en_dusuk', 'kapanis', 'hacim']
        
        objects = []
        for arr in array_data:
            try:
                if len(arr) < 6:
                    logger.warning(f"Array too short, expected 6 elements: {arr}")
                    continue
                
                obj = {
                    field_names[0]: arr[0],  # date
                    field_names[1]: arr[1],  # open
                    field_names[2]: arr[2],  # high
                    field_names[3]: arr[3],  # low
                    field_names[4]: arr[4],  # close
                    field_names[5]: arr[5]   # volume
                }
                objects.append(obj)
                
            except (IndexError, TypeError) as e:
                logger.warning(f"Error converting array to OHLCV: {e}")
                continue
        
        return objects
    
    @staticmethod
    def fund_performance_to_array(fund_data: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        Convert fund performance data to array format.
        
        Args:
            fund_data: List of fund performance dictionaries or Pydantic objects
            
        Returns:
            List of arrays in format [date, price, portfolio_value, shares, investors]
        """
        if not fund_data:
            return []
        
        arrays = []
        for point in fund_data:
            try:
                # Convert Pydantic model to dict if needed
                if hasattr(point, 'model_dump'):
                    point_dict = point.model_dump()
                elif hasattr(point, 'dict'):
                    point_dict = point.dict()
                else:
                    point_dict = point
                
                # Handle different field name variations
                date_val = (point_dict.get('tarih') or point_dict.get('date') or 
                           point_dict.get('timestamp'))
                
                # Convert datetime to string if needed
                if isinstance(date_val, datetime):
                    date_val = date_val.strftime('%Y-%m-%d')
                elif isinstance(date_val, int):
                    date_val = datetime.fromtimestamp(date_val).strftime('%Y-%m-%d')
                
                # Get fund values
                price_val = float(point_dict.get('fiyat') or point_dict.get('price') or point_dict.get('nav') or 0)
                portfolio_val = float(point_dict.get('portfoy_degeri') or point_dict.get('portfolio_value') or 0)
                shares_val = int(point_dict.get('tedavuldeki_pay') or point_dict.get('shares') or 0)
                investors_val = int(point_dict.get('yatirimci_sayisi') or point_dict.get('investors') or 0)
                
                array_point = [
                    date_val,
                    round(price_val, 4),  # Fund prices need more precision
                    int(portfolio_val),
                    shares_val,
                    investors_val
                ]
                arrays.append(array_point)
                
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error converting fund point to array: {e}")
                continue
        
        return arrays
    
    @staticmethod
    def crypto_ohlcv_to_array(crypto_data: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        Convert crypto OHLCV data to array format.
        
        Args:
            crypto_data: List of crypto OHLCV dictionaries or Pydantic objects
            
        Returns:
            List of arrays in format [timestamp, open, high, low, close, volume]
        """
        if not crypto_data:
            return []
        
        arrays = []
        for point in crypto_data:
            try:
                # Convert Pydantic model to dict if needed
                if hasattr(point, 'model_dump'):
                    point_dict = point.model_dump()
                elif hasattr(point, 'dict'):
                    point_dict = point.dict()
                else:
                    point_dict = point
                
                # Handle timestamp
                timestamp_val = (point_dict.get('timestamp') or point_dict.get('time') or 
                               point_dict.get('t') or 0)
                
                # Convert datetime to timestamp if needed
                if isinstance(timestamp_val, datetime):
                    timestamp_val = int(timestamp_val.timestamp())
                
                # Get OHLCV values (crypto format)
                open_val = float(point_dict.get('open') or point_dict.get('o') or 0)
                high_val = float(point_dict.get('high') or point_dict.get('h') or 0)
                low_val = float(point_dict.get('low') or point_dict.get('l') or 0)
                close_val = float(point_dict.get('close') or point_dict.get('c') or 0)
                volume_val = float(point_dict.get('volume') or point_dict.get('v') or 0)
                
                array_point = [
                    int(timestamp_val),
                    round(open_val, 6),   # Crypto needs more precision
                    round(high_val, 6),
                    round(low_val, 6),
                    round(close_val, 6),
                    int(volume_val)
                ]
                arrays.append(array_point)
                
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error converting crypto point to array: {e}")
                continue
        
        return arrays
    
    @staticmethod
    def optimize_data_to_arrays(data: Dict[str, Any], data_type: str = "ohlcv") -> Dict[str, Any]:
        """
        Convert data objects to array format based on data type.
        
        Args:
            data: Dictionary containing data points
            data_type: Type of data ("ohlcv", "crypto", "fund")
            
        Returns:
            Dictionary with array format data
        """
        try:
            if data_type == "ohlcv":
                # Stock/index OHLCV data
                if 'veri_noktalari' in data:
                    arrays = ArrayFormatOptimizer.ohlcv_to_array(data['veri_noktalari'])
                    data['data_arrays'] = arrays
                    data['format_type'] = 'array'
                    # Keep original for backward compatibility
                    # del data['veri_noktalari']
                
            elif data_type == "crypto":
                # Crypto OHLCV data
                if 'ohlc_data' in data:
                    arrays = ArrayFormatOptimizer.crypto_ohlcv_to_array(data['ohlc_data'])
                    data['data_arrays'] = arrays
                    data['format_type'] = 'array'
                elif 'klines' in data:
                    arrays = ArrayFormatOptimizer.crypto_ohlcv_to_array(data['klines'])
                    data['data_arrays'] = arrays
                    data['format_type'] = 'array'
                elif 'kline_data' in data:
                    # Handle KriptoKlineSonucu structure
                    kline_data = data['kline_data']
                    if kline_data and isinstance(kline_data, dict):
                        # Convert BtcTurk Graph API format to standard OHLCV
                        if 't' in kline_data and 'o' in kline_data:
                            converted_data = []
                            for i in range(len(kline_data.get('t', []))):
                                converted_data.append({
                                    'timestamp': kline_data['t'][i],
                                    'open': kline_data['o'][i],
                                    'high': kline_data['h'][i],
                                    'low': kline_data['l'][i],
                                    'close': kline_data['c'][i],
                                    'volume': kline_data['v'][i]
                                })
                            arrays = ArrayFormatOptimizer.crypto_ohlcv_to_array(converted_data)
                            data['data_arrays'] = arrays
                            data['format_type'] = 'array'
                
            elif data_type == "fund":
                # Fund performance data
                if 'fiyat_noktalari' in data:
                    arrays = ArrayFormatOptimizer.fund_performance_to_array(data['fiyat_noktalari'])
                    data['data_arrays'] = arrays
                    data['format_type'] = 'array'
            
            return data
            
        except Exception as e:
            logger.error(f"Error optimizing data to arrays: {e}")
            return data
    
    @staticmethod
    def calculate_array_savings(original_data: List[Dict], array_data: List[List]) -> Dict[str, Any]:
        """
        Calculate token savings from array format conversion.
        
        Args:
            original_data: Original object format data
            array_data: Array format data
            
        Returns:
            Dictionary with savings metrics
        """
        import json
        
        try:
            original_json = json.dumps(original_data, default=str, ensure_ascii=False)
            array_json = json.dumps(array_data, default=str, ensure_ascii=False)
            
            original_size = len(original_json)
            array_size = len(array_json)
            
            # Token estimation (1 token ≈ 4 characters)
            original_tokens = original_size // 4
            array_tokens = array_size // 4
            
            savings_bytes = original_size - array_size
            savings_tokens = original_tokens - array_tokens
            savings_percent = (savings_bytes / original_size) * 100 if original_size > 0 else 0
            
            return {
                "original_size_bytes": original_size,
                "array_size_bytes": array_size,
                "savings_bytes": savings_bytes,
                "original_tokens_est": original_tokens,
                "array_tokens_est": array_tokens,
                "savings_tokens_est": savings_tokens,
                "savings_percent": round(savings_percent, 2),
                "data_points": len(array_data)
            }
            
        except Exception as e:
            logger.error(f"Error calculating array savings: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_array_format_info() -> Dict[str, Any]:
        """
        Get information about array format structure.
        
        Returns:
            Dictionary with format information
        """
        return {
            "ohlcv_format": {
                "structure": "[date, open, high, low, close, volume]",
                "types": ["string", "float", "float", "float", "float", "integer"],
                "description": "Stock/Index OHLCV data in array format"
            },
            "crypto_format": {
                "structure": "[timestamp, open, high, low, close, volume]",
                "types": ["integer", "float", "float", "float", "float", "integer"],
                "description": "Cryptocurrency OHLCV data in array format"
            },
            "fund_format": {
                "structure": "[date, price, portfolio_value, shares, investors]",
                "types": ["string", "float", "integer", "integer", "integer"],
                "description": "Fund performance data in array format"
            },
            "benefits": [
                "60-70% token savings compared to object format",
                "Faster JSON serialization/deserialization",
                "Compatible with charting libraries",
                "Reduced memory footprint"
            ]
        }