"""
Monthly KPI Fetcher
Updates: TSMC revenue, Silicon Analysts, FRED semiconductor index, API pricing trend, InferenceMAX
Frequency: 1st of each month at 6am UTC via GitHub Actions

Run manually: python fetchers/monthly.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_kpis, save_kpis, update_kpi, log_error, http_get,
    calculate_pct_change, safe_float, safe_int, update_frequency_timestamp, print_summary
)
from datetime import datetime
import os


def fetch_tsmc_revenue():
    """Fetch TSMC monthly revenue from SEC EDGAR 6-K filings (most recent)."""
    try:
        print("  Fetching TSMC monthly revenue...")
        
        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": "0001046735",
            "type": "6-K",
            "dateb": "",
            "owner": "exclude",
            "count": 5
        }
        
        query_url = url + "?" + "&".join(f"{k}={v}" for k, v in params.items() if v)
        response = http_get(query_url, timeout=15)
        
        if not response:
            return None
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("    (Note: TSMC revenue typically published on 10th of month)")
        print("    See: investor.tsmc.com/english/monthly-revenue")
        
        return {
            "status": "manual_required",
            "note": "Visit investor.tsmc.com on 10th of month for latest revenue",
            "last_checked": datetime.utcnow().isoformat() + "Z"
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_silicon_analysts():
    try:
        print("  Fetching Silicon Analysts market pulse...")
        
        response = http_get(
            "https://siliconanalysts.com/api/v1/market-pulse",
            timeout=15
        )
        
        if not response:
            print("    API not responding, using fallback scrape")
            return fetch_silicon_analysts_scrape()
        
        # Try parsing as JSON
        try:
            data = response.json()
            if isinstance(data, dict):
                return {
                    "tsmc_3nm_price": data.get('tsmc_3nm_wafer_price_usd') or data.get('tsmc_3nm_price') or data.get('wafer_price_3nm'),
                    "hbm_price": data.get('hbm_spot_price_usd') or data.get('hbm_price') or data.get('hbm_cost'),
                    "cowos_capacity_percent": data.get('cowos_utilization_percent') or data.get('cowos_utilization') or data.get('packaging_utilization'),
                    "last_updated": data.get('updated_at', datetime.utcnow().isoformat() + "Z")
                }
        except:
            pass
        
        # Fallback to scraping the market page
        return fetch_silicon_analysts_scrape()
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return fetch_silicon_analysts_scrape()


def fetch_silicon_analysts_scrape():
    try:
        import re
        from bs4 import BeautifulSoup
        
        print("    Trying scrape fallback...")
        response = http_get("https://siliconanalysts.com/market", timeout=15)
        
        if not response:
            return None
        
        text = response.text
        
        # Extract TSMC 3nm price
        tsmc_match = re.search(r'3nm.*?\$(\d{1,3}(?:,\d{3})*)', text, re.IGNORECASE)
        tsmc_price = None
        if tsmc_match:
            tsmc_price = int(tsmc_match.group(1).replace(',', ''))
        
        # Extract CoWoS utilization
        cowos_match = re.search(r'CoWoS.*?(\d{2,3}).*?%', text, re.IGNORECASE)
        cowos_pct = None
        if cowos_match:
            cowos_pct = int(cowos_match.group(1))
        
        if tsmc_price or cowos_pct:
            return {
                "tsmc_3nm_price": tsmc_price,
                "hbm_price": None,
                "cowos_capacity_percent": cowos_pct,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
        
        return None
    
    except Exception as e:
        print(f"    Scrape fallback error: {str(e)}")
        return None


def fetch_fred_semiconductor_index():
    try:
        print("  Fetching FRED semiconductor production index...")
        
        fred_key = os.getenv('FRED_API_KEY')
        
        if not fred_key:
            print("    FRED_API_KEY not set in environment")
            return None
        
        print(f"    Key found: {fred_key[:4]}...")
        
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "IPG3344S",
            "api_key": fred_key,
            "limit": "12",
            "sort_order": "desc",
            "file_type": "json"
        }
        
        query_url = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        print(f"    URL: {query_url[:80]}...")
        
        response = http_get(query_url, timeout=15)
        
        if not response:
            print("    No response from FRED")
            return None
        
        print(f"    Response status: {response.status_code}")
        
        data = response.json()
        
        if 'observations' not in data:
            print(f"    Unexpected response: {str(data)[:200]}")
            return None
        
        obs = data['observations']
        
        # Filter out missing values (FRED uses "." for missing)
        obs = [o for o in obs if o['value'] != '.']
        
        if not obs:
            return None
        
        latest = obs[0]
        prev = obs[1] if len(obs) > 1 else latest
        
        latest_value = safe_float(latest['value'])
        prev_value = safe_float(prev['value'])
        change = calculate_pct_change(latest_value, prev_value)
        
        return {
            "index_value": latest_value,
            "date": latest['date'],
            "change_pct": change,
            "series": "IPG3344S"
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_api_pricing_log():
    try:
        print("  Fetching API pricing snapshot...")
        sources = [
            ("OpenAI", "https://openai.com/api/pricing/"),
            ("Anthropic", "https://www.anthropic.com/pricing"),
            ("Google", "https://ai.google.dev/pricing")
        ]
        results = []
        for provider, url in sources:
            response = http_get(url, timeout=10)
            if response:
                results.append(f"{provider} ✓")
            else:
                results.append(f"{provider} ✗")
        return "  ".join(results)
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_inferencemax_efficiency():
    try:
        import re
        from bs4 import BeautifulSoup
        print("  Fetching InferenceX (formerly InferenceMAX) metrics...")
        
        response = http_get("https://inferencex.semianalysis.com/", timeout=15)
        
        if not response:
            return None
        
        text = response.text
        
        # Look for tokens per second or cost metrics
        tps_match = re.search(r'(\d{2,3},\d{3})\s*tokens per second', text, re.IGNORECASE)
        cost_match = re.search(r'\$?([\d.]+)\s*(?:per|/)\s*million tokens', text, re.IGNORECASE)
        
        result = {
            "status": "live",
            "url": "https://inferencex.semianalysis.com",
            "note": "InferenceMAX renamed to InferenceX by SemiAnalysis",
            "last_checked": datetime.utcnow().isoformat() + "Z"
        }
        
        if tps_match:
            result["top_throughput_tps"] = int(tps_match.group(1).replace(',', ''))
        
        if cost_match:
            result["cost_per_million_tokens"] = float(cost_match.group(1))
        
        return result
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def main():
    """Main function: fetch all monthly KPIs and update JSON."""
    
    print("\n" + "="*60)
    print("MONTHLY KPI FETCHER — Started at", datetime.utcnow().isoformat() + "Z")
    print("="*60 + "\n")
    
    data = load_kpis()
    
    # 1. TSMC Revenue
    print("1. TSMC Monthly Revenue (NT$)")
    tsmc = fetch_tsmc_revenue()
    if tsmc:
        update_kpi(data, "tsmc_monthly_revenue", tsmc.get('status'), unit="manual_check")
        print("   ⓘ TSMC releases on 10th of each month")
        print("     Visit: investor.tsmc.com/english/monthly-revenue")
    else:
        log_error(data, "tsmc_revenue", "SEC EDGAR parsing incomplete")
        print("   ⓘ Manual entry required")
    
    # 2. Silicon Analysts
    print("\n2. Silicon Analysts — Market Pulse")
    sa = fetch_silicon_analysts()
    if sa:
        if sa.get('tsmc_3nm_price'):
            update_kpi(data, "tsmc_3nm_wafer_price", sa['tsmc_3nm_price'], unit="USD")
            print(f"   ✓ TSMC 3nm: ${sa['tsmc_3nm_price']}/wafer")
        if sa.get('hbm_price'):
            update_kpi(data, "hbm_spot_price", sa['hbm_price'], unit="USD")
            print(f"   ✓ HBM spot: ${sa['hbm_price']}")
        if sa.get('cowos_capacity_percent'):
            update_kpi(data, "cowos_utilization", sa['cowos_capacity_percent'], unit="%")
            print(f"   ✓ CoWoS capacity: {sa['cowos_capacity_percent']}%")
    else:
        log_error(data, "silicon_analysts", "API not responding")
        print("   ✗ API error")
    
    # 3. FRED
    print("\n3. FRED — Semiconductor Production Index")
    fred = fetch_fred_semiconductor_index()
    if fred:
        update_kpi(data, "fred_semi_index", fred['index_value'], unit="index", 
                   change_pct=fred['change_pct'])
        print(f"   ✓ Index: {fred['index_value']} (date: {fred['date']})")
        if fred['change_pct']:
            print(f"     Change: {fred['change_pct']:+.1f}%")
    else:
        log_error(data, "fred_semi_index", "API key missing or error")
        print("   ✗ Failed (FRED_API_KEY required)")
    
    # 4. API Pricing Log
    print("\n4. AI API Pricing Snapshot")
    pricing = fetch_api_pricing_log()
    if pricing:
        update_kpi(data, "api_pricing_log", pricing, unit="snapshot")
        print("   ✓ Pricing sources checked")
        for provider, status in pricing.items():
            print(f"     {provider}: {status.get('status', 'unknown')}")
    else:
        log_error(data, "api_pricing_log", "Failed to fetch")
        print("   ✗ Failed")
    
    # 5. InferenceMAX
    print("\n5. InferenceMAX — Hardware Efficiency")
    imax = fetch_inferencemax_efficiency()
    if imax:
        update_kpi(data, "inferencemax_efficiency", imax['status'])
        print("   ✓ InferenceX dashboard live at inferencex.semianalysis.com")
    else:
        log_error(data, "inferencemax", "Failed to fetch")
        print("   ✗ Failed")
    
    # Save and print summary
    update_frequency_timestamp(data, "monthly")
    save_kpis(data)
    print_summary(data, "monthly")


if __name__ == "__main__":
    main()
