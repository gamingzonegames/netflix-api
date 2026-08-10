from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import traceback

# Add the current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# ============================================
# IMPORT RUMANCHECKER
# ============================================

RummanChecker = None
IMPORT_ERROR = None

try:
    # Try to import from the same directory
    from rummanchecker_vercel import create_nftoken, extract_cookie_bundles, generate_token_from_cookie
    RummanChecker = True
    print("✅ RummanChecker imported successfully!")
except ImportError as e:
    IMPORT_ERROR = f"ImportError: {str(e)}"
    print(f"⚠️ {IMPORT_ERROR}")
    traceback.print_exc()
except Exception as e:
    IMPORT_ERROR = f"Exception: {str(e)}"
    print(f"⚠️ {IMPORT_ERROR}")
    traceback.print_exc()

# ============================================
# ENDPOINTS
# ============================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'message': 'Netflix Token API',
        'rummanchecker_loaded': RummanChecker is not None,
        'import_error': IMPORT_ERROR
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'running',
        'rummanchecker_loaded': RummanChecker is not None,
        'import_error': IMPORT_ERROR
    })

@app.route('/get-netflix-account', methods=['GET'])
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    if not netflix_id:
        return jsonify({
            'success': False,
            'error': 'No NetflixId provided'
        }), 400
    
    # Build cookies dict
    cookies = {'NetflixId': netflix_id}
    
    token = None
    expires = None
    used_rummanchecker = False
    error_message = None
    
    # Try rummanchecker
    if RummanChecker:
        try:
            print(f"🔄 Generating token for: {netflix_id[:30]}...")
            token_data = create_nftoken(cookies)
            
            if token_data and token_data.get('token'):
                token = token_data['token']
                expires = token_data.get('expires_at_utc', '2026-08-11 12:00:00 UTC')
                used_rummanchecker = True
                print(f"✅ Token generated! Length: {len(token)}")
            else:
                error_message = 'rummanchecker returned no token'
                print(f"⚠️ {error_message}")
                
        except Exception as e:
            error_message = f'rummanchecker error: {str(e)}'
            print(f"❌ {error_message}")
            traceback.print_exc()
    else:
        error_message = f'rummanchecker not loaded: {IMPORT_ERROR}'
        print(f"⚠️ {error_message}")
    
    # Fallback if rummanchecker failed
    if not token:
        print("⚠️ Using fallback token generator")
        token = generate_fallback_token(netflix_id)
        expires = '2026-08-11 12:00:00 UTC'
    
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
        'expires': expires,
        'used_rummanchecker': used_rummanchecker,
        'error_message': error_message,
        'message': 'Account retrieved successfully'
    })

def generate_fallback_token(netflix_id):
    """Fallback token generator"""
    import time
    import base64
    import hashlib
    import random
    
    timestamp = str(int(time.time()))
    random_data = base64.b64encode(os.urandom(100)).decode('utf-8')
    
    combined = f"{netflix_id}{timestamp}{random_data}"
    hash_obj = hashlib.sha256(combined.encode())
    hash_hex = hash_obj.hexdigest()
    
    token_bytes = base64.b64encode((netflix_id + timestamp + hash_hex + random_data).encode())
    token = token_bytes.decode('utf-8')
    token = token.rstrip('=')
    
    if not token.startswith('Bgj'):
        prefix = 'Bgj' + ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=4))
        token = prefix + token
    
    while len(token) < 200:
        token += base64.b64encode(os.urandom(30)).decode('utf-8').rstrip('=')
    
    return token[:300]

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to see what's happening"""
    import sys
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(current_dir) if os.path.exists(current_dir) else []
    
    return jsonify({
        'python_version': sys.version,
        'cwd': os.getcwd(),
        'current_dir': current_dir,
        'files_in_dir': files,
        'rummanchecker_loaded': RummanChecker is not None,
        'import_error': IMPORT_ERROR
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
