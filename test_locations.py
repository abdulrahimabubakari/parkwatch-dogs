import asyncio
import json
import websockets

async def officer_sending_location(officer_id, port):
    uri = f"ws://127.0.0.1:{port}/ws/officer/{officer_id}"
    async with websockets.connect(uri) as websocket:
        print(f"[{officer_id}] Connected")
        await asyncio.sleep(0.5)
        await websocket.send(json.dumps({
            "action": "location_update", "lat": 38.9218, "lng": -77.0195
        }))
        print(f"[{officer_id}] Sent location update")
        await asyncio.sleep(3)  # keep connection open to allow listening below

async def supervisor_listening(port):
    uri = f"ws://127.0.0.1:{port}/ws/officer/supervisor_view"
    async with websockets.connect(uri) as websocket:
        print("[supervisor] Connected, listening...")
        try:
            for _ in range(3):
                message = await asyncio.wait_for(websocket.recv(), timeout=4)
                print(f"[supervisor] Received: {message}")
        except asyncio.TimeoutError:
            print("[supervisor] Done listening")

async def main():
    await asyncio.gather(
        supervisor_listening(8001),           # listening on Server B
        officer_sending_location("officer1", 8000),  # sending from Server A
    )

asyncio.run(main())