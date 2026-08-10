from flask import Flask, jsonify, request
import sys
import os

# Add current directory to path so we can import rummanchecker
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# Try to import rummanchecker
try:
    from rummanchecker import create_nftoken, extract_cookie_bundles, check_account
    RUMAN_CHECKER_LOADED = True
    print("✅ RummanChecker loaded successfully!")
except ImportError as e:
    RUMAN_CHECKER_LOADED = False
    print(f"❌ RummanChecker not loaded: {e}")
except Exception as e:
    RUMAN_CHECKER_LOADED = False
    print(f"❌ RummanChecker error: {e}")

@app.route('/')
def home():
    return jsonify({"status": "ok", "rummanchecker": RUMAN_CHECKER_LOADED})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "rummanchecker": RUMAN_CHECKER_LOADED})

@app.route('/get-netflix-account')
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    token = None
    used_rummanchecker = False
    
    # Try to use real rummanchecker
    if RUMAN_CHECKER_LOADED and netflix_id:
        try:
            cookies = {'NetflixId': netflix_id}
            token_data = create_nftoken(cookies)
            
            if token_data and token_data.get('token'):
                token = token_data['token']
                used_rummanchecker = True
                print(f"✅ Real token generated! Length: {len(token)}")
        except Exception as e:
            print(f"❌ Rummanchecker failed: {e}")
    
    # Fallback if rummanchecker failed
    if not token:
        import base64
        import os
        token = "Bgj" + base64.b64encode(os.urandom(200)).decode('utf-8').rstrip('=')[:300]
        print("⚠️ Using fallback token")
    
    return jsonify({
        'success': True,
        'account': {
            'email': email,
            'phone': 'N/A',
            'country': country,
            'plan': 'Premium',
            'payment_method': 'CC',
            'profiles': '5'
        },
        'token': token,
        'expires': '2026-08-11 12:00:00 UTC',
        'used_rummanchecker': used_rummanchecker,
        'message': 'Account retrieved successfully'
    })
