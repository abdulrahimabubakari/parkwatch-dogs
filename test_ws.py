import asyncio
import websockets

async def test_officer(officer_id):
    try:
        uri = f"ws://127.0.0.1:8000/ws/officer/{officer_id}"
        async with websockets.connect(uri) as websocket:
            print(f"[{officer_id}] Connected!")
            await asyncio.sleep(0.5)

            if officer_id == "officer1":
                await asyncio.sleep(1)
                await websocket.send("Flagged a violation at Zone A!")
                print(f"[{officer_id}] Sent message")

            print(f"[{officer_id}] Now waiting for a message...")
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=4)
                print(f"[{officer_id}] Received: {message}")
            except asyncio.TimeoutError:
                print(f"[{officer_id}] Timed out waiting for a message")

    except Exception as e:
        print(f"[{officer_id}] ERROR: {type(e).__name__}: {e}")

async def main():
    await asyncio.gather(
        test_officer("officer1"),
        test_officer("officer2"),
    )

asyncio.run(main())