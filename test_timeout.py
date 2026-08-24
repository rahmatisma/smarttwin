import urllib.request
import json
import urllib.error

url = 'http://127.0.0.1:8000/api/v1/simulation/run'
data = json.dumps({
    'intersectionId': 'simpang4-pingit',
    'durationSeconds': 10,
    'gui': True,
    'guiDelayMs': 100,
    'seed': 42
}).encode('utf-8')
headers = {'Content-Type': 'application/json'}
req = urllib.request.Request(url, data=data, headers=headers)

try:
    print("Sending POST request...")
    with urllib.request.urlopen(req, timeout=10) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.URLError as e:
    print("Error:", e.reason)
except Exception as e:
    print("Exception:", e)
