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
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_kpis():
    ensure_data_dir()
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"meta": {"last_update": None, "frequency_last_run": {"daily": None, "weekly": None, "monthly": None, "quarterly": None}}, "kpis": {}, "errors": []}

def save_kpis(data):
    ensure_data_dir()
    data["meta"]["last_update"] = datetime.utcnow().isoformat() + "Z"
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def update_kpi(data, kpi_name, value, unit="", change_pct=None, status="ok"):
    if "kpis" not in data:
        data["kpis"] = {}
    data["kpis"][kpi_name] = {"value": value, "unit": unit, "timestamp": datetime.utcnow().isoformat() + "Z", "change_pct": change_pct, "status": status}

def log_error(data, kpi_name, error):
    if "errors" not in data:
        data["errors"] = []
    data["errors"] = data["errors"][-49:] if len(data["errors"]) >= 50 else data["errors"]
    data["errors"].append({"kpi": kpi_name, "error": error, "timestamp": datetime.utcnow().isoformat() + "Z"})

def http_get(url, headers=None, timeout=10, retries=3):
    default_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if headers:
        default_headers.update(headers)
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=default_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    return None

def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def calculate_pct_change(new_value, old_value):
    if old_value == 0 or old_value is None:
        return None
    return round(((new_value - old_value) / abs(old_value)) * 100, 2)

def update_frequency_timestamp(data, frequency):
    if "meta" not in data:
        data["meta"] = {}
    if "frequency_last_run" not in data["meta"]:
        data["meta"]["frequency_last_run"] = {}
    data["meta"]["frequency_last_run"][frequency] = datetime.utcnow().isoformat() + "Z"

def print_summary(data, frequency):
    errors = data.get("errors", [])
    recent_errors = [e for e in errors if frequency in str(e.get("timestamp", ""))]
    print(f"Update complete for {frequency.upper()} tier at {data['meta']['last_update']}")
