import httpx, asyncio, os
async def test():
    filepath = r"C:\Users\Sergey\Desktop\test.jpg"   # <-- ИЗМЕНИ НА СВОЙ ФАЙЛ
    if not os.path.exists(filepath):
        print("Файл не найден")
        return
    async with httpx.AsyncClient(timeout=15) as client:
        with open(filepath, 'rb') as f:
            resp = await client.post('http://localhost:8000/api/park/fili/photos', files={'file': f})
        print(resp.status_code, resp.text)
asyncio.run(test())