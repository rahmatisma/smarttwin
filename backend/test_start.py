import requests
import time

url = 'http://localhost:8000/api/v1/simulation/run'
data = {
    'intersectionId': 'simpang4-pingit',
    'durationSeconds': 60,
    'gui': True,
    'guiDelayMs': 100,
    'seed': 42
}

try:
    print('Starting simulation...')
    r = requests.post(url, json=data)
    print(r.status_code)
    print(r.json())
    
    time.sleep(3)
    
    stream_url = 'http://localhost:8000/api/v1/simulation/stream'
    print('Checking stream...')
    stream_resp = requests.get(stream_url, stream=True)
    print(stream_resp.status_code)
    print(stream_resp.headers)
    
    time.sleep(5)
    
    print('Stopping simulation...')
    requests.post('http://localhost:8000/api/v1/simulation/stop')
    print('Done')
    
except Exception as e:
    print(f'Error: {e}')
