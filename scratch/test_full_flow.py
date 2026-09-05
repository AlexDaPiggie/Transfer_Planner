import requests

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://assist.org/'
})

# 1. Fetch homepage to get cookies
r1 = s.get('https://assist.org/')
print("Cookies after homepage:", s.cookies.get_dict())

# 2. Get the X-XSRF-TOKEN cookie value and set it as X-XSRF-TOKEN header
token = s.cookies.get('X-XSRF-TOKEN') or s.cookies.get('XSRF-TOKEN')
if token:
    s.headers['X-XSRF-TOKEN'] = token
    print("Using token header:", token[:30] + "...")

# 3. Call api/appsettings
r_settings = s.get('https://assist.org/api/appsettings')
print("Status appsettings:", r_settings.status_code)
print("Response appsettings:", r_settings.text[:200])

# 4. Now call /api/AcademicYears
r_ay = s.get('https://assist.org/api/AcademicYears')
print("Status AcademicYears:", r_ay.status_code)
print("Response AcademicYears:", r_ay.text[:200])
