import requests

# Use a session to get cookies first from assist.org
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://assist.org/'
})

# 1. Visit homepage to get XSRF-TOKEN cookie
res_home = session.get('https://assist.org/')
print("Cookies:", session.cookies.get_dict())

# 2. Add X-XSRF-TOKEN header if cookie present
xsrf_token = session.cookies.get('XSRF-TOKEN')
if xsrf_token:
    session.headers['X-XSRF-TOKEN'] = xsrf_token
    print("Found XSRF-TOKEN:", xsrf_token)

# 3. Request AcademicYears
res_years = session.get('https://assist.org/api/AcademicYears')
print("Status:", res_years.status_code)
print("Response:", res_years.text[:300])
