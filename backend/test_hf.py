import asyncio
import httpx
from app.core.config import settings
async def run():
 client = httpx.AsyncClient(headers={'Authorization': f'Bearer {settings.hf_token}'}, follow_redirects=True)
 req = client.build_request('GET', 'https://huggingface.co/datasets/rahmatisma/smarttwin/resolve/main/27.mp4')
 try:
  res = await client.send(req, stream=True)
  print('Status:', res.status_code)
 except Exception as e:
  print('Error:', e)
asyncio.run(run())
