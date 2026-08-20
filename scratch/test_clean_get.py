import requests

s = requests.Session()
# GET requests should NOT have Content-Type: application/json according to HTTP spec
headers_list = [
    {}, # plain
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*'},
]

for idx, h in enumerate(headers_list):
    r = requests.get('https://assist.org/api/AcademicYears', headers=h)
    print(f"Test {idx} -> Status: {r.status_code}, Body: {r.text[:100]}")
