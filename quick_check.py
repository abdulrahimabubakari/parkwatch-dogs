import asyncio
import json
import websockets

async def test():
    uri = "wss://parkwatch-dogs.onrender.com/ws/officer/quicktest"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action": "check_plate", "plate": "NPQ0315", "zone_id": 3}))
        response = await asyncio.wait_for(ws.recv(), timeout=15)
        print("Got response:", response)

asyncio.run(test())