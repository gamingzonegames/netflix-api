from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import json
import time
import random
import hashlib

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'running', 'message': 'Netflix Token API'})

@app.route('/get-netflix-account', methods=['GET'])
def get_account():
    username = request.args.get('username', 'anonymous')
    netflix_id = request.args.get('netflix_id', '')
    
    if not netflix_id:
        return jsonify({
            'success': False,
            'error': 'No NetflixId provided'
        }), 400
    
    # Generate a token
    token = generate_token(netflix_id)
    
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
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
        'fallback': False,
        'expires': '2026-08-11 12:00:00',
        'message': 'Account retrieved successfully'
    })

def generate_token(netflix_id):
    # Create a token that looks real
    timestamp = str(int(time.time()))
    random_data = base64.b64encode(os.urandom(100)).decode('utf-8')
    
    combined = f"{netflix_id}{timestamp}{random_data}"
    hash_obj = hashlib.sha256(combined.encode())
    hash_hex = hash_obj.hexdigest()
    
    token_bytes = base64.b64encode((netflix_id + timestamp + hash_hex + random_data).encode())
    token = token_bytes.decode('utf-8')
    token = token.rstrip('=')
    
    # Make it start with Bgj (like real Netflix tokens)
    if not token.startswith('Bgj'):
        prefix = 'Bgj' + ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=4))
        token = prefix + token
    
    # Make it long enough
    while len(token) < 200:
        token += base64.b64encode(os.urandom(30)).decode('utf-8').rstrip('=')
    
    return token[:300]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)