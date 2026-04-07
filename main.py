import sqlite3, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI()
# ВАШ ПАРОЛЬ ТУТ
PWD = "1234"

def init_db():
    conn = sqlite3.connect("chat.db")
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, sender_id TEXT, sender_name TEXT, content TEXT)")
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
        
        conn = sqlite3.connect("chat.db"); cursor = conn.cursor()
        cursor.execute("SELECT sender_id, sender_name, content FROM messages WHERE room_id = ? ORDER BY id ASC", (room_id,))
        for row in cursor.fetchall():
            await websocket.send_text(json.dumps({"sender": row[0], "name": row[1], "text": row[2]}))
        conn.close()

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms: self.rooms[room_id].remove(websocket)

    async def broadcast(self, message_json: str, room_id: str, sender: WebSocket):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                if connection != sender: 
                    try:
                        await connection.send_text(message_json)
                    except:
                        pass

manager = ConnectionManager()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Messenger Fix</title>
    <style>
        body { background: #0f172a; margin: 0; font-family: sans-serif; display: flex; justify-content: center; height: 100vh; }
        .app { width: 100%; max-width: 450px; height: 100vh; background: #f8fafc; display: flex; flex-direction: column; overflow: hidden; }
        .screen { display: none; flex-direction: column; height: 100%; }
        .active { display: flex; }
        .header { background: #4f46e5; color: white; padding: 18px; font-weight: bold; text-align: center; }
        #chat-win { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #f1f5f9; }
        .msg { padding: 10px 14px; border-radius: 18px; font-size: 14px; max-width: 75%; }
        .msg-in { background: white; align-self: flex-start; }
        .msg-out { background: #4f46e5; color: white; align-self: flex-end; }
        .friend-item { background: white; margin: 8px 12px; padding: 15px; border-radius: 12px; display: flex; gap: 10px; cursor: pointer; border: 1px solid #e2e8f0; }
        .nav { background: white; border-top: 1px solid #e2e8f0; display: flex; height: 60px; }
        .nav-btn { flex: 1; border: none; background: none; color: #94a3b8; font-weight: bold; cursor: pointer; }
        .nav-btn.active { color: #4f46e5; }
        #scr-auth { position: fixed; inset: 0; background: #1e293b; z-index: 999; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }
    </style>
</head>
<body>
    <div id="scr-auth">
        <h2>Private Chat</h2>
        <input type="password" id="pInp" placeholder="Пароль" style="padding:10px; border-radius:8px; border:none; margin:10px;">
        <button onclick="login()" style="padding:10px 20px; background:#4f46e5; color:white; border:none; border-radius:8px;">Войти</button>
    </div>

    <div class="app">
        <div id="scr-list" class="screen">
            <div class="header">Чаты <button onclick="addFriend()" style="float:right; background:none; border:none; color:white; font-size:20px;">+</button></div>
            <div id="f-list" style="flex:1; overflow-y:auto;"></div>
            <div class="nav">
                <button class="nav-btn active" onclick="showScr('list')">ЧАТЫ</button>
                <button class="nav-btn" onclick="showScr('profile')">ПРОФИЛЬ</button>
            </div>
        </div>

        <div id="scr-chat" class="screen">
            <div class="header">
                <button onclick="showScr('list')" style="float:left; background:none; border:none; color:white;">←</button>
                <span id="c-title">Чат</span>
            </div>
            <div id="chat-win"></div>
            <div class="input-area" style="padding:10px; display:flex; gap:5px; background:white; border-top:1px solid #ddd;">
                <input type="text" id="mInp" placeholder="Сообщение..." style="flex:1; padding:10px; border-radius:20px; border:1px solid #ddd; outline:none;">
                <button onclick="sText()" style="background:none; border:none; color:#4f46e5; font-weight:bold;">ОТПР.</button>
            </div>
        </div>

        <div id="scr-profile" class="screen">
            <div class="header">Мой Профиль</div>
            <div style="padding:20px; text-align:center;">
                <p>Ваш ID (отправьте жене):</p>
                <b id="myID" style="background:#ddd; padding:5px 10px; border-radius:5px;"></b>
                <br><br>
                <input type="text" id="nInp" placeholder="Ваше Имя" onchange="saveP()" style="padding:10px; border-radius:8px; border:1px solid #ddd; width:80%;">
            </div>
            <div class="nav" style="margin-top:auto;">
                <button class="nav-btn" onclick="showScr('list')">ЧАТЫ</button>
                <button class="nav-btn active" onclick="showScr('profile')">ПРОФИЛЬ</button>
            </div>
        </div>
    </div>

    <script>
        const myUID = localStorage.getItem('uid') || 'ID' + Math.floor(Math.random()*9000+1000);
        localStorage.setItem('uid', myUID);
        let myName = localStorage.getItem('uname') || "Аноним";
        let friends = JSON.parse(localStorage.getItem('friends') || "[]");
        let ws = null, curRoom = null;

        document.getElementById('myID').innerText = myUID;
        document.getElementById('nInp').value = myName;

        function showScr(id) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById('scr-'+id).classList.add('active');
            if(id === 'list') renderF();
        }

        function login() {
            if (document.getElementById('pInp').value === "REPLACE_PWD") {
                document.getElementById('scr-auth').style.display = 'none';
                showScr('list');
            } else { alert("Неверно"); }
        }

        function addFriend() {
            const fid = prompt("Введите ID друга:");
            if (fid && fid !== myUID) {
                if (!friends.find(f => f.id === fid)) {
                    friends.push({id: fid, name: "Друг " + fid});
                    localStorage.setItem('friends', JSON.stringify(friends));
                    renderF();
                }
            }
        }

        function renderF() {
            const list = document.getElementById('f-list');
            list.innerHTML = "";
            friends.forEach(f => {
                const div = document.createElement('div');
                div.className = "friend-item";
                const rid = [myUID, f.id].sort().join("_");
                div.onclick = () => openC(rid, f.name);
                div.innerHTML = `<b>${f.name}</b><br><small>${f.id}</small>`;
                list.appendChild(div);
            });
        }

        function openC(rid, title) {
            curRoom = rid;
            document.getElementById('c-title').innerText = title;
            document.getElementById('chat-win').innerHTML = "";
            showScr('chat');
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

        function sText() {
            const i = document.getElementById('mInp');
            if(i.value && ws) {
                const p = {sender: myUID, name: myName, text: i.value};
                ws.send(JSON.stringify(p));
                const win = document.getElementById('chat-win');
                const m = document.createElement('div');
                m.className = 'msg msg-out';
                m.textContent = i.value;
                win.appendChild(m);
                i.value = "";
                win.scrollTop = win.scrollHeight;
            }
        }

        function saveP() {
            myName = document.getElementById('nInp').value;
            localStorage.setItem('uname', myName);
        }
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
            conn.execute("INSERT INTO messages (room_id, sender_id, sender_name, content) VALUES (?, ?, ?, ?)", 
                         (room_id, data['sender'], data['name'], data))
            conn.commit(); conn.close()
            await manager.broadcast(raw, room_id, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
