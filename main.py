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
    <title>Telegram Clone MVP</title>
    <script src="https://tailwindcss.com"></script>
    <style>
        body { background-color: #e6ebee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        #chat-window { height: calc(100vh - 120px); overflow-y: auto; scrollbar-width: thin; }
        .msg-bubble { max-width: 70%; padding: 8px 12px; border-radius: 12px; position: relative; font-size: 15px; line-height: 1.4; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .msg-in { background-color: white; align-self: flex-start; border-bottom-left-radius: 4px; }
        .msg-out { background-color: #effdde; align-self: flex-end; border-bottom-right-radius: 4px; }
    </style>
</head>
<body class="flex flex-col h-screen">

    <!-- Шапка в стиле ТГ -->
    <div class="bg-[#517da2] text-white p-3 flex items-center shadow-md z-10">
        <div class="w-10 h-10 bg-blue-400 rounded-full flex items-center justify-center font-bold mr-3">P</div>
        <div>
            <div class="font-bold text-sm">Python Chat Room</div>
            <div class="text-xs text-blue-100">в сети: много участников</div>
        </div>
    </div>

    <!-- Область сообщений -->
    <div id="chat-window" class="flex-1 p-4 flex flex-col space-y-3">
        <div class="self-center bg-[#00000033] text-white text-[11px] px-3 py-1 rounded-full my-2">СЕГОДНЯ</div>
    </div>

    <!-- Поле ввода -->
    <div class="bg-white p-2 flex items-center gap-2 border-t">
        <button class="text-gray-400 p-2"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path></svg></button>
        <input type="text" id="messageInput" placeholder="Написать сообщение..." 
            class="flex-1 outline-none text-sm p-2" autocomplete="off" />
        <button onclick="send()" class="text-[#517da2] font-bold p-2 hover:bg-gray-100 rounded-full transition">ОТПРАВИТЬ</button>
    </div>

    <script>
        var ws = new WebSocket((window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws");
        var chat = document.getElementById('chat-window');

        ws.onmessage = function(event) {
            var div = document.createElement('div');
            // Простая логика: если в тексте есть "Вы:", красим как исходящее (условно)
            div.className = 'msg-bubble msg-in';
            div.textContent = event.data;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        };

        function send() {
            var input = document.getElementById("messageInput");
            if (input.value.trim()) {
                ws.send(input.value);
                
                // Сразу отображаем своё сообщение как "исходящее" (светло-зеленое)
                var div = document.createElement('div');
                div.className = 'msg-bubble msg-out';
                div.textContent = input.value;
                chat.appendChild(div);
                
                input.value = "";
                chat.scrollTop = chat.scrollHeight;
            }
        }

        document.getElementById("messageInput").addEventListener("keypress", (e) => {
            if(e.key === "Enter") send();
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
            # Рассылаем всем остальным
            for connection in manager.active_connections:
                if connection != websocket:
                    await connection.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
