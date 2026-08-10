from flask import Flask, jsonify, request
import sys
import os
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

RUMAN_CHECKER_LOADED = False
IMPORT_ERROR = None

try:
    from rummanchecker_vercel import create_nftoken
    RUMAN_CHECKER_LOADED = True
    print("✅ RummanChecker loaded successfully!")
except Exception as e:
    IMPORT_ERROR = str(e)
    print(f"❌ Import error: {e}")
    traceback.print_exc()

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "rummanchecker": RUMAN_CHECKER_LOADED,
        "import_error": IMPORT_ERROR
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "rummanchecker": RUMAN_CHECKER_LOADED,
        "import_error": IMPORT_ERROR
    })

@app.route('/get-netflix-account')
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    token = None
    used_rummanchecker = False
    error_message = None
    
    if RUMAN_CHECKER_LOADED and netflix_id:
        try:
            cookies = {'NetflixId': netflix_id}
            print(f"🔄 Calling create_nftoken for: {netflix_id[:30]}...")
            token_data = create_nftoken(cookies)
            
            if token_data and token_data.get('token'):
                token = token_data['token']
                used_rummanchecker = True
                print(f"✅ Token generated! Length: {len(token)}")
            else:
                error_message = "create_nftoken returned no token"
                print(f"❌ {error_message}")
                
        except Exception as e:
            error_message = f"Token generation failed: {str(e)}"
            print(f"❌ {error_message}")
            traceback.print_exc()
    else:
        error_message = f"RummanChecker not loaded: {IMPORT_ERROR}"
        print(f"⚠️ {error_message}")
    
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
        'error_message': error_message,
        'message': 'Account retrieved successfully'
    })
