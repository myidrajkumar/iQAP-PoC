from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, List
import json


# --- A simple in-memory connection manager ---
class ConnectionManager:
    def __init__(self):
        # Maps a run_id to a list of active WebSockets for that run
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # List for general notification clients
        self.notification_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, run_id: int):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)
        print(
            f"WebSocket connected for run_id: {run_id}. Total connections for run: {len(self.active_connections[run_id])}"
        )

    def disconnect(self, websocket: WebSocket, run_id: int):
        if run_id in self.active_connections:
            self.active_connections[run_id].remove(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
            print(f"WebSocket disconnected for run_id: {run_id}.")

    async def broadcast_update(self, run_id: int, message: dict):
        if run_id in self.active_connections:
            # Create a JSON string from the message dict
            json_message = json.dumps(message)
            for connection in self.active_connections[run_id]:
                await connection.send_text(json_message)

    async def connect_notifications(self, websocket: WebSocket):
        await websocket.accept()
        self.notification_connections.append(websocket)
        print("Client connected for general notifications.")

    def disconnect_notifications(self, websocket: WebSocket):
        self.notification_connections.remove(websocket)
        print("Client disconnected from general notifications.")

    async def broadcast_notification(self, message: dict):
        json_message = json.dumps(message)
        for connection in self.notification_connections:
            await connection.send_text(json_message)


manager = ConnectionManager()

app = FastAPI(title="iQAP Realtime Service")


@app.websocket("/ws/notifications")
async def websocket_notification_endpoint(websocket: WebSocket):
    await manager.connect_notifications(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_notifications(websocket)


# --- WebSocket Endpoint for the Frontend ---
@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: int):
    await manager.connect(websocket, run_id)
    try:
        while True:
            # Keep the connection alive by waiting for messages (e.g., pings)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, run_id)


@app.post("/notify/run-created")
async def notify_run_created(notification: dict):
    try:
        await manager.broadcast_notification(notification)
        return {"status": "notification sent"}
    except Exception as e:
        print(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to send notification.")


# --- REST Endpoint for the Execution Agent ---
@app.post("/update/{run_id}")
async def send_update_to_client(run_id: int, update: dict):
    try:
        await manager.broadcast_update(run_id, update)
        return {"status": "update sent"}
    except Exception as e:
        print(f"Error sending update for run_id {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send update.")


@app.get("/")
def read_root():
    return {"message": "iQAP Realtime Service is running."}