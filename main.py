import sqlite3, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI()
SECRET_PASSWORD = "1234"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chat.db")
    # Добавляем room_id, чтобы разделять переписки
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, sender_id TEXT, sender_name TEXT, content TEXT)")
    conn.commit()
    conn.close()

init_db()

# --- МЕНЕДЖЕР КОМНАТ ---
class ConnectionManager:
    def __init__(self):
        # Храним соединения по комнатам: { "room1": [ws1, ws2], "room2": [ws3] }
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)
        
        # Загружаем историю конкретной комнаты
        conn = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("SELECT sender_id, sender_name, content FROM messages WHERE room_id = ? ORDER BY id ASC", (room_id,))
        for row in cursor.fetchall():
            await websocket.send_text(json.dumps({"sender": row[0], "name": row[1], "text": row[2]}))
        conn.close()

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].remove(websocket)

    async def broadcast(self, message_json: str, room_id: str, sender: WebSocket):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                if connection != sender:
                    await connection.send_text(message_json)

manager = ConnectionManager()

html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>Rooms Messenger</title>
    <script src="https://tailwindcss.com"></script>
    <style>
        .screen {{ display: none; height: 100vh; flex-direction: column; background: #f3f4f6; }}
        .active-screen {{ display: flex; }}
        .msg-bubble {{ max-width: 80%; padding: 8px 12px; border-radius: 15px; font-size: 14px; }}
        .msg-in {{ background: white; align-self: flex-start; border-bottom-left-radius: 2px; }}
        .msg-out {{ background: #dcfce7; align-self: flex-end; border-bottom-right-radius: 2px; }}
    </style>
</head>
<body class="bg-slate-900">

    <!-- ЭКРАН ПАРОЛЯ -->
    <div id="scr-auth" class="screen active-screen items-center justify-center text-white">
        <h1 class="text-2xl font-bold mb-6">Вход в систему</h1>
        <input type="password" id="pInp" class="w-64 p-3 rounded-xl text-black text-center" placeholder="Пароль">
        <button onclick="login()" class="mt-4 bg-indigo-600 px-10 py-3 rounded-xl">Войти</button>
    </div>

    <!-- ЭКРАН СПИСКА ЧАТОВ -->
    <div id="scr-list" class="screen max-w-md mx-auto border-x bg-white">
        <div class="bg-indigo-600 p-4 text-white font-bold shadow-md flex justify-between">
            <span>Мои чаты</span>
            <button onclick="showScreen('profile')">👤</button>
        </div>
        <div class="flex-1 overflow-y-auto">
            <div onclick="openRoom('general', 'Общий чат')" class="p-4 border-b flex items-center gap-4 hover:bg-gray-50 cursor-pointer">
                <div class="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center text-xl">🌍</div>
                <div><div class="font-bold">Общий чат</div><div class="text-xs text-gray-400">Все участники проекта</div></div>
            </div>
            <div onclick="openRoom('work', 'Работа')" class="p-4 border-b flex items-center gap-4 hover:bg-gray-50 cursor-pointer">
                <div class="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center text-xl">💼</div>
                <div><div class="font-bold">Рабочие моменты</div><div class="text-xs text-gray-400">Только важные дела</div></div>
            </div>
        </div>
    </div>

    <!-- ЭКРАН ДИАЛОГА -->
    <div id="scr-chat" class="screen max-w-md mx-auto border-x bg-[#e6ebee]">
        <div class="bg-indigo-600 p-3 text-white flex items-center gap-3 shadow-md">
            <button onclick="closeRoom()" class="text-xl">←</button>
            <div id="chat-title" class="font-bold">Чат</div>
        </div>
        <div id="chat-msgs" class="flex-1 p-4 overflow-y-auto flex flex-col gap-3"></div>
        <div class="p-3 bg-white flex items-center gap-2 border-t">
            <input type="text" id="mInp" class="flex-1 bg-gray-100 p-2 rounded-full outline-none" placeholder="Сообщение...">
            <button onclick="sendMsg()" class="bg-indigo-600 text-white w-10 h-10 rounded-full flex items-center justify-center font-bold">></button>
        </div>
    </div>

    <!-- ЭКРАН ПРОФИЛЯ -->
    <div id="scr-profile" class="screen max-w-md mx-auto border-x bg-white">
        <div class="bg-indigo-600 p-4 text-white font-bold flex gap-4">
            <button onclick="showScreen('list')">←</button>
            <span>Профиль</span>
        </div>
        <div class="p-8 flex flex-col items-center gap-6">
            <img id="avatar" src="https://placeholder.com" class="w-24 h-24 rounded-full border-4 border-indigo-100">
            <input type="text" id="nameInp" class="w-full p-3 border rounded-xl" onchange="saveName()">
            <button onclick="location.reload()" class="text-red-500 font-bold">Выйти</button>
        </div>
    </div>

    <script>
        if (!localStorage.getItem('uid')) localStorage.setItem('uid', 'u'+Date.now());
        const uid = localStorage.getItem('uid');
        let uName = localStorage.getItem('uname') || "Аноним";
        let curRoom = null;
        let ws = null;

        document.getElementById('nameInp').value = uName;

        function showScreen(id) {{
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active-screen'));
            document.getElementById('scr-'+id).classList.add('active-screen');
        }}

        function login() {{
            if (document.getElementById('pInp').value === "{SECRET_PASSWORD}") showScreen('list');
            else alert("Ошибка!");
        }}

        function openRoom(id, title) {{
            curRoom = id;
            document.getElementById('chat-title').innerText = title;
            document.getElementById('chat-msgs').innerHTML = "";
            showScreen('chat');
            
            if (ws) ws.close();
            ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/" + id);
            
            ws.onmessage = (e) => {{
                const data = JSON.parse(e.data);
                append(data, data.sender === uid);
            }};
        }}

        function closeRoom() {{
            if (ws) ws.close();
            showScreen('list');
        }}

        function append(data, out) {{
            const box = document.getElementById('chat-msgs');
            const d = document.createElement('div');
            d.className = `msg-bubble ${{out ? 'msg-out shadow-sm' : 'msg-in shadow-sm'}}`;
            d.innerHTML = `<div class="text-[10px] font-bold text-indigo-500 mb-0.5">${{out ? 'Вы' : data.name}}</div>` + data.text;
            box.appendChild(d);
            box.scrollTop = box.scrollHeight;
        }}

        function sendMsg() {{
            const i = document.getElementById('mInp');
            if (i.value && ws) {{
                const payload = {{ sender: uid, name: uName, text: i.value, room: curRoom }};
                ws.send(JSON.stringify(payload));
                append(payload, true);
                i.value = "";
            }}
        }}

        function saveName() {{
            uName = document.getElementById('nameInp').value;
            localStorage.setItem('uname', uName);
        }}

        document.getElementById("mInp").onkeypress = (e) => {{ if(e.key === "Enter") sendMsg(); }};
    </script>
</body>
</html>
"""

@app.get("/")
async def get(): return HTMLResponse(html)

@app.websocket("/ws/{{room_id}}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            conn = sqlite3.connect("chat.db")
            conn.execute("INSERT INTO messages (room_id, sender_id, sender_name, content) VALUES (?, ?, ?, ?)", 
                         (room_id, data['sender'], data['name'], data['text']))
            conn.commit(); conn.close()
            await manager.broadcast(raw, room_id, websocket)
    except WebSocketDisconnect: manager.disconnect(websocket, room_id)
