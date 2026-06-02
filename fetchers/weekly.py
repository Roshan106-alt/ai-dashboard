"""
Weekly KPI Fetcher
Updates: GitHub AI repo stars, HuggingFace downloads, AI job postings, OpenRouter token volume
Frequency: Every Monday at 6am UTC via GitHub Actions

Run manually: python fetchers/weekly.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_kpis, save_kpis, update_kpi, log_error, http_get,
    calculate_pct_change, safe_int, update_frequency_timestamp, print_summary
)
from datetime import datetime


def fetch_github_ai_repos():
    try:
        import os
        print("  Fetching GitHub AI repo metrics...")
        
        headers = {}
        gh_token = os.getenv('GH_TOKEN', '')
        if gh_token:
            headers["Authorization"] = f"token {gh_token}"
        
        url = "https://api.github.com/search/repositories?q=topic:llm+topic:ai+stars:>10000&sort=stars&order=desc&per_page=30"
        response = http_get(url, headers=headers)
        
        if not response:
            return None
        
        data = response.json()
        
        if 'items' not in data or len(data['items']) == 0:
            return None
        
        top_repos = data['items'][:10]
        total_stars = sum(r['stargazers_count'] for r in top_repos)
        most_starred = top_repos[0]
        
        return {
            "total_stars_top10": total_stars,
            "most_starred_repo": most_starred['full_name'],
            "most_starred_count": most_starred['stargazers_count']
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_hugging_face_models():
    """Fetch download stats for top AI models on HuggingFace."""
    try:
        print("  Fetching HuggingFace model metrics...")
        
        # HuggingFace Hub API for top models
        url = "https://huggingface.co/api/models"
        params = {
            "sort": "downloads",
            "direction": -1,
            "limit": 50
        }
        
        # Build query string
        query_url = url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        response = http_get(query_url, timeout=15)
        
        if not response:
            return None
        
        data = response.json()
        
        if not isinstance(data, list) or len(data) == 0:
            return None
        
        # Calculate metrics
        ai_models = [m for m in data if 'downloads' in m][:20]
        
        total_downloads = sum(m.get('downloads', 0) for m in ai_models)
        avg_downloads = total_downloads / len(ai_models) if ai_models else 0
        most_downloaded = ai_models[0] if ai_models else None
        
        return {
            "total_downloads_top20": total_downloads,
            "avg_downloads_per_model": round(avg_downloads, 0),
            "most_downloaded": most_downloaded['id'] if most_downloaded else "N/A",
            "most_downloaded_count": most_downloaded.get('downloads', 0) if most_downloaded else 0,
            "models_tracked": len(ai_models)
        }
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_ai_job_postings():
    try:
        import os
        print("  Fetching AI job postings via Adzuna...")
        
        app_id = os.getenv('ADZUNA_APP_ID')
        api_key = os.getenv('ADZUNA_API_KEY')
        
        if not app_id or not api_key:
            print("    ADZUNA credentials not set")
            return None
        
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
        params = f"?app_id={app_id}&app_key={api_key}&what=artificial+intelligence+machine+learning&results_per_page=1&content-type=application/json"
        
        response = http_get(url + params, timeout=15)
        
        if not response:
            return None
        
        data = response.json()
        
        count = data.get('count', 0)
        
        if count:
            return {
                "ai_job_postings": count,
                "source": "Adzuna"
            }
        
        return None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def fetch_openrouter_token_throughput():
    """Fetch top models by weekly token throughput from OpenRouter."""
    try:
        from bs4 import BeautifulSoup
        
        print("  Fetching OpenRouter token throughput...")
        
        # OpenRouter's data page is publicly scrapeable
        response = http_get("https://openrouter.ai/data", timeout=15)
        
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # For MVP, we'll check if page loaded and return a note
        if 'ranking' in response.text.lower() or 'token' in response.text.lower():
            return {
                "openrouter_status": "live",
                "note": "See openrouter.ai/data for real-time token throughput rankings",
                "last_checked": datetime.utcnow().isoformat() + "Z"
            }
        else:
            return None
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None


def main():
    """Main function: fetch all weekly KPIs and update JSON."""
    
    print("\n" + "="*60)
    print("WEEKLY KPI FETCHER — Started at", datetime.utcnow().isoformat() + "Z")
    print("="*60 + "\n")
    
    data = load_kpis()
    
    # 1. GitHub
    print("1. GitHub AI Repo Stars")
    github = fetch_github_ai_repos()
    if github:
        update_kpi(data, "github_ai_stars_top10", github['total_stars_top10'], unit="stars")
        print(f"   ✓ Top 10 repos: {github['total_stars_top10']:,} stars")
        print(f"     Most starred: {github['most_starred_repo']} ({github['most_starred_count']:,})")
    else:
        log_error(data, "github_ai_repos", "Failed to fetch")
        print("   ✗ Failed")
    
    # 2. HuggingFace
    print("\n2. HuggingFace Model Downloads")
    hf = fetch_hugging_face_models()
    if hf and hf.get('total_downloads_top20'):
        update_kpi(data, "huggingface_downloads_top20", hf['total_downloads_top20'], unit="downloads")
        print(f"   ✓ Top 20 models: {hf['total_downloads_top20']:,} downloads")
        print(f"     Most downloaded: {hf['most_downloaded']}")
    else:
        log_error(data, "huggingface_models", "Failed to fetch or no data")
        print("   ✗ Failed")
    
    # 3. Job Postings
    print("\n3. AI Job Postings")
    jobs = fetch_ai_job_postings()
    if jobs and jobs.get('ai_job_postings'):
        update_kpi(data, "ai_job_postings", jobs['ai_job_postings'], unit="postings")
        print(f"   ✓ {jobs['ai_job_postings']:,} postings found")
    else:
        log_error(data, "ai_job_postings", "Failed to fetch (Indeed blocks scrapers)")
        print("   ✗ Failed (Indeed actively blocks scrapers — recommend job board API)")
    
    # 4. OpenRouter Token Throughput
    print("\n4. OpenRouter — Token Throughput")
    or_data = fetch_openrouter_token_throughput()
    if or_data:
        update_kpi(data, "openrouter_throughput_status", or_data.get('openrouter_status', 'unknown'))
        print("   ✓ OpenRouter data accessible")
    else:
        log_error(data, "openrouter_throughput", "Failed to fetch")
        print("   ✗ Failed")
    
    # Save and print summary
    update_frequency_timestamp(data, "weekly")
    save_kpis(data)
    print_summary(data, "weekly")


if __name__ == "__main__":
    main()
