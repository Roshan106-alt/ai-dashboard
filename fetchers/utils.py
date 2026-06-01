"""
Shared utilities for all KPI fetchers.
Handles JSON I/O, HTTP requests, error logging, and data validation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
import requests
from typing import Dict, Any, Optional
import time

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_FILE = DATA_DIR / "kpis.json"


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_kpis() -> Dict[str, Any]:
    """Load current KPI data from JSON file. Return empty template if file doesn't exist."""
    ensure_data_dir()
    
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    
    return {
        "meta": {
            "last_update": None,
            "frequency_last_run": {
                "daily": None,
                "weekly": None,
                "monthly": None,
                "quarterly": None
            }
        },
        "kpis": {},
        "errors": []
    }


def save_kpis(data: Dict[str, Any]):
    """Save KPI data to JSON file."""
    ensure_data_dir()
    data["meta"]["last_update"] = datetime.utcnow().isoformat() + "Z"
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def update_kpi(data: Dict[str, Any], kpi_name: str, value: Any, unit: str = "", 
               change_pct: Optional[float] = None, status: str = "ok"):
    """Update a single KPI in the data structure."""
    if "kpis" not in data:
        data["kpis"] = {}
    data["kpis"][kpi_name] = {
        "value": value,
        "unit": unit,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "change_pct": change_pct,
        "status": status
    }


def log_error(data: Dict[str, Any], kpi_name: str, error: str):
    """Log an error for a KPI."""
    if "errors" not in data:
        data["errors"] = []
    data["errors"] = data["errors"][-49:] if len(data["errors"]) >= 50 else data["errors"]
    data["errors"].append({
        "kpi": kpi_name,
        "error": error,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


def http_get(url: str, headers: Optional[Dict] = None, timeout: int = 10, 
             retries: int = 3) -> Optional[requests.Response]:
    """Make HTTP GET request with retry logic."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    if headers:
        default_headers.update(headers)
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=default_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"  Attempt {attempt + 1} failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  All {retries} attempts failed: {str(e)}")
                return None
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def calculate_pct_change(new_value: float, old_value: float) -> Optional[float]:
    """Calculate percentage change."""
    if old_value == 0 or old_value is None:
        return None
    return round(((new_value - old_value) / abs(old_value)) * 100, 2)


def update_frequency_timestamp(data: Dict[str, Any], frequency: str):
    """Update the last_run timestamp for a frequency tier."""
    if "meta" not in data:
        data["meta"] = {}
    if "frequency_last_run" not in data["meta"]:
        data["meta"]["frequency_last_run"] = {}
    data["meta"]["frequency_last_run"][frequency] = datetime.utcnow().isoformat() + "Z"


def print_summary(data, frequency):
    errors = data.get("errors", [])
    recent_errors = [e for e in errors if frequency in str(e.get("timestamp", ""))]
    print(f"\n{'='*60}")
    print(f"Update complete for {frequency.upper()} tier")
    print(f"Time: {data['meta']['last_update']}")
    print(f"Total KPIs: {len(data['kpis'])}")
    print(f"Recent errors: {len(recent_errors)}")
    if recent_errors:
        for err in recent_errors[-3:]:
            print(f"  - {err['kpi']}: {err['error']}")
    print(f"{'='*60}\n")
