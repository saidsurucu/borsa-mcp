"""
Main FastMCP server file for the Borsa Istanbul (BIST) data service.
This version uses KAP for company search and yfinance for all financial data.
"""
import logging
import os
from pydantic import Field
from typing import Literal, List, Dict, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from borsa_client import BorsaApiClient
from borsa_models import (
    SirketAramaSonucu, FinansalVeriSonucu, YFinancePeriodEnum,
    SirketProfiliSonucu, FinansalTabloSonucu, AnalistVerileriSonucu,
    TemettuVeAksiyonlarSonucu, HizliBilgiSonucu, KazancTakvimSonucu,
    TeknikAnalizSonucu, SektorKarsilastirmaSonucu, KapHaberleriSonucu,
    KapHaberDetayi, KapHaberSayfasi, KatilimFinansUygunlukSonucu, EndeksAramaSonucu,
    EndeksSirketleriSonucu, EndeksKoduAramaSonucu, FonAramaSonucu, FonDetayBilgisi,
    FonPerformansSonucu, FonPortfoySonucu, FonKarsilastirmaSonucu, FonTaramaKriterleri,
    FonTaramaSonucu, FonMevzuatSonucu
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
logging.getLogger("yfinance").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
# --- End Logging Configuration ---

app = FastMCP(
    name="BorsaMCP",
    instructions="An MCP server for Borsa Istanbul (BIST) and TEFAS mutual fund data. Provides tools to search for companies (from KAP), fetch historical financial data and statements (from Yahoo Finance), and analyze Turkish mutual funds (from TEFAS).",
    dependencies=["httpx", "pdfplumber", "yfinance", "pandas", "beautifulsoup4", "lxml", "requests"]
)

borsa_client = BorsaApiClient()

# Define Literal types for yfinance periods to ensure clean schema generation
YFinancePeriodLiteral = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"]
StatementPeriodLiteral = Literal["annual", "quarterly"]

@app.tool()
async def find_ticker_code(
    sirket_adi_veya_kodu: str = Field(..., description="Enter the company's name or code to find its official BIST ticker. You can search using: company name (e.g., 'Garanti'), partial name (e.g., 'Aselsan'), or existing ticker (e.g., 'GARAN'). Search is case-insensitive and supports Turkish characters.")
) -> SirketAramaSonucu:
    """
    Searches for companies listed on Borsa Istanbul (BIST) to find their official ticker codes.
    
    This tool searches through all 793 companies currently listed on BIST using data from KAP (Public Disclosure Platform).
    It performs fuzzy matching on company names and exact matching on ticker codes.
    
    Use cases:
    - Find the ticker code for a Turkish company you want to analyze
    - Verify the correct spelling or official name of a BIST company
    - Discover companies in a specific city or with similar names
    - Get the complete list of companies matching your search criteria
    
    Returns detailed information including:
    - Official company name (in Turkish)
    - BIST ticker code (e.g., GARAN, ASELS, TUPRS)
    - Registered city location
    - Total number of matching results
    
    Examples:
    - Search 'garanti' → Returns GARAN (T. GARANTİ BANKASI A.Ş.)
    - Search 'aselsan' → Returns ASELS (ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.)
    - Search 'istanbul' → Returns all companies with 'Istanbul' in their name
    """
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
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'ASELS', 'THYAO' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include the '.IS' suffix - it will be added automatically for Turkish stocks and indices."),
    mynet_detaylari: bool = Field(False, description="Include detailed Turkish-specific company information from Mynet Finans (management, shareholders, subsidiaries, currency position). Default is False for faster response.")
) -> SirketProfiliSonucu:
    """
    Fetches comprehensive company profile and fundamental information with optional Turkish-specific details.
    
    **Standard Mode (mynet_detaylari=False):**
    Uses Yahoo Finance for international financial data including business description, industry classification,
    market metrics, and key financial ratios. Perfect for getting fundamental analysis data.
    
    **Enhanced Mode (mynet_detaylari=True):**
    Combines Yahoo Finance data with detailed Turkish-specific information from Mynet Finans including
    management structure, shareholder composition, subsidiaries, and currency positions.
    
    **Yahoo Finance Data (Always Included):**
    
    **Basic Information:**
    - Company full name and ticker symbol
    - Business sector and industry classification
    - Number of full-time employees
    - Headquarters city and country
    - Official website URL
    
    **Market Data:**
    - Current market capitalization
    - 52-week price range (high/low)
    - Beta coefficient (volatility vs market)
    - Currency of trading
    
    **Valuation Metrics:**
    - Trailing P/E ratio (price-to-earnings)
    - Forward P/E ratio (based on estimates)
    - Dividend yield percentage
    
    **Business Description:**
    - Detailed business summary explaining company operations
    - Core business activities and revenue sources
    - Market position and competitive advantages
    
    **Mynet Finans Data (When mynet_detaylari=True):**
    
    **Corporate Governance:**
    - Board of directors (Yönetim Kurulu) member names
    - General manager information
    - Establishment and IPO dates
    - Employee count details
    
    **Ownership Structure:**
    - Shareholders list with capital amounts and percentages
    - Detailed ownership breakdown
    - Corporate investor information
    
    **Corporate Structure:**
    - Subsidiaries and affiliates with capital and ownership percentages
    - Investment portfolio details
    - Group company relationships
    
    **Financial Position (For Banks/Financial Institutions):**
    - Foreign currency assets (TL equivalent)
    - Foreign currency liabilities (TL equivalent)
    - Net foreign currency position
    - Derivative instruments net position
    
    **Use Cases:**
    - **Standard Mode**: Quick fundamental analysis and screening
    - **Enhanced Mode**: Deep due diligence and corporate governance analysis
    - Investment committee reports requiring detailed company structure
    - Regulatory compliance and know-your-customer (KYC) processes
    - Merger & acquisition analysis
    - Risk assessment for corporate banking
    
    **Performance Considerations:**
    - Standard mode: Fast response (~1-2 seconds)
    - Enhanced mode: Slower response (~3-5 seconds) due to web scraping
    - Enhanced mode may occasionally timeout for some companies
    
    **Data Quality Notes:**
    - Yahoo Finance: Better for large-cap, liquid BIST stocks
    - Mynet Finans: More complete for Turkish regulatory information
    - Combined approach provides most comprehensive company analysis
    """
    logger.info(f"Tool 'get_sirket_profili' called for ticker: '{ticker_kodu}', mynet_detaylari: {mynet_detaylari}")
    try:
        if mynet_detaylari:
            # Use hybrid approach for comprehensive data
            data = await borsa_client.get_sirket_bilgileri_hibrit(ticker_kodu)
            if data.get("error"):
                return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=None, error_message=data["error"])
            
            # Return hybrid result structure
            return SirketProfiliSonucu(
                ticker_kodu=ticker_kodu, 
                bilgiler=data.get("yahoo_data", {}).get("bilgiler"),
                mynet_bilgileri=data.get("mynet_data", {}).get("bilgiler"),
                veri_kalitesi=data.get("veri_kalitesi"),
                kaynak="hibrit"
            )
        else:
            # Standard Yahoo Finance only approach
            data = await borsa_client.get_sirket_bilgileri_yfinance(ticker_kodu)
            if data.get("error"):
                return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=None, error_message=data["error"])
            return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=data.get("bilgiler"), kaynak="yahoo")
            
    except Exception as e:
        logger.exception(f"Error in tool 'get_sirket_profili' for ticker {ticker_kodu}.")
        return SirketProfiliSonucu(ticker_kodu=ticker_kodu, bilgiler=None, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_bilanco(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'AKBNK', 'ASELS' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix."),
    periyot: StatementPeriodLiteral = Field("annual", description="Choose 'annual' for yearly statements or 'quarterly' for quarterly statements. Annual data provides longer-term trends, while quarterly shows more recent performance.")
) -> FinansalTabloSonucu:
    """
    Fetches the balance sheet (bilanço) for a Turkish company from Yahoo Finance.
    
    The balance sheet provides a snapshot of the company's financial position at a specific point in time,
    showing assets, liabilities, and shareholders' equity. This is fundamental for assessing financial health,
    liquidity, and capital structure.
    
    **Key Balance Sheet Components Returned:**
    
    **Assets (Aktifler):**
    - Current Assets: Cash, inventory, accounts receivable, short-term investments
    - Non-Current Assets: Property, plant & equipment, intangible assets, long-term investments
    - Total Assets: Sum of all company resources
    
    **Liabilities (Pasifler):**
    - Current Liabilities: Short-term debt, accounts payable, accrued expenses
    - Non-Current Liabilities: Long-term debt, deferred tax liabilities, pension obligations
    - Total Liabilities: All company obligations
    
    **Equity (Özsermaye):**
    - Share Capital: Paid-in capital from shareholders
    - Retained Earnings: Accumulated profits reinvested in business
    - Total Shareholders' Equity: Owners' stake in the company
    
    **Analysis Applications:**
    - **Liquidity Analysis**: Current ratio, quick ratio assessment
    - **Leverage Analysis**: Debt-to-equity, debt-to-assets ratios
    - **Asset Quality**: Asset turnover, return on assets calculations
    - **Financial Stability**: Working capital, equity ratios
    - **Growth Trends**: Compare multiple periods to see expansion
    
    **Data Coverage:**
    - Annual: Up to 4 years of yearly data
    - Quarterly: Up to 4 quarters of recent data
    - All amounts typically in Turkish Lira (TRY)
    - Dates are automatically converted to Turkish timezone
    
    **Best Practices:**
    - Compare with industry peers for context
    - Analyze trends over multiple periods
    - Cross-reference with cash flow and income statements
    - Pay attention to working capital changes
    """
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
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'TUPRS', 'THYAO' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix."),
    periyot: StatementPeriodLiteral = Field("annual", description="Choose 'annual' for yearly statements or 'quarterly' for quarterly statements. Annual shows full-year performance, quarterly reveals seasonal patterns and recent trends.")
) -> FinansalTabloSonucu:
    """
    Fetches the income statement (kar-zarar tablosu) for a Turkish company from Yahoo Finance.
    
    The income statement shows the company's financial performance over a specific period, detailing
    revenues, expenses, and profitability. This is essential for analyzing operational efficiency,
    growth trends, and earning power.
    
    **Key Income Statement Components Returned:**
    
    **Revenue Section (Gelirler):**
    - Total Revenue: Primary business income from sales/services
    - Operating Revenue: Core business activities revenue
    - Other Revenue: Non-operating income sources
    
    **Expense Section (Giderler):**
    - Cost of Revenue: Direct costs of producing goods/services
    - Operating Expenses: Selling, general & administrative costs
    - Research & Development: Innovation and product development costs
    - Interest Expense: Cost of debt financing
    - Tax Expense: Corporate income taxes
    
    **Profitability Metrics (Karlılık):**
    - Gross Profit: Revenue minus cost of goods sold
    - Operating Income: Profit from core business operations
    - EBITDA: Earnings before interest, taxes, depreciation, amortization
    - Net Income: Bottom-line profit after all expenses
    - Earnings Per Share (EPS): Net income divided by shares outstanding
    
    **Analysis Applications:**
    - **Profitability Analysis**: Gross, operating, and net profit margins
    - **Growth Analysis**: Revenue and earnings growth rates over time
    - **Efficiency Analysis**: Operating leverage and cost control
    - **Quality of Earnings**: Recurring vs one-time items assessment
    - **Comparative Analysis**: Performance vs industry peers
    
    **Key Ratios You Can Calculate:**
    - Gross Margin = Gross Profit / Revenue
    - Operating Margin = Operating Income / Revenue  
    - Net Margin = Net Income / Revenue
    - Revenue Growth = (Current Period - Prior Period) / Prior Period
    
    **Data Coverage:**
    - Annual: Up to 4 years of yearly data
    - Quarterly: Up to 4 quarters of recent data
    - Amounts typically in Turkish Lira (TRY)
    - All dates converted to Turkish timezone
    
    **Investment Insights:**
    - Track revenue growth consistency
    - Monitor margin expansion/compression
    - Identify seasonal business patterns (quarterly data)
    - Assess operational leverage and scalability
    """
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
async def get_nakit_akisi_tablosu(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'EREGL', 'BIMAS' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix."),
    periyot: StatementPeriodLiteral = Field("annual", description="Choose 'annual' for yearly cash flows or 'quarterly' for quarterly cash flows. Annual data shows longer-term cash generation patterns, quarterly reveals seasonal cash flow variations.")
) -> FinansalTabloSonucu:
    """
    Fetches the cash flow statement (nakit akışı tablosu) for a Turkish company from Yahoo Finance.
    
    The cash flow statement tracks actual cash movements in and out of the business, providing insight
    into liquidity, cash generation ability, and financial flexibility. This is crucial for assessing
    the quality of earnings and the company's ability to fund operations, investments, and dividends.
    
    **Key Cash Flow Components Returned:**
    
    **Operating Cash Flow (Faaliyet Nakit Akışı):**
    - Cash from Sales: Actual cash received from customers
    - Cash Paid to Suppliers: Cash outflows for inventory and services
    - Cash Paid to Employees: Salary and wage payments
    - Tax Payments: Actual cash taxes paid
    - Net Operating Cash Flow: Cash generated from core business operations
    
    **Investing Cash Flow (Yatırım Nakit Akışı):**
    - Capital Expenditures: Cash spent on property, plant & equipment
    - Acquisitions: Cash spent on purchasing other companies
    - Asset Sales: Cash received from selling assets
    - Investment Purchases/Sales: Cash flows from financial investments
    - Net Investing Cash Flow: Cash used for/generated from investments
    
    **Financing Cash Flow (Finansman Nakit Akışı):**
    - Debt Proceeds: Cash received from borrowing
    - Debt Repayments: Cash used to pay down debt
    - Dividends Paid: Cash distributed to shareholders
    - Share Buybacks: Cash used to repurchase company stock
    - Share Issuances: Cash received from issuing new shares
    - Net Financing Cash Flow: Cash flows from financing activities
    
    **Key Metrics (Önemli Metrikler):**
    - Free Cash Flow: Operating Cash Flow - Capital Expenditures
    - Cash Flow Margin: Operating Cash Flow / Revenue
    - Cash Conversion: How efficiently profits convert to cash
    
    **Analysis Applications:**
    - **Liquidity Assessment**: Company's ability to meet short-term obligations
    - **Quality of Earnings**: Comparing net income to operating cash flow
    - **Capital Allocation**: How management invests and finances the business
    - **Dividend Sustainability**: Whether cash flow supports dividend payments
    - **Financial Flexibility**: Ability to fund growth and handle downturns
    
    **Key Insights:**
    - Positive operating cash flow indicates healthy core business
    - Negative investing cash flow often shows growth investments
    - Financing cash flows reveal capital structure decisions
    - Free cash flow measures cash available for shareholders
    
    **Warning Signs:**
    - Operating cash flow consistently below net income
    - Heavy reliance on external financing
    - Declining free cash flow trends
    - Inability to self-fund capital expenditures
    
    **Data Coverage:**
    - Annual: Up to 4 years of yearly data
    - Quarterly: Up to 4 quarters of recent data
    - All amounts typically in Turkish Lira (TRY)
    - Dates converted to Turkish timezone
    """
    logger.info(f"Tool 'get_nakit_akisi_tablosu' called for ticker: '{ticker_kodu}', period: {periyot}")
    try:
        data = await borsa_client.get_nakit_akisi_yfinance(ticker_kodu, periyot)
        if data.get("error"):
            return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=data["error"])
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=data.get("tablo", []))
    except Exception as e:
        logger.exception(f"Error in tool 'get_nakit_akisi_tablosu' for ticker {ticker_kodu}.")
        return FinansalTabloSonucu(ticker_kodu=ticker_kodu, period_type=periyot, tablo=[], error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_finansal_veri(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'TUPRS', 'AKBNK' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix."),
    zaman_araligi: YFinancePeriodLiteral = Field("1mo", description="Time period for historical data: '1d'=1 day, '5d'=5 days, '1mo'=1 month, '3mo'=3 months, '6mo'=6 months, '1y'=1 year, '2y'=2 years, '5y'=5 years, 'ytd'=year to date, 'max'=all available data. Choose based on your analysis needs: short-term trading (1d-1mo), medium-term analysis (3mo-1y), long-term trends (2y-max).")
) -> FinansalVeriSonucu:
    """
    Fetches historical OHLCV (Open, High, Low, Close, Volume) price data for Turkish stocks and BIST indices.
    
    This tool provides comprehensive historical price and volume data essential for technical analysis,
    performance tracking, volatility assessment, and trend identification. The data is sourced from
    Yahoo Finance and automatically adjusted for stock splits and dividends. Works with both individual
    stocks and BIST indices for market-wide analysis.
    
    **Data Components Returned:**
    
    **Price Data (Fiyat Verileri):**
    - **Open (Açılış)**: Opening price for each trading session
    - **High (En Yüksek)**: Highest price reached during the session
    - **Low (En Düşük)**: Lowest price reached during the session
    - **Close (Kapanış)**: Final trading price for the session
    - **Volume (Hacim)**: Number of shares traded during the session
    
    **Timestamp Information:**
    - All dates/times in Turkish timezone (Europe/Istanbul)
    - Exact trading session timestamps
    - Excludes non-trading days (weekends, holidays)
    
    **Analysis Applications:**
    
    **Technical Analysis:**
    - Candlestick pattern identification
    - Moving averages calculation (SMA, EMA)
    - Support and resistance level detection
    - Technical indicators (RSI, MACD, Bollinger Bands)
    
    **Performance Analysis:**
    - Price return calculations over different periods
    - Volatility measurement and risk assessment
    - Drawdown analysis and recovery periods
    - Comparison with market indices (BIST100, BIST30)
    
    **Volume Analysis:**
    - Trading activity patterns and trends
    - Volume-price relationship analysis
    - Liquidity assessment
    - Institutional vs retail trading patterns
    
    **Investment Research:**
    - Historical price performance evaluation
    - Entry/exit point identification
    - Risk-return profile assessment
    - Long-term trend analysis
    
    **Time Period Recommendations:**
    - **1d-5d**: Intraday trading and short-term analysis
    - **1mo-3mo**: Short-term trend analysis and swing trading
    - **6mo-1y**: Medium-term investment analysis
    - **2y-5y**: Long-term investment and cyclical analysis
    - **max**: Complete historical perspective and major trend analysis
    
    **Data Quality Notes:**
    - Prices adjusted for splits and dividends
    - Volume data available for all major BIST stocks
    - Data quality best for liquid, large-cap stocks
    - Some smaller companies may have gaps in historical data
    
    **Common Use Cases:**
    - Calculate stock and index returns over specific periods
    - Create price charts and technical analysis for stocks and indices
    - Assess stock/index volatility and risk metrics
    - Compare performance across different time frames and markets
    - Identify seasonal patterns and trading anomalies
    - Analyze index performance vs individual stocks
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

@app.tool()
async def get_analist_tahminleri(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'TUPRS', 'ASELS' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix.")
) -> AnalistVerileriSonucu:
    """
    Fetches comprehensive analyst research data including recommendations, price targets, and trends.
    
    This tool aggregates professional analyst opinions and research from investment banks and research firms
    covering Turkish stocks. It provides valuable market sentiment indicators and professional price targets
    that can inform investment decisions.
    
    **Analyst Data Components Returned:**
    
    **Price Targets (Fiyat Hedefleri):**
    - **Current Price**: Latest stock price for comparison
    - **Average Target**: Consensus price target from all analysts
    - **High Target**: Most optimistic analyst price target
    - **Low Target**: Most conservative analyst price target
    - **Number of Analysts**: Count of analysts providing targets
    - **Upside/Downside Potential**: Implied return to average target
    
    **Recommendation Summary (Tavsiye Özeti):**
    - **Strong Buy**: Number of strong buy recommendations
    - **Buy**: Number of buy recommendations  
    - **Hold**: Number of hold recommendations
    - **Sell**: Number of sell recommendations
    - **Strong Sell**: Number of strong sell recommendations
    - **Average Rating**: Weighted average of all recommendations
    
    **Recent Analyst Actions (Son Analist Hareketleri):**
    - **Upgrades**: Recent rating improvements with details
    - **Downgrades**: Recent rating downgrades with reasons
    - **Initiations**: New coverage starts by research firms
    - **Reiterations**: Confirmations of existing ratings
    - **Analyst Firm Names**: Which firms provided recommendations
    - **Action Dates**: When recommendations were made
    
    **Recommendation Trends (Tavsiye Trendleri):**
    - **Historical Changes**: How recommendations evolved over time
    - **Consensus Shifts**: Movement in overall analyst sentiment
    - **Rating Distribution**: Breakdown of current recommendation mix
    
    **Analysis Applications:**
    
    **Investment Decision Making:**
    - Gauge professional sentiment on stock prospects
    - Compare current price to analyst price targets
    - Identify consensus vs contrarian opportunities
    - Track changes in analyst sentiment over time
    
    **Risk Assessment:**
    - High analyst coverage suggests institutional interest
    - Wide price target ranges indicate uncertainty
    - Recent downgrades may signal fundamental concerns
    - Lack of coverage might indicate limited institutional interest
    
    **Market Timing:**
    - Upgrades often precede positive price momentum
    - Downgrades may indicate potential headwinds
    - Initiation of coverage can drive institutional buying
    - Target price changes influence trading activity
    
    **Interpretation Guidelines:**
    
    **Strong Signals:**
    - Unanimous buy/sell recommendations across analysts
    - Recent major rating changes from respected firms
    - Significant price target adjustments
    - New coverage initiations with positive outlooks
    
    **Caution Indicators:**
    - Wide divergence in price targets (high uncertainty)
    - Recent downgrades from multiple firms
    - Lack of recent analyst updates (stale coverage)
    - Average ratings around "hold" (neutral sentiment)
    
    **Data Quality Notes:**
    - Coverage varies significantly by company size
    - Large-cap BIST stocks have better analyst coverage
    - International investment banks focus on major Turkish companies
    - Local Turkish research firms may cover smaller companies
    - Some recommendations may be in Turkish language
    
    **Best Practices:**
    - Consider analyst track record and firm reputation
    - Look for recent updates (within 3-6 months)
    - Compare with your own fundamental analysis
    - Consider analyst incentives and potential conflicts
    - Use as one input among many for investment decisions
    """
    logger.info(f"Tool 'get_analist_tahminleri' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_analist_verileri_yfinance(ticker_kodu)
        if data.get("error"):
            return AnalistVerileriSonucu(ticker_kodu=ticker_kodu, error_message=data["error"])
        
        return AnalistVerileriSonucu(
            ticker_kodu=ticker_kodu,
            fiyat_hedefleri=data.get("fiyat_hedefleri"),
            tavsiyeler=data.get("tavsiyeler", []),
            tavsiye_ozeti=data.get("tavsiye_ozeti"),
            tavsiye_trendi=data.get("tavsiye_trendi")
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_analist_tahminleri' for ticker {ticker_kodu}.")
        return AnalistVerileriSonucu(ticker_kodu=ticker_kodu, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_temettu_ve_aksiyonlar(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'AKBNK', 'SISE' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix.")
) -> TemettuVeAksiyonlarSonucu:
    """
    Fetches comprehensive dividend history and corporate actions for Turkish stocks.
    
    This tool provides complete dividend payment history and corporate actions like stock splits,
    essential for income investors and total return calculations. Turkish companies often pay
    substantial dividends, making this data crucial for investment analysis.
    
    **Dividend Data (Temettü Bilgileri):**
    - Historical dividend payments with exact dates and amounts
    - 12-month trailing dividend total for yield calculations
    - Most recent dividend payment details
    - Dividend frequency patterns (annual, semi-annual, etc.)
    
    **Corporate Actions (Kurumsal İşlemler):**
    - Stock splits and their ratios (e.g., 2:1 split)
    - Bonus share distributions
    - Rights offerings and their terms
    - Spin-offs and other corporate restructuring
    
    **Analysis Applications:**
    - Calculate dividend yield: (Annual Dividends / Current Price) × 100
    - Assess dividend sustainability and growth trends
    - Determine total return including dividends
    - Evaluate dividend policy consistency
    - Plan income-focused investment strategies
    
    **Investment Insights:**
    - Turkish companies often have generous dividend policies
    - Banking sector typically pays regular dividends
    - Holding companies may have variable dividend patterns
    - Consider tax implications of dividend income in Turkey
    """
    logger.info(f"Tool 'get_temettu_ve_aksiyonlar' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_temettu_ve_aksiyonlar_yfinance(ticker_kodu)
        if data.get("error"):
            return TemettuVeAksiyonlarSonucu(ticker_kodu=ticker_kodu, error_message=data["error"])
        
        return TemettuVeAksiyonlarSonucu(
            ticker_kodu=ticker_kodu,
            temettuler=data.get("temettuler", []),
            bolunmeler=data.get("bolunmeler", []),
            tum_aksiyonlar=data.get("tum_aksiyonlar", []),
            toplam_temettu_12ay=data.get("toplam_temettu_12ay"),
            son_temettu=data.get("son_temettu")
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_temettu_ve_aksiyonlar' for ticker {ticker_kodu}.")
        return TemettuVeAksiyonlarSonucu(ticker_kodu=ticker_kodu, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_hizli_bilgi(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'TUPRS', 'EREGL' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix.")
) -> HizliBilgiSonucu:
    """
    Fetches essential financial metrics and key ratios for quick company assessment.
    
    This tool provides the most important financial metrics in a single call, perfect for rapid
    screening, portfolio monitoring, or getting a quick overview before deeper analysis.
    Optimized for speed without heavy data processing.
    
    **Key Metrics Returned:**
    
    **Current Market Data:**
    - Real-time or latest stock price
    - Market capitalization in Turkish Lira
    - Today's trading volume and average volume
    - 52-week high and low prices
    - Daily price range (high/low)
    
    **Valuation Ratios:**
    - P/E Ratio (Price-to-Earnings)
    - Forward P/E based on estimates
    - P/B Ratio (Price-to-Book)
    - PEG Ratio (P/E to Growth)
    
    **Financial Health:**
    - Debt-to-Equity ratio
    - Return on Equity (ROE)
    - Return on Assets (ROA)
    - Current ratio for liquidity
    
    **Income & Growth:**
    - Dividend yield percentage
    - Earnings growth rate
    - Revenue growth rate
    - Profit margins
    
    **Risk Metrics:**
    - Beta coefficient vs market
    - Stock volatility measures
    
    **Use Cases:**
    - Quick stock screening and comparison
    - Portfolio performance monitoring
    - Pre-analysis overview before detailed research
    - Real-time market data for trading decisions
    - Fundamental ratio calculations
    """
    logger.info(f"Tool 'get_hizli_bilgi' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_hizli_bilgi_yfinance(ticker_kodu)
        if data.get("error"):
            return HizliBilgiSonucu(ticker_kodu=ticker_kodu, error_message=data["error"])
        
        return HizliBilgiSonucu(
            ticker_kodu=ticker_kodu,
            bilgiler=data.get("bilgiler")
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_hizli_bilgi' for ticker {ticker_kodu}.")
        return HizliBilgiSonucu(ticker_kodu=ticker_kodu, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_kazanc_takvimi(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'AKBNK', 'TUPRS' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix.")
) -> KazancTakvimSonucu:
    """
    Fetches earnings calendar, estimates, and growth data for earnings-focused analysis.
    
    This tool provides comprehensive earnings information including upcoming earnings dates,
    analyst estimates, historical results, and growth metrics. Essential for earnings-based
    investment strategies and understanding company performance cycles.
    
    **Earnings Calendar Data:**
    - Upcoming earnings announcement dates
    - Historical earnings dates and results
    - Quarterly and annual earnings patterns
    - Earnings season timing and consistency
    
    **Analyst Estimates:**
    - EPS (Earnings Per Share) estimates: high, low, average
    - Revenue estimates: high, low, average
    - Estimate accuracy and surprise history
    - Consensus changes over time
    
    **Historical Performance:**
    - Actual reported EPS vs estimates
    - Earnings surprise percentages (beat/miss)
    - Revenue surprise analysis
    - Historical earnings growth patterns
    
    **Growth Metrics:**
    - Annual earnings growth rate
    - Quarterly earnings growth rate
    - Revenue growth trends
    - Growth sustainability assessment
    
    **Investment Applications:**
    - Plan around earnings announcements
    - Assess analyst expectation accuracy
    - Identify earnings growth trends
    - Evaluate management guidance quality
    - Time investment decisions around earnings
    
    **Turkish Market Context:**
    - Turkish companies typically report quarterly
    - Earnings seasons follow international patterns
    - Consider Turkish lira impact on multinational companies
    - Banking sector earnings often lead market sentiment
    """
    logger.info(f"Tool 'get_kazanc_takvimi' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_kazanc_takvimi_yfinance(ticker_kodu)
        if data.get("error"):
            return KazancTakvimSonucu(ticker_kodu=ticker_kodu, error_message=data["error"])
        
        return KazancTakvimSonucu(
            ticker_kodu=ticker_kodu,
            kazanc_tarihleri=data.get("kazanc_tarihleri", []),
            kazanc_takvimi=data.get("kazanc_takvimi"),
            buyume_verileri=data.get("buyume_verileri"),
            gelecek_kazanc_sayisi=data.get("gelecek_kazanc_sayisi", 0),
            gecmis_kazanc_sayisi=data.get("gecmis_kazanc_sayisi", 0)
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_kazanc_takvimi' for ticker {ticker_kodu}.")
        return KazancTakvimSonucu(ticker_kodu=ticker_kodu, error_message=f"An unexpected error occurred: {str(e)}")

@app.tool()
async def get_teknik_analiz(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'ASELS', 'THYAO' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix.")
) -> TeknikAnalizSonucu:
    """
    Comprehensive technical analysis with indicators, trends, and trading signals for stocks and BIST indices.
    
    This tool performs complete technical analysis using 6 months of price data, calculating
    essential technical indicators and providing clear buy/sell signals. Perfect for traders
    and technical analysts seeking professional-grade analysis of individual stocks or market indices.
    
    **Technical Indicators Calculated:**
    
    **Moving Averages:**
    - SMA: 5, 10, 20, 50, 200-day simple moving averages
    - EMA: 12, 26-day exponential moving averages
    - Golden Cross/Death Cross signals (SMA50 vs SMA200)
    
    **Momentum Indicators:**
    - RSI (14-day): Overbought/oversold conditions
    - MACD: Trend following momentum indicator
    - MACD Signal Line and Histogram
    - Stochastic Oscillator (%K and %D)
    
    **Volatility Indicators:**
    - Bollinger Bands: Upper, middle, lower bands
    - Price position relative to bands
    - Band squeeze/expansion analysis
    
    **Volume Analysis:**
    - Current vs average volume comparison
    - Volume trend analysis (high/normal/low)
    - Volume-price relationship assessment
    
    **Trend Analysis:**
    - Short-term trend (5 vs 10-day SMA)
    - Medium-term trend (20 vs 50-day SMA)
    - Long-term trend (50 vs 200-day SMA)
    - Current price position vs key moving averages
    
    **Price Analysis:**
    - Daily price change and percentage
    - Distance from 52-week high/low
    - Support and resistance level proximity
    
    **Trading Signals:**
    - Overall buy/sell/neutral recommendation
    - Signal strength (strong buy, buy, hold, sell, strong sell)
    - Detailed signal explanation and reasoning
    - Confluence of multiple indicator signals
    
    **Signal Interpretation:**
    - **Strong Buy**: Multiple bullish indicators align
    - **Buy**: Predominantly positive technical signals
    - **Neutral**: Mixed or inconclusive signals
    - **Sell**: Predominantly negative technical signals
    - **Strong Sell**: Multiple bearish indicators align
    
    **Best for:**
    - Short to medium-term trading decisions on stocks and indices
    - Entry/exit point identification for individual stocks or market timing
    - Risk management and stop-loss placement
    - Trend confirmation and momentum assessment
    - Index-based market analysis and sector rotation strategies
    """
    logger.info(f"Tool 'get_teknik_analiz' called for ticker: '{ticker_kodu}'")
    try:
        data = await borsa_client.get_teknik_analiz_yfinance(ticker_kodu)
        if data.get("error"):
            return TeknikAnalizSonucu(ticker_kodu=ticker_kodu, error_message=data["error"])
        
        return TeknikAnalizSonucu(
            ticker_kodu=ticker_kodu,
            analiz_tarihi=data.get("analiz_tarihi"),
            fiyat_analizi=data.get("fiyat_analizi"),
            trend_analizi=data.get("trend_analizi"),
            hareketli_ortalamalar=data.get("hareketli_ortalamalar"),
            teknik_indiktorler=data.get("teknik_indiktorler"),
            hacim_analizi=data.get("hacim_analizi"),
            analist_tavsiyeleri=data.get("analist_tavsiyeleri"),
            al_sat_sinyali=data.get("al_sat_sinyali"),
            sinyal_aciklamasi=data.get("sinyal_aciklamasi")
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_teknik_analiz' for ticker {ticker_kodu}.")
        from datetime import datetime
        return TeknikAnalizSonucu(
            ticker_kodu=ticker_kodu, 
            analiz_tarihi=datetime.now().replace(microsecond=0),
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_sektor_karsilastirmasi(
    ticker_listesi: List[str] = Field(..., description="List of BIST ticker codes to analyze by sector (e.g., ['GARAN', 'AKBNK', 'YKBNK'] for banking comparison, or ['ASELS', 'HAZER', 'HKMAT'] for defense). Do not include '.IS' suffix. Minimum 3 tickers recommended for meaningful sector analysis.")
) -> SektorKarsilastirmaSonucu:
    """
    Comprehensive sector analysis comparing multiple Turkish companies across industries.
    
    This tool performs detailed cross-sector analysis by grouping companies into their respective
    sectors and calculating sector-wide metrics, averages, and performance comparisons.
    Perfect for sector rotation strategies and industry analysis.
    
    **Sector Analysis Components:**
    
    **Company Classification:**
    - Automatic sector and industry grouping
    - Company size classification (large/mid/small cap)
    - Geographic distribution analysis
    - Market cap weighting within sectors
    
    **Financial Metrics by Sector:**
    - Average P/E, P/B, ROE ratios per sector
    - Sector-wide debt levels and financial health
    - Profit margin comparisons across industries
    - Revenue growth rates by sector
    
    **Performance Analysis:**
    - 1-year sector performance comparison
    - Risk-adjusted returns by industry
    - Volatility analysis across sectors
    - Beta coefficients and market correlation
    
    **Sector Rankings:**
    - Best performing sector by returns
    - Lowest risk sector by volatility
    - Largest sector by total market cap
    - Most attractive sector by valuation metrics
    
    **Individual Company Context:**
    - Each company's position within its sector
    - Relative performance vs sector peers
    - Valuation premium/discount to sector average
    - Company-specific risk factors
    
    **Investment Applications:**
    
    **Sector Rotation Strategy:**
    - Identify outperforming and underperforming sectors
    - Time entry/exit based on sector cycles
    - Diversification across uncorrelated sectors
    
    **Relative Value Analysis:**
    - Find undervalued companies within strong sectors
    - Identify sector leaders and laggards
    - Compare similar companies across sectors
    
    **Risk Management:**
    - Assess sector concentration risk
    - Understand correlation between holdings
    - Balance portfolio across defensive/cyclical sectors
    
    **Turkish Market Insights:**
    - Banking sector dominance in BIST
    - Industrial and holding company structures
    - Export-oriented vs domestic-focused sectors
    - Government policy impact on specific industries
    
    **Best Practices:**
    - Include 3+ companies per sector for meaningful analysis
    - Mix large and small caps for comprehensive view
    - Consider macroeconomic factors affecting sectors
    - Regular updates as sector dynamics change
    """
    logger.info(f"Tool 'get_sektor_karsilastirmasi' called for tickers: {ticker_listesi}")
    try:
        data = await borsa_client.get_sektor_karsilastirmasi_yfinance(ticker_listesi)
        if data.get("error"):
            return SektorKarsilastirmaSonucu(
                analiz_tarihi=data.get("analiz_tarihi"), 
                toplam_sirket_sayisi=0, 
                sektor_sayisi=0,
                error_message=data["error"]
            )
        
        return SektorKarsilastirmaSonucu(
            analiz_tarihi=data.get("analiz_tarihi"),
            toplam_sirket_sayisi=data.get("toplam_sirket_sayisi", 0),
            sektor_sayisi=data.get("sektor_sayisi", 0),
            sirket_verileri=data.get("sirket_verileri", []),
            sektor_ozetleri=data.get("sektor_ozetleri", []),
            en_iyi_performans_sektor=data.get("en_iyi_performans_sektor"),
            en_dusuk_risk_sektor=data.get("en_dusuk_risk_sektor"),
            en_buyuk_sektor=data.get("en_buyuk_sektor"),
            genel_piyasa_degeri=data.get("genel_piyasa_degeri"),
            genel_ortalama_getiri=data.get("genel_ortalama_getiri"),
            genel_ortalama_volatilite=data.get("genel_ortalama_volatilite")
        )
    except Exception as e:
        logger.exception(f"Error in tool 'get_sektor_karsilastirmasi' for tickers {ticker_listesi}.")
        return SektorKarsilastirmaSonucu(
            analiz_tarihi=None, 
            toplam_sirket_sayisi=0, 
            sektor_sayisi=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_kap_haberleri(
    ticker_kodu: str = Field(..., description="The BIST ticker code of the company or index (e.g., 'GARAN', 'ASELS', 'AEFES' for stocks; 'XU100', 'XBANK', 'XK100' for indices). Do not include '.IS' suffix."),
    haber_sayisi: int = Field(10, description="Number of recent KAP news items to retrieve (1-20). Default is 10 for optimal performance.")
) -> KapHaberleriSonucu:
    """
    Fetches recent KAP (Public Disclosure Platform) news and announcements for Turkish companies.
    
    This tool provides access to official corporate announcements, regulatory filings, and important
    company news directly from KAP through Mynet Finans. Essential for staying updated on
    material developments affecting Turkish public companies.
    
    **KAP News Types Typically Included:**
    
    **Corporate Governance:**
    - Board of directors changes and appointments
    - General manager and executive appointments
    - Corporate governance compliance ratings
    - Shareholder meeting announcements and results
    
    **Financial Disclosures:**
    - Financial statement releases (quarterly/annual)
    - Dividend distribution announcements
    - Capital increases and rights offerings
    - Bond issuances and debt financing
    
    **Material Events:**
    - Special situation disclosures (özel durum açıklaması)
    - Merger and acquisition announcements
    - Strategic partnership agreements
    - Major contract wins or losses
    
    **Regulatory Compliance:**
    - Trade halt announcements from Borsa Istanbul
    - Regulatory sanctions or warnings
    - Compliance with listing requirements
    - Insider trading disclosures
    
    **Operational Updates:**
    - Business expansion or restructuring
    - New product launches or services
    - Facility openings or closures
    - Environmental and sustainability initiatives
    
    **Data Returned for Each News Item:**
    - **Headline**: Full news title with ticker codes
    - **Date & Time**: Precise publication timestamp
    - **News URL**: Direct link to full announcement detail
    - **News ID**: Unique identifier for tracking
    - **Category Context**: Inferred from headline (e.g., financial filing, governance)
    
    **Use Cases:**
    
    **Investment Research:**
    - Monitor material events affecting stock price
    - Track corporate governance changes
    - Identify dividend and capital structure updates
    - Research M&A activity and strategic developments
    
    **Compliance & Risk Management:**
    - Monitor regulatory compliance status
    - Track insider trading disclosures
    - Identify potential reputational risks
    - Stay informed on legal proceedings
    
    **Portfolio Management:**
    - Set up news alerts for portfolio holdings
    - Monitor quarterly earnings release schedules
    - Track dividend payment announcements
    - Identify corporate actions requiring attention
    
    **Due Diligence:**
    - Research recent corporate developments
    - Verify management changes and appointments
    - Check for any regulatory issues or sanctions
    - Understand recent strategic direction changes
    
    **Performance Characteristics:**
    - **Response Time**: 2-4 seconds (web scraping from Mynet)
    - **Update Frequency**: Real-time as announcements are published
    - **Data Quality**: Official KAP announcements, highly reliable
    - **Language**: Turkish (original KAP language)
    
    **Best Practices:**
    - Check news regularly for active portfolio holdings
    - Cross-reference with stock price movements for impact analysis
    - Use in combination with technical analysis for trading decisions
    - Monitor before earnings seasons for guidance updates
    
    **Turkish Market Context:**
    - KAP is the official disclosure platform for all Turkish public companies
    - All material events must be disclosed within specific timeframes
    - News directly affects stock prices and trading volumes
    - Important for understanding Turkish regulatory environment
    """
    logger.info(f"Tool 'get_kap_haberleri' called for ticker: '{ticker_kodu}', limit: {haber_sayisi}")
    
    # Validate parameters
    if haber_sayisi < 1 or haber_sayisi > 20:
        return KapHaberleriSonucu(
            ticker_kodu=ticker_kodu,
            error_message="haber_sayisi must be between 1 and 20"
        )
    
    try:
        data = await borsa_client.get_kap_haberleri_mynet(ticker_kodu, haber_sayisi)
        
        if data.get("error"):
            return KapHaberleriSonucu(
                ticker_kodu=ticker_kodu,
                error_message=data["error"]
            )
        
        # Convert to KapHaberi objects
        from borsa_models import KapHaberi
        kap_haberleri = []
        for haber_data in data.get("kap_haberleri", []):
            haber = KapHaberi(
                baslik=haber_data["baslik"],
                tarih=haber_data["tarih"],
                url=haber_data.get("url"),
                haber_id=haber_data.get("haber_id"),
                title_attr=haber_data.get("title_attr")
            )
            kap_haberleri.append(haber)
        
        return KapHaberleriSonucu(
            ticker_kodu=ticker_kodu,
            kap_haberleri=kap_haberleri,
            toplam_haber=data.get("toplam_haber", 0),
            kaynak_url=data.get("kaynak_url")
        )
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_kap_haberleri' for ticker {ticker_kodu}.")
        return KapHaberleriSonucu(
            ticker_kodu=ticker_kodu,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_kap_haber_detayi(
    haber_url: str = Field(..., description="The full URL of the KAP news to fetch details for. Must be a valid Mynet Finans KAP news URL (e.g., 'https://finans.mynet.com/borsa/haberdetay/68481a49b209972f87e77d92/')."),
    sayfa_numarasi: int = Field(1, description="Page number for large documents (1-based). Documents over 5000 characters are automatically paginated.")
) -> KapHaberDetayi:
    """
    Fetches detailed content of a specific KAP news article and converts it to markdown format with automatic pagination.
    
    This tool retrieves the full content of KAP announcements from Mynet Finans and converts
    complex HTML tables and structures into readable markdown format. For large documents (>5000 characters),
    the content is automatically paginated for better readability and performance. Essential for analyzing
    detailed corporate disclosures, financial reports, and regulatory filings.
    
    **Content Types Typically Processed:**
    
    **Company Information Forms (Şirket Genel Bilgi Formu):**
    - Management team details with roles and backgrounds
    - Board of directors information
    - Executive career histories
    - Organizational structure changes
    
    **Financial Reports:**
    - Quarterly and annual financial statements
    - Detailed balance sheet breakdowns
    - Income statement line items
    - Cash flow analysis tables
    - Footnotes and explanations
    
    **Material Event Disclosures:**
    - Detailed transaction information
    - Contract terms and conditions
    - Strategic initiative descriptions
    - Risk factor explanations
    
    **Corporate Actions:**
    - Dividend distribution details
    - Capital increase structures
    - Share buyback programs
    - Corporate restructuring plans
    
    **Markdown Output Features:**
    
    **Document Structure:**
    - Main title as H1 header
    - Document type clearly indicated
    - Section headers as H2
    - Subsection headers as H3
    - Horizontal rules for separation
    
    **Table Formatting:**
    - Complex tables converted to markdown tables
    - Column headers properly aligned
    - Cell content truncated if too long (100+ chars)
    - Maintains data integrity and readability
    
    **Content Organization:**
    - Hierarchical structure preserved
    - Related information grouped together
    - Clear visual separation between sections
    - Consistent formatting throughout
    
    **Pagination Features:**
    - Documents over 5000 characters automatically paginated
    - Page size: 5000 characters per page
    - Page indicators showing current/total pages
    - Navigation instructions for next pages
    - Full document statistics provided
    
    **Use Cases:**
    
    **Detailed Analysis:**
    - Deep dive into management changes
    - Analyze financial statement details
    - Review contract terms and conditions
    - Understand corporate restructuring
    
    **Compliance Review:**
    - Verify regulatory disclosure completeness
    - Check for required information elements
    - Analyze disclosure timing and accuracy
    - Document compliance trail
    
    **Investment Research:**
    - Extract key financial metrics
    - Analyze management quality and experience
    - Review strategic direction changes
    - Assess operational updates
    
    **Report Generation:**
    - Create readable summaries for clients
    - Generate investment committee materials
    - Prepare due diligence documentation
    - Archive important announcements
    
    **Technical Features:**
    
    **HTML Processing:**
    - BeautifulSoup parsing for reliability
    - Handles complex nested table structures
    - Preserves data relationships
    - Cleans up formatting artifacts
    
    **Markdown Conversion:**
    - Standard markdown syntax
    - Compatible with all markdown renderers
    - Preserves table structure
    - Maintains readability
    
    **Error Handling:**
    - Validates URL format
    - Handles missing content gracefully
    - Returns partial content if available
    - Clear error messages
    
    **Performance:**
    - Response time: 2-5 seconds
    - Depends on document complexity
    - Efficient table processing
    - Minimal memory footprint
    
    **Example Output Structure:**
    ```markdown
    # ANADOLU EFES BİRACILIK VE MALT SANAYİİ A.Ş. Şirket Genel Bilgi Formu 10 Haziran 2025
    
    **Belge Türü:** Sirket Genel Bilgi Formu
    
    ---
    
    ## Yönetime İlişkin Bilgiler
    
    ### Yönetimde Söz Sahibi Olan Personel
    
    | Adı-Soyadı | Görevi | Mesleği | Son 5 Yılda Üstlendiği Görevler | Ortaklık Dışında Görevler |
    |---|---|---|---|---|
    | ONUR ALTÜRK | Bira Grubu Başkanı | Üst Düzey Yönetici | Efes Türkiye Genel Müdürü | |
    | GÖKÇE YANAŞMAYAN | Mali İşler Direktörü | Üst Düzey Yönetici | Efes Moldova Genel Müdürü | |
    ```
    
    **Best Practices:**
    - Always verify URL is from get_kap_haberleri output
    - Process important announcements promptly
    - Archive markdown output for future reference
    - Cross-reference with other data sources
    - Use for detailed due diligence work
    """
    logger.info(f"Tool 'get_kap_haber_detayi' called for URL: '{haber_url}', page: {sayfa_numarasi}")
    
    # Basic URL validation
    if not haber_url or not haber_url.startswith("http"):
        return KapHaberDetayi(
            baslik="",
            belge_turu="",
            markdown_icerik="",
            toplam_karakter=0,
            sayfa_numarasi=1,
            toplam_sayfa=1,
            sonraki_sayfa_var=False,
            sayfa_boyutu=5000,
            haber_url=haber_url,
            error_message="Invalid URL format. Please provide a valid HTTP/HTTPS URL."
        )
    
    # Validate page number
    if sayfa_numarasi < 1:
        return KapHaberDetayi(
            baslik="",
            belge_turu="",
            markdown_icerik="",
            toplam_karakter=0,
            sayfa_numarasi=1,
            toplam_sayfa=1,
            sonraki_sayfa_var=False,
            sayfa_boyutu=5000,
            haber_url=haber_url,
            error_message="Page number must be 1 or greater."
        )
    
    try:
        data = await borsa_client.get_kap_haber_detayi_mynet(haber_url, sayfa_numarasi)
        
        if data.get("error"):
            return KapHaberDetayi(
                baslik="",
                belge_turu="",
                markdown_icerik="",
                toplam_karakter=0,
                sayfa_numarasi=sayfa_numarasi,
                toplam_sayfa=1,
                sonraki_sayfa_var=False,
                sayfa_boyutu=5000,
                haber_url=haber_url,
                error_message=data["error"]
            )
        
        return KapHaberDetayi(
            baslik=data.get("baslik", ""),
            belge_turu=data.get("belge_turu"),
            markdown_icerik=data.get("markdown_icerik", ""),
            toplam_karakter=data.get("toplam_karakter", 0),
            sayfa_numarasi=data.get("sayfa_numarasi", 1),
            toplam_sayfa=data.get("toplam_sayfa", 1),
            sonraki_sayfa_var=data.get("sonraki_sayfa_var", False),
            sayfa_boyutu=data.get("sayfa_boyutu", 5000),
            haber_url=data.get("haber_url", haber_url)
        )
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_kap_haber_detayi' for URL {haber_url}.")
        return KapHaberDetayi(
            baslik="",
            belge_turu="",
            markdown_icerik="",
            toplam_karakter=0,
            sayfa_numarasi=sayfa_numarasi,
            toplam_sayfa=1,
            sonraki_sayfa_var=False,
            sayfa_boyutu=5000,
            haber_url=haber_url,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_katilim_finans_uygunluk(
    ticker_kodu: str = Field(description="The ticker code of the company to check for participation finance compatibility (e.g., 'ARCLK', 'GARAN')")
) -> KatilimFinansUygunlukSonucu:
    """
    Fetches participation finance (Islamic finance) compatibility data for a specific BIST company from KAP
    and checks participation finance index membership.
    
    This tool provides comprehensive Islamic finance compatibility assessment by:
    1. Searching official KAP participation finance database for detailed compliance data
    2. Checking if the company is included in BIST participation finance indices (XK100, XK050, XK030)
    
    **KAP Data (if available):**
    - Company ticker code and name
    - Financial statement period and presentation currency
    - Compatibility assessments for various Islamic finance criteria:
      * Activities incompatible with participation finance principles
      * Privileges incompatible with participation finance
      * Support for actions defined in participation finance standards
      * Direct incompatible activities and income
    - Financial ratios: percentage of incompatible income, assets, and debts
    
    **Participation Index Check:**
    - Membership in XK100 (BIST Katılım 100)
    - Membership in XK050 (BIST Katılım 50)
    - Membership in XK030 (BIST Katılım 30)
    - Live data fetched from Mynet Finans
    
    **Enhanced Logic:**
    - If KAP data exists: Returns detailed compliance information + index membership
    - If KAP data missing but company in participation index: Indicates index membership as compliance signal
    - Example: "No KAP participation finance data found, but company is included in participation finance index XK100"
    
    **Use cases:**
    - Comprehensive Sharia compliance assessment
    - Islamic finance investment due diligence
    - Religious compliance verification for Muslim investors
    - ESG and ethical investment screening
    - Cross-validation of compliance through multiple sources
    
    **Data sources:** 
    - KAP (Public Disclosure Platform) for detailed compliance reports
    - Mynet Finans for participation finance index composition
    
    Args:
        ticker_kodu: The BIST ticker code to search for (e.g., 'ASELS', 'GARAN', 'AKBNK')
    
    Returns:
        KatilimFinansUygunlukSonucu: Complete participation finance assessment including 
        detailed KAP data (if available) and participation finance index membership status.
    """
    logger.info(f"Tool 'get_katilim_finans_uygunluk' called for ticker: '{ticker_kodu}'")
    
    # Basic input validation
    if not ticker_kodu or not ticker_kodu.strip():
        return KatilimFinansUygunlukSonucu(
            ticker_kodu="",
            sirket_bilgisi=None,
            veri_bulundu=False,
            kaynak_url="https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid",
            error_message="Ticker code is required and cannot be empty."
        )
    
    try:
        data = await borsa_client.get_katilim_finans_uygunluk(ticker_kodu)
        
        # data is already a KatilimFinansUygunlukSonucu object, not a dict
        if hasattr(data, 'error_message') and data.error_message:
            return KatilimFinansUygunlukSonucu(
                ticker_kodu=ticker_kodu,
                sirket_bilgisi=None,
                veri_bulundu=False,
                kaynak_url="https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid",
                error_message=data.error_message
            )
        
        return data
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_katilim_finans_uygunluk' for ticker {ticker_kodu}")
        return KatilimFinansUygunlukSonucu(
            ticker_kodu=ticker_kodu,
            sirket_bilgisi=None,
            veri_bulundu=False,
            kaynak_url="https://www.kap.org.tr/tr/kfifAllInfoListByItem/KPY97SummaryGrid",
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_endeks_kodu(
    endeks_adi_veya_kodu: str = Field(..., description="Enter the index name or code to find BIST indices. You can search using: index name (e.g., 'Bankacılık', 'Teknoloji'), partial name (e.g., 'BIST 100'), or index code (e.g., 'XU100', 'XBANK'). Search is case-insensitive and supports Turkish characters.")
) -> EndeksKoduAramaSonucu:
    """
    Searches for BIST index codes by name or partial code.
    
    This tool searches through all 66 BIST indices to find matching index codes.
    It performs fuzzy matching on index names and codes, similar to the company ticker search.
    
    Use cases:
    - Find the correct index code for analysis
    - Discover all indices in a specific category (e.g., 'Katılım' for Islamic indices)
    - Search for regional indices (e.g., 'İstanbul', 'İzmir')
    - Find sector-specific indices (e.g., 'Banka', 'Teknoloji')
    - Get proper index codes for other tools
    
    Returns detailed information including:
    - Matching index codes (e.g., XU100, XBANK)
    - Full index names in Turkish
    - Number of companies in each index
    - List of companies (for indices with data)
    
    Examples:
    - Search 'banka' → Returns XBANK (BIST BANKA) and XLBNK (BIST LİKİT BANKA)
    - Search '100' → Returns XU100 (BIST 100) and related indices
    - Search 'teknoloji' → Returns XUTEK (BIST TEKNOLOJİ) and XBLSM (BIST BİLİŞİM)
    - Search 'katılım' → Returns all Islamic finance indices
    - Search 'istanbul' → Returns XSIST (BIST İSTANBUL)
    """
    logger.info(f"Tool 'get_endeks_kodu' called with query: '{endeks_adi_veya_kodu}'")
    
    if not endeks_adi_veya_kodu or len(endeks_adi_veya_kodu) < 2:
        raise ToolError("You must enter at least 2 characters to search.")
    
    try:
        result = await borsa_client.search_indices_from_kap(endeks_adi_veya_kodu)
        
        # Log search results
        if result.sonuc_sayisi > 0:
            logger.info(f"Found {result.sonuc_sayisi} indices matching '{endeks_adi_veya_kodu}'")
        else:
            logger.warning(f"No indices found matching '{endeks_adi_veya_kodu}'")
        
        return result
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_endeks_kodu' for query '{endeks_adi_veya_kodu}'.")
        return EndeksKoduAramaSonucu(
            arama_terimi=endeks_adi_veya_kodu,
            sonuclar=[],
            sonuc_sayisi=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )


@app.tool()
async def get_endeks_sirketleri(
    endeks_kodu: str = Field(description="The index code to get company details for (e.g., 'XU100', 'XBANK', 'BIST 100')")
) -> EndeksSirketleriSonucu:
    """
    Get basic company information (ticker codes and names) for all companies in a specific BIST index.
    
    This tool fetches the list of companies in a given BIST index, returning only essential information:
    company ticker codes and company names. This is a simplified, fast version focused on index composition.
    
    Key Features:
    - Company ticker codes (e.g., GARAN, AKBNK, ASELS)
    - Company names (official company names)
    - Total number of companies in the index
    - Fast response time (no detailed financial data)
    
    Use Cases:
    - Get list of companies in an index for further analysis
    - Index composition overview
    - Quick company identification within indices
    - Prepare ticker lists for other tools
    
    Data Source:
    - Index composition: Mynet Finans (live data)
    
    Examples:
    - get_endeks_sirketleri("XU100") - Get all BIST 100 company tickers and names
    - get_endeks_sirketleri("XBANK") - Get all banking sector company tickers and names
    - get_endeks_sirketleri("XUTEK") - Get all technology sector company tickers and names
    """
    logger.info(f"Tool 'get_endeks_sirketleri' called with endeks_kodu='{endeks_kodu}'")
    
    try:
        if not endeks_kodu or not endeks_kodu.strip():
            raise ToolError("Index code cannot be empty")
            
        data = await borsa_client.get_endeks_sirketleri(endeks_kodu.strip())
        
        if data.error_message:
            logger.warning(f"Tool 'get_endeks_sirketleri' returned error: {data.error_message}")
        else:
            logger.info(f"Tool 'get_endeks_sirketleri' completed successfully for '{endeks_kodu}' - {data.toplam_sirket} companies")
        
        return data
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_endeks_sirketleri' for endeks_kodu='{endeks_kodu}'")
        return EndeksSirketleriSonucu(
            endeks_kodu=endeks_kodu,
            toplam_sirket=0,
            sirketler=[],
            error_message=f"An unexpected error occurred: {str(e)}"
        )

# --- TEFAS Fund Tools ---

@app.tool()
async def search_funds(
    search_term: str = Field(..., description="Enter the fund's name, code, or founder to search. You can search using: fund name (e.g., 'Garanti Hisse', 'altın', 'teknoloji'), fund code (e.g., 'TGE'), or founder company (e.g., 'QNB Finans'). Search is case-insensitive and supports Turkish characters."),
    limit: int = Field(20, description="Maximum number of results to return (default: 20, max: 50).", ge=1, le=50),
    fund_category: str = Field("all", description="Filter by fund category: 'all' (all funds), 'debt' (Debt Securities), 'variable' (Variable Funds), 'basket' (Fund Baskets), 'guaranteed' (Guaranteed Funds), 'real_estate' (Real Estate), 'venture' (Venture Capital), 'equity' (Equity Funds), 'mixed' (Mixed Funds), 'participation' (Participation Funds), 'precious_metals' (Precious Metals), 'money_market' (Money Market), 'flexible' (Flexible Funds).")
) -> FonAramaSonucu:
    """
    Searches for mutual funds in TEFAS (Turkish Electronic Fund Trading Platform).
    
    **Advanced TEFAS API Integration:**
    Uses the official TEFAS BindComparisonFundReturns API, providing comprehensive, 
    up-to-date fund data with performance metrics included in search results.
    
    **Performance Data Included:**
    Search results include real-time performance data (1M, 3M, 6M, 1Y, YTD, 3Y, 5Y returns),
    automatically sorted by 1-year performance for better fund discovery.
    
    **Turkish Character Support:**
    Automatically handles Turkish characters - search for 'altın' or 'altin', both will work.
    Examples: 'garanti' finds 'GARANTİ', 'katilim' finds 'KATILIM', 'hisse' finds 'HİSSE'.
    
    **Data Source:**
    Official TEFAS API with real-time data covering 844 active funds + comprehensive performance metrics
    
    Use cases:
    - Find top performing funds: 'altın fonları' → gold funds sorted by performance
    - Search with performance: 'teknoloji' → technology funds with current returns
    - Find by company: 'garanti portföy' → Garanti funds with latest performance  
    - Quick code lookup: 'TGE' → exact fund match with metrics
    - Thematic search: 'katılım' → participation funds with returns
    - Category filtering: fund_category='equity' → only equity funds
    - Mixed search: 'garanti' + fund_category='debt' → Garanti debt funds only
    
    Returns:
    - Fund code (e.g., AFO, BLT, DBA for gold funds)
    - Full fund name in Turkish
    - Current performance metrics (1M, 3M, 6M, 1Y, YTD, 3Y, 5Y)
    - Automatic sorting by 1-year return
    
    Examples:
    - Search 'altın' → Returns gold funds sorted by 1-year performance
    - Search 'garanti hisse' → Returns Garanti equity funds with current returns
    - Search 'katılım' → Returns Islamic finance funds with performance data
    - Search 'TGE' → Returns exact fund match with full metrics
    - Search 'teknoloji' + fund_category='equity' → Technology equity funds only
    - Search 'garanti' + fund_category='debt' + limit=5 → Top 5 Garanti debt funds
    """
    logger.info(f"Tool 'search_funds' called with query: '{search_term}', limit: {limit}")
    
    if not search_term or len(search_term) < 2:
        raise ToolError("You must enter at least 2 characters to search.")
    
    try:
        result = await borsa_client.tefas_provider.search_funds_advanced(search_term, limit, "YAT", fund_category)
        return FonAramaSonucu(**result)
    except Exception as e:
        logger.exception(f"Error in tool 'search_funds' for query '{search_term}'.")
        return FonAramaSonucu(
            arama_terimi=search_term,
            sonuclar=[],
            sonuc_sayisi=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_fund_detail(
    fund_code: str = Field(..., description="The TEFAS fund code (e.g., 'TGE', 'AFA', 'IPB'). Use search_funds to find the correct fund code first."),
    include_price_history: bool = Field(False, description="Include detailed price history (1-week, 1-month, 3-month, 6-month). Default is False for faster response.")
) -> FonDetayBilgisi:
    """
    Fetches comprehensive details and performance metrics for a specific Turkish mutual fund from official TEFAS GetAllFundAnalyzeData API.
    
    **Complete Fund Information:**
    - **Basic Data**: Current NAV, AUM, investor count, fund category, ranking in category
    - **Performance**: Returns for 1m, 3m, 6m, YTD, 1y, 3y, 5y periods with daily changes
    - **Risk Metrics**: Standard deviation, Sharpe ratio, alpha, beta, risk score (1-7)
    - **Fund Profile**: ISIN code, trading hours, minimum amounts, commissions, KAP links
    - **Portfolio Allocation**: Asset type breakdown (equities, bonds, repos, etc.) with percentages
    - **Category Rankings**: Position within fund category, total funds in category, market share
    
    **Optional Price History** (include_price_history=True):
    - 1-week price history (fundPrices1H)
    - 1-month price history (fundPrices1A)  
    - 3-month price history (fundPrices3A)
    - 6-month price history (fundPrices6A)
    
    **New Enhanced Features:**
    - **Category Ranking**: "84 / 163" format showing fund's position among peers
    - **Portfolio Breakdown**: Detailed asset allocation (e.g., 27.99% Government Bonds, 25.03% Equities)
    - **Technical Profile**: Trading parameters, valor dates, commission structure
    - **Market Share**: Fund's percentage of total market
    
    **Use Cases:**
    - **Investment Analysis**: Complete fund evaluation with all metrics
    - **Portfolio Research**: Asset allocation strategy analysis  
    - **Performance Comparison**: Ranking vs peers in same category
    - **Due Diligence**: Technical details for institutional analysis
    - **Risk Assessment**: Comprehensive risk profiling
    
    **Examples:**
    - get_fund_detail("TGE") → Garanti equity fund with portfolio allocation
    - get_fund_detail("AAK", include_price_history=True) → Full data with 6-month price history
    - get_fund_detail("AFO") → Gold fund with category ranking and technical profile
    """
    logger.info(f"Tool 'get_fund_detail' called with fund_code: '{fund_code}', include_price_history: {include_price_history}")
    
    if not fund_code or not fund_code.strip():
        raise ToolError("Fund code cannot be empty")
    
    try:
        return await borsa_client.get_fund_detail(fund_code.strip().upper(), include_price_history)
    except Exception as e:
        logger.exception(f"Error in tool 'get_fund_detail' for fund_code '{fund_code}'.")
        return FonDetayBilgisi(
            fon_kodu=fund_code,
            fon_adi="",
            tarih="",
            fiyat=0,
            tedavuldeki_pay_sayisi=0,
            toplam_deger=0,
            birim_pay_degeri=0,
            yatirimci_sayisi=0,
            kurulus="",
            yonetici="",
            fon_turu="",
            risk_degeri=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_fund_performance(
    fund_code: str = Field(..., description="The TEFAS fund code (e.g., 'TGE', 'AFA', 'IPB', 'AAK')."),
    start_date: str = Field(None, description="Start date in YYYY-MM-DD format (default: 1 year ago). Example: '2024-01-01'"),
    end_date: str = Field(None, description="End date in YYYY-MM-DD format (default: today). Example: '2024-12-31'")
) -> FonPerformansSonucu:
    """
    Fetches historical performance data for a Turkish mutual fund using official TEFAS BindHistoryInfo API.
    
    **Enhanced TEFAS API Integration:**
    Uses the official TEFAS historical data endpoint (same as TEFAS website), providing
    comprehensive fund performance data with precise timestamps and portfolio metrics.
    
    **Data Provided:**
    - Daily NAV (Net Asset Value) history with exact timestamps
    - Fund size (AUM) and outstanding shares over time
    - Investor count history and trends
    - Total return calculation for the specified period
    - Annualized return with compound growth rate
    - Portfolio value evolution (PORTFOYBUYUKLUK)
    - Fund title and official information
    
    **Performance Calculations:**
    - **Total Return**: ((Latest Price - Oldest Price) / Oldest Price) × 100
    - **Annualized Return**: ((Latest Price / Oldest Price)^(365/days) - 1) × 100
    - **Date Range**: Flexible period analysis (1 day to 5 years maximum)
    
    **Time Zone & Formatting:**
    All timestamps converted to Turkey timezone (Europe/Istanbul) and formatted as YYYY-MM-DD.
    Data sorted by date (newest first) for easy chronological analysis.
    
    **Use Cases:**
    
    **Performance Analysis:**
    - Chart fund NAV evolution over any time period
    - Calculate precise returns for investment periods
    - Compare fund performance across different market cycles
    - Analyze volatility and return patterns
    
    **Portfolio Monitoring:**
    - Track AUM growth and fund size changes
    - Monitor investor sentiment via investor count trends
    - Assess fund liquidity and market acceptance
    - Evaluate management effectiveness over time
    
    **Investment Research:**
    - Historical due diligence for fund selection
    - Performance attribution and risk analysis
    - Benchmark comparison preparation
    - Tax planning with precise date ranges
    
    **Examples:**
    - get_fund_performance("TGE") → Last 1 year Garanti equity fund performance
    - get_fund_performance("AAK", "2024-01-01", "2024-12-31") → 2024 ATA multi-asset fund performance
    - get_fund_performance("AFA", "2023-06-01", "2024-06-01") → 1-year AK Asset Management fund analysis
    - get_fund_performance("IPB", "2024-06-01", "2024-06-22") → Recent 3-week İş Portföy performance
    
    **Response Format:**
    Returns detailed performance data including fund code, date range, complete price history,
    calculated returns, data point count, and source attribution for audit trails.
    
    **Data Quality:**
    - Official TEFAS timestamps (milliseconds precision)
    - Real portfolio values and investor counts
    - Validated fund codes and comprehensive error handling
    - Maximum 3-month date range limit (TEFAS restriction)
    """
    logger.info(f"Tool 'get_fund_performance' called with fund_code: '{fund_code}', period: {start_date} to {end_date}")
    
    if not fund_code or not fund_code.strip():
        raise ToolError("Fund code cannot be empty")
    
    try:
        return await borsa_client.get_fund_performance(fund_code.strip().upper(), start_date, end_date)
    except Exception as e:
        logger.exception(f"Error in tool 'get_fund_performance' for fund_code '{fund_code}'.")
        return FonPerformansSonucu(
            fon_kodu=fund_code,
            baslangic_tarihi=start_date or "",
            bitis_tarihi=end_date or "",
            fiyat_geçmisi=[],
            veri_sayisi=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )

@app.tool()
async def get_fund_portfolio(
    fund_code: str = Field(..., description="The TEFAS fund code (e.g., 'TGE', 'AFA', 'IPB', 'AAK')."),
    start_date: str = Field(None, description="Start date in YYYY-MM-DD format (default: 1 week ago). Example: '2024-06-15'"),
    end_date: str = Field(None, description="End date in YYYY-MM-DD format (default: today). Example: '2024-06-22'")
) -> FonPortfoySonucu:
    """
    Fetches historical portfolio allocation composition of a Turkish mutual fund using official TEFAS BindHistoryAllocation API.
    
    **Enhanced TEFAS API Integration:**
    Uses the official TEFAS allocation history endpoint (same as TEFAS website), providing
    comprehensive portfolio allocation data over time with detailed asset type breakdowns.
    
    **Portfolio Allocation Data:**
    - Asset allocation percentages by category over time
    - Complete asset type mapping (50+ categories)
    - Historical allocation changes and trends
    - Investment strategy evolution analysis
    - Asset concentration and diversification metrics
    
    **Asset Categories Tracked:**
    
    **Equity & Securities:**
    - Hisse Senedi (HS) - Domestic equity holdings
    - Yabancı Hisse Senedi (YHS) - Foreign equity holdings
    - Borsa Yatırım Fonu (BYF) - ETF holdings
    - Yabancı Borsa Yatırım Fonu (YBYF) - Foreign ETF holdings
    
    **Fixed Income:**
    - Devlet Tahvili (DT) - Government bonds
    - Özel Sektör Tahvili (OST) - Corporate bonds
    - Eurobond Tahvil (EUT) - Eurobond holdings
    - Yabancı Borçlanma Araçları (YBA) - Foreign debt instruments
    
    **Money Market & Cash:**
    - Vadesiz Mevduat (VM) - Demand deposits
    - Vadeli Mevduat (VDM) - Time deposits
    - Ters Repo (TR) - Reverse repo operations
    - Döviz (D) - Foreign currency holdings
    
    **Islamic Finance:**
    - Kira Sertifikası (KKS) - Lease certificates
    - Katılım Hesabı (KH) - Participation accounts
    - Özel Sektör Kira Sertifikası (OSKS) - Private sector lease certificates
    
    **Alternative Investments:**
    - Kıymetli Maden (KM) - Precious metals
    - Gayrimenkul Yatırım (GYY) - Real estate investments
    - Girişim Sermayesi Yatırım (GSYY) - Venture capital investments
    - Yabancı Yatırım Fonu (YYF) - Foreign mutual funds
    
    **Time-Series Analysis:**
    All timestamps converted to Turkey timezone (Europe/Istanbul) with chronological sorting.
    Data shows allocation evolution over the specified period for strategy analysis.
    
    **Use Cases:**
    
    **Investment Strategy Analysis:**
    - Track allocation changes over time
    - Understand fund manager's investment approach
    - Analyze response to market conditions
    - Evaluate strategic asset allocation consistency
    
    **Risk Assessment:**
    - Monitor concentration levels in specific assets
    - Assess diversification effectiveness
    - Track foreign currency exposure
    - Evaluate credit risk through bond allocations
    
    **Performance Attribution:**
    - Correlate allocation changes with performance
    - Identify best/worst performing allocations
    - Understand style drift over time
    - Analyze sector rotation patterns
    
    **Due Diligence:**
    - Verify fund strategy alignment with prospectus
    - Compare actual vs. stated investment approach
    - Monitor regulatory compliance
    - Assess manager consistency
    
    **Examples:**
    - get_fund_portfolio("TGE") → Last week's Garanti equity fund allocations
    - get_fund_portfolio("AAK", "2024-06-01", "2024-06-22") → ATA multi-asset fund allocation evolution over 3 weeks
    - get_fund_portfolio("AFO") → Recent allocation data for AK gold fund
    - get_fund_portfolio("IPB", "2024-06-15", "2024-06-22") → İş Portföy allocation changes over 1 week
    
    **Response Format:**
    Returns historical allocation data with date range, complete allocation history,
    latest allocation summary, data point count, and source attribution.
    
    **Data Quality:**
    - Official TEFAS timestamps (milliseconds precision)
    - Complete asset type mapping with Turkish names
    - Validated fund codes and comprehensive error handling
    - Default 1-week range for recent allocation analysis
    """
    logger.info(f"Tool 'get_fund_portfolio' called with fund_code: '{fund_code}', period: {start_date} to {end_date}")
    
    if not fund_code or not fund_code.strip():
        raise ToolError("Fund code cannot be empty")
    
    try:
        return await borsa_client.get_fund_portfolio(fund_code.strip().upper(), start_date, end_date)
    except Exception as e:
        logger.exception(f"Error in tool 'get_fund_portfolio' for fund_code '{fund_code}'.")
        return FonPortfoySonucu(
            fon_kodu=fund_code,
            tarih="",
            portfoy_detayi=[],
            varlik_dagilimi={},
            toplam_varlik=0,
            error_message=f"An unexpected error occurred: {str(e)}"
        )



@app.tool()
async def compare_funds(
    fund_type: str = Field("EMK", description="Fund type: 'YAT' (Investment Funds), 'EMK' (Pension Funds), 'BYF' (ETFs), 'GYF' (REITs), 'GSYF' (Venture Capital)."),
    start_date: str = Field(None, description="Start date in DD.MM.YYYY format (e.g., '25.05.2025'). If not provided, defaults to 30 days ago."),
    end_date: str = Field(None, description="End date in DD.MM.YYYY format (e.g., '20.06.2025'). If not provided, defaults to today."),
    periods: List[str] = Field(["1A", "3A", "6A", "YB", "1Y"], description="List of return periods: '1A' (1 month), '3A' (3 months), '6A' (6 months), 'YB' (year-to-date), '1Y' (1 year), '3Y' (3 years), '5Y' (5 years)."),
    founder: str = Field("Tümü", description="Filter by fund management company. Use 'Tümü' for all, or specific codes like 'AKP' (AK Portföy), 'GPY' (Garanti Portföy), 'ISP' (İş Portföy), etc."),
    fund_codes: List[str] = Field(None, description="Optional list of specific fund codes to compare (e.g., ['AFO', 'EUN']). If provided, only these funds will be included in results.")
) -> Dict[str, Any]:
    """
    Compares and screens Turkish mutual funds using TEFAS official comparison API.
    
    This unified tool serves as both fund comparison and screening tool using the exact same 
    endpoint as TEFAS website's fund comparison page, providing comprehensive analysis with 
    multiple return periods, filters, and statistical analysis.
    
    **Key Features:**
    - Official TEFAS comparison data (same as website)
    - Multiple fund types: Investment, Pension, ETF, REIT, Venture Capital
    - Flexible date ranges and return periods
    - Filter by management company
    - Comprehensive statistics and rankings
    - Dual functionality: comparison and screening
    
    **Modes of Operation:**
    
    **1. Fund Comparison Mode:**
    - Provide specific fund_codes to compare selected funds
    - Examples: ['TGE', 'AFA', 'IPB'], ['AAK', 'GPA']
    
    **2. Fund Screening Mode:**
    - Leave fund_codes empty (None) to screen all funds by criteria
    - Use fund_type, founder, periods for filtering
    - Returns all matching funds sorted by performance
    
    **Use Cases:**
    - **Comparison**: compare_funds(fund_codes=['TGE', 'AFA']) → Compare specific equity funds
    - **Screening**: compare_funds(fund_type='EMK', founder='GPY') → Screen all Garanti pension funds
    - **Market Analysis**: compare_funds(fund_type='BYF') → Screen all ETFs
    - **Performance Analysis**: compare_funds(fund_type='YAT', periods=['1Y', '3Y']) → Screen investment funds with 1Y and 3Y returns
    
    **Examples:**
    - compare_funds(fund_codes=['TGE', 'AFA']) → Compare 2 specific equity funds
    - compare_funds(fund_type='EMK', founder='GPY') → Screen Garanti pension funds
    - compare_funds(fund_type='BYF') → Screen all ETFs
    - compare_funds(fund_type='YAT', periods=['1Y']) → Screen investment funds by 1-year performance
    
    Returns detailed comparison/screening data including fund details, performance metrics,
    statistical summaries, and ranking information.
    """
    result = await borsa_client.compare_funds_advanced(
        fund_codes=fund_codes,
        fund_type=fund_type,
        start_date=start_date,
        end_date=end_date,
        periods=periods,
        founder=founder
    )
    return result

@app.tool()
async def get_fon_mevzuati() -> FonMevzuatSonucu:
    """
    Retrieves Turkish investment fund regulation guide.
    
    This tool provides comprehensive fund regulation documentation that LLMs can reference
    when answering legal questions about investment funds. Content covers only investment
    fund-specific regulations, not the entire stock market regulations.
    
    **Covered Topics:**
    
    **Fund Types and Structures:**
    - Mixed umbrella funds and their regulations
    - Index funds and tracking rules
    - Money market participation funds
    - Special provisions for participation funds
    - Private funds and special arrangements
    
    **Portfolio Management:**
    - Asset restrictions and portfolio limits
    - Derivative instrument investment rules
    - Foreign investment guidelines
    - Risk management requirements
    - Liquidity management rules
    
    **Transactions and Restrictions:**
    - Repo and reverse repo transaction rules
    - Over-the-counter transactions
    - Securities lending regulations
    - Swap contract guidelines
    - Maturity calculation methods
    
    **Special Regulations:**
    - Issuer limits and calculations
    - Related party transactions
    - Asset-backed securities rules
    - Income-indexed securities
    - Precious metal investments
    
    **Fund Naming and Titles:**
    - Fund title regulations
    - "Participation" terminology usage
    - "Partnership" labeled funds
    - Special purpose fund naming
    
    **Use Cases:**
    - Fund establishment and structuring
    - Portfolio management decisions
    - Risk management and compliance
    - Investment strategy development
    - Legal compliance monitoring
    
    **Important Note:**
    This fund regulation guide applies only to **investment funds**. Stocks,
    bond markets, CMB general regulations, or other capital market instruments
    require separate regulatory documents.
    
    **Updates:**
    The fund regulation document's last update date is provided in the response.
    For critical decisions, verify current regulations from the official CMB website.
    """
    logger.info("Tool 'get_fon_mevzuati' called")
    try:
        return await borsa_client.get_fon_mevzuati()
    except Exception as e:
        logger.exception("Error in tool 'get_fon_mevzuati'")
        return FonMevzuatSonucu(
            mevzuat_adi="Yatırım Fonları Mevzuat Rehberi",
            icerik="",
            karakter_sayisi=0,
            kaynak_dosya="fon_mevzuat_kisa.md",
            error_message=f"Fon mevzuatı dokümanı alınırken beklenmeyen bir hata oluştu: {str(e)}"
        )

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
