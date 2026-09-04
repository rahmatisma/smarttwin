import asyncio
import httpx
from app.core.config import settings
from app.services.cctv_service import get_video_hf_location

async def run():
    try:
        # video 27 is the one we want to test
        repo, path = get_video_hf_location(27)
        print('Repo:', repo, 'Path:', path)
    except Exception as e:
        print('Error getting location:', e)
        return

    hf_url = f"https://huggingface.co/datasets/{repo}/resolve/main/{path}"
    print('HF URL:', hf_url)
    
    client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {settings.hf_token}"},
        timeout=30.0,
    )
    req = client.build_request("GET", hf_url)
    try:
        res = await client.send(req, stream=True)
        print('Status:', res.status_code)
    except Exception as e:
        print('Error sending:', e)

if __name__ == '__main__':
    asyncio.run(run())
