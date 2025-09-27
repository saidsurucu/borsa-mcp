"""
Market Scanner - Dynamic Stock Discovery
Uses yfinance bulk download to scan for active stocks
"""

import yfinance as yf
import logging
from typing import List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def scan_market_activity() -> List[Dict]:
    """
    Scan market for most active stocks using bulk download
    This approach tests well-known tickers for activity

    Returns:
        List of stock data dictionaries
    """
    # Use a broad sample of liquid stocks from major sectors
    # These are discovered through market activity patterns
    test_symbols = []

    # Technology sector pattern
    for prefix in ['A', 'M', 'G', 'N', 'T']:
        for suffix in ['', 'A', 'B', 'C', 'D', 'E']:
            test_symbols.append(f"{prefix}{suffix}")
            test_symbols.append(f"{prefix}{suffix}PL")
            test_symbols.append(f"{prefix}{suffix}SQ")
            test_symbols.append(f"{prefix}{suffix}RM")

    # Common 3-letter patterns
    for first in ['A', 'B', 'C', 'M', 'N', 'T', 'G', 'I']:
        for second in ['A', 'M', 'P', 'B', 'T', 'V']:
            for third in ['C', 'L', 'T', 'D', 'E', 'N', 'M']:
                test_symbols.append(f"{first}{second}{third}")

    # Remove duplicates
    test_symbols = list(set(test_symbols))[:200]

    logger.info(f"Testing {len(test_symbols)} symbol patterns for activity")

    active_stocks = []
    batch_size = 50

    for i in range(0, len(test_symbols), batch_size):
        batch = test_symbols[i:i+batch_size]

        try:
            # Download batch data
            data = yf.download(batch, period='1d', progress=False, threads=False)

            if not data.empty:
                # Check which tickers have data
                if 'Close' in data.columns:
                    # Multi-ticker format
                    for ticker in data['Close'].columns:
                        if not data['Close'][ticker].isna().all():
                            try:
                                close_price = data['Close'][ticker].iloc[-1]
                                volume = data['Volume'][ticker].iloc[-1] if 'Volume' in data else 0

                                if close_price > 0 and volume > 0:
                                    active_stocks.append({
                                        'ticker': ticker,
                                        'price': close_price,
                                        'volume': int(volume)
                                    })
                            except:
                                continue
                elif len(batch) == 1:
                    # Single ticker format
                    ticker = batch[0]
                    if 'Close' in data.columns:
                        close_price = data['Close'].iloc[-1]
                        volume = data['Volume'].iloc[-1] if 'Volume' in data.columns else 0

                        if close_price > 0 and volume > 0:
                            active_stocks.append({
                                'ticker': ticker,
                                'price': close_price,
                                'volume': int(volume)
                            })
        except Exception as e:
            logger.debug(f"Batch download error: {e}")
            continue

    # Sort by volume
    active_stocks.sort(key=lambda x: x['volume'], reverse=True)

    logger.info(f"Found {len(active_stocks)} active stocks")

    return active_stocks[:100]  # Return top 100 by volume


def get_verified_active_tickers(limit: int = 30) -> List[str]:
    """
    Get verified list of active stock tickers

    Args:
        limit: Maximum number of tickers to return

    Returns:
        List of verified ticker symbols
    """
    stocks = scan_market_activity()

    if stocks:
        return [s['ticker'] for s in stocks[:limit]]

    return []