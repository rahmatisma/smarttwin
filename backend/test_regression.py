import requests

try:
    url = 'http://localhost:8000/api/v1/simulation/run'
    data = {
        'intersectionId': 'simpang4-pingit',
        'durationSeconds': 60,
        'gui': True,
        'guiDelayMs': 100,
        'seed': 42
    }
    print("Testing /simulation/run")
    r = requests.post(url, json=data)
    print(r.status_code)
    print(r.json())
except Exception as e:
    print(e)
