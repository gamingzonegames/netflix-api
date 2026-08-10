from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "ok", "message": "API is running"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/get-netflix-account', methods=['GET'])
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    # Generate a token
    import hashlib
    import base64
    import time
    import os
    
    token = "Bgj" + base64.b64encode(os.urandom(200)).decode('utf-8').rstrip('=')[:300]
    
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

# This is required for Vercel
app = app
