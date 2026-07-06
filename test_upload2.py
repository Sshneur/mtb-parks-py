import httpx, asyncio, os, traceback

async def test():
    filepath = r"C:\Users\Sergey\Desktop\test.jpg"
    if not os.path.exists(filepath):
        print("Файл не найден")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            with open(filepath, 'rb') as f:
                resp = await client.post('http://localhost:8000/api/park/fili/photos', files={'file': f})
            print(resp.status_code, resp.text)
    except Exception as e:
        print("ОШИБКА:")
        traceback.print_exc()

asyncio.run(test())