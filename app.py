import os
import re
import time
import json
import requests
from datetime import datetime
from flask import Flask, request, Response
from bs4 import BeautifulSoup

app = Flask(__name__)

# -------------------------
# Config - Updated Branding
# -------------------------
TARGET_BASE = os.getenv("TARGET_BASE", "https://pakistandatabase.com")
TARGET_PATH = os.getenv("TARGET_PATH", "/databases/sim.php")
ALLOW_UPSTREAM = True
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "1.0"))
LAST_CALL = {"ts": 0.0}

# Final Branding Update
COPYRIGHT_HANDLE = "@Akash_Exploits_bot"
COPYRIGHT_NOTICE = "👉🏻 " + COPYRIGHT_HANDLE
DEV_NAME = "Akash Exploitss"

# -------------------------
# API KEYS DATABASE
# -------------------------
API_KEYS = {
    "AKASH_PARMA": {
        "name": "Premium User",
        "expiry": "2030-03-30",
        "status": "active"
    },
    "AKASH_PAID30DAYS": {
        "name": "VIP User",
        "expiry": "2026-03-20",
        "status": "active"
    }
}

# -------------------------
# Helpers
# -------------------------
def is_mobile(value: str) -> bool:
    return bool(re.fullmatch(r"92\d{9,12}", (value or "").strip()))

def is_cnic(value: str) -> bool:
    return bool(re.fullmatch(r"\d{13}", (value or "").strip()))

def classify_query(value: str):
    v = value.strip()
    if is_mobile(v): return "mobile", v
    if is_cnic(v): return "cnic", v
    raise ValueError("Invalid format")

def rate_limit_wait():
    now = time.time()
    elapsed = now - LAST_CALL["ts"]
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_CALL["ts"] = time.time()

def fetch_upstream(query_value: str):
    rate_limit_wait()
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": TARGET_BASE.rstrip("/") + "/",
    }
    url = TARGET_BASE.rstrip("/") + TARGET_PATH
    data = {"search_query": query_value}
    resp = session.post(url, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    return resp.text

def parse_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table: return []
    results = []
    for tr in table.find_all("tr")[1:]: # Skip header
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 4:
            results.append({
                "mobile": cols[0],
                "name": cols[1],
                "cnic": cols[2],
                "address": cols[3]
            })
    return results

def validate_api_key(api_key: str):
    if not api_key: return False, {"error": "Key Missing"}
    key_data = API_KEYS.get(api_key)
    if not key_data: return False, {"error": "Access Denied"}
    
    expiry_date = datetime.strptime(key_data["expiry"], "%Y-%m-%d")
    today = datetime.now()
    if today > expiry_date: return False, {"error": "Key Expired"}
    
    return True, {
        "user": key_data["name"],
        "expiry": key_data["expiry"],
        "status": "Active"
    }

def respond_json(obj, status=200):
    return Response(
        json.dumps(obj, indent=2, ensure_ascii=False), 
        mimetype="application/json",
        status=status
    )

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def home():
    return f"""
    <h2>🔐 {DEV_NAME.upper()} - SYSTEM LIVE</h2>
    <p>Developer: {COPYRIGHT_HANDLE}</p>
    <p>Usage: <code>/api/number?num=92XXXXXXXXXX&key=YOUR_KEY</code></p>
    <p>Contact: <a href="https://t.me/Akash_Exploits_bot">Support Bot</a></p>
    """

@app.route("/api/number", methods=["GET"])
def api_number():
    number = request.args.get("num")
    api_key = request.args.get("key")
    
    is_valid, key_info = validate_api_key(api_key)
    if not is_valid: return respond_json({"success": False, **key_info}, status=401)
    
    if not number: return respond_json({"success": False, "error": "Enter Number"}, status=400)
    
    try:
        qtype, normalized = classify_query(number)
        html = fetch_upstream(normalized)
        results = parse_table(html)
        
        return respond_json({
            "success": True,
            "api_owner": DEV_NAME,
            "bot_handle": COPYRIGHT_HANDLE,
            "key_status": key_info,
            "results_count": len(results),
            "data": results,
            "copyright": COPYRIGHT_NOTICE
        })
        
    except Exception as e:
        return respond_json({"success": False, "error": str(e)}, status=500)

@app.route("/health", methods=["GET"])
def health():
    return respond_json({
        "status": "running",
        "developer": COPYRIGHT_HANDLE,
        "system": "TITAN HYPERION V6"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
