import requests
import re

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Find Ia.settings
pos = js_text.find('settings')
matches = [m.start() for m in re.finditer(r'settings\s*[:=]', js_text)]
print('Settings matches:', len(matches))
for m in matches[:5]:
    print(js_text[max(0, m-50):min(len(js_text), m+200)])
    print('='*40)
