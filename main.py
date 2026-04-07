from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Messenger MVP</title>
    <style>
        body { background-color: #1e293b; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }
        .app-container { background-color: #e6ebee; width: 100%; max-width: 450px; height: 90vh; display: flex; flex-direction: column; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
        .header { background-color: #4f46e5; color: white; padding: 15px; text-align: center; font-weight: bold; }
        #chat { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 14px; border-radius: 12px; font-size: 14px; max-width: 80%; box-shadow: 0 1px 2px rgba(0,0,0,0.1); word-wrap: break-word; }
        .msg-in { background-color: white; align-self: flex-start; border-bottom-left-radius: 2px; }
        .msg-out { background-color: #effdde; align-self: flex-end; border-bottom-right-radius: 2px; border: 1px solid #dcfce7; }
        .input-area { background-color: white; padding: 12px; display: flex; gap: 10px; border-top: 1px solid #ddd; align-items: center; }
        input { flex: 1; padding: 10px 15px; border-radius: 20px; border: 1px solid #ddd; outline: none; }
        .btn-send { background-color: #4f46e5; color: white; border: none; padding: 10px 18px; border-radius: 20px; font-weight: bold; cursor: pointer; }
        .btn-file { font-size: 24px; cursor: pointer; background: none; border: none; padding: 0 5px; }
        img { max-width: 100%; border-radius: 8px; margin-top: 5px; display: block; }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">Python Messenger MVP</div>
        
        <div id="chat"></div>

        <div class="input-area">
             <!-- Скрытый выбор файла -->
             <input type="file" id="fileInput" accept="image/*" style="display:none" onchange="sendImage()">
             <button class="btn-file" onclick="document.getElementById('fileInput').click()">📎</button>
             
             <input type="text" id="msgInput" placeholder="Сообщение..." autocomplete="off">
             <button class="btn-send" onclick="sendText()">ОТПР.</button>
        </div>
    </div>

    <script>
        var ws = new WebSocket((window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws");
        var chat = document.getElementById('chat');

        function appendMessage(data, isOut) {
            var div = document.createElement('div');
            div.className = 'msg ' + (isOut ? 'msg-out' : 'msg-in');
            
            if (data.startsWith("IMG:")) {
                var img = document.createElement('img');
                img.src = data.replace("IMG:", "");
                div.appendChild(img);
            } else {
                div.textContent = data;
            }
            
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        ws.onmessage = function(event) {
            appendMessage(event.data, false);
        };

        function sendText() {
            var input = document.getElementById("msgInput");
            if (input.value.trim()) {
                ws.send(input.value);
                appendMessage(input.value, true);
                input.value = "";
            }
        }

        function sendImage() {
            var file = document.getElementById('fileInput').files[0];
            if (!file) return;

            var reader = new FileReader();
            reader.onload = function(e) {
                var base64Img = "IMG:" + e.target.result;
                ws.send(base64Img);
                appendMessage(base64Img, true);
            };
            reader.readAsDataURL(file);
        }

        document.getElementById("msgInput").addEventListener("keypress", (e) => {
            if(e.key === "Enter") sendText();
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            for connection in manager.active_connections:
                if connection != websocket:
                    await connection.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
