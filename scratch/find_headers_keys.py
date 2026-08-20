import requests
import re

js = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Search for any header names or keys
for m in re.finditer(r'["\'](X-[a-zA-Z0-9_\-]+|api[_-]?key|Authorization)["\']', js, re.I):
    pos = m.start()
    print("KEY:", m.group(0))
    print("CONTEXT:", js[max(0, pos-80):min(len(js), pos+150)])
    print("="*40)
