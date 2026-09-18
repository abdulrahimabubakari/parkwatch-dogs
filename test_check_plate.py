import asyncio
import json
import websockets

async def officer_client(officer_id, port):
    uri = f"ws://127.0.0.1:{port}/ws/officer/{officer_id}"
    async with websockets.connect(uri) as websocket:
        print(f"[{officer_id}] Connected on port {port}")

        if officer_id == "officer1":
            await asyncio.sleep(1)

            # Test 1: valid, active permit -> should get a private check_result, NOT a broadcast
            await websocket.send(json.dumps({
                "action": "check_plate", "plate": "NPQ0315", "zone_id": 3
            }))
            print("[officer1] Sent check for VALID plate (NPQ0315, zone 3)")
            await asyncio.sleep(1)

            # Test 2: expired permit -> should trigger a violation.created broadcast
            await websocket.send(json.dumps({
                "action": "check_plate", "plate": "NBY3978", "zone_id": 1
            }))
            print("[officer1] Sent check for EXPIRED plate (NBY3978, zone 1)")

        # listen for whatever comes back, for up to 6 seconds
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=6)
                print(f"[{officer_id}] Received: {message}")
        except asyncio.TimeoutError:
            print(f"[{officer_id}] Done listening (timeout)")

async def main():
    await asyncio.gather(
        officer_client("officer1", 8000),
        officer_client("officer2", 8001),
    )

asyncio.run(main())