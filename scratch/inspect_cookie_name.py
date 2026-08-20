import requests

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Search for cookie name in tokenService
pos = js_text.find('getToken()')
print('getToken() snippet:', js_text[max(0, pos-100):min(len(js_text), pos+300)])
