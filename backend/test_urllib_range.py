import urllib.request
import json
try:
    # Test range request on HF proxy
    req = urllib.request.Request('http://127.0.0.1:8000/api/v1/cctv/videos/27/stream', headers={'Range': 'bytes=0-100'})
    res = urllib.request.urlopen(req)
    print(res.status)
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code, e.reason)
    print('Body:', e.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
