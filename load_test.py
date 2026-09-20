import asyncio
import json
import time
import websockets

HOST = "parkwatch-dogs.onrender.com"
NUM_OFFICERS = 15

TEST_PLATES = ["NBY3978", "NPQ0315", "CFL6061"]

results = []

async def simulate_officer(officer_num):
    officer_id = f"loadtest_officer_{officer_num}"
    uri = f"wss://{HOST}/ws/officer/{officer_id}"
    start = time.time()
    try:
        async with websockets.connect(uri) as websocket:
            connect_time = time.time() - start

            plate = TEST_PLATES[officer_num % len(TEST_PLATES)]
            check_start = time.time()
            await websocket.send(json.dumps({
                "action": "check_plate", "plate": plate, "zone_id": 1
            }))
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            check_time = time.time() - check_start

            await websocket.send(json.dumps({
                "action": "location_update", "lat": 38.9218, "lng": -77.0195
            }))

            results.append({
                "officer": officer_id,
                "success": True,
                "connect_time_ms": round(connect_time * 1000, 1),
                "check_time_ms": round(check_time * 1000, 1),
            })
    except Exception as e:
        results.append({
            "officer": officer_id,
            "success": False,
            "error": f"{type(e).__name__}: {e}"
        })

async def main():
    print(f"Simulating {NUM_OFFICERS} concurrent officers against {HOST}...")
    overall_start = time.time()
    await asyncio.gather(*[simulate_officer(i) for i in range(NUM_OFFICERS)])
    overall_time = time.time() - overall_start

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    print(f"\n--- Results ---")
    print(f"Total time for all {NUM_OFFICERS} concurrent connections: {overall_time:.2f}s")
    print(f"Successful: {len(successes)}/{NUM_OFFICERS}")
    print(f"Failed: {len(failures)}")

    if successes:
        avg_connect = sum(r["connect_time_ms"] for r in successes) / len(successes)
        avg_check = sum(r["check_time_ms"] for r in successes) / len(successes)
        max_check = max(r["check_time_ms"] for r in successes)
        print(f"Avg connect time: {avg_connect:.1f}ms")
        print(f"Avg check_plate response time: {avg_check:.1f}ms")
        print(f"Max check_plate response time: {max_check:.1f}ms")

    for f in failures:
        print(f"FAILED - {f['officer']}: {f['error']}")

asyncio.run(main())