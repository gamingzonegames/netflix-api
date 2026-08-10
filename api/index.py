from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/get-netflix-account')
def get_account():
    netflix_id = request.args.get('netflix_id', '')
    email = request.args.get('email', 'N/A')
    country = request.args.get('country', 'US')
    
    import base64
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
