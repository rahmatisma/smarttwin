import urllib.request, json
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/simulation/run',
    data=json.dumps({
        'intersectionId': 'simpang4-pingit',
        'durationSeconds': 60,
        'gui': False,
        'guiDelayMs': 100,
        'seed': 42
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    print(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
except Exception as e:
    print("ERROR:", type(e), str(e))
