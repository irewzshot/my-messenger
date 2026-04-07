import sqlite3
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

# --- КОНФИГУРАЦИЯ ---
SECRET_PASSWORD = "1234" 

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chat.db")
    # Создаем таблицу с ID отправителя и контентом
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id TEXT, content TEXT)")
    conn.commit()
    conn.close()

# Удалите старый chat.db перед запуском, если структура поменялась!
init_db()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Отправка истории
        conn = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("SELECT sender_id, content FROM messages ORDER BY id ASC")
        for row in cursor.fetchall():
            # row[0] - это sender_id, row[1] - это content
            await websocket.send_text(json.dumps({"sender": row[0], "text": row[1]}))
        conn.close()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message_json: str, sender: WebSocket):
        for connection in self.active_connections:
            if connection != sender:
                await connection.send_text(message_json)

manager = ConnectionManager()

html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fixed Messenger</title>
    <style>
        body {{ background: #1e293b; display: flex; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }}
        .app {{ background: #e6ebee; width: 100%; max-width: 450px; height: 100vh; display: flex; flex-direction: column; position: relative; }}
        #auth-screen {{ position: absolute; inset: 0; background: #1e293b; z-index: 100; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }}
        .pass-input {{ padding: 12px; border-radius: 12px; border: none; margin: 15px; text-align: center; width: 200px; outline: none; }}
        .header {{ background: #517da2; color: white; padding: 15px; text-align: center; font-weight: bold; }}
        #chat {{ flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }}
        .msg {{ padding: 10px 14px; border-radius: 14px; font-size: 15px; max-width: 85%; box-shadow: 0 1px 2px rgba(0,0,0,0.1); word-wrap: break-word; }}
        .msg-in {{ background: white; align-self: flex-start; border-bottom-left-radius: 4px; }}
        .msg-out {{ background: #effdde; align-self: flex-end; border-bottom-right-radius: 4px; border: 1px solid #dcfce7; }}
        .input-area {{ background: white; padding: 12px; display: flex; gap: 10px; align-items: center; border-top: 1px solid #ddd; }}
        input[type="text"] {{ flex: 1; padding: 10px; border-radius: 20px; border: 1px solid #ddd; outline: none; }}
        img, audio {{ max-width: 100%; border-radius: 10px; margin-top: 5px; display: block; }}
        .btn-icon {{ font-size: 24px; cursor: pointer; border: none; background: none; }}
        .recording {{ color: red; animation: pulse 1s infinite; }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
    </style>
</head>
<body>
    <div class="app">
        <div id="auth-screen">
            <h3>Введите пароль</h3>
            <input type="password" id="pInp" class="pass-input">
            <button onclick="login()" style="background: #4f46e5; color: white; border: none; padding: 10px 30px; border-radius: 12px; cursor: pointer;">Войти</button>
        </div>

        <div class="header">Secure Messenger</div>
        <div id="chat"></div>
        <div class="input-area">
             <input type="file" id="fInp" accept="image/*" style="display:none" onchange="sImg()">
             <button class="btn-icon" onclick="document.getElementById('fInp').click()">📎</button>
             <button id="vBtn" class="btn-icon" onclick="toggleVoice()">🎙️</button>
             <input type="text" id="mInp" placeholder="Сообщение..." autocomplete="off">
             <button onclick="sText()" style="color:#517da2; font-weight:bold; border:none; background:none; cursor:pointer;">ОТПР.</button>
        </div>
    </div>

    <script>
        // Сохраняем уникальный ID в браузере
        if (!localStorage.getItem('myChatID')) {{
            localStorage.setItem('myChatID', 'user_' + Math.floor(Math.random() * 1000000));
        }}
        const myID = localStorage.getItem('myChatID');

        let ws;
        const chat = document.getElementById('chat');

        function login() {{
            if (document.getElementById('pInp').value === "{SECRET_PASSWORD}") {{
                document.getElementById('auth-screen').style.display = 'none';
                startChat();
            }} else {{ alert("Неверно!"); }}
        }}

        function startChat() {{
            ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
            
            ws.onmessage = (e) => {{
                try {{
                    const data = JSON.parse(e.data);
                    addMsg(data.text, data.sender === myID);
                }} catch (err) {{ console.error("Ошибка парсинга:", err); }}
            }};
        }}

        function addMsg(data, out) {{
            const d = document.createElement('div');
            d.className = 'msg ' + (out ? 'msg-out' : 'msg-in');
            if (data.startsWith("IMG:")) {{
                const i = document.createElement('img'); i.src = data.replace("IMG:", ""); d.appendChild(i);
            }} else if (data.startsWith("AUDIO:")) {{
                const a = document.createElement('audio'); a.controls = true; a.src = data.replace("AUDIO:", ""); d.appendChild(a);
            }} else {{ d.textContent = data; }}
            chat.appendChild(d);
            chat.scrollTop = chat.scrollHeight;
        }}

        function sText() {{
            const i = document.getElementById('mInp');
            if (i.value && ws) {{
                const payload = JSON.stringify({{ sender: myID, text: i.value }});
                ws.send(payload);
                addMsg(i.value, true);
                i.value = '';
            }}
        }}

        function sImg() {{
            const f = document.getElementById('fInp').files[0];
            if (!f) return;
            const r = new FileReader();
            r.onload = (e) => {{
                const b = "IMG:" + e.target.result;
                ws.send(JSON.stringify({{ sender: myID, text: b }}));
                addMsg(b, true);
            }};
            r.readAsDataURL(f);
        }}

        // --- ГОЛОСОВЫЕ ---
        let mediaRecorder;
        let audioChunks = [];
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
                        const b = "AUDIO:" + e.target.result;
                        ws.send(JSON.stringify({{ sender: myID, text: b }}));
                        addMsg(b, true);
                    }};
                    r.readAsDataURL(blob);
                    stream.getTracks().forEach(t => t.stop());
                }};
                mediaRecorder.start();
                btn.classList.add('recording');
            }} else {{
                mediaRecorder.stop();
                btn.classList.remove('recording');
            }}
        }}

        document.getElementById("mInp").onkeypress = (e) => {{ if(e.key === "Enter") sText(); }};
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
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            # Сохраняем в базу
            conn = sqlite3.connect("chat.db")
            conn.execute("INSERT INTO messages (sender_id, content) VALUES (?, ?)", (data['sender'], data['text']))
            conn.commit()
            conn.close()
            
            # Рассылаем всем кроме себя
            await manager.broadcast(raw_data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
