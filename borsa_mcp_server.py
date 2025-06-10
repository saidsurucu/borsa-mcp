"""
Main FastMCP server file for the Borsa Istanbul (BIST) data service.
This version uses KAP for company search and yfinance for all financial data.
"""
import logging
import os
from pydantic import Field
from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from borsa_client import BorsaApiClient
from borsa_models import (
    SirketAramaSonucu, FinansalVeriSonucu, YFinancePeriodEnum,
    SirketProfiliSonucu, FinansalTabloSonucu
)

# --- Logging Configuration ---
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, "borsa_mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

app = FastMCP(
    name="BorsaMCP",
    instructions="An MCP server for Borsa Istanbul (BIST) data. Provides tools to search for companies (from KAP) and fetch historical financial data and statements (from Yahoo Finance).",
    dependencies=["httpx", "pdfplumber", "yfinance", "pandas"]
)

borsa_client = BorsaApiClient()

# Define a Literal type for yfinance periods to ensure clean schema generation
YFinancePeriodLiteral = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"]
StatementPeriodLiteral = Literal["annual", "quarterly"]

@app.tool()
async def find_ticker_code(
    sirket_adi_veya_kodu: str = Field(..., description="Enter the company's name or code to find its official BIST ticker.")
) -> SirketAramaSonucu:
    """Searches for a company on Borsa Istanbul (BIST) to find its official ticker code."""
    logger.info(f"Tool 'find_ticker_code' called with query: '{sirket_adi_veya_kodu}'")
    if not sirket_adi_veya_kodu or len(sirket_adi_veya_kodu) < 2:
        raise ToolError("You must enter at least 2 characters to search.")
    try:
        return await borsa_client.search_companies_from_kap(sirket_adi_veya_kodu)
    except Exception as e:
        logger.exception(f"Error in tool 'find_ticker_code' for query '{sirket_adi_veya_kodu}'.")
        return SirketAramaSonucu(arama_terimi=sirket_adi_veya_kodu, sonuclar=[], sonuc_sayisi=0, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_sirket_profili(
    ticker_kodu: str = Field(..., description="The stock ticker of the company. E.g., 'GARAN', 'TUPRS'.")
) -> SirketProfiliSonucu:
    """Fetches general company profile information from Yahoo Finance."""
    logger.info(f"Tool 'get_sirket_profili' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_sirket_bilgileri_yfinance(ticker_kodu)
        if data.get("error"):
            return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=None, error_message=data["error"])
        return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=data.get("bilgiler"))
    except Exception as e:
        logger.exception(f"Error in tool 'get_sirket_profili' for ticker {ticker_kodu}.")
        return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=None, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_bilanco(
    ticker_kodu: str = Field(..., description="The stock ticker of the company. E.g., 'GARAN'."),
    periyot: StatementPeriodLiteral = Field("annual", description="The period type for the statement: 'annual' or 'quarterly'.")
) -> FinansalTabloSonucu:
    """Fetches the balance sheet for a specific company from Yahoo Finance."""
    logger.info(f"Tool 'get_bilanco' called for ticker: '{ticker_kodu}', period: {periyot}")
    try:
        data = await borsa_client.get_bilanco_yfinance(ticker_kodu, periyot)
        if data.get("error"):
            return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=data["error"])
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=data.get("tablo", []))
    except Exception as e:
        logger.exception(f"Error in tool 'get_bilanco' for ticker {ticker_kodu}.")
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_kar_zarar_tablosu(
    ticker_kodu: str = Field(..., description="The stock ticker of the company. E.g., 'GARAN'."),
    periyot: StatementPeriodLiteral = Field("annual", description="The period type for the statement: 'annual' or 'quarterly'.")
) -> FinansalTabloSonucu:
    """Fetches the income statement (Profit/Loss) for a specific company from Yahoo Finance."""
    logger.info(f"Tool 'get_kar_zarar_tablosu' called for ticker: '{ticker_kodu}', period: {periyot}")
    try:
        data = await borsa_client.get_kar_zarar_yfinance(ticker_kodu, periyot)
        if data.get("error"):
            return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=data["error"])
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=data.get("tablo", []))
    except Exception as e:
        logger.exception(f"Error in tool 'get_kar_zarar_tablosu' for ticker {ticker_kodu}.")
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_finansal_veri(
    ticker_kodu: str = Field(..., description="The stock code of the company. E.g., 'GARAN', 'TUPRS'."),
    zaman_araligi: YFinancePeriodLiteral = Field("1mo", description="The time range for the historical data. Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max.")
) -> FinansalVeriSonucu:
    """
    Fetches historical Open, High, Low, Close, Volume (OHLCV) data for a given stock ticker
    from Yahoo Finance.
    """
    logger.info(f"Tool 'get_finansal_veri' called for ticker: '{ticker_kodu}', period: {zaman_araligi}")
    try:
        zaman_araligi_enum = YFinancePeriodEnum(zaman_araligi)
        data = await borsa_client.get_finansal_veri(ticker_kodu, zaman_araligi_enum)
        if data.get("error"):
            return FinansalVeriSonucu(ticker_kodu=ticker_kodu, zaman_araligi=zaman_araligi_enum, veri_noktalari=[], error_message=data["error"])
        
        return FinansalVeriSonucu(
            ticker_kodu=ticker_kodu,
            zaman_araligi=zaman_araligi_enum,
            veri_noktalari=data.get("veri_noktalari", [])
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_finansal_veri' for ticker {ticker_kodu}.")
        return FinansalVeriSonucu(ticker_kodu=ticker_kodu, zaman_araligi=YFinancePeriodEnum(zaman_araligi), veri_noktalari=[], error_message=f"An unexpected error occurred: {str(e)}")

def main():
    """Main function to run the server."""
    logger.info(f"Starting {app.name} server...")
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info(f"{app.name} server shut down by user.")
    except Exception as e:
        logger.exception(f"{app.name} server crashed.")

if __name__ == "__main__":
    main()
