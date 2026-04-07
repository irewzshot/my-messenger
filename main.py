import os
import json
import datetime
import sqlite3
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# База данных
DB_PATH = "family.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()

init_db()

# Хранилище активных подключений
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    
    # При входе отправляем историю (последние 50 сообщений)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT sender, text FROM messages ORDER BY id DESC LIMIT 50")
        history = [{"sender": r[0], "text": r[1]} for r in cursor.fetchall()][::-1]
        await websocket.send_text(json.dumps({"type": "history", "data": history}))

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            
            # Сохраняем в базу
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("INSERT INTO messages (sender, text) VALUES (?, ?)", 
                             (client_id, msg_data["text"]))
                conn.commit()

            # Рассылаем всем
            await manager.broadcast({"type": "msg", "sender": client_id, "text": msg_data["text"]})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
