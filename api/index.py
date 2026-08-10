from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import base64
import hashlib
import random

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'message': 'Netflix Token API is live!'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time())
    })

@app.route('/get-netflix-account', methods=['GET'])
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    if not netflix_id:
        return jsonify({'success': False, 'error': 'No NetflixId provided'}), 400
    
    # Generate a simple token
    token = generate_token(netflix_id)
    
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
        'used_rummanchecker': False,
        'message': 'Account retrieved successfully'
    })

def generate_token(netflix_id):
    """Generate a simple token"""
    timestamp = str(int(time.time()))
    random_data = base64.b64encode(os.urandom(100)).decode('utf-8')
    
    combined = f"{netflix_id}{timestamp}{random_data}"
    hash_obj = hashlib.sha256(combined.encode())
    hash_hex = hash_obj.hexdigest()
    
    token_bytes = base64.b64encode((netflix_id + timestamp + hash_hex + random_data).encode())
    token = token_bytes.decode('utf-8')
    token = token.rstrip('=')
    
    if not token.startswith('Bgj'):
        token = 'Bgj' + token
    
    while len(token) < 200:
        token += base64.b64encode(os.urandom(30)).decode('utf-8').rstrip('=')
    
    return token[:300]

@app.route('/debug', methods=['GET'])
def debug():
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(current_dir) if os.path.exists(current_dir) else []
    
    return jsonify({
        'python_version': sys.version,
        'cwd': os.getcwd(),
        'current_dir': current_dir,
        'files_in_dir': files,
        'working': True
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
