#!/usr/bin/env python3
"""Check MCP tools count"""

print("📊 CHECKING MCP TOOLS COUNT")
print("=" * 40)

try:
    import re
    
    # Read borsa_mcp_server.py file
    with open('borsa_mcp_server.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count @app.tool occurrences
    tool_decorators = re.findall(r'@app\.tool\(', content)
    total_tools = len(tool_decorators)
    
    print(f"🔧 Total @app.tool decorators found: {total_tools}")
    
    # Find Coinbase tools specifically
    coinbase_tools = re.findall(r'async def (get_coinbase_\w+)', content)
    print(f"🌍 Coinbase tools found: {len(coinbase_tools)}")
    
    if coinbase_tools:
        print("   Coinbase tools:")
        for i, tool in enumerate(coinbase_tools, 1):
            print(f"   {i}. {tool}")
    
    # Find BtcTurk tools for comparison
    btcturk_tools = re.findall(r'async def (get_kripto_\w+)', content)
    print(f"🇹🇷 BtcTurk tools found: {len(btcturk_tools)}")
    
    # Find other tool categories
    stock_tools = re.findall(r'async def ((?:find_ticker_code|get_sirket_|get_bilanco|get_kar_zarar|get_nakit|get_finansal|get_analist|get_temettu|get_hizli|get_kazanc|get_teknik|get_sektor|get_kap|get_katilim|get_endeks)\w*)', content)
    fund_tools = re.findall(r'async def ((?:search_funds|get_fund_|compare_funds|get_fon_)\w*)', content)
    
    print(f"📈 Stock tools found: {len(stock_tools)}")
    print(f"💰 Fund tools found: {len(fund_tools)}")
    
    # Expected count
    expected_total = len(stock_tools) + len(btcturk_tools) + len(coinbase_tools) + len(fund_tools)
    
    print("\n📋 BREAKDOWN:")
    print(f"   Stock tools: {len(stock_tools)}")
    print(f"   BtcTurk crypto: {len(btcturk_tools)}")  
    print(f"   Coinbase crypto: {len(coinbase_tools)}")
    print(f"   Fund tools: {len(fund_tools)}")
    print(f"   Expected total: {expected_total}")
    print(f"   Actual total: {total_tools}")
    
    if total_tools == 35:
        print("\n✅ TOOL COUNT CORRECT: 35 tools as expected!")
    elif total_tools == expected_total:
        print(f"\n✅ TOOL COUNT MATCHES BREAKDOWN: {total_tools} tools")
    else:
        print(f"\n⚠️ TOOL COUNT MISMATCH: Expected ~35, found {total_tools}")
    
    if len(coinbase_tools) == 6:
        print("✅ COINBASE TOOLS COMPLETE: All 6 tools implemented")
    else:
        print(f"⚠️ COINBASE TOOLS INCOMPLETE: {len(coinbase_tools)}/6 found")
        
except Exception as e:
    print(f"❌ Error checking tools: {e}")
    import traceback
    traceback.print_exc()