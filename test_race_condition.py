import asyncio
import json
import websockets

# Two officers scan the SAME plate, in the SAME zone, at nearly the same instant
PLATE = "NBY3978"  # our known expired plate from Day 3
ZONE = 1

async def officer_scan(officer_id, port):
    uri = f"ws://127.0.0.1:{port}/ws/officer/{officer_id}"
    async with websockets.connect(uri) as websocket:
        # no artificial delay - fire as close to simultaneously as possible
        await websocket.send(json.dumps({
            "action": "check_plate", "plate": PLATE, "zone_id": ZONE
        }))
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=4)
            print(f"[{officer_id}] Received: {message}")
        except asyncio.TimeoutError:
            print(f"[{officer_id}] No response")

async def main():
    # fire both at the same time, on two separate server processes
    await asyncio.gather(
        officer_scan("officer1", 8000),
        officer_scan("officer2", 8001),
    )

asyncio.run(main())