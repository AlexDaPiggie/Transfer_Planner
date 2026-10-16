import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}
js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Search for function getRequestOptions or getRequestOptions(
matches = [m.start() for m in re.finditer(r'getRequestOptions\b', js_text)]
print('Matches count:', len(matches))
for idx, m in enumerate(matches):
    print(f'Match {idx}:', js_text[max(0, m-50):min(len(js_text), m+200)])
    print('='*40)
