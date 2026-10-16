import requests
import re

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Find U7 definition
pos = js_text.find('U7=')
if pos != -1:
    print('U7 definition:', js_text[pos:pos+200])

# Find vit and _it
pos_vit = js_text.find('vit=')
print('vit definition:', js_text[pos_vit:pos_vit+200])
