import sqlite3
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

# --- КОНФИГУРАЦИЯ ---
SECRET_PASSWORD = "Busya.2320"  # <--- ИЗМЕНИТЕ ПАРОЛЬ ЗДЕСЬ

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chat.db")
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT)")
    conn.commit()
    conn.close()

init_db()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Отправка истории при входе
        conn = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM messages ORDER BY id ASC")
        for row in cursor.fetchall():
            await websocket.send_text(row[0])
        conn.close()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str, sender: WebSocket):
        for connection in self.active_connections:
            if connection != sender:
                await connection.send_text(message)

manager = ConnectionManager()

html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Private Messenger</title>
    <style>
        body {{ background: #1e293b; display: flex; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }}
        .app {{ background: #e6ebee; width: 100%; max-width: 450px; height: 100vh; display: flex; flex-direction: column; position: relative; }}
        
        /* Экран пароля */
        #auth-screen {{ position: absolute; inset: 0; background: #1e293b; z-index: 100; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; }}
        .pass-input {{ padding: 12px; border-radius: 12px; border: none; margin: 15px; text-align: center; width: 200px; outline: none; color: #333; }}
        
        .header {{ background: #517da2; color: white; padding: 15px; text-align: center; font-weight: bold; font-size: 18px; }}
        #chat {{ flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }}
        .msg {{ padding: 10px 14px; border-radius: 14px; font-size: 15px; max-width: 85%; box-shadow: 0 1px 2px rgba(0,0,0,0.1); word-wrap: break-word; }}
        .msg-in {{ background: white; align-self: flex-start; border-bottom-left-radius: 4px; }}
        .msg-out {{ background: #effdde; align-self: flex-end; border-bottom-right-radius: 4px; border: 1px solid #dcfce7; }}
        
        .input-area {{ background: white; padding: 12px; display: flex; gap: 10px; align-items: center; border-top: 1px solid #ddd; }}
        input {{ flex: 1; padding: 10px 15px; border-radius: 20px; border: 1px solid #ddd; outline: none; }}
        
        img {{ max-width: 100%; border-radius: 10px; margin-top: 5px; display: block; }}
        audio {{ max-width: 100%; height: 40px; margin-top: 5px; display: block; }}
        
        .btn-icon {{ font-size: 24px; cursor: pointer; border: none; background: none; transition: 0.2s; }}
        .recording {{ color: red; animation: pulse 1s infinite; transform: scale(1.2); }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
    </style>
</head>
<body>
    <div class="app">
        <!-- Экран авторизации -->
        <div id="auth-screen">
            <div style="font-size: 40px;">🔐</div>
            <h3>Доступ ограничен</h3>
            <input type="password" id="pInp" class="pass-input" placeholder="Введите пароль">
            <button onclick="login()" style="background: #4f46e5; color: white; border: none; padding: 10px 30px; border-radius: 12px; cursor: pointer;">Войти</button>
        </div>

        <div class="header">Private Chat</div>
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
        let ws;
        const chat = document.getElementById('chat');
        let mediaRecorder;
        let audioChunks = [];

        async function login() {{
            const pass = document.getElementById('pInp').value;
            // Простая проверка пароля (для полной защиты лучше делать через fetch на сервер)
            if (pass === "{SECRET_PASSWORD}") {{
                document.getElementById('auth-screen').style.display = 'none';
                startChat();
            }} else {{
                alert("Неверный пароль!");
            }}
        }}

        function startChat() {{
            ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
            
            ws.onmessage = (e) => addMsg(e.data, false);
            
            ws.onclose = () => {{
                alert("Соединение потеряно. Обновите страницу.");
            }};
        }}

        function addMsg(data, out) {{
            const d = document.createElement('div');
            d.className = 'msg ' + (out ? 'msg-out' : 'msg-in');
            
            if (data.startsWith("IMG:")) {{
                const i = document.createElement('img'); i.src = data.replace("IMG:", ""); d.appendChild(i);
            }} else if (data.startsWith("AUDIO:")) {{
                const a = document.createElement('audio'); a.controls = true; a.src = data.replace("AUDIO:", ""); d.appendChild(a);
            }} else {{
                d.textContent = data;
            }}
            chat.appendChild(d);
            chat.scrollTop = chat.scrollHeight;
        }}

        function sText() {{
            const i = document.getElementById('mInp');
            if (i.value && ws) {{ ws.send(i.value); addMsg(i.value, true); i.value = ''; }}
        }}

        function sImg() {{
            const f = document.getElementById('fInp').files[0];
            if (!f) return;
            const r = new FileReader();
            r.onload = (e) => {{ const b = "IMG:" + e.target.result; ws.send(b); addMsg(b, true); }};
            r.readAsDataURL(f);
        }}

        async function toggleVoice() {{
            const btn = document.getElementById('vBtn');
            if (!mediaRecorder || mediaRecorder.state === "inactive") {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                    const mimeType = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm';
                    mediaRecorder = new MediaRecorder(stream, {{ mimeType }});
                    audioChunks = [];
                    mediaRecorder.ondataavailable = e => {{ if(e.data.size > 0) audioChunks.push(e.data); }};
                    mediaRecorder.onstop = () => {{
                        const blob = new Blob(audioChunks, {{ type: mimeType }});
                        const reader = new FileReader();
                        reader.onload = (e) => {{
                            const b = "AUDIO:" + e.target.result;
                            ws.send(b); addMsg(b, true);
                        }};
                        reader.readAsDataURL(blob);
                        stream.getTracks().forEach(t => t.stop());
                    }};
                    mediaRecorder.start();
                    btn.classList.add('recording');
                }} catch(e) {{ alert("Микрофон недоступен"); }}
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
            data = await websocket.receive_text()
            # Сохранение в базу
            conn = sqlite3.connect("chat.db")
            conn.execute("INSERT INTO messages (content) VALUES (?)", (data,))
            conn.commit()
            conn.close()
            # Рассылка другим
            await manager.broadcast(data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
