import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
from dotenv import load_dotenv
import redis.asyncio as aioredis
from api.permits import check_plate_and_log_violation
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(title="ParkWatch Real-Time API")
app.mount("/static", StaticFiles(directory="static"), name="static")

REDIS_URL = os.getenv("REDIS_URL")
CHANNEL = "parkwatch_events"


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, officer_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[officer_id] = websocket
        print(f"Officer {officer_id} connected. Local active: {len(self.active_connections)}")

    def disconnect(self, officer_id: str):
        if officer_id in self.active_connections:
            del self.active_connections[officer_id]
        print(f"Officer {officer_id} disconnected. Local active: {len(self.active_connections)}")

    async def broadcast_local(self, message: str):
        # sends only to officers connected to THIS process
        for connection in list(self.active_connections.values()):
            await connection.send_text(message)


manager = ConnectionManager()
redis_client = aioredis.from_url(
    REDIS_URL,
    decode_responses=True,
    health_check_interval=30,   # periodically pings Redis to detect dead connections early
    socket_keepalive=True,
    retry_on_timeout=True,
)


async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(CHANNEL)
    print("Subscribed to Redis channel:", CHANNEL)
    async for message in pubsub.listen():
        if message["type"] == "message":
            await manager.broadcast_local(message["data"])


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())


@app.get("/")
def root():
    return {"status": "ok", "service": "parkwatch-realtime", "local_connections": len(manager.active_connections)}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.websocket("/ws/officer/{officer_id}")
async def officer_socket(websocket: WebSocket, officer_id: str):
    await manager.connect(officer_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid_json"}))
                continue

            action = data.get("action")

            if action == "check_plate":
                plate = data.get("plate")
                zone_id = data.get("zone_id")
                result = check_plate_and_log_violation(plate, zone_id, officer_id)
                print(f"[{officer_id}] checked {plate} in zone {zone_id}: {result}")

                if not result["valid"]:
                    event = {
                        "type": "violation.created",
                        "officer_id": officer_id,
                        "plate": plate,
                        "zone_id": zone_id,
                        **result,
                    }
                    try:
                        await redis_client.publish(CHANNEL, json.dumps(event))
                    except Exception as e:
                        print(f"Redis publish failed, retrying once: {e}")
                        await redis_client.publish(CHANNEL, json.dumps(event))
                else:
                    await websocket.send_text(json.dumps({"type": "check_result", **result}))

            elif action == "location_update":
                lat = data.get("lat")
                lng = data.get("lng")
                event = {
                    "type": "location.update",
                    "officer_id": officer_id,
                    "lat": lat,
                    "lng": lng,
                    "timestamp": datetime.now().isoformat(),
                }
                try:
                    await redis_client.publish(CHANNEL, json.dumps(event))
                except Exception as e:
                    print(f"Redis publish failed, retrying once: {e}")
                    await redis_client.publish(CHANNEL, json.dumps(event))

            else:
                await websocket.send_text(json.dumps({"error": "unknown_action"}))

    except WebSocketDisconnect:
        manager.disconnect(officer_id)