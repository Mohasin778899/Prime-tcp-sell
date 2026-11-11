import urllib3
import requests
import time
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FIREBASE_URL = "https://garena-es-13d62-default-rtdb.asia-southeast1.firebasedatabase.app"

class Firebase:
    def __init__(self, url=FIREBASE_URL):
        self.url = url.rstrip('/')
    
    def get(self, path):
        try:
            r = requests.get(f"{self.url}/{path}.json", timeout=15, verify=False)
            return r.json() if r.status_code == 200 else None
        except:
            return None
    
    def put(self, path, data):
        try:
            r = requests.put(f"{self.url}/{path}.json", json=data, timeout=15, verify=False)
            return r.status_code == 200
        except:
            return False
    
    def patch(self, path, data):
        try:
            r = requests.patch(f"{self.url}/{path}.json", json=data, timeout=15, verify=False)
            return r.status_code == 200
        except:
            return False
    
    def push(self, path, data):
        try:
            r = requests.post(f"{self.url}/{path}.json", json=data, timeout=15, verify=False)
            return r.json().get("name") if r.status_code == 200 else None
        except:
            return None
    
    def delete(self, path):
        try:
            r = requests.delete(f"{self.url}/{path}.json", timeout=15, verify=False)
            return r.status_code == 200
        except:
            return False

firebase = Firebase()

# ═══════════════════════════════════════════
# DEFAULT PACKAGES
# ═══════════════════════════════════════════
DEFAULT_PACKAGES = {
    "pkg_0": {
        "id": "pkg_0", "name": "🎁 Free Trial", "days": 0.3, "price": 0,
        "features": ["7 Hours Trial", "Basic Features", "One Time Use"],
        "enabled": True, "order": 0, "badge_color": "#4ade80",
        "created_at": int(time.time())
    },
    "pkg_1": {
        "id": "pkg_1", "name": "🥉 Bronze", "days": 7, "price": 150,
        "features": ["7 Days Premium", "Auto Payment", "Basic Features"],
        "enabled": True, "order": 1, "badge_color": "#cd7f32",
        "created_at": int(time.time())
    },
    "pkg_2": {
        "id": "pkg_2", "name": "🥈 Silver", "days": 15, "price": 300,
        "features": ["15 Days Premium", "Auto Payment", "All Features"],
        "enabled": True, "order": 2, "badge_color": "#c0c0c0",
        "created_at": int(time.time())
    },
    "pkg_3": {
        "id": "pkg_3", "name": "🥇 Gold", "days": 30, "price": 550,
        "features": ["30 Days Premium", "Auto Payment", "All Features", "Priority Support"],
        "enabled": True, "order": 3, "badge_color": "#ffd700",
        "created_at": int(time.time())
    },
    "pkg_4": {
        "id": "pkg_4", "name": "💎 Diamond", "days": 90, "price": 1500,
        "features": ["90 Days Premium", "Auto Payment", "All Features", "Priority Support", "Special Badge"],
        "enabled": True, "order": 4, "badge_color": "#00ffff",
        "created_at": int(time.time())
    }
}

# ═══════════════════════════════════════════
# SYSTEM SETTINGS
# ═══════════════════════════════════════════
def get_system_settings():
    settings = firebase.get("system_settings")
    if not settings:
        default = {
            "bkash_number": "01328498160",
            "nagad_number": "01328498160",
            "rocket_number": "01328498160",
            "payment_enabled": True
        }
        firebase.put("system_settings", default)
        return default
    return settings

def update_system_settings(data):
    return firebase.patch("system_settings", data)

# ═══════════════════════════════════════════
# PACKAGE MANAGEMENT
# ═══════════════════════════════════════════
def get_all_packages():
    packages = firebase.get("packages")
    if not packages:
        firebase.put("packages", DEFAULT_PACKAGES)
        return DEFAULT_PACKAGES
    return packages

def get_active_packages():
    packages = get_all_packages()
    active = [p for p in packages.values() if p.get("enabled", True)]
    active.sort(key=lambda x: x.get("order", 999))
    return active

def create_package(name, days, price, features=None, badge_color="#ff6b35"):
    packages = get_all_packages()
    
    # নতুন প্যাকেজের জন্য আইডি জেনারেট করা
    existing_ids = []
    for k in packages.keys():
        if k.startswith("pkg_"):
            try:
                existing_ids.append(int(k.replace("pkg_", "")))
            except:
                pass
                
    new_num = max(existing_ids) + 1 if existing_ids else 1
    new_id = f"pkg_{new_num}"
    max_order = max([p.get("order", 0) for p in packages.values()], default=0)
    
    # ডাটা টাইপ নিশ্চিত করা
    try:
        days_val = float(days)
        price_val = float(price)
    except:
        days_val = 0.0
        price_val = 0.0

    package_data = {
        "id": new_id, 
        "name": name, 
        "days": days_val, 
        "price": price_val,
        "features": features or [f"{days_val} Days Premium", "Auto Payment"],
        "enabled": True, 
        "order": max_order + 1,
        "badge_color": badge_color, 
        "created_at": int(time.time())
    }
    firebase.put(f"packages/{new_id}", package_data)
    return {"success": True, "package": package_data}

def update_package(package_id, **kwargs):
    package = firebase.get(f"packages/{package_id}")
    if not package:
        return {"success": False, "error": "Package not found"}
    
    update_data = {}
    allowed_fields = ["name", "days", "price", "features", "enabled", "order", "badge_color"]
    for key, value in kwargs.items():
        if key in allowed_fields:
            if key == "days": update_data[key] = float(value)
            elif key == "price": update_data[key] = float(value)
            elif key == "order": update_data[key] = int(value)
            elif key == "enabled": update_data[key] = bool(value)
            else: update_data[key] = value
    
    if not update_data:
        return {"success": False, "error": "No valid fields"}
    
    firebase.patch(f"packages/{package_id}", update_data)
    return {"success": True, "updated": update_data}

def delete_package(package_id):
    package = firebase.get(f"packages/{package_id}")
    if not package:
        return {"success": False, "error": "Package not found"}
    firebase.delete(f"packages/{package_id}")
    return {"success": True}

def toggle_package(package_id):
    package = firebase.get(f"packages/{package_id}")
    if not package:
        return {"success": False, "error": "Package not found"}
    new_status = not package.get("enabled", True)
    firebase.patch(f"packages/{package_id}", {"enabled": new_status})
    return {"success": True, "enabled": new_status}

# ═══════════════════════════════════════════
# USER HELPERS
# ═══════════════════════════════════════════
def get_user(user_id):
    return firebase.get(f"users/{user_id}")

def create_user(user_id, username, password, email=None, ip_address=None):
    if ip_address:
        existing = firebase.get(f"ip_accounts/{ip_address.replace('.', '_')}")
        if existing:
            return {"success": False, "error": "❌ একটি IP থেকে শুধু ১টি অ্যাকাউন্ট!"}
    
    user_data = {
        "user_id": str(user_id), 
        "username": str(username).strip(),
        "password": str(password).strip(),
        "email": email or "", 
        "balance": 0, 
        "is_premium": False,
        "premium_expires": 0, 
        "package_name": "Free",
        "created_at": int(time.time()), 
        "ip_address": ip_address or "",
        "bot_uid": "", 
        "bot_password": "", 
        "bot_name": "",
        "player_uid": "",
        "bot_enabled": False, 
        "total_orders": 0, 
        "total_spent": 0
    }
    
    saved = firebase.put(f"users/{user_id}", user_data)
    if not saved:
        return {"success": False, "error": "❌ Firebase-এ ডাটা সেভ হয়নি! Rules চেক করুন।"}

    if ip_address:
        firebase.put(f"ip_accounts/{ip_address.replace('.', '_')}", {
            "user_id": str(user_id), 
            "created_at": int(time.time())
        })
        
    return {"success": True, "user": user_data}

def update_user(user_id, data):
    return firebase.patch(f"users/{user_id}", data)

def get_user_balance(user_id):
    user = get_user(user_id)
    return float(user.get("balance", 0)) if user else 0

def add_balance(user_id, amount):
    user = get_user(user_id)
    if not user: return False
    new_bal = float(user.get("balance", 0)) + float(amount)
    firebase.patch(f"users/{user_id}", {"balance": new_bal})
    return True

def deduct_balance(user_id, amount):
    user = get_user(user_id)
    if not user: return False, "User not found"
    bal = float(user.get("balance", 0))
    if bal < float(amount): return False, "Insufficient balance"
    firebase.patch(f"users/{user_id}", {"balance": bal - float(amount)})
    return True, "Success"

# ═══════════════════════════════════════════
# PREMIUM
# ═══════════════════════════════════════════
def activate_premium(user_id, duration_days, package_name):
    user = get_user(user_id)
    if not user:
        return {"success": False, "error": "User not found"}
    
    now = int(time.time())
    current_expiry = int(user.get("premium_expires", 0))
    start_time = current_expiry if current_expiry > now else now
    # Fractional days handling (for trial)
    new_expiry = start_time + int(float(duration_days) * 86400)
    
    firebase.patch(f"users/{user_id}", {
        "is_premium": True, "premium_expires": new_expiry,
        "package_name": package_name, "premium_started": now
    })
    firebase.push(f"premium_history/{user_id}", {
        "package": package_name, "duration": duration_days,
        "activated_at": now, "expires_at": new_expiry
    })
    return {"success": True, "expires_at": new_expiry}

def check_premium_expiry(user_id):
    user = get_user(user_id)
    if not user or not user.get("is_premium", False): return False
    expiry = int(user.get("premium_expires", 0))
    now = int(time.time())
    if now > expiry:
        firebase.patch(f"users/{user_id}", {"is_premium": False, "bot_enabled": False})
        return False
    return True

def get_premium_remaining(user_id):
    user = get_user(user_id)
    if not user or not user.get("is_premium"): return 0
    expiry = int(user.get("premium_expires", 0))
    return max(0, expiry - int(time.time()))

def extend_user_premium(user_id, additional_days):
    user = get_user(user_id)
    if not user: return {"success": False, "error": "User not found"}
    now = int(time.time())
    current_expiry = int(user.get("premium_expires", 0))
    base = current_expiry if current_expiry > now else now
    new_expiry = base + int(float(additional_days) * 86400)
    firebase.patch(f"users/{user_id}", {"is_premium": True, "premium_expires": new_expiry})
    return {"success": True, "new_expiry": new_expiry}

def force_expire_user(user_id):
    firebase.patch(f"users/{user_id}", {
        "is_premium": False, "premium_expires": 0, "bot_enabled": False
    })
    return {"success": True}

# ═══════════════════════════════════════════
# BOT SESSION
# ═══════════════════════════════════════════
def save_bot_session(user_id, bot_uid, bot_password, name, player_uid=""):
    firebase.patch(f"users/{user_id}", {
        "bot_uid": bot_uid, "bot_password": bot_password, "bot_name": name,
        "player_uid": player_uid
    })

def enable_bot(user_id):
    firebase.patch(f"users/{user_id}", {"bot_enabled": True})

def disable_bot(user_id):
    firebase.patch(f"users/{user_id}", {"bot_enabled": False})

# ═══════════════════════════════════════════
# PAYMENT
# ═══════════════════════════════════════════
def verify_payment_trx(trx_id, method="bkash"):
    used = firebase.get(f"Auto Pay/{trx_id}")
    if used:
        return {"success": False, "error": "❌ এই TRX আগে ব্যবহার হয়েছে!"}
    
    all_payments = firebase.get("XNXANIKPAY")
    if not all_payments:
        return {"success": False, "error": "❌ SMS ডাটা নেই!"}
    
    found = None
    for key, payment in all_payments.items():
        if str(payment.get("txid", "")).strip().lower() == trx_id.lower():
            found = payment
            break
    
    if not found:
        return {"success": False, "error": "❌ TRX পাওয়া যায়নি!\n⏳ ১-২ মিনিট অপেক্ষা করুন"}
    
    try:
        amount = float(found.get("amount", 0))
    except:
        return {"success": False, "error": "❌ ভুল amount!"}
    
    if amount < 10:
        return {"success": False, "error": "❌ মিনিমাম ৳10!"}
    
    return {"success": True, "amount": amount, "trx_id": trx_id, "method": method}

def mark_trx_used(trx_id, user_id, amount, method):
    firebase.put(f"Auto Pay/{trx_id}", {
        "amount": amount, "usedBy": str(user_id), "method": method,
        "time": int(time.time()), "date": datetime.now().strftime("%d-%m-%Y %I:%M %p")
    })