from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict

app = FastAPI(title="ParkWatch Real-Time API")


class ConnectionManager:
    def __init__(self):
        # officer_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, officer_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[officer_id] = websocket
        print(f"Officer {officer_id} connected. Total active: {len(self.active_connections)}")

    def disconnect(self, officer_id: str):
        if officer_id in self.active_connections:
            del self.active_connections[officer_id]
        print(f"Officer {officer_id} disconnected. Total active: {len(self.active_connections)}")

    async def send_to(self, officer_id: str, message: str):
        if officer_id in self.active_connections:
            await self.active_connections[officer_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)


manager = ConnectionManager()


@app.get("/")
def root():
    return {"status": "ok", "service": "parkwatch-realtime", "active_connections": len(manager.active_connections)}


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
            # For now, just echo it back to everyone connected (this proves broadcast works)
            await manager.broadcast(f"Officer {officer_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(officer_id)