import sqlite3, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI()
PWD = "1234"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chat.db")
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, sender_id TEXT, content TEXT)")
    conn.commit()
    conn.close()

init_db()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.rooms: self.rooms[room_id] = []
        self.rooms[room_id].append(websocket)
        # Загрузка истории
        conn = sqlite3.connect("chat.db"); cursor = conn.cursor()
        cursor.execute("SELECT sender_id, content FROM messages WHERE room_id = ? ORDER BY id ASC", (room_id,))
        for row in cursor.fetchall():
            await websocket.send_text(json.dumps({"sender": row[0], "text": row[1]}))
        conn.close()

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].remove(websocket)

    async def broadcast(self, message_json: str, room_id: str, sender: WebSocket):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                if connection != sender:
                    try: await connection.send_text(message_json)
                    except: pass

manager = ConnectionManager()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Chat Stable</title>
    <style>
        body { background: #0f172a; margin: 0; font-family: sans-serif; display: flex; justify-content: center; height: 100vh; }
        .app { width: 100%; max-width: 450px; height: 100vh; background: #f8fafc; display: flex; flex-direction: column; overflow: hidden; }
        .screen { display: none; flex-direction: column; height: 100%; }
        .active { display: flex; }
        .header { background: #4f46e5; color: white; padding: 15px; font-weight: bold; text-align: center; }
        #chat-win { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #eef2f7; }
        .msg { padding: 10px 14px; border-radius: 15px; font-size: 14px; max-width: 80%; word-wrap: break-word; }
        .msg-in { background: white; align-self: flex-start; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .msg-out { background: #4f46e5; color: white; align-self: flex-end; }
        .f-item { background: white; margin: 8px 12px; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; cursor: pointer; }
        .nav { background: white; border-top: 1px solid #ddd; display: flex; height: 60px; }
        .nav-btn { flex: 1; border: none; background: none; color: #94a3b8; font-weight: bold; cursor: pointer; }
        .nav-btn.active { color: #4f46e5; }
        #auth { position: fixed; inset: 0; background: #1e293b; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }
    </style>
</head>
<body>
    <div id="auth">
        <h2>Private Chat</h2>
        <input type="password" id="pInp" placeholder="Пароль" style="padding:12px; border-radius:8px; border:none; margin:10px; text-align:center;">
        <button onclick="login()" style="padding:12px 24px; background:#4f46e5; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">ВОЙТИ</button>
    </div>

    <div class="app">
        <!-- Список чатов -->
        <div id="scr-list" class="screen">
            <div class="header">Мои чаты <button onclick="addF()" style="float:right; background:none; border:none; color:white; font-size:22px;">+</button></div>
            <div id="f-list" style="flex:1; overflow-y:auto; padding-top:10px;"></div>
            <div class="nav">
                <button class="nav-btn active" onclick="show('list')">ЧАТЫ</button>
                <button class="nav-btn" onclick="show('profile')">ПРОФИЛЬ</button>
            </div>
        </div>

        <!-- Окно чата -->
        <div id="scr-chat" class="screen">
            <div class="header">
                <button onclick="show('list')" style="float:left; background:none; border:none; color:white; font-size:18px;">←</button>
                <span id="c-title">Чат</span>
            </div>
            <div id="chat-win"></div>
            <div style="padding:10px; display:flex; gap:8px; background:white; border-top:1px solid #ddd;">
                <input type="text" id="mInp" placeholder="Сообщение..." style="flex:1; padding:12px; border-radius:20px; border:1px solid #ddd; outline:none;">
                <button onclick="send()" style="border:none; background:none; color:#4f46e5; font-weight:bold; cursor:pointer;">ОТПР.</button>
            </div>
        </div>

        <!-- Профиль -->
        <div id="scr-profile" class="screen">
            <div class="header">Ваш Профиль</div>
            <div style="padding:30px; text-align:center;">
                <p style="color:#64748b; font-size:13px;">Ваш ID (скопируйте целиком):</p>
                <b id="myID" style="background:#e2e8f0; padding:8px 15px; border-radius:6px; font-family:monospace; font-size:18px;"></b>
                <p style="margin-top:40px; color:#94a3b8; font-size:11px;">Чтобы начать чат, вы оба должны добавить друг друга по ID через кнопку +</p>
            </div>
            <div class="nav" style="margin-top:auto;">
                <button class="nav-btn" onclick="show('list')">ЧАТЫ</button>
                <button class="nav-btn active" onclick="show('profile')">ПРОФИЛЬ</button>
            </div>
        </div>
    </div>

    <script>
        const myUID = localStorage.getItem('uid') || 'ID' + Math.floor(Math.random()*9000+1000);
        localStorage.setItem('uid', myUID);
        let friends = JSON.parse(localStorage.getItem('f') || "[]");
        let ws = null, curRoom = null;

        document.getElementById('myID').innerText = myUID;

        function show(id) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById('scr-'+id).classList.add('active');
            if(id === 'list') render();
        }

        function login() {
            if (document.getElementById('pInp').value === "REPLACE_PWD") {
                document.getElementById('auth').style.display = 'none';
                show('list');
            } else alert("Неверно");
        }

        function addF() {
            const fid = prompt("Введите ID друга (вместе с буквами ID):");
            if (fid && fid.trim() !== "" && fid !== myUID) {
                if (!friends.find(f => f === fid)) {
                    friends.push(fid);
                    localStorage.setItem('f', JSON.stringify(friends));
                    render();
                }
            }
        }

        function render() {
            const list = document.getElementById('f-list');
            list.innerHTML = "";
            friends.forEach(fid => {
                const div = document.createElement('div');
                div.className = "f-item";
                // Создаем комнату: сортируем ID, чтобы у обоих был одинаковый ключ
                const rid = [myUID, fid].sort().join("_");
                div.onclick = () => openC(rid, "Чат с " + fid);
                div.innerHTML = `<b>Собеседник</b><br><small style="color:#94a3b8">${fid}</small>`;
                list.appendChild(div);
            });
        }

        function openC(rid, title) {
            curRoom = rid;
            document.getElementById('c-title').innerText = title;
            document.getElementById('chat-win').innerHTML = "";
            show('chat');
            
            if(ws) ws.close();
            const protocol = location.protocol === "https:" ? "wss://" : "ws://";
            ws = new WebSocket(protocol + location.host + "/ws/" + rid);
            
            ws.onmessage = (e) => {
                const d = JSON.parse(e.data);
                const win = document.getElementById('chat-win');
                const m = document.createElement('div');
                m.className = 'msg ' + (d.sender === myUID ? 'msg-out' : 'msg-in');
                m.textContent = d.text;
                win.appendChild(m);
                win.scrollTop = win.scrollHeight;
            };
        }

        function send() {
            const i = document.getElementById('mInp');
            if(i.value && ws && ws.readyState === WebSocket.OPEN) {
                const p = {sender: myUID, text: i.value};
                ws.send(JSON.stringify(p));
                
                // Сами себе отрисовываем сразу
                const win = document.getElementById('chat-win');
                const m = document.createElement('div');
                m.className = 'msg msg-out';
                m.textContent = i.value;
                win.appendChild(m);
                i.value = "";
                win.scrollTop = win.scrollHeight;
            } else if (ws.readyState !== WebSocket.OPEN) {
                alert("Соединение потеряно. Попробуйте перезайти в чат.");
            }
        }

        document.getElementById("mInp").onkeypress = (e) => { if(e.key === "Enter") send(); };
    </script>
</body>
</html>
""".replace("REPLACE_PWD", PWD)

@app.get("/")
async def get(): return HTMLResponse(html_content)

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            conn = sqlite3.connect("chat.db")
            conn.execute("INSERT INTO messages (room_id, sender_id, content) VALUES (?, ?, ?)", 
                         (room_id, data['sender'], data))
            conn.commit(); conn.close()
            await manager.broadcast(raw, room_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
