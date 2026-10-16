import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find instances of /api/
for m in re.finditer(r'["\'](/api/[a-zA-Z0-9_\-/]+)["\']', js_text):
    start = max(0, m.start() - 150)
    end = min(len(js_text), m.end() + 150)
    print("MATCH:", m.group(1))
    print("CONTEXT:", js_text[start:end])
    print("-" * 50)
