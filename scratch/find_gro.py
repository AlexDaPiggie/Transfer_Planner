import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}
js_text = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers=headers).text

# Find getRequestOptions definition
pos = js_text.find('getRequestOptions(')
print('Definition of getRequestOptions:', js_text[pos:pos+400])

# Find tokenService methods
pos_token = js_text.find('class TokenService')
if pos_token == -1:
    # search for token in class definition
    pos_token = js_text.find('TokenService')
print('Token pos:', pos_token)
if pos_token != -1:
    print('Token context:', js_text[pos_token-100:pos_token+300])
