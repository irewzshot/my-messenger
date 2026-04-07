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

html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Pro Messenger</title>
    <style>
        /* ГЛОБАЛЬНЫЕ СТИЛИ */
        body {{ background-color: #0f172a; margin: 0; font-family: -apple-system, sans-serif; display: flex; justify-content: center; height: 100vh; color: #1e293b; }}
        .app-container {{ width: 100%; max-width: 450px; height: 100vh; background-color: #f1f5f9; position: relative; display: flex; flex-direction: column; box-shadow: 0 0 50px rgba(0,0,0,0.5); overflow: hidden; }}
        
        .screen {{ display: none; flex-direction: column; height: 100%; width: 100%; }}
        .active {{ display: flex; }}

        /* ШАПКА */
        .header {{ background-color: #4f46e5; color: white; padding: 16px; font-weight: 700; text-align: center; font-size: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 10; }}
        
        /* ЭКРАН ПАРОЛЯ */
        #scr-auth {{ background-color: #1e293b; align-items: center; justify-content: center; color: white; }}
        .auth-card {{ background: #334155; padding: 30px; border-radius: 24px; text-align: center; width: 80%; }}
        .input-field {{ width: 100%; padding: 12px; margin: 15px 0; border-radius: 12px; border: none; outline: none; font-size: 16px; box-sizing: border-box; }}
        .btn-primary {{ background: #4f46e5; color: white; border: none; padding: 14px 28px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 16px; }}

        /* СПИСОК ЧАТОВ */
        .room-item {{ background: white; margin: 8px 12px; padding: 16px; border-radius: 16px; display: flex; align-items: center; gap: 15px; cursor: pointer; transition: 0.2s; border: 1px solid #e2e8f0; }}
        .room-item:active {{ transform: scale(0.98); background: #f8fafc; }}
        .avatar {{ width: 48px; height: 48px; background: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; }}

        /* ЧАТ */
        #chat-window {{ flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #f8fafc; }}
        .msg {{ padding: 10px 14px; border-radius: 18px; font-size: 14px; max-width: 75%; line-height: 1.4; position: relative; }}
        .msg-in {{ background: white; align-self: flex-start; border-bottom-left-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .msg-out {{ background: #4f46e5; color: white; align-self: flex-end; border-bottom-right-radius: 4px; box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3); }}
        .msg-name {{ font-size: 10px; font-weight: 700; margin-bottom: 4px; opacity: 0.8; text-transform: uppercase; }}

        /* ВВОД */
        .input-area {{ background: white; padding: 12px; display: flex; gap: 8px; align-items: center; border-top: 1px solid #e2e8f0; }}
        .input-area input {{ flex: 1; padding: 12px 18px; border-radius: 24px; border: 1px solid #e2e8f0; outline: none; background: #f1f5f9; font-size: 15px; }}
        .btn-icon {{ background: none; border: none; font-size: 24px; cursor: pointer; padding: 5px; }}

        img {{ max-width: 100%; border-radius: 12px; margin-top: 5px; }}
        audio {{ max-width: 100%; height: 36px; margin-top: 5px; }}
        .recording {{ color: #ef4444; animation: pulse 1s infinite; }}
        @keyframes pulse {{ 50% {{ opacity: 0.4; }} }}
    </style>
</head>
<body>

    <div class="app-container">
        
        <!-- ЭКРАН ПАРОЛЯ -->
        <div id="scr-auth" class="screen active">
            <div class="auth-card">
                <div style="font-size: 50px; margin-bottom: 10px;">🔐</div>
                <div style="font-weight: 800; font-size: 20px; margin-bottom: 20px;">Messenger Pro</div>
                <input type="password" id="pInp" class="input-field" placeholder="Пароль">
                <button onclick="login()" class="btn-primary">Войти</button>
            </div>
        </div>

        <!-- СПИСОК ЧАТОВ -->
        <div id="scr-list" class="screen">
            <div class="header">Сообщения</div>
            <div style="flex: 1; overflow-y: auto; padding-top: 10px;">
                <div class="room-item" onclick="openRoom('general', '🌍 Общий чат')">
                    <div class="avatar">🌍</div>
                    <div><div style="font-weight:bold;">Общий чат</div><div style="font-size:12px; color:#64748b;">Все участники здесь</div></div>
                </div>
                <div class="room-item" onclick="openRoom('work', '💼 Рабочий чат')">
                    <div class="avatar">💼</div>
                    <div><div style="font-weight:bold;">Работа</div><div style="font-size:12px; color:#64748b;">Только важные дела</div></div>
                </div>
            </div>
        </div>

        <!-- ОКНО ЧАТА -->
        <div id="scr-chat" class="screen">
            <div class="header" style="display: flex; align-items: center; justify-content: space-between;">
                <button onclick="closeRoom()" style="background:none; border:none; color:white; font-size:24px; cursor:pointer;">←</button>
                <span id="chat-title">Чат</span>
                <div style="width:24px;"></div>
            </div>
            <div id="chat-window"></div>
            <div class="input-area">
                <input type="file" id="fInp" accept="image/*" style="display:none" onchange="sImg()">
                <button class="btn-icon" onclick="document.getElementById('fInp').click()">📎</button>
                <button id="vBtn" class="btn-icon" onclick="toggleVoice()">🎙️</button>
                <input type="text" id="mInp" placeholder="Сообщение..." autocomplete="off">
                <button onclick="sText()" style="background:none; border:none; color:#4f46e5; font-weight:800; cursor:pointer; padding: 0 10px;">ОТПР.</button>
            </div>
        </div>

    </div>

    <script>
        if (!localStorage.getItem('uid')) localStorage.setItem('uid', 'u'+Date.now());
        const uid = localStorage.getItem('uid');
        let uName = "Аноним", curRoom = null, ws = null, mediaRecorder, audioChunks = [];

        function showScr(id) {{
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById('scr-'+id).classList.add('active');
        }}

        function login() {{
            if (document.getElementById('pInp').value === "{SECRET_PASSWORD}") showScr('list');
            else alert("Неверный пароль!");
        }}

        function openRoom(id, title) {{
            curRoom = id;
            document.getElementById('chat-title').innerText = title;
            document.getElementById('chat-window').innerHTML = "";
            showScr('chat');
            if (ws) ws.close();
            ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/" + id);
            ws.onmessage = (e) => {{
                const data = JSON.parse(e.data);
                add(data, data.sender === uid);
            }};
        }}

        function closeRoom() {{ if(ws) ws.close(); showScr('list'); }}

        function add(data, out) {{
            const win = document.getElementById('chat-window');
            const d = document.createElement('div');
            d.className = 'msg ' + (out ? 'msg-out' : 'msg-in');
            
            let body = `<div class="msg-name" style="color: ${{out ? '#c7d2fe' : '#4f46e5'}}">${{out ? 'Вы' : data.name}}</div>`;
            if (data.text.startsWith("IMG:")) {{
                body += `<img src="${{data.text.replace("IMG:", "")}}">`;
            }} else if (data.text.startsWith("AUDIO:")) {{
                body += `<audio controls src="${{data.text.replace("AUDIO:", "")}}"></audio>`;
            }} else {{
                body += `<div>${{data.text}}</div>`;
            }}
            
            d.innerHTML = body;
            win.appendChild(d);
            win.scrollTop = win.scrollHeight;
        }}

        function sText() {{
            const i = document.getElementById('mInp');
            if (i.value && ws) {{
                const p = {{ sender: uid, name: uName, text: i.value }};
                ws.send(JSON.stringify(p));
                add(p, true); i.value = "";
            }}
        }}

        function sImg() {{
            const f = document.getElementById('fInp').files[0];
            const r = new FileReader();
            r.onload = (e) => {{
                const p = {{ sender: uid, name: uName, text: "IMG:" + e.target.result }};
                ws.send(JSON.stringify(p)); add(p, true);
            }};
            r.readAsDataURL(f);
        }}

        async function toggleVoice() {{
            const btn = document.getElementById('vBtn');
            if (!mediaRecorder || mediaRecorder.state === "inactive") {{
                const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                const mime = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm';
                mediaRecorder = new MediaRecorder(stream, {{ mimeType: mime }});
                audioChunks = [];
                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                mediaRecorder.onstop = () => {{
                    const blob = new Blob(audioChunks, {{ type: mime }});
                    const r = new FileReader();
                    r.onload = (e) => {{
                        const p = {{ sender: uid, name: uName, text: "AUDIO:" + e.target.result }};
                        ws.send(JSON.stringify(p)); add(p, true);
                    }};
                    r.readAsDataURL(blob);
                    stream.getTracks().forEach(t => t.stop());
                }};
                mediaRecorder.start(); btn.classList.add('recording');
            }} else {{ mediaRecorder.stop(); btn.classList.remove('recording'); }}
        }}

        document.getElementById("mInp").onkeypress = (e) => {{ if(e.key === "Enter") sText(); }};
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
                         (room_id, data['sender'], data['name'], data))
            conn.commit(); conn.close()
            await manager.broadcast(raw, room_id, websocket)
    except WebSocketDisconnect: manager.disconnect(websocket, room_id)
