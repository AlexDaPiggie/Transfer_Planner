import requests

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/json',
    'Referer': 'https://assist.org/'
})

# 1. Fetch homepage to initialize cookies (XSRF-TOKEN and ARRAffinity)
r_init = s.get('https://assist.org/')
print("Cookies received:", s.cookies.get_dict())

xsrf = s.cookies.get('XSRF-TOKEN')
if xsrf:
    s.headers['X-XSRF-TOKEN'] = xsrf

# 2. Try fetching /api/AcademicYears
r_ay = s.get('https://assist.org/api/AcademicYears')
print("Status AcademicYears:", r_ay.status_code)
print("Text AcademicYears:", r_ay.text[:200])

# 3. Try fetching /api/institutions
r_inst = s.get('https://assist.org/api/institutions')
print("Status institutions:", r_inst.status_code)
print("Text institutions:", r_inst.text[:200])
