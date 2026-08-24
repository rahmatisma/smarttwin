import urllib.request

try:
    print("Fetching cameras from supabase...")
    import requests
    response = requests.get("http://127.0.0.1:8000/api/v1/traffic/cameras?intersection_id=all")
    print(response.status_code)
    # The actual endpoint in supabaseData.ts is: fetchCameras
except Exception as e:
    print(e)
