"""
Verification script for Phase 3 (Tier 2) data availability.
Checks if required data is available for advanced financial calculations.
"""

import asyncio
import logging
from borsa_client import BorsaApiClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def verify_shares_outstanding_history():
    """
    Verify if historical shares outstanding data is available.
    Required for Piotroski F-Score.
    """
    print("\n" + "=" * 80)
    print("VERIFICATION 1: Historical Shares Outstanding")
    print("Required for: Piotroski F-Score")
    print("=" * 80)

    client = BorsaApiClient()
    try:
        ticker = "GARAN"
        print(f"\nChecking {ticker} for shares outstanding data...")

        # Get company info
        info_result = await client.get_sirket_bilgileri_yfinance(ticker)
        if info_result.get('error'):
            print(f"❌ Error fetching company info: {info_result['error']}")
            return False

        sirket_bilgileri = info_result.get('sirket_bilgileri', {})
        shares_outstanding = sirket_bilgileri.get('sharesOutstanding')

        if shares_outstanding:
            print(f"✅ Current shares outstanding: {shares_outstanding:,.0f}")
            print(f"   Note: Yahoo Finance provides current value only, not historical trend")
            print(f"   Decision: ⚠️ PARTIAL - Can calculate current metrics, but historical trend unavailable")
            print(f"   Recommendation: Implement simplified version without historical comparison")
            return "partial"
        else:
            print(f"❌ Shares outstanding not available")
            return False

    except Exception as e:
        print(f"❌ Verification FAILED: {e}")
        logger.exception("Shares outstanding verification exception")
        return False
    finally:
        await client.close()


async def verify_retained_earnings():
    """
    Verify if Retained Earnings field is available in balance sheet.
    Required for Altman Z-Score.
    """
    print("\n" + "=" * 80)
    print("VERIFICATION 2: Retained Earnings")
    print("Required for: Altman Z-Score")
    print("=" * 80)

    client = BorsaApiClient()
    try:
        ticker = "GARAN"
        print(f"\nChecking {ticker} balance sheet for Retained Earnings...")

        # Get balance sheet
        balance_result = await client.get_bilanco_yfinance(ticker, 'quarterly')
        if balance_result.get('error'):
            print(f"❌ Error fetching balance sheet: {balance_result['error']}")
            return False

        # Check all available field names
        tablo = balance_result.get('tablo', [])
        if not tablo:
            print(f"❌ No balance sheet data available")
            return False

        # Extract all field names
        field_names = [row.get('Kalem') for row in tablo if row.get('Kalem')]
        print(f"\n   Found {len(field_names)} balance sheet fields")

        # Check for Retained Earnings
        retained_earnings_fields = [
            'Retained Earnings',
            'Retained Earnings Accumulated Deficit',
            'Accumulated Deficit'
        ]

        found = False
        for field in retained_earnings_fields:
            if field in field_names:
                print(f"✅ Found: {field}")
                found = True
                break

        if found:
            print(f"   Decision: ✅ AVAILABLE - Can implement Altman Z-Score")
            return True
        else:
            print(f"❌ Retained Earnings field not found")
            print(f"   Available fields include: {', '.join(field_names[:10])}...")
            print(f"   Decision: ❌ NOT AVAILABLE - Cannot implement Altman Z-Score")
            return False

    except Exception as e:
        print(f"❌ Verification FAILED: {e}")
        logger.exception("Retained earnings verification exception")
        return False
    finally:
        await client.close()


async def verify_dividend_data():
    """
    Verify if dividend and buyback data is available.
    Required for Shareholder Yield.
    """
    print("\n" + "=" * 80)
    print("VERIFICATION 3: Dividend Data")
    print("Required for: Shareholder Yield")
    print("=" * 80)

    client = BorsaApiClient()
    try:
        ticker = "GARAN"
        print(f"\nChecking {ticker} for dividend data...")

        # Get dividend data
        dividend_result = await client.get_temettu_ve_aksiyonlar_yfinance(ticker)
        if dividend_result.get('error'):
            print(f"❌ Error fetching dividend data: {dividend_result['error']}")
            return False

        dividends = dividend_result.get('temettuler', [])
        splits = dividend_result.get('hisse_bolunmeleri', [])

        if dividends:
            print(f"✅ Dividend history available: {len(dividends)} records")
            print(f"   Latest dividend: {dividends[0] if dividends else 'N/A'}")
            print(f"   Stock splits: {len(splits)} records")
            print(f"   Note: Share buyback data not directly available from Yahoo Finance")
            print(f"   Decision: ⚠️ PARTIAL - Can calculate dividend yield, but buybacks unavailable")
            print(f"   Recommendation: Implement dividend yield only (no buybacks)")
            return "partial"
        else:
            print(f"❌ Dividend data not available")
            return False

    except Exception as e:
        print(f"❌ Verification FAILED: {e}")
        logger.exception("Dividend data verification exception")
        return False
    finally:
        await client.close()


async def verify_inflation_data():
    """
    Verify if inflation data is available for real growth calculation.
    Required for Real Growth Rate.
    """
    print("\n" + "=" * 80)
    print("VERIFICATION 4: Inflation Data")
    print("Required for: Real Growth Rate")
    print("=" * 80)

    client = BorsaApiClient()
    try:
        print(f"\nChecking TCMB inflation data availability...")

        # Get inflation data
        inflation_result = await client.get_turkiye_enflasyon(
            inflation_type='tufe',
            limit=1
        )

        if inflation_result.data:
            latest = inflation_result.data[0]
            print(f"✅ Inflation data available")
            print(f"   Latest: {latest.ay_yil} - Annual: {latest.yillik_enflasyon}%, Monthly: {latest.aylik_enflasyon}%")
            print(f"   Total records: {inflation_result.total_records}")
            print(f"   Decision: ✅ AVAILABLE - Can implement Real Growth Rate")
            return True
        else:
            print(f"❌ Inflation data not available")
            return False

    except Exception as e:
        print(f"❌ Verification FAILED: {e}")
        logger.exception("Inflation data verification exception")
        return False
    finally:
        await client.close()


async def run_all_verifications():
    """Run all Phase 3 data verifications."""
    print("\n" + "=" * 80)
    print("PHASE 3 (TIER 2) DATA AVAILABILITY VERIFICATION")
    print("=" * 80)

    results = {}

    # Run all verifications
    results['shares_outstanding'] = await verify_shares_outstanding_history()
    results['retained_earnings'] = await verify_retained_earnings()
    results['dividend_data'] = await verify_dividend_data()
    results['inflation_data'] = await verify_inflation_data()

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    print(f"\n1. Piotroski F-Score: ", end="")
    if results['shares_outstanding'] == "partial":
        print("⚠️ PARTIAL (current data only)")
    elif results['shares_outstanding']:
        print("✅ AVAILABLE")
    else:
        print("❌ NOT AVAILABLE")

    print(f"2. Altman Z-Score: ", end="")
    if results['retained_earnings']:
        print("✅ AVAILABLE")
    else:
        print("❌ NOT AVAILABLE")

    print(f"3. Shareholder Yield: ", end="")
    if results['dividend_data'] == "partial":
        print("⚠️ PARTIAL (dividends only)")
    elif results['dividend_data']:
        print("✅ AVAILABLE")
    else:
        print("❌ NOT AVAILABLE")

    print(f"4. Real Growth Rate: ", end="")
    if results['inflation_data']:
        print("✅ AVAILABLE")
    else:
        print("❌ NOT AVAILABLE")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("\n✅ IMPLEMENT:")
    if results['retained_earnings']:
        print("   - Altman Z-Score (complete implementation)")
    if results['inflation_data']:
        print("   - Real Growth Rate (complete implementation)")

    print("\n⚠️ IMPLEMENT WITH LIMITATIONS:")
    if results['shares_outstanding'] == "partial":
        print("   - Simplified Piotroski F-Score (without historical comparisons)")
    if results['dividend_data'] == "partial":
        print("   - Dividend Yield (without buybacks)")

    print("\n❌ SKIP:")
    if not results['shares_outstanding']:
        print("   - Piotroski F-Score (no shares data)")
    if not results['retained_earnings']:
        print("   - Altman Z-Score (no retained earnings)")
    if not results['dividend_data']:
        print("   - Shareholder Yield (no dividend data)")
    if not results['inflation_data']:
        print("   - Real Growth Rate (no inflation data)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_verifications())
