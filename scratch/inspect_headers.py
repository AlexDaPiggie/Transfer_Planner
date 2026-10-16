import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find where AcademicYears is called
pos = js_text.find('/api/AcademicYears')
print('Context around AcademicYears:', js_text[max(0, pos-200):pos+300])

# Find interceptors or headers
headers_matches = re.findall(r'headers\s*:\s*\{[^}]+\}', js_text)
print('Headers matches:', headers_matches[:5])

# Find all occurrences of API calls
for match in re.finditer(r'this\.http\.get\(([^)]+)\)', js_text):
    print('HTTP GET:', match.group(1))
