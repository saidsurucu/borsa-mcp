"""
Compact JSON Optimizer
Reduces JSON response size by removing null values, shortening field names, and optimizing data structures.
"""

from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)

class CompactJSONOptimizer:
    """
    Optimizes JSON responses for token efficiency by removing redundant data and shortening field names.
    """
    
    # Field name mappings for compact format
    FIELD_MAPPING = {
        # Common fields
        "ticker_kodu": "ticker",
        "sirket_adi": "name",
        "error_message": "error",
        "sonuc_sayisi": "count",
        "sonuclar": "results",
        "toplam_haber": "total",
        "kaynak_url": "source",
        "arama_terimi": "search_term",
        
        # Financial data
        "zaman_araligi": "period",
        "veri_noktalari": "data_points",
        "acilis": "open",
        "kapanis": "close",
        "en_yuksek": "high",
        "en_dusuk": "low",
        "hacim": "volume",
        "tarih": "date",
        
        # Company info
        "longBusinessSummary": "biz_summary",
        "fullTimeEmployees": "employees",
        "marketCap": "market_cap",
        "fiftyTwoWeekLow": "low_52w",
        "fiftyTwoWeekHigh": "high_52w",
        
        # Participation finance
        "uygun_olmayan_faaliyet": "non_comp_act",
        "uygun_olmayan_imtiyaz": "non_comp_priv",
        "destekleme_eylemi": "support_act",
        "dogrudan_uygun_olmayan_faaliyet": "direct_non_comp",
        "uygun_olmayan_gelir_orani": "non_comp_inc",
        "uygun_olmayan_varlik_orani": "non_comp_asset",
        "uygun_olmayan_borc_orani": "non_comp_debt",
        
        # Index data
        "endeks_kodu": "index_code",
        "endeks_adi": "index_name",
        "sirket_sayisi": "company_count",
        "sirketler": "companies",
        
        # Fund data
        "fon_kodu": "fund_code",
        "fon_adi": "fund_name",
        "fon_turu": "fund_type",
        "kurulus": "establishment",
        "yonetici": "manager",
        "risk_degeri": "risk_level",
        "fiyat": "price",
        "tedavuldeki_pay_sayisi": "shares_outstanding",
        "toplam_deger": "total_value",
        "yatirimci_sayisi": "investor_count",
        
        # News data
        "kap_haberleri": "news",
        "baslik": "title",
        "haber_id": "news_id",
        "title_attr": "title_full",
        
        # Crypto data
        "trading_pairs": "pairs",
        "currencies": "curr",
        "symbol": "sym",
        "quote_currency": "quote",
        "base_currency": "base",
        "guncel_fiyat": "current_price",
        "degisim_yuzdesi": "change_pct",
        "degisim_miktari": "change_amt",
        "pair_symbol": "pair",
        "ohlc_data": "ohlc",
        "kline_data": "kline",
        "klines": "klines",
        "resolution": "res",
        "total_periods": "periods",
        "total_candles": "candles",
        "from_timestamp": "from",
        "to_timestamp": "to",
        "from_time": "from",
        "to_time": "to",
        "toplam_veri": "total",
        "toplam_islem": "total",
        
        # Fund data
        "fiyat_noktalari": "prices",
        "performans_noktalari": "perf",
        "baslangic_tarihi": "start",
        "bitis_tarihi": "end",
        "toplam_getiri": "total_return",
        "yillik_getiri": "annual_return",
        "en_yuksek_fiyat": "max_price",
        "en_dusuk_fiyat": "min_price",
        "volatilite": "volatility",
        "veri_nokta_sayisi": "data_count",
        "kaynak": "source"
    }
    
    # Enum value mappings for compact format
    ENUM_MAPPING = {
        "EVET": "Y",
        "HAYIR": "N",
        "Consolidated": "C",
        "Non-consolidated": "N",
        "quarterly": "Q",
        "annual": "A",
        "P1D": "1D",
        "P5D": "5D",
        "P1MO": "1M",
        "P3MO": "3M",
        "P6MO": "6M",
        "P1Y": "1Y",
        "P2Y": "2Y",
        "P5Y": "5Y",
        "P10Y": "10Y",
        "PMAX": "MAX"
    }
    
    @staticmethod
    def remove_null_values(data: Any) -> Any:
        """
        Recursively removes null/None values from dictionaries and lists.
        
        Args:
            data: The data structure to clean
            
        Returns:
            Cleaned data structure without null values
        """
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                if value is not None:
                    cleaned_value = CompactJSONOptimizer.remove_null_values(value)
                    if cleaned_value is not None:
                        cleaned[key] = cleaned_value
            return cleaned if cleaned else None
        elif isinstance(data, list):
            cleaned = []
            for item in data:
                cleaned_item = CompactJSONOptimizer.remove_null_values(item)
                if cleaned_item is not None:
                    cleaned.append(cleaned_item)
            return cleaned if cleaned else None
        else:
            return data
    
    @staticmethod
    def shorten_field_names(data: Any) -> Any:
        """
        Recursively shortens field names using the mapping dictionary.
        
        Args:
            data: The data structure to process
            
        Returns:
            Data structure with shortened field names
        """
        if isinstance(data, dict):
            shortened = {}
            for key, value in data.items():
                # Use shortened key if available, otherwise keep original
                short_key = CompactJSONOptimizer.FIELD_MAPPING.get(key, key)
                shortened_value = CompactJSONOptimizer.shorten_field_names(value)
                shortened[short_key] = shortened_value
            return shortened
        elif isinstance(data, list):
            return [CompactJSONOptimizer.shorten_field_names(item) for item in data]
        else:
            return data
    
    @staticmethod
    def shorten_enum_values(data: Any) -> Any:
        """
        Recursively shortens enum values using the mapping dictionary.
        
        Args:
            data: The data structure to process
            
        Returns:
            Data structure with shortened enum values
        """
        if isinstance(data, dict):
            shortened = {}
            for key, value in data.items():
                shortened_value = CompactJSONOptimizer.shorten_enum_values(value)
                shortened[key] = shortened_value
            return shortened
        elif isinstance(data, list):
            return [CompactJSONOptimizer.shorten_enum_values(item) for item in data]
        elif isinstance(data, str):
            # Check if this string value can be shortened
            return CompactJSONOptimizer.ENUM_MAPPING.get(data, data)
        else:
            return data
    
    @staticmethod
    def optimize_numeric_precision(data: Any) -> Any:
        """
        Optimizes numeric precision to reduce token count.
        
        Args:
            data: The data structure to process
            
        Returns:
            Data structure with optimized numeric precision
        """
        if isinstance(data, dict):
            optimized = {}
            for key, value in data.items():
                optimized_value = CompactJSONOptimizer.optimize_numeric_precision(value)
                optimized[key] = optimized_value
            return optimized
        elif isinstance(data, list):
            return [CompactJSONOptimizer.optimize_numeric_precision(item) for item in data]
        elif isinstance(data, str):
            # Try to convert string numbers to actual numbers
            try:
                if '.' in data:
                    num = float(data)
                    # Round to 2 decimal places for most financial data
                    return round(num, 2)
                else:
                    return int(data)
            except (ValueError, TypeError):
                return data
        elif isinstance(data, float):
            # Round floats to 2 decimal places
            return round(data, 2)
        else:
            return data
    
    @staticmethod
    def apply_compact_optimizations(data: Any, 
                                  remove_nulls: bool = True,
                                  shorten_fields: bool = True,
                                  shorten_enums: bool = True,
                                  optimize_numbers: bool = True,
                                  array_format: bool = False) -> Any:
        """
        Apply all compact JSON optimizations to the data.
        
        Args:
            data: The data structure to optimize
            remove_nulls: Whether to remove null values
            shorten_fields: Whether to shorten field names
            shorten_enums: Whether to shorten enum values
            optimize_numbers: Whether to optimize numeric precision
            array_format: Whether to convert OHLCV data to array format
            
        Returns:
            Optimized data structure
        """
        result = data
        
        # Apply array format optimization first (most impactful)
        if array_format:
            result = CompactJSONOptimizer.apply_array_format_optimization(result)
        
        if remove_nulls:
            result = CompactJSONOptimizer.remove_null_values(result)
        
        if shorten_fields:
            result = CompactJSONOptimizer.shorten_field_names(result)
        
        if shorten_enums:
            result = CompactJSONOptimizer.shorten_enum_values(result)
        
        if optimize_numbers:
            result = CompactJSONOptimizer.optimize_numeric_precision(result)
        
        return result
    
    @staticmethod
    def apply_array_format_optimization(data: Any) -> Any:
        """
        Apply array format optimization to OHLCV data.
        
        Args:
            data: The data structure to optimize
            
        Returns:
            Data structure with array format optimization applied
        """
        try:
            from array_format_optimizer import ArrayFormatOptimizer
            
            # Determine data type based on structure
            if isinstance(data, dict):
                # Stock/Index OHLCV data
                if 'veri_noktalari' in data:
                    return ArrayFormatOptimizer.optimize_data_to_arrays(data, "ohlcv")
                
                # Crypto OHLCV data
                elif 'ohlc_data' in data or 'klines' in data or 'kline_data' in data:
                    return ArrayFormatOptimizer.optimize_data_to_arrays(data, "crypto")
                
                # Fund performance data
                elif 'fiyat_noktalari' in data:
                    return ArrayFormatOptimizer.optimize_data_to_arrays(data, "fund")
            
            return data
            
        except ImportError:
            logger.warning("ArrayFormatOptimizer not available, skipping array format optimization")
            return data
        except Exception as e:
            logger.error(f"Error applying array format optimization: {e}")
            return data
    
    @staticmethod
    def estimate_token_savings(original_data: Any, optimized_data: Any) -> Dict[str, Any]:
        """
        Estimate token savings from optimization.
        
        Args:
            original_data: Original data structure
            optimized_data: Optimized data structure
            
        Returns:
            Dictionary with savings metrics
        """
        import json
        
        # Convert Pydantic models to dictionaries if needed
        if hasattr(original_data, 'model_dump'):
            original_data = original_data.model_dump()
        if hasattr(optimized_data, 'model_dump'):
            optimized_data = optimized_data.model_dump()
        
        # Convert to JSON strings for comparison
        original_json = json.dumps(original_data, ensure_ascii=False, default=str)
        optimized_json = json.dumps(optimized_data, ensure_ascii=False, default=str)
        
        original_size = len(original_json)
        optimized_size = len(optimized_json)
        
        # Rough token estimation (1 token ≈ 4 characters)
        original_tokens = original_size // 4
        optimized_tokens = optimized_size // 4
        
        savings_bytes = original_size - optimized_size
        savings_tokens = original_tokens - optimized_tokens
        savings_percent = (savings_bytes / original_size) * 100 if original_size > 0 else 0
        
        return {
            "original_size_bytes": original_size,
            "optimized_size_bytes": optimized_size,
            "savings_bytes": savings_bytes,
            "original_tokens_est": original_tokens,
            "optimized_tokens_est": optimized_tokens,
            "savings_tokens_est": savings_tokens,
            "savings_percent": round(savings_percent, 2)
        }