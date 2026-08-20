import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find definition of Zh
pos = js_text.find('class Zh')
if pos == -1:
    pos = js_text.find('let Zh')
if pos == -1:
    pos = js_text.find('Zh=')

print('Zh definition snippet:', js_text[pos:pos+600])
