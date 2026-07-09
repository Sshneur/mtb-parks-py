from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from database.connection import get_connection
from jose import jwt
import os

router = APIRouter()
SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"

def get_admin_user(request: Request):
    """Проверяет, что пользователь админ, и возвращает его данные"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        return payload
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Неверный токен")

@router.get("/api/admin/metrics")
async def get_metrics(user=Depends(get_admin_user)):
    """Возвращает JSON с метриками"""
    conn = get_connection()
    try:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_users_7d = conn.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-7 days')"
        ).fetchone()[0]

        total_requests = conn.execute("SELECT COUNT(*) FROM request_log").fetchone()[0]
        today_requests = conn.execute(
            "SELECT COUNT(*) FROM request_log WHERE date(created_at) = date('now')"
        ).fetchone()[0]

        updates = conn.execute(
            "SELECT * FROM update_log ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        errors = conn.execute(
            "SELECT * FROM update_log WHERE status='failed' ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

        return {
            "users": {"total": total_users, "new_7d": new_users_7d},
            "requests": {"total": total_requests, "today": today_requests},
            "last_updates": [dict(u) for u in updates],
            "last_errors": [dict(e) for e in errors]
        }
    finally:
        conn.close()

@router.get("/api/admin/users")
async def get_users(user=Depends(get_admin_user)):
    """Возвращает список всех пользователей с колонкой photo_votes_count"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, email, username, role, created_at, photo_votes_count FROM users ORDER BY photo_votes_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.post("/api/admin/users/{user_id}/promote")
async def promote_user(user_id: int, admin_user=Depends(get_admin_user)):
    """Повышает пользователя до админа (только для админов)"""
    conn = get_connection()
    try:
        user = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if user["role"] == "admin":
            return {"ok": True, "message": "Пользователь уже админ"}
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
        conn.commit()
        return {"ok": True, "message": f"Пользователь {user_id} теперь админ"}
    finally:
        conn.close()

@router.get("/api/admin/photos/pending")
async def get_pending_photos(user=Depends(get_admin_user)):
    """Возвращает список фото, ожидающих модерации"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT id, park_id, filename, original_name, created_at, user_id
            FROM park_photos
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@router.post("/api/admin/photos/{photo_id}/approve")
async def approve_photo(photo_id: int, user=Depends(get_admin_user)):
    """Одобряет фото"""
    conn = get_connection()
    try:
        conn.execute("UPDATE park_photos SET status = 'approved' WHERE id = ?", (photo_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@router.post("/api/admin/photos/{photo_id}/reject")
async def reject_photo(photo_id: int, user=Depends(get_admin_user)):
    """Отклоняет фото"""
    conn = get_connection()
    try:
        conn.execute("UPDATE park_photos SET status = 'rejected' WHERE id = ?", (photo_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

# ===== НОВЫЙ ЭНДПОИНТ ДЛЯ ОБНОВЛЕНИЯ =====
@router.post("/api/admin/refresh")
async def refresh_data(user=Depends(get_admin_user)):
    """Принудительное обновление данных в админке"""
    return {"ok": True, "message": "Данные обновлены"}

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Отдаёт HTML админ-панели"""
    return HTMLResponse(content=ADMIN_HTML)

# ===== ОБНОВЛЁННЫЙ HTML =====
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Админ-панель МТБ Парки</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background: #0b0d14; color: #eef5ff; }
        .card { border: 1px solid rgba(74,144,226,0.25); border-radius: 8px; padding: 16px; margin: 10px 0; background: rgba(18,22,30,0.85); }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #333; padding: 8px; text-align: left; }
        th { background: #1a2a3a; }
        .error { color: #ff6b6b; }
        .hidden { display: none; }
        #login-form { margin-bottom: 20px; }
        input { padding: 8px; margin: 4px; border-radius: 6px; border: 1px solid #555; background: #1a1e2b; color: white; }
        button { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; }
        .approve-btn { background: #4caf50; color: white; }
        .reject-btn { background: #e74c3c; color: white; }
        .photo-item { margin: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .promote-btn { background: #f39c12; color: white; }
    </style>
</head>
<body>
    <h1>🚵 Админ-панель МТБ Парки 2.0</h1>

    <div id="login-form">
        <input type="text" id="email" placeholder="Email">
        <input type="password" id="password" placeholder="Пароль">
        <button onclick="login()">Войти</button>
        <span id="login-error" class="error"></span>
    </div>

    <div id="dashboard" class="hidden">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
            <h2>📊 Метрики</h2>
            <button onclick="refreshAll()" style="padding:10px 24px; background:#4caf50; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">🔄 Обновить данные</button>
        </div>
        <div id="metrics"></div>
        <div id="users-table"></div>
        <div id="photos-moderation"></div>
        <button onclick="logout()" style="margin-top:20px; background:#e74c3c; color:white; padding:10px 20px; border:none; border-radius:8px; cursor:pointer;">Выйти</button>
    </div>

    <script>
        let token = '';

        async function login() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password})
            });
            const data = await res.json();
            if (data.ok) {
                token = data.token;
                document.getElementById('login-form').classList.add('hidden');
                document.getElementById('dashboard').classList.remove('hidden');
                loadMetrics();
                loadUsers();
                loadPendingPhotos();
            } else {
                document.getElementById('login-error').textContent = 'Неверный email или пароль';
            }
        }

        function logout() {
            token = '';
            document.getElementById('login-form').classList.remove('hidden');
            document.getElementById('dashboard').classList.add('hidden');
        }

        async function loadMetrics() {
            const res = await fetch('/api/admin/metrics', {
                headers: {'Authorization': 'Bearer ' + token}
            });
            const data = await res.json();
            if (res.status !== 200) {
                alert('Доступ запрещён');
                logout();
                return;
            }
            let html = '';
            html += '<div class="card"><b>Пользователи:</b> всего ' + data.users.total + ', новых за 7 дней: ' + data.users.new_7d + '</div>';
            html += '<div class="card"><b>Запросы:</b> всего ' + data.requests.total + ', сегодня: ' + data.requests.today + '</div>';

            html += '<div class="card"><h3>Последние обновления погоды</h3><table><tr><th>Парк</th><th>Тип</th><th>Статус</th><th>Сообщение</th><th>Дата</th></tr>';
            for (const u of data.last_updates) {
                html += '<tr><td>' + u.park_id + '</td><td>' + u.update_type + '</td><td>' + u.status + '</td><td>' + (u.message||'') + '</td><td>' + u.created_at + '</td></tr>';
            }
            html += '</table></div>';

            if (data.last_errors.length > 0) {
                html += '<div class="card"><h3>Последние ошибки</h3><table><tr><th>Парк</th><th>Тип</th><th>Сообщение</th><th>Дата</th></tr>';
                for (const e of data.last_errors) {
                    html += '<tr><td>' + e.park_id + '</td><td>' + e.update_type + '</td><td>' + e.message + '</td><td>' + e.created_at + '</td></tr>';
                }
                html += '</table></div>';
            }
            document.getElementById('metrics').innerHTML = html;
        }

        async function loadUsers() {
            const res = await fetch('/api/admin/users', {
                headers: {'Authorization': 'Bearer ' + token}
            });
            if (res.ok) {
                const users = await res.json();
                let html = '<div class="card"><h3>👥 Пользователи</h3><table><tr><th>ID</th><th>Email</th><th>Никнейм</th><th>Роль</th><th>Оценок</th><th>Действие</th></tr>';
                for (const u of users) {
                    const isAdmin = u.role === 'admin';
                    html += `<tr>
                        <td>${u.id}</td>
                        <td>${u.email}</td>
                        <td>${u.username || '—'}</td>
                        <td>${u.role}</td>
                        <td><strong>${u.photo_votes_count || 0}</strong></td>
                        <td>`;
                    if (!isAdmin) {
                        html += `<button class="promote-btn" onclick="promoteUser(${u.id})">⭐ Сделать админом</button>`;
                    } else {
                        html += `<span style="color:#4caf50;">✅ Админ</span>`;
                    }
                    html += `</td></tr>`;
                }
                html += '</table></div>';
                document.getElementById('users-table').innerHTML = html;
            }
        }

        async function promoteUser(userId) {
            if (!confirm('Подтвердите повышение пользователя до администратора?')) return;
            const res = await fetch('/api/admin/users/' + userId + '/promote', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + token}
            });
            if (res.ok) {
                alert('Пользователь повышен до админа!');
                loadUsers();
            } else {
                alert('Ошибка при повышении');
            }
        }

        async function loadPendingPhotos() {
            const res = await fetch('/api/admin/photos/pending', {
                headers: {'Authorization': 'Bearer ' + token}
            });
            if (res.ok) {
                const photos = await res.json();
                let html = '<div class="card"><h3>🖼️ Модерация фото</h3>';
                if (photos.length === 0) {
                    html += '<p>Нет фото, ожидающих проверки.</p>';
                } else {
                    for (const p of photos) {
                        html += `<div class="photo-item">
                            <img src="/photos/${p.park_id}/${p.filename}" style="width:100px; height:100px; object-fit:cover; border-radius:8px;">
                            <div>
                                <b>Парк: ${p.park_id}</b><br>
                                <small>${p.original_name} (${p.created_at})</small>
                            </div>
                            <button class="approve-btn" onclick="approvePhoto(${p.id})">✅ Одобрить</button>
                            <button class="reject-btn" onclick="rejectPhoto(${p.id})">❌ Отклонить</button>
                        </div>`;
                    }
                }
                html += '</div>';
                document.getElementById('photos-moderation').innerHTML = html;
            }
        }

        async function approvePhoto(photoId) {
            await fetch('/api/admin/photos/' + photoId + '/approve', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + token}
            });
            loadPendingPhotos();
        }

        async function rejectPhoto(photoId) {
            await fetch('/api/admin/photos/' + photoId + '/reject', {
                method: 'POST',
                headers: {'Authorization': 'Bearer ' + token}
            });
            loadPendingPhotos();
        }

        // === НОВАЯ ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ===
        async function refreshAll() {
            const btn = event.target;
            btn.textContent = '⏳ Обновление...';
            btn.disabled = true;
            try {
                const res = await fetch('/api/admin/refresh', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (res.ok) {
                    await loadMetrics();
                    await loadUsers();
                    await loadPendingPhotos();
                    btn.textContent = '✅ Обновлено';
                    setTimeout(() => { btn.textContent = '🔄 Обновить данные'; btn.disabled = false; }, 1500);
                } else {
                    alert('Ошибка обновления');
                    btn.textContent = '🔄 Обновить данные';
                    btn.disabled = false;
                }
            } catch (e) {
                alert('Ошибка сети');
                btn.textContent = '🔄 Обновить данные';
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""