import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find getRequestOptions
pos = js_text.find('getRequestOptions')
print('getRequestOptions snippet:', js_text[pos:pos+600])

# Find tokenService
pos2 = js_text.find('class TokenService')
if pos2 == -1:
    pos2 = js_text.find('tokenService')
print('tokenService snippet:', js_text[pos2:pos2+600])
