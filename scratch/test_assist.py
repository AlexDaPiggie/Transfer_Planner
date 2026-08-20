import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

r = requests.get('https://assist.org/', headers=headers)
print('Status:', r.status_code)
print('HTML snippet:', r.text[:300])

# Find script URLs
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
print('Scripts found:', scripts)

for s in scripts:
    s_url = s if s.startswith('http') else f"https://assist.org/{s.lstrip('/')}"
    res = requests.get(s_url, headers=headers)
    print(f'Script {s_url} length: {len(res.text)}')
    # Search for API endpoints in js
    api_matches = re.findall(r'["\'](/api/[^"\']+|https?://[^"\']+/api/[^"\']+)["\']', res.text)
    if api_matches:
        print('API endpoints in JS:', set(api_matches[:10]))
    # Search for academic year or institution strings
    ay_matches = re.findall(r'["\']([^"\']*(?:AcademicYear|Institutions|agreements|articulation)[^"\']*)["\']', res.text, re.I)
    if ay_matches:
        print('Matching keywords in JS:', set(ay_matches[:10]))
