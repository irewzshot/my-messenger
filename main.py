import sqlite3, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict

app = FastAPI()
SECRET_PASSWORD = "1234"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chat.db")
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, sender_id TEXT, sender_name TEXT, content TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS profiles (uid TEXT PRIMARY KEY, name TEXT, avatar TEXT)")
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
                if connection != sender: await connection.send_text(message_json)

manager = ConnectionManager()

html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pro Messenger</title>
    <style>
        body { background: #0f172a; margin: 0; font-family: -apple-system, sans-serif; display: flex; justify-content: center; height: 100vh; color: #1e293b; }
        .app { width: 100%; max-width: 450px; height: 100vh; background: #f8fafc; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .screen { display: none; flex-direction: column; height: 100%; width: 100%; }
        .active { display: flex; }
        
        .header { background: #4f46e5; color: white; padding: 18px; font-weight: bold; text-align: center; font-size: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        
        /* Список чатов */
        .friend-item { background: white; margin: 8px 12px; padding: 14px; border-radius: 16px; display: flex; align-items: center; gap: 12px; cursor: pointer; border: 1px solid #e2e8f0; transition: 0.2s; }
        .friend-item:active { transform: scale(0.98); background: #f1f5f9; }
        .av-mini { width: 48px; height: 48px; background: #e2e8f0; border-radius: 50%; object-fit: cover; }

        /* Чат */
        #chat-win { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #f1f5f9; }
        .msg { padding: 10px 14px; border-radius: 18px; font-size: 14px; max-width: 75%; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .msg-in { background: white; align-self: flex-start; border-bottom-left-radius: 4px; }
        .msg-out { background: #4f46e5; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        
        .input-area { background: white; padding: 12px; display: flex; gap: 10px; border-top: 1px solid #e2e8f0; }
        .input-area input { flex: 1; padding: 12px; border-radius: 24px; border: 1px solid #e2e8f0; outline: none; background: #f8fafc; }
        
        /* Профиль */
        .profile-card { padding: 30px; text-align: center; flex: 1; }
        .av-big { width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid white; box-shadow: 0 10px 20px rgba(0,0,0,0.1); cursor: pointer; }
        
        /* Навигация */
        .nav { background: white; border-top: 1px solid #e2e8f0; display: flex; height: 70px; padding-bottom: env(safe-area-inset-bottom); }
        .nav-btn { flex: 1; border: none; background: none; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; color: #94a3b8; transition: 0.3s; }
        .nav-btn.active { color: #4f46e5; }
        .nav-icon { font-size: 22px; }

        /* Авторизация */
        #scr-auth { background: #1e293b; align-items: center; justify-content: center; color: white; z-index: 1000; }
        .card { background: #334155; padding: 30px; border-radius: 28px; width: 80%; text-align: center; }
        .btn-auth { width: 100%; padding: 14px; background: #4f46e5; color: white; border: none; border-radius: 14px; font-weight: bold; margin-top: 10px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="app">
        <!-- ЭКРАН ПАРОЛЯ -->
        <div id="scr-auth" class="screen active">
            <div class="card">
                <div style="font-size: 50px; margin-bottom: 10px;">🔐</div>
                <h2 style="margin-bottom: 20px;">Messenger Pro</h2>
                <input type="password" id="pInp" placeholder="Пароль" style="width:100%; padding:14px; border-radius:12px; border:none; box-sizing: border-box; text-align:center;">
                <button onclick="login()" class="btn-auth">Войти</button>
            </div>
        </div>

        <!-- СПИСОК ЧАТОВ -->
        <div id="scr-list" class="screen">
            <div class="header">Чаты <button onclick="addFriend()" style="float:right; background:none; border:none; color:white; font-size:24px;">+</button></div>
            <div id="friends-list" style="flex:1; overflow-y:auto; padding-top:10px;"></div>
            <div class="nav">
                <button class="nav-btn active" onclick="showScr('list')"><span class="nav-icon">💬</span><span style="font-size:11px;">Чаты</span></button>
                <button class="nav-btn" onclick="showScr('profile')"><span class="nav-icon">👤</span><span style="font-size:11px;">Профиль</span></button>
            </div>
        </div>

        <!-- ОКНО ЧАТА -->
        <div id="scr-chat" class="screen">
            <div class="header">
                <button onclick="showScr('list')" style="float:left; background:none; border:none; color:white; font-size:20px;">←</button>
                <span id="chat-title">Чат</span>
            </div>
            <div id="chat-win"></div>
            <div class="input-area">
                <input type="file" id="fInp" accept="image/*" style="display:none" onchange="sImg()">
                <button onclick="document.getElementById('fInp').click()" style="background:none; border:none; font-size:24px;">📎</button>
                <input type="text" id="mInp" placeholder="Сообщение..." autocomplete="off">
                <button onclick="sText()" style="background:none; border:none; color:#4f46e5; font-weight:bold; font-size:16px;">ОТПР.</button>
            </div>
        </div>

        <!-- ПРОФИЛЬ -->
        <div id="scr-profile" class="screen">
            <div class="header">Настройки профиля</div>
            <div class="profile-card">
                <input type="file" id="avInp" accept="image/*" style="display:none" onchange="updateAv()">
                <img id="myAv" src="https://placeholder.com" class="av-big" onclick="document.getElementById('avInp').click()">
                <p style="font-size:12px; color:#64748b; margin: 15px 0 5px;">Ваш ID для друзей:</p>
                <code id="myID" style="background:#e2e8f0; padding:4px 8px; border-radius:6px; font-weight:bold;"></code>
                
                <div style="margin-top:25px; text-align:left;">
                    <label style="font-size:11px; color:#64748b; margin-left:10px;">ВАШЕ ИМЯ</label>
                    <input type="text" id="nameInp" style="width:100%; padding:14px; border-radius:14px; border:1px solid #e2e8f0; margin-top:5px; box-sizing:border-box;" onchange="saveProfile()">
                </div>
                
                <button onclick="location.reload()" style="margin-top:50px; color:#ef4444; border:none; background:none; font-weight:bold; cursor:pointer;">Выйти из аккаунта</button>
            </div>
            <div class="nav">
                <button class="nav-btn" onclick="showScr('list')"><span class="nav-icon">💬</span><span style="font-size:11px;">Чаты</span></button>
                <button class="nav-btn active" onclick="showScr('profile')"><span class="nav-icon">👤</span><span style="font-size:11px;">Профиль</span></button>
            </div>
        </div>
    </div>

    <script>
        if (!localStorage.getItem('uid')) localStorage.setItem('uid', 'ID' + Math.floor(Math.random()*9000+1000));
        const uid = localStorage.getItem('uid');
        let uName = localStorage.getItem('uname') || "Пользователь";
        let uAv = localStorage.getItem('uav') || "https://placeholder.com";
        let friends = JSON.parse(localStorage.getItem('friends') || "[]");
        let ws = null, curRoom = null;

        document.getElementById('myID').innerText = uid;
        document.getElementById('nameInp').value = uName;
        document.getElementById('myAv').src = uAv;

        function showScr(id) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById('scr-'+id).classList.add('active');
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            if(id === 'list') renderFriends();
        }

        function login() {
            if (document.getElementById('pInp').value === "{SECRET_PASSWORD}") showScr('list');
            else alert("Неверный пароль");
        }

        function addFriend() {
            const fID = prompt("Введите ID друга:");
            if (fID && fID !== uid) {
                if (!friends.find(f => f.id === fID)) {
                    friends.push({ id: fID, name: "Друг " + fID });
                    localStorage.setItem('friends', JSON.stringify(friends));
                    renderFriends();
                }
            }
        }

        function renderFriends() {
            const list = document.getElementById('friends-list');
            list.innerHTML = "";
            friends.forEach(f => {
                const div = document.createElement('div');
                div.className = "friend-item";
                const rid = [uid, f.id].sort().join("_");
                div.onclick = () => openChat(rid, f.name);
                div.innerHTML = `<img src="https://placeholder.com" class="av-mini"><div><div style="font-weight:bold;">${f.name}</div><div style="font-size:11px; color:#64748b;">${f.id}</div></div>`;
                list.appendChild(div);
            });
        }

        function openChat(rid, title) {
            curRoom = rid;
            document.getElementById('chat-title').innerText = title;
            document.getElementById('chat-win').innerHTML = "";
            showScr('chat');
            if(ws) ws.close();
            ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/" + rid);
            ws.onmessage = (e) => {
                const d = JSON.parse(e.data);
                append(d, d.sender === uid);
            };
        }

        function append(d, out) {
            const w = document.getElementById('chat-win');
            const m = document.createElement('div');
            m.className = 'msg ' + (out ? 'msg-out' : 'msg-in');
            if (d.text.startsWith("IMG:")) {
                m.innerHTML = `<img src="${d.text.replace("IMG:", "")}">`;
            } else {
                m.textContent = d.text;
            }
            w.appendChild(m);
            w.scrollTop = w.scrollHeight;
        }

        function sText() {
            const i = document.getElementById('mInp');
            if(i.value && ws) {
                const p = { sender: uid, name: uName, text: i.value };
                ws.send(JSON.stringify(p));
                append(p, true);
                i.value = "";
            }
        }

        function sImg() {
            const f = document.getElementById('fInp').files[0];
            const r = new FileReader();
            r.onload = (e) => {
                const b = "IMG:" + e.target.result;
                ws.send(JSON.stringify({ sender: uid, name: uName, text: b }));
                append({text: b}, true);
            };
            r.readAsDataURL(f);
        }

        function updateAv() {
            const f = document.getElementById('avInp').files[0];
            const r = new FileReader();
            r.onload = (e) => {
                uAv = e.target.result;
                document.getElementById('myAv').src = uAv;
                localStorage.setItem('uav', uAv);
            };
            r.readAsDataURL(f);
        }

        function saveProfile() {
            uName = document.getElementById('nameInp').value;
            localStorage.setItem('uname', uName);
        }

        document.getElementById("mInp").onkeypress = (e) => { if(e.key === "Enter") sText(); };
    </script>
</body>
</html>
""".replace("{SECRET_PASSWORD}", SECRET_PASSWORD)

@app.get("/")
async def get(): return HTMLResponse(html_template)

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
    except WebSocketDisconnect: manager.disconnect(websocket, room_id)
