import requests
import re

js = requests.get('https://assist.org/main.7ffdf5991193db15.js', headers={'User-Agent': 'Mozilla/5.0'}).text

# Find where getAcademicYears is used in components
for m in re.finditer(r'getAcademicYears\([^)]*\)', js):
    pos = m.start()
    print("CALL:", m.group(0))
    print("SURROUNDING:", js[max(0, pos-100):min(len(js), pos+200)])
    print("="*40)
