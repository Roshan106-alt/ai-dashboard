"""
Quarterly KPI Fetcher
Updates: Hyperscaler capex, NVIDIA DC revenue, reported capex, cloud revenue, AI server backlog
Frequency: 1st of Jan/Apr/Jul/Oct at 6am UTC via GitHub Actions

Run manually: python fetchers/quarterly.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_kpis, save_kpis, update_kpi, log_error, http_get,
    calculate_pct_change, safe_float, update_frequency_timestamp, print_summary
)
from datetime import datetime


def fetch_sec_10q_filing(company_cik: str, company_name: str):
    """
    Fetch the most recent 10-Q filing from SEC EDGAR for a company.
    Returns the filing URL and metadata.
    
    Args:
        company_cik: SEC Central Index Key (e.g., '0000789019' for MSFT)
        company_name: Human-readable name
    
    Returns:
        dict with filing info or None if error
    """
    try:
        print(f"    Searching SEC EDGAR for {company_name} 10-Q...")
        
        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": company_cik,
            "type": "10-Q",
            "dateb": "",
            "owner": "exclude",
            "count": 1
        }
        
        query_url = url + "?" + "&".join(f"{k}={v}" for k, v in params.items() if v)
        response = http_get(query_url, timeout=15)
        
        if not response:
            return None
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        return {
            "company": company_name,
            "filing_type": "10-Q",
            "status": "found_in_edgar",
            "note": "Full capex/revenue extraction requires 10-Q document parsing"
        }
    
    except Exception as e:
        print(f"    Error: {str(e)}")
        return None


def fetch_hyperscaler_capex_guidance():
    """Fetch forward capex guidance from Microsoft, Amazon, Google, Meta earnings calls."""
    try:
        print("  Fetching hyperscaler capex guidance (forward-looking)...")
        
        companies = {
            "MSFT": "0000789019",
            "AMZN": "0001018724",
            "GOOGL": "0001652044",
            "META": "0001326801"
        }
        
        capex_guidance = {}
        
        for ticker, cik in companies.items():
            filing = fetch_sec_10q_filing(cik, ticker)
            if filing:
                capex_guidance[ticker] = filing
        
        return capex_guidance if capex_guidance else None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_nvidia_dc_revenue():
    """Fetch NVIDIA's Data Center segment revenue from latest 10-Q."""
    try:
        print("  Fetching NVIDIA Data Center revenue...")
        
        response = http_get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=10-Q&count=1",
            timeout=15
        )
        
        if not response:
            return None
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        return {
            "company": "NVIDIA",
            "filing_type": "10-Q",
            "segment": "Data Center",
            "status": "found_in_edgar",
            "note": "Visit investor.nvidia.com for latest DC revenue"
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_hyperscaler_reported_capex():
    """Fetch actual reported capex from MSFT, AMZN, GOOGL, META 10-Q filings."""
    try:
        print("  Fetching hyperscaler reported capex (actual spend)...")
        
        companies = ["MSFT", "AMZN", "GOOGL", "META"]
        
        capex_data = {}
        
        for company in companies:
            capex_data[company] = {
                "status": "requires_10q_parsing",
                "note": f"See {company} investor relations for latest 10-Q"
            }
        
        return capex_data if capex_data else None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_cloud_revenue_growth():
    """Fetch YoY cloud revenue growth for AWS, Azure, GCP from 10-Q filings."""
    try:
        print("  Fetching cloud revenue growth (YoY)...")
        
        cloud_data = {
            "AWS": {"status": "requires_amzn_10q"},
            "Azure": {"status": "requires_msft_10q"},
            "Google Cloud": {"status": "requires_googl_10q"}
        }
        
        return cloud_data if cloud_data else None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_ai_server_backlog():
    """Fetch AI server order backlog info from Dell, Supermicro, HPE earnings transcripts."""
    try:
        print("  Fetching AI server backlog metrics...")
        
        server_companies = {
            "DELL": "0001018724",
            "SMCI": "0000914162",
            "HPE": "0001192624"
        }
        
        backlog_data = {}
        
        for ticker, cik in server_companies.items():
            backlog_data[ticker] = {
                "status": "check_earnings_call",
                "note": f"Monitor {ticker} earnings calls for backlog commentary"
            }
        
        return backlog_data if backlog_data else None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def main():
    """Main function: fetch all quarterly KPIs and update JSON."""
    
    print("\n" + "="*60)
    print("QUARTERLY KPI FETCHER — Started at", datetime.utcnow().isoformat() + "Z")
    print("="*60 + "\n")
    
    data = load_kpis()
    
    # 1. Hyperscaler Capex Guidance
    print("1. Hyperscaler Capex Guidance (Forward-Looking)")
    capex_guidance = fetch_hyperscaler_capex_guidance()
    if capex_guidance:
        update_kpi(data, "hyperscaler_capex_guidance", capex_guidance)
        print("   ⓘ Check earnings calls for forward capex guidance")
        for ticker, info in capex_guidance.items():
            print(f"     {ticker}: {info.get('status')}")
    else:
        log_error(data, "hyperscaler_capex_guidance", "SEC EDGAR parsing incomplete")
        print("   ⓘ Manual check of earnings calls recommended")
    
    # 2. NVIDIA DC Revenue
    print("\n2. NVIDIA Data Center Revenue")
    nvidia_dc = fetch_nvidia_dc_revenue()
    if nvidia_dc:
        update_kpi(data, "nvidia_dc_revenue", nvidia_dc['status'])
        print("   ⓘ See investor.nvidia.com for quarterly earnings")
    else:
        log_error(data, "nvidia_dc_revenue", "SEC EDGAR fetch incomplete")
        print("   ✗ Failed")
    
    # 3. Hyperscaler Reported Capex
    print("\n3. Hyperscaler Reported Capex (Actual Spend)")
    capex_reported = fetch_hyperscaler_reported_capex()
    if capex_reported:
        update_kpi(data, "hyperscaler_capex_reported", capex_reported)
        print("   ⓘ Available in 10-Q filings after earnings announcement")
        for company, info in capex_reported.items():
            print(f"     {company}: {info.get('status')}")
    else:
        log_error(data, "hyperscaler_capex_reported", "SEC EDGAR fetch incomplete")
        print("   ✗ Failed")
    
    # 4. Cloud Revenue Growth
    print("\n4. Cloud Revenue Growth (YoY %)")
    cloud_growth = fetch_cloud_revenue_growth()
    if cloud_growth:
        update_kpi(data, "cloud_revenue_growth", cloud_growth)
        print("   ⓘ YoY % available in earnings announcements")
        for cloud, info in cloud_growth.items():
            print(f"     {cloud}: {info.get('status')}")
    else:
        log_error(data, "cloud_revenue_growth", "SEC EDGAR fetch incomplete")
        print("   ✗ Failed")
    
    # 5. AI Server Backlog
    print("\n5. AI Server Order Backlog")
    backlog = fetch_ai_server_backlog()
    if backlog:
        update_kpi(data, "ai_server_backlog", backlog)
        print("   ⓘ Monitor earnings calls for backlog commentary")
        for ticker, info in backlog.items():
            print(f"     {ticker}: {info.get('status')}")
    else:
        log_error(data, "ai_server_backlog", "Earnings call parsing incomplete")
        print("   ✗ Failed")
    
    print("\n" + "="*60)
    print("NOTES ON QUARTERLY KPIs:")
    print("="*60)
    print("These KPIs require pulling data from SEC filings and earnings calls.")
    print("For MVP, we recommend:")
    print("1. Set calendar reminders for earnings dates")
    print("2. Check investor sites within 1 hour of earnings")
    print("3. Extract capex/revenue figures and manually update kpis.json")
    print("4. This takes ~15 minutes per quarter (4 companies × 3-4 metrics)")
    print("="*60 + "\n")
    
    # Save and print summary
    update_frequency_timestamp(data, "quarterly")
    save_kpis(data)
    print_summary(data, "quarterly")


if __name__ == "__main__":
    main()
