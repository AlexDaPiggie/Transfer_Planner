import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find DataService class
pos = js_text.find('class DataService')
if pos == -1:
    pos = js_text.find('DataService')
print('DataService match:', js_text[pos:pos+500])

# Find interceptors (HttpInterceptor)
interceptor_pos = js_text.find('intercept(')
if interceptor_pos != -1:
    print('Interceptor:', js_text[interceptor_pos-100:interceptor_pos+400])

# Search for any string containing "https://"
urls = re.findall(r'https?://[a-zA-Z0-9\.\-_/]+', js_text)
print('Unique external URLs:', set([u for u in urls if 'google' not in u and 'w3' not in u]))
