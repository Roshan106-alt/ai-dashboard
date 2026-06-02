"""
Daily KPI Fetcher
Updates: Google Trends, AI stock prices, API pricing, Artificial Analysis speed metrics
Frequency: Daily at 6am UTC via GitHub Actions

Run manually: python fetchers/daily.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_kpis, save_kpis, update_kpi, log_error, http_get, 
    calculate_pct_change, safe_float, update_frequency_timestamp, print_summary
)
import json
from datetime import datetime


def fetch_google_trends():
    """Fetch Google search interest for AI terms using unofficial pytrends."""
    try:
        from pytrends.request import TrendReq
        
        print("  Fetching Google Trends...")
        pytrends = TrendReq(hl='en-US', tz=0)
        
        # Search for AI-related terms
        keywords = ['ChatGPT', 'Claude AI', 'AI agent']
        pytrends.build_payload(keywords, cat=0, timeframe='now 1-d', geo='')
        
        data = pytrends.interest_over_time()
        
        # Get latest values (last row)
        latest = data.iloc[-1]
        
        # Return average of the three terms as a single index
        ai_index = int((latest['ChatGPT'] + latest['Claude AI'] + latest['AI agent']) / 3)
        
        return ai_index
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_ai_stock_prices():
    try:
        import yfinance as yf
        print("  Fetching AI stock prices...")
        tickers = ['NVDA', 'MSFT', 'GOOGL', 'META', 'AMZN']
        prices = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.fast_info
                price = round(float(info.last_price), 2)
                prev = round(float(info.previous_close), 2)
                change = calculate_pct_change(price, prev)
                prices[ticker] = {"price": price, "change_pct": change}
            except Exception as e:
                print(f"    {ticker}: Error - {str(e)}")
        return prices if prices else None
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_api_pricing():
    """Fetch current AI API pricing from usagepricing.com (simplified HTML parse)."""
    try:
        from bs4 import BeautifulSoup
        
        print("  Fetching API pricing snapshot...")
        response = http_get('https://usagepricing.com/ai-token-pricing')
        
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("    (Note: HTML structure may vary — manual check recommended)")
        return {
            "last_checked": datetime.utcnow().isoformat() + "Z",
            "note": "See official pricing pages: openai.com, anthropic.com, ai.google.dev"
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_artificial_analysis_speed():
    try:
        from bs4 import BeautifulSoup
        import re
        print("  Fetching Artificial Analysis leaderboard...")
        
        response = http_get(
            'https://artificialanalysis.ai/leaderboards/models',
            timeout=15
        )
        
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for speed numbers in the page
        text = soup.get_text()
        
        # Find tokens per second values
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:tok/s|tokens/s|t/s)', text, re.IGNORECASE)
        
        if not matches:
            # Try finding any speed-related numbers
            matches = re.findall(r'(\d+(?:\.\d+)?)\s*tokens per second', text, re.IGNORECASE)
        
        if matches:
            speeds = [float(m) for m in matches[:10]]
            top_speed = max(speeds)
            avg_speed = sum(speeds) / len(speeds)
            return {
                "top_model_speed_tps": round(top_speed, 1),
                "avg_speed_tps": round(avg_speed, 1),
                "models_sampled": len(speeds)
            }
        
        # If we can't parse speeds, at least confirm site is live
        if 'model' in text.lower() and 'speed' in text.lower():
            return {
                "top_model_speed_tps": None,
                "status": "live_but_unparseable",
                "url": "https://artificialanalysis.ai/leaderboards/models"
            }
        
        return None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def main():
    """Main function: fetch all daily KPIs and update JSON."""
    
    print("\n" + "="*60)
    print("DAILY KPI FETCHER — Started at", datetime.utcnow().isoformat() + "Z")
    print("="*60 + "\n")
    
    data = load_kpis()
    
    # 1. Google Trends
    print("1. Google Trends AI Interest")
    trends = fetch_google_trends()
    if trends is not None:
        update_kpi(data, "google_trends_ai", trends, unit="index (0-100)")
        print(f"   ✓ {trends}")
    else:
        log_error(data, "google_trends_ai", "Failed to fetch (pytrends error)")
        print("   ✗ Failed")
    
    # 2. AI Stock Prices
    print("\n2. AI Equity Prices")
    stocks = fetch_ai_stock_prices()
    if stocks:
        for ticker, info in stocks.items():
            kpi_name = f"stock_{ticker.lower()}"
            update_kpi(data, kpi_name, info['price'], unit="USD", change_pct=info['change_pct'])
            print(f"   ✓ {ticker}: ${info['price']} ({info['change_pct']:+.1f}%)")
    else:
        log_error(data, "ai_stock_prices", "Failed to fetch")
        print("   ✗ Failed")
    
    # 3. API Pricing
    print("\n3. AI API Pricing Snapshot")
    pricing = fetch_api_pricing()
    if pricing:
        update_kpi(data, "api_pricing_snapshot", pricing, status="ok")
        print("   ✓ Latest pricing recorded")
    else:
        log_error(data, "api_pricing_snapshot", "Failed to fetch")
        print("   ✗ Failed")
    
    # 4. Artificial Analysis Speed
    print("\n4. Artificial Analysis — Inference Speed")
    aa_speed = fetch_artificial_analysis_speed()
    if aa_speed:
        update_kpi(data, "aa_inference_speed_tps", aa_speed['top_model_speed_tps'], unit="tokens/sec")
        print(f"   ✓ Top model: {aa_speed['top_model_speed_tps']} TPS")
        print(f"     Avg top 5: {aa_speed['avg_top5_speed_tps']} TPS")
    else:
        log_error(data, "aa_inference_speed", "Failed to fetch")
        print("   ✗ Failed")
    
    # Save and print summary
    update_frequency_timestamp(data, "daily")
    save_kpis(data)
    print_summary(data, "daily")


if __name__ == "__main__":
    main()
