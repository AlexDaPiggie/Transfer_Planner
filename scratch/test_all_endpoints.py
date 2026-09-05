import requests

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://assist.org/'
})

# 1. Init session
s.get('https://assist.org/')
token = s.cookies.get('X-XSRF-TOKEN') or s.cookies.get('XSRF-TOKEN')
s.headers['X-XSRF-TOKEN'] = token

# 2. Test AcademicYears
r_ay = s.get('https://assist.org/api/AcademicYears')
print("AcademicYears count:", len(r_ay.json()))

# 3. Test institutions
r_inst = s.get('https://assist.org/api/institutions')
print("Institutions count:", len(r_inst.json()))
print("Sample institution:", r_inst.json()[0])

# 4. Test agreements (De Anza to UC Berkeley for 2024-2025: year 75)
# De Anza = 113, UC Berkeley = 19 (let's find their IDs)
insts = {i['names'][0]['name']: i['id'] for i in r_inst.json()}
de_anza_id = [i['id'] for i in r_inst.json() if 'De Anza' in i['names'][0]['name']][0]
ucb_id = [i['id'] for i in r_inst.json() if 'Berkeley' in i['names'][0]['name']][0]
print(f"De Anza ID: {de_anza_id}, UCB ID: {ucb_id}")

r_agr = s.get(f'https://assist.org/api/agreements?receivingInstitutionId={ucb_id}&sendingInstitutionId={de_anza_id}&academicYearId=75&categoryCode=major')
print("Agreements count:", len(r_agr.json().get('reports', [])))
print("Sample agreement report:", r_agr.json().get('reports', [])[0])
