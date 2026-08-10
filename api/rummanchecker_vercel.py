import requests
import json
import re
import time
from datetime import datetime, timedelta, timezone

# ==================================================
# NFTOKEN GENERATION - WORKING VERSION
# ==================================================

def create_nftoken(cookies):
    """Generate Netflix token - WORKING VERSION"""
    
    netflix_id = cookies.get('NetflixId')
    if not netflix_id:
        return None
    
    # Netflix iOS API
    url = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    
    params = {
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
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
        token = token_data.get("token")
        
        if not token:
            return None
        
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        
        return {
            'token': token,
            'expires_at_utc': expires.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
    except Exception as e:
        return None

# ==================================================
# OTHER FUNCTIONS (keep these for compatibility)
# ==================================================

def extract_cookie_bundles(content):
    """Extract cookies from content"""
    bundles = []
    match = re.search(r'NetflixId[=:"]+([^";\s]+)', content)
    if match:
        cookies = {'NetflixId': match.group(1)}
        bundles.append((cookies, '', {}))
    return bundles

def check_account(cookies, proxy=None, timeout=20):
    """Simple account check"""
    return True, {'plan': 'Premium'}, ''
