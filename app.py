import os
import sys
import subprocess
import threading
import time
import random
import atexit
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit

from firebase_client import (
    firebase, get_user, create_user, update_user, get_user_balance,
    add_balance, deduct_balance, activate_premium, check_premium_expiry,
    get_premium_remaining, save_bot_session, enable_bot, disable_bot,
    verify_payment_trx, mark_trx_used,
    get_all_packages, get_active_packages, create_package,
    update_package, delete_package, toggle_package,
    extend_user_premium, force_expire_user,
    get_system_settings, update_system_settings
)

os.environ['PYTHONUNBUFFERED'] = '1'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "MOHASIN_TXT_SUPER_SECRET_2026_X99")

socketio = SocketIO(
    app, cors_allowed_origins="*", async_mode='threading',
    ping_timeout=60, ping_interval=25
)

user_sessions = {}
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "MOHASIN_ADMIN_2026")

# ═══════════════════════════════════════════
# CLEANUP & MONITORS
# ═══════════════════════════════════════════
def cleanup_processes():
    for username, data in list(user_sessions.items()):
        if data.get('running') and data.get('proc'):
            try:
                data['proc'].terminate()
            except:
                pass

atexit.register(cleanup_processes)

def heartbeat_monitor():
    while True:
        try:
            for username, data in list(user_sessions.items()):
                if data.get('running') and data.get('proc'):
                    if data['proc'].poll() is not None:
                        try:
                            proc = subprocess.Popen(
                                [sys.executable, '-u', 'main.py'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True,
                                cwd=BASE_DIR
                            )
                            data['proc'] = proc
                            data['start_time'] = datetime.now()
                            threading.Thread(target=stream_logs, args=(proc, username), daemon=True).start()
                            socketio.emit('status_update', {'running': True, 'user': username, 'restarted': True})
                        except Exception as e:
                            print(f"❌ Restart: {e}")
        except Exception as e:
            print(f"Heartbeat: {e}")
        time.sleep(30)

def expiry_monitor():
    while True:
        try:
            for username, data in list(user_sessions.items()):
                user_id = data.get('user_id')
                if not user_id:
                    continue
                if not check_premium_expiry(user_id):
                    if data.get('running'):
                        if data.get('proc'):
                            try:
                                data['proc'].terminate()
                            except:
                                pass
                        data['running'] = False
                        disable_bot(user_id)
                        socketio.emit('status_update', {'running': False, 'user': username, 'premium_expired': True})
        except Exception as e:
            print(f"Expiry: {e}")
        time.sleep(300)

def keep_alive_ping():
    import requests
    while True:
        try:
            port = int(os.environ.get("PORT", 8080))
            requests.get(f'http://127.0.0.1:{port}/health', timeout=5, verify=False)
        except:
            pass
        time.sleep(300)

def stream_logs(proc, username):
    try:
        while True:
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            if line:
                socketio.emit('new_log', {'data': line.strip(), 'user': username})
            else:
                time.sleep(0.1)
    except Exception as e:
        print(f"Log: {e}")

threading.Thread(target=heartbeat_monitor, daemon=True).start()
threading.Thread(target=expiry_monitor, daemon=True).start()
threading.Thread(target=keep_alive_ping, daemon=True).start()

# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════
def login_required(f):
    def wrap(*args, **kwargs):
        if 'logged_in' in session and 'user_id' in session:
            return f(*args, **kwargs)
        return redirect(url_for('login_page'))
    wrap.__name__ = f.__name__
    return wrap

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

# ═══════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════
@app.route('/login')
def login_page():
    if 'logged_in' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Username & password required"})
    if len(username) < 3 or len(password) < 4:
        return jsonify({"status": "error", "message": "Username min 3, password min 4"})

    users = firebase.get("users") or {}
    for uid, u in users.items():
        if str(u.get("username", "")).lower() == username.lower():
            return jsonify({"status": "error", "message": "❌ Username already taken!"})

    user_id = str(random.randint(100000, 999999))
    ip = get_client_ip()
    result = create_user(user_id, username, password, email, ip)

    if not result["success"]:
        return jsonify({"status": "error", "message": result.get("error", "Registration failed")})

    return jsonify({"status": "success", "message": "✅ Account created! Please login.", "user_id": user_id})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "Required"})

    if username == "admin" and password == ADMIN_PASSWORD:
        session['logged_in'] = True
        session['is_admin'] = True
        session['user_id'] = "admin"
        session['username'] = "admin"
        return jsonify({"status": "success", "is_admin": True})

    users = firebase.get("users") or {}
    for uid, u in users.items():
        db_username = str(u.get("username", "")).strip()
        db_password = str(u.get("password", "")).strip()
        
        if db_username.lower() == username.lower():
            if db_password == password:
                session['logged_in'] = True
                session['user_id'] = uid
                session['username'] = db_username
                session['is_admin'] = False
                return jsonify({"status": "success", "is_admin": False, "user_id": uid})
            else:
                return jsonify({"status": "error", "message": "❌ পাসওয়ার্ড ভুল!"})

    return jsonify({"status": "error", "message": "❌ ইউজারনেম খুঁজে পাওয়া যায়নি!"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    if session.get('is_admin'):
        return render_template('admin.html')
    return render_template('index.html')

# ═══════════════════════════════════════════
# USER APIS
# ═══════════════════════════════════════════
@app.route('/api/user/info')
@login_required
def api_user_info():
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    if is_admin:
        return jsonify({
            "is_admin": True, "username": "admin", "balance": 0,
            "is_premium": True, "premium_remaining": -1, "package_name": "ADMIN",
            "player_uid": "", "bot_uid": ""
        })

    user = get_user(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"})

    remaining = get_premium_remaining(user_id)
    is_premium = user.get("is_premium", False) and remaining > 0

    return jsonify({
        "is_admin": False, "user_id": user_id,
        "username": user.get("username"),
        "balance": float(user.get("balance", 0)),
        "is_premium": is_premium,
        "premium_remaining": remaining,
        "package_name": user.get("package_name", "Free"),
        "player_uid": user.get("player_uid", ""),
        "bot_uid": user.get("bot_uid", "")
    })

@app.route('/api/user/save_account', methods=['POST'])
@login_required
def api_save_account():
    data = request.json
    player_uid = data.get('player_uid', '').strip()
    guest_uid = data.get('guest_uid', '').strip()
    guest_pass = data.get('guest_pass', '').strip()
    
    if not guest_uid or not guest_pass:
        return jsonify({"status": "error", "message": "Guest UID & Password required"})
        
    user_id = session['user_id']
    save_bot_session(user_id, guest_uid, guest_pass, session.get('username', 'User'), player_uid)
    return jsonify({"status": "success", "message": "✅ Account info saved successfully!"})

@app.route('/api/settings')
@login_required
def api_get_settings():
    return jsonify(get_system_settings())

@app.route('/api/packages')
@login_required
def api_packages():
    return jsonify({"packages": get_active_packages()})

@app.route('/api/buy_package', methods=['POST'])
@login_required
def api_buy_package():
    data = request.json
    package_id = data.get('package_id')
    if not package_id:
        return jsonify({"status": "error", "message": "Package ID required"})

    package = firebase.get(f"packages/{package_id}")
    if not package:
        return jsonify({"status": "error", "message": "❌ Not found"})
    if not package.get("enabled", True):
        return jsonify({"status": "error", "message": "❌ Disabled"})

    user_id = session['user_id']
    balance = get_user_balance(user_id)
    price = float(package.get("price", 0))

    if balance < price:
        return jsonify({"status": "error", "message": f"❌ Need ৳{price}, have ৳{balance}"})

    ok, msg = deduct_balance(user_id, price)
    if not ok:
        return jsonify({"status": "error", "message": msg})

    result = activate_premium(user_id, package.get("days", 30), package.get("name"))
    if not result['success']:
        add_balance(user_id, price)
        return jsonify({"status": "error", "message": "Failed"})

    firebase.push(f"transactions/{user_id}", {
        "type": "Package Purchase", "package": package.get("name"),
        "amount": price, "days": package.get("days"),
        "date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "time": int(time.time())
    })

    return jsonify({
        "status": "success",
        "message": f"✅ {package.get('name')} activated!",
        "new_balance": get_user_balance(user_id)
    })

# ═══════════════════════════════════════════
# BOT CONTROL
# ═══════════════════════════════════════════
@app.route('/api/bot/start', methods=['POST'])
@login_required
def api_bot_start():
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    username = session.get('username', 'user')

    if not is_admin:
        if not check_premium_expiry(user_id):
            return jsonify({"status": "error", "message": "❌ Premium নেই বা expire!"})

    user = get_user(user_id)
    if not user and not is_admin:
        return jsonify({"status": "error", "message": "User not found"})
        
    guest_uid = user.get("bot_uid", "") if user else ""
    guest_password = user.get("bot_password", "") if user else ""
    player_uid = user.get("player_uid", "") if user else ""
    bot_name = user.get("bot_name", username) if user else username

    if not guest_uid or not guest_password:
        return jsonify({"status": "error", "message": "❌ গেমের UID/PW সেভ করা নেই! আগে Save Account করুন।"})

    if username in user_sessions and user_sessions[username].get('running'):
        return jsonify({"status": "error", "message": "Bot already running"})

    try:
        with open(os.path.join(BASE_DIR, 'MOHASIN.py'), 'w', encoding='utf-8') as f:
            f.write(f"UID = '{guest_uid}'\nPW = '{guest_password}'\n")
            f.write(f'REGION_PREF = "BD"\nADMIN_UID = "8797238043"\n')
            f.write(f'PLAYER_UID = "{player_uid}"\n')

        if not is_admin:
            enable_bot(user_id)

        proc = subprocess.Popen(
            [sys.executable, '-u', 'main.py'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
            cwd=BASE_DIR
        )

        user_sessions[username] = {
            'proc': proc, 'running': True,
            'start_time': datetime.now(),
            'uid': guest_uid, 'password': guest_password,
            'player_uid': player_uid,
            'user_id': user_id, 'name': bot_name
        }

        threading.Thread(target=stream_logs, args=(proc, username), daemon=True).start()
        return jsonify({"status": "success", "message": "✅ Bot started!", "pid": proc.pid})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed: {str(e)}"})

@app.route('/api/bot/stop', methods=['POST'])
@login_required
def api_bot_stop():
    username = session.get('username', 'user')
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    if username not in user_sessions or not user_sessions[username].get('running'):
        return jsonify({"status": "error", "message": "Not running"})

    try:
        proc = user_sessions[username].get('proc')
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
        user_sessions[username]['running'] = False
        user_sessions[username]['proc'] = None
        if not is_admin:
            disable_bot(user_id)
        return jsonify({"status": "success", "message": "✅ Stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/bot/restart', methods=['POST'])
@login_required
def api_bot_restart():
    username = session.get('username', 'user')
    if username not in user_sessions or not user_sessions[username].get('uid'):
        return jsonify({"status": "error", "message": "No creds"})

    proc = user_sessions[username].get('proc')
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except:
            try:
                proc.kill()
            except:
                pass

    time.sleep(1)
    try:
        proc = subprocess.Popen(
            [sys.executable, '-u', 'main.py'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
            cwd=BASE_DIR
        )
        user_sessions[username]['proc'] = proc
        user_sessions[username]['running'] = True
        user_sessions[username]['start_time'] = datetime.now()
        threading.Thread(target=stream_logs, args=(proc, username), daemon=True).start()
        return jsonify({"status": "success", "message": "✅ Restarted!", "pid": proc.pid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/bot/status')
@login_required
def api_bot_status():
    username = session.get('username', 'user')
    if username in user_sessions and user_sessions[username].get('running'):
        start = user_sessions[username].get('start_time', datetime.now())
        uptime = int((datetime.now() - start).total_seconds())
        return jsonify({"running": True, "uptime": uptime})
    return jsonify({"running": False, "uptime": 0})

# ═══════════════════════════════════════════
# PAYMENT
# ═══════════════════════════════════════════
@app.route('/api/payment/verify', methods=['POST'])
@login_required
def api_payment_verify():
    settings = get_system_settings()
    if not settings.get("payment_enabled", True):
        return jsonify({"status": "error", "message": "⚠️ পেমেন্ট সাময়িকভাবে বন্ধ আছে!"})

    data = request.json
    trx_id = data.get('trx_id', '').strip()
    method = data.get('method', 'bkash').lower()

    if not trx_id:
        return jsonify({"status": "error", "message": "TRX required"})

    result = verify_payment_trx(trx_id, method)
    if not result['success']:
        return jsonify({"status": "error", "message": result['error']})

    user_id = session['user_id']
    amount = result['amount']
    add_balance(user_id, amount)
    mark_trx_used(trx_id, user_id, amount, method)

    firebase.push(f"transactions/{user_id}", {
        "type": "Deposit", "amount": amount, "method": method,
        "trx_id": trx_id,
        "date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "time": int(time.time())
    })

    return jsonify({
        "status": "success",
        "message": f"✅ ৳{amount} added!",
        "amount": amount,
        "new_balance": get_user_balance(user_id)
    })

# ═══════════════════════════════════════════
# ADMIN APIS
# ═══════════════════════════════════════════
@app.route('/api/admin/settings/update', methods=['POST'])
@login_required
def api_admin_update_settings():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})
    
    data = request.json
    update_data = {}
    if 'bkash_number' in data: update_data['bkash_number'] = data['bkash_number']
    if 'nagad_number' in data: update_data['nagad_number'] = data['nagad_number']
    if 'rocket_number' in data: update_data['rocket_number'] = data['rocket_number']
    if 'payment_enabled' in data: update_data['payment_enabled'] = data['payment_enabled']
    
    if update_data:
        update_system_settings(update_data)
        return jsonify({"status": "success", "message": "✅ Settings updated!"})
    return jsonify({"status": "error", "message": "No data"})

@app.route('/api/admin/users')
@login_required
def api_admin_users():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    users = firebase.get("users") or {}
    user_list = []
    for uid, u in users.items():
        user_list.append({
            "user_id": uid, "username": u.get("username"),
            "balance": float(u.get("balance", 0)),
            "is_premium": u.get("is_premium", False),
            "premium_expires": u.get("premium_expires", 0),
            "package_name": u.get("package_name", "Free"),
            "bot_uid": u.get("bot_uid", ""),
            "player_uid": u.get("player_uid", ""),
            "created_at": u.get("created_at", 0)
        })
    return jsonify({"users": user_list})

@app.route('/api/admin/add_balance', methods=['POST'])
@login_required
def api_admin_add_balance():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    user_id = data.get('user_id')
    amount = float(data.get('amount', 0))
    if not user_id or amount <= 0:
        return jsonify({"status": "error", "message": "Invalid"})

    add_balance(user_id, amount)
    firebase.push(f"transactions/{user_id}", {
        "type": "Admin Add", "amount": amount,
        "date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "time": int(time.time())
    })
    return jsonify({"status": "success", "message": f"✅ ৳{amount} added"})

@app.route('/api/admin/set_premium', methods=['POST'])
@login_required
def api_admin_set_premium():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    user_id = data.get('user_id')
    days = float(data.get('days', 30))
    if not user_id:
        return jsonify({"status": "error", "message": "User ID required"})

    result = activate_premium(user_id, days, f"Admin {days}d")
    if result['success']:
        return jsonify({"status": "success", "message": f"✅ {days}d added"})
    return jsonify({"status": "error", "message": "Failed"})

@app.route('/api/admin/revoke_premium', methods=['POST'])
@login_required
def api_admin_revoke_premium():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Required"})

    firebase.patch(f"users/{user_id}", {
        "is_premium": False, "premium_expires": 0, "bot_enabled": False
    })
    return jsonify({"status": "success", "message": "✅ Revoked"})

@app.route('/api/admin/user/extend_premium', methods=['POST'])
@login_required
def api_admin_extend_premium():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    user_id = data.get('user_id')
    days = data.get('days', 30)
    if not user_id:
        return jsonify({"status": "error", "message": "Required"})

    result = extend_user_premium(user_id, float(days))
    if result['success']:
        return jsonify({"status": "success", "message": f"✅ {days}d extended"})
    return jsonify({"status": "error", "message": "Failed"})

@app.route('/api/admin/user/force_expire', methods=['POST'])
@login_required
def api_admin_force_expire():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Required"})

    force_expire_user(user_id)
    return jsonify({"status": "success", "message": "✅ Force expired"})

@app.route('/api/admin/packages')
@login_required
def api_admin_packages():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    packages = get_all_packages()
    pkg_list = list(packages.values())
    pkg_list.sort(key=lambda x: x.get("order", 999))
    return jsonify({"packages": pkg_list})

@app.route('/api/admin/package/create', methods=['POST'])
@login_required
def api_admin_create_package():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    name = data.get('name', '').strip()
    days = data.get('days')
    price = data.get('price')
    features = data.get('features', [])
    badge_color = data.get('badge_color', '#ff6b35')

    if not name:
        return jsonify({"status": "error", "message": "Package Name required!"})

    try:
        days = float(days)
        price = float(price)
        if days <= 0:
            return jsonify({"status": "error", "message": "Days must be greater than 0!"})
        if price < 0:
            return jsonify({"status": "error", "message": "Price cannot be negative!"})
    except Exception as e:
        return jsonify({"status": "error", "message": "Days and Price must be valid numbers!"})

    # Features যদি স্ট্রিং হিসেবে আসে, তবে লিস্টে কনভার্ট করা
    if isinstance(features, str):
        features = [f.strip() for f in features.split('\n') if f.strip()]

    result = create_package(name, days, price, features, badge_color)
    if result['success']:
        return jsonify({"status": "success", "message": f"✅ {name} created!", "package": result['package']})
    return jsonify({"status": "error", "message": result.get('error', 'Failed to create package')})

@app.route('/api/admin/package/update', methods=['POST'])
@login_required
def api_admin_update_package():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    package_id = data.get('package_id')
    if not package_id:
        return jsonify({"status": "error", "message": "Required"})

    update_fields = {}
    for field in ['name', 'days', 'price', 'features', 'enabled', 'order', 'badge_color']:
        if field in data:
            update_fields[field] = data[field]

    if not update_fields:
        return jsonify({"status": "error", "message": "No fields"})

    result = update_package(package_id, **update_fields)
    if result['success']:
        return jsonify({"status": "success", "message": "✅ Updated!"})
    return jsonify({"status": "error", "message": result.get('error', 'Failed')})

@app.route('/api/admin/package/delete', methods=['POST'])
@login_required
def api_admin_delete_package():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    package_id = data.get('package_id')
    if not package_id:
        return jsonify({"status": "error", "message": "Required"})

    result = delete_package(package_id)
    if result['success']:
        return jsonify({"status": "success", "message": "✅ Deleted!"})
    return jsonify({"status": "error", "message": "Failed"})

@app.route('/api/admin/package/toggle', methods=['POST'])
@login_required
def api_admin_toggle_package():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    data = request.json
    package_id = data.get('package_id')
    if not package_id:
        return jsonify({"status": "error", "message": "Required"})

    result = toggle_package(package_id)
    if result['success']:
        status = "enabled" if result['enabled'] else "disabled"
        return jsonify({"status": "success", "message": f"✅ {status}", "enabled": result['enabled']})
    return jsonify({"status": "error", "message": "Failed"})

@app.route('/api/admin/stop_all_bots', methods=['POST'])
@login_required
def api_admin_stop_all():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    count = 0
    for username, data in list(user_sessions.items()):
        if data.get('running'):
            proc = data.get('proc')
            if proc:
                try:
                    proc.terminate()
                    count += 1
                except:
                    pass
            data['running'] = False
            data['proc'] = None

    return jsonify({"status": "success", "message": f"✅ {count} bots stopped"})

@app.route('/api/admin/all_bots')
@login_required
def api_admin_all_bots():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Admin only"})

    bots = []
    for username, data in user_sessions.items():
        if data.get('running'):
            start = data.get('start_time', datetime.now())
            uptime = int((datetime.now() - start).total_seconds())
            bots.append({
                "username": username, "user_id": data.get('user_id'),
                "bot_uid": data.get('uid'), "bot_name": data.get('name'),
                "player_uid": data.get('player_uid'),
                "uptime": uptime,
                "pid": data['proc'].pid if data.get('proc') else None
            })
    return jsonify({"bots": bots})

@app.route('/health')
def health():
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "active_bots": sum(1 for u in user_sessions.values() if u.get('running')),
        "total_users": len(firebase.get("users") or {})
    })

@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)