import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()

app = FastAPI(title="ParkWatch Real-Time API")

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
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


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
            data = await websocket.receive_text()
            print(f"Received from {officer_id}: {data}")
            payload = json.dumps({"from": officer_id, "message": data})
            await redis_client.publish(CHANNEL, payload)
    except WebSocketDisconnect:
        manager.disconnect(officer_id)