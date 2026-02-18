import os
import re
import time
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, Response, url_for
from bs4 import BeautifulSoup

app = Flask(__name__)

# -------------------------
# Config
# -------------------------
TARGET_BASE = os.getenv("TARGET_BASE", "https://pakistandatabase.com")
TARGET_PATH = os.getenv("TARGET_PATH", "/databases/sim.php")
ALLOW_UPSTREAM = True
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "1.0"))
LAST_CALL = {"ts": 0.0}

COPYRIGHT_HANDLE = os.getenv("COPYRIGHT_HANDLE", "@Akashishare")
COPYRIGHT_NOTICE = "👉🏻 " + COPYRIGHT_HANDLE

# -------------------------
# API KEYS DATABASE (Hardcoded for Vercel)
# -------------------------
API_KEYS = {
    "AKASH_PARMA": {
        "name": "Premium User",
        "expiry": "2030-03-30",
        "status": "active"
    },
    "AKASH_PAID3DAYS": {
        "name": "Free Trial",
        "expiry": "2026-02-31",
        "status": "active"
    },
    "AKASH_PAID31DAYS": {
        "name": "Free Trial",
        "expiry": "2026-02-31",
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
    if is_mobile(v):
        return "mobile", v
    if is_cnic(v):
        return "cnic", v
    raise ValueError("Invalid query. Use mobile with country code (92...) or CNIC (13 digits).")

def rate_limit_wait():
    now = time.time()
    elapsed = now - LAST_CALL["ts"]
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_CALL["ts"] = time.time()

def fetch_upstream(query_value: str):
    if not ALLOW_UPSTREAM:
        raise PermissionError("Upstream fetching disabled.")
    rate_limit_wait()
    session = requests.Session()
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
        "Referer": TARGET_BASE.rstrip("/") + "/",
        "Accept-Language": "en-US,en;q=0.9",
    }
    url = TARGET_BASE.rstrip("/") + TARGET_PATH
    data = {"search_query": query_value}
    resp = session.post(url, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    return resp.text

def parse_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "api-response"}) or soup.find("table")
    if not table:
        return []
    tbody = table.find("tbody")
    if not tbody:
        return []
    results = []
    for tr in tbody.find_all("tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 4:
            results.append({
                "mobile": cols[0],
                "name": cols[1],
                "cnic": cols[2],
                "address": cols[3]
                # Operator field removed as requested
            })
    return results

def validate_api_key(api_key: str):
    """Validate API key and check expiry"""
    if not api_key:
        return False, {"error": "API Key missing! Use ?key=YOUR_KEY"}
    
    key_data = API_KEYS.get(api_key)
    if not key_data:
        return False, {"error": "Invalid API Key! Access Denied."}
    
    # Check expiry
    expiry_date = datetime.strptime(key_data["expiry"], "%Y-%m-%d")
    today = datetime.now()
    
    if today > expiry_date:
        return False, {"error": f"API Key expired on {key_data['expiry']}"}
    
    # Calculate days remaining
    days_remaining = (expiry_date - today).days
    
    key_info = {
        "key_name": key_data["name"],
        "expiry_date": key_data["expiry"],
        "days_remaining": days_remaining,
        "status": "Active"
    }
    
    return True, key_info

def respond_json(obj, pretty=False, status=200):
    if pretty:
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        return Response(text, mimetype="application/json; charset=utf-8", status=status)
    return Response(
        json.dumps(obj, ensure_ascii=False), 
        mimetype="application/json; charset=utf-8",
        status=status
    )

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def home():
    return """
    <h2>🔐 AKASHHACKER - NUMBER INFO API</h2>
    <p>Secure API with Key Authentication</p>
    <p>Use: <code>/api/number?num=92XXXXXXXXXX&key=YOUR_API_KEY</code></p>
    <p>📞 For API Key: Contact @AkashExploits1 on Telegram</p>
    """

@app.route("/api/number", methods=["GET"])
def api_number():
    """Main API endpoint with key authentication"""
    # Get parameters
    number = request.args.get("num")
    api_key = request.args.get("key")
    pretty = request.args.get("pretty") in ("1", "true", "True")
    
    # 1. Validate API Key
    is_valid, key_result = validate_api_key(api_key)
    if not is_valid:
        return respond_json({
            "success": False,
            **key_result
        }, pretty=pretty, status=401)
    
    # 2. Check if number provided
    if not number:
        return respond_json({
            "success": False,
            "error": "Please provide phone number with ?num=92XXXXXXXXXX"
        }, pretty=pretty, status=400)
    
    # 3. Validate number format
    try:
        qtype, normalized = classify_query(number)
    except ValueError as e:
        return respond_json({
            "success": False,
            "error": "Invalid number format",
            "detail": "Use Pakistani mobile with 92XXXXXXXXXX format"
        }, pretty=pretty, status=400)
    
    # 4. Fetch data from upstream
    try:
        html = fetch_upstream(normalized)
        results = parse_table(html)
        
        if not results:
            return respond_json({
                "success": True,
                "developer": "AKASHHACKER",
                "key_details": key_result,
                "query": normalized,
                "query_type": qtype,
                "results_count": 0,
                "data": [],
                "message": "No records found for this number",
                "copyright": COPYRIGHT_NOTICE
            }, pretty=pretty)
        
        # Success response
        return respond_json({
            "success": True,
            "developer": "AKASHHACKER",
            "key_details": key_result,
            "query": normalized,
            "query_type": qtype,
            "results_count": len(results),
            "data": results,
            "copyright": COPYRIGHT_NOTICE
        }, pretty=pretty)
        
    except Exception as e:
        return respond_json({
            "success": False,
            "error": "Fetch failed",
            "detail": str(e),
            "developer": "AKASHHACKER",
            "key_details": key_result
        }, pretty=pretty, status=500)

@app.route("/api/keys", methods=["GET"])
def list_keys():
    """List all API keys (for admin)"""
    admin_key = request.args.get("admin")
    if admin_key != "ADMIN_SECRET_KEY":  # Set in Vercel env
        return respond_json({"error": "Unauthorized"}, status=403)
    
    return respond_json({
        "total_keys": len(API_KEYS),
        "keys": API_KEYS
    }, pretty=True)

@app.route("/health", methods=["GET"])
def health():
    return respond_json({
        "status": "operational",
        "service": "Number Info API",
        "developer": "@Akashishare",
        "keys_active": len([k for k in API_KEYS.values() if k["status"] == "active"]),
        "copyright": COPYRIGHT_NOTICE
    })

# -------------------------
# Vercel Handler
# -------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"🚀 AKASHHACKER API Starting...")
    print(f"📡 Mode: LIVE | Keys: {len(API_KEYS)}")
    app.run(host="0.0.0.0", port=port, debug=False)
