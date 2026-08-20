import requests
import re

js = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Find Ia definition or load() method
pos = js.find('class Ia')
if pos == -1:
    pos = js.find('let Ia')
if pos == -1:
    pos = js.find('Ia=')

print('Ia definition:', js[pos:pos+400])
