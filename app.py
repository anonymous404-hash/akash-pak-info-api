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

COPYRIGHT_HANDLE = os.getenv("COPYRIGHT_HANDLE", "@AkashHacker")
COPYRIGHT_NOTICE = "👉🏻 " + COPYRIGHT_HANDLE

# -------------------------
# API KEYS DATABASE (Hardcoded for Vercel)
# -------------------------
API_KEYS = {
    "AKASH_PARMA": {
        "name": "Premium User",
        "expiry": "999999",
        "status": "active",
        "daily_limit": ,        # प्रति दिन अधिकतम 1000 कॉल
        "used_today": 0,
        "total_used": 0
    },
    "AKASH_TEST_KEY": {
        "name": "Test User",
        "expiry": "2026-02-20",
        "status": "active",
        "daily_limit": 100,
        "used_today": 0,
        "total_used": 0
    },
    "AKASH_FREE": {
        "name": "Free Trial",
        "expiry": "2026-02-15",
        "status": "active",
        "daily_limit": 10,
        "used_today": 0,
        "total_used": 0
    }
}

# दैनिक रीसेट के लिए अंतिम दिन ट्रैक करें
LAST_RESET_DAY = datetime.now().date()

# -------------------------
# Helpers
# -------------------------
def reset_daily_usage_if_needed():
    """हर दिन सभी कीज़ के used_today को रीसेट करें"""
    global LAST_RESET_DAY
    today = datetime.now().date()
    if today > LAST_RESET_DAY:
        for key_data in API_KEYS.values():
            key_data["used_today"] = 0
        LAST_RESET_DAY = today

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
            })
    return results

def validate_api_key(api_key: str):
    """Validate API key, check expiry and daily limit"""
    if not api_key:
        return False, {"error": "API Key missing! Use ?key=YOUR_KEY"}
    
    # पहले दैनिक रीसेट करें अगर जरूरी हो
    reset_daily_usage_if_needed()
    
    key_data = API_KEYS.get(api_key)
    if not key_data:
        return False, {"error": "Invalid API Key! Access Denied."}
    
    # Check expiry
    expiry_date = datetime.strptime(key_data["expiry"], "%Y-%m-%d")
    today = datetime.now()
    
    if today > expiry_date:
        return False, {"error": f"API Key expired on {key_data['expiry']}"}
    
    # Check daily limit
    if key_data["used_today"] >= key_data["daily_limit"]:
        return False, {
            "error": "Daily limit exceeded",
            "limit": key_data["daily_limit"],
            "used_today": key_data["used_today"]
        }
    
    # Calculate days remaining
    days_remaining = (expiry_date - today).days
    
    key_info = {
        "key_name": key_data["name"],
        "expiry_date": key_data["expiry"],
        "days_remaining": days_remaining,
        "status": "Active",
        "daily_limit": key_data["daily_limit"],
        "used_today": key_data["used_today"],
        "remaining_today": key_data["daily_limit"] - key_data["used_today"]
    }
    
    return True, key_info

def increment_usage(api_key: str):
    """API key के उपयोग की गिनती बढ़ाएँ"""
    if api_key in API_KEYS:
        API_KEYS[api_key]["used_today"] += 1
        API_KEYS[api_key]["total_used"] += 1

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
    <p>Secure API with Key Authentication & Daily Limits</p>
    <p>Use: <code>/api/number?num=92XXXXXXXXXX&key=YOUR_API_KEY</code></p>
    <p>📞 For API Key: Contact @AkashExploits1 on Telegram</p>
    """

@app.route("/api/number", methods=["GET"])
def api_number():
    """Main API endpoint with key authentication and daily limits"""
    # Get parameters
    number = request.args.get("num")
    api_key = request.args.get("key")
    pretty = request.args.get("pretty") in ("1", "true", "True")
    
    # 1. Validate API Key (includes expiry and daily limit)
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
    
    # 4. अब उपयोग बढ़ाएँ (हम इसे सफलता के बाद भी कर सकते हैं, लेकिन यहाँ पहले कर रहे हैं)
    increment_usage(api_key)
    
    # 5. Fetch data from upstream
    try:
        html = fetch_upstream(normalized)
        results = parse_table(html)
        
        if not results:
            # उपयोग पहले ही बढ़ चुका है, लेकिन हम key_details को अपडेट करेंगे
            # वर्तमान key_details प्राप्त करें (फिर से validate न करें)
            key_data = API_KEYS[api_key]
            expiry_date = datetime.strptime(key_data["expiry"], "%Y-%m-%d")
            days_remaining = (expiry_date - datetime.now()).days
            key_details = {
                "key_name": key_data["name"],
                "expiry_date": key_data["expiry"],
                "days_remaining": days_remaining,
                "status": "Active",
                "daily_limit": key_data["daily_limit"],
                "used_today": key_data["used_today"],
                "remaining_today": key_data["daily_limit"] - key_data["used_today"]
            }
            return respond_json({
                "success": True,
                "developer": "AKASHHACKER",
                "key_details": key_details,
                "query": normalized,
                "query_type": qtype,
                "results_count": 0,
                "data": [],
                "message": "No records found for this number",
                "copyright": COPYRIGHT_NOTICE
            }, pretty=pretty)
        
        # Success response – key_details को नए सिरे से लें (used_today अपडेट हो चुका है)
        key_data = API_KEYS[api_key]
        expiry_date = datetime.strptime(key_data["expiry"], "%Y-%m-%d")
        days_remaining = (expiry_date - datetime.now()).days
        key_details = {
            "key_name": key_data["name"],
            "expiry_date": key_data["expiry"],
            "days_remaining": days_remaining,
            "status": "Active",
            "daily_limit": key_data["daily_limit"],
            "used_today": key_data["used_today"],
            "remaining_today": key_data["daily_limit"] - key_data["used_today"]
        }
        
        return respond_json({
            "success": True,
            "developer": "AKASHHACKER",
            "key_details": key_details,
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
            "key_details": key_result  # validation से प्राप्त key_details
        }, pretty=pretty, status=500)

@app.route("/api/keys", methods=["GET"])
def list_keys():
    """List all API keys (for admin)"""
    admin_key = request.args.get("admin")
    if admin_key != "ADMIN_SECRET_KEY":  # Set in Vercel env
        return respond_json({"error": "Unauthorized"}, status=403)
    
    # केवल सार्वजनिक जानकारी दिखाएँ, used_today आदि न दिखाएँ
    public_keys = {}
    for k, v in API_KEYS.items():
        public_keys[k] = {
            "name": v["name"],
            "expiry": v["expiry"],
            "status": v["status"],
            "daily_limit": v["daily_limit"]
        }
    
    return respond_json({
        "total_keys": len(API_KEYS),
        "keys": public_keys
    }, pretty=True)

@app.route("/health", methods=["GET"])
def health():
    return respond_json({
        "status": "operational",
        "service": "Number Info API",
        "developer": "AKASHHACKER",
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
    print(f"⏰ Daily reset enabled")
    app.run(host="0.0.0.0", port=port, debug=False)
