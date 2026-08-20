from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from database.connection import get_connection
from database.models import SOIL_COEFFICIENTS
import jwt
from config.security import JWT_SECRET as SECRET_KEY, ALGORITHM
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_admin_user(request: Request):
    """Проверяет, что пользователь админ, и возвращает его данные"""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT role FROM users WHERE id = ?", (payload.get("user_id"),)
        ).fetchone()
    finally:
        conn.close()
    if not row or row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return payload

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
            SELECT id, park_id, filename, original_name, created_at, user_id, comment
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
    """Отклоняет фото и удаляет файл с диска"""
    conn = get_connection()
    try:
        photo = conn.execute(
            "SELECT park_id, filename FROM park_photos WHERE id = ?", (photo_id,)
        ).fetchone()
        if not photo:
            raise HTTPException(status_code=404, detail="Фото не найдено")
        conn.execute("UPDATE park_photos SET status = 'rejected' WHERE id = ?", (photo_id,))
        conn.commit()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "data", "photos", photo["park_id"], photo["filename"])
        try:
            os.remove(filepath)
        except OSError as e:
            logger.error(f"Не удалось удалить файл {filepath}: {e}")
        return {"ok": True}
    finally:
        conn.close()

# ===== УПРАВЛЕНИЕ ПАРКАМИ =====
@router.get("/api/admin/parks")
async def get_all_parks_admin(user=Depends(get_admin_user)):
    """Все парки с editable-полями"""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM parks ORDER BY group_id, name").fetchall()
        parks = []
        for r in rows:
            p = dict(r)
            p["soil_options"] = list(SOIL_COEFFICIENTS.keys())
            parks.append(p)
        return parks
    finally:
        conn.close()

@router.put("/api/admin/parks/{park_id}")
async def update_park(park_id: str, data: dict, user=Depends(get_admin_user)):
    """Обновляет настройки парка"""
    allowed = {"name", "description", "trails_count", "soil_type", "forest_coef", "dry_hours_default", "is_active"}
    conn = get_connection()
    try:
        park = conn.execute("SELECT * FROM parks WHERE id = ?", (park_id,)).fetchone()
        if not park:
            raise HTTPException(status_code=404, detail="Парк не найден")
        updates = []
        values = []
        for key, val in data.items():
            if key in allowed:
                if key == "soil_type" and val not in SOIL_COEFFICIENTS:
                    raise HTTPException(status_code=400, detail=f"Недопустимый тип грунта: {val}")
                updates.append(f"{key} = ?")
                values.append(val)
        if not updates:
            return {"ok": False, "message": "Нет полей для обновления"}
        values.append(park_id)
        conn.execute(f"UPDATE parks SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

# ===== НОВЫЙ ЭНДПОИНТ ДЛЯ ОБНОВЛЕНИЯ =====
@router.post("/api/admin/refresh")
async def refresh_data(user=Depends(get_admin_user)):
    """Принудительное обновление данных в админке"""
    from api.cache import invalidate_cache
    invalidate_cache()
    return {"ok": True, "message": "Кеш сброшен, данные обновлены"}

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>Админ-панель — Что с грунтом?</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <meta name="theme-color" content="#0b0d14">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #0b0d14; color: #eef5ff; }
        .card { border: 1px solid rgba(74,144,226,0.25); border-radius: 12px; padding: 16px; margin: 12px 0; background: rgba(18,22,30,0.85); }
        .card h3 { font-size: 1rem; color: #b8d6ff; margin-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #333; padding: 8px; text-align: left; }
        th { background: #1a2a3a; }
        .error { color: #ff6b6b; }
        .hidden { display: none; }
        #login-form { max-width: 360px; margin: 40px auto; }
        #login-form input { display: block; width: 100%; box-sizing: border-box; padding: 14px; margin: 8px 0; border-radius: 10px; border: 1px solid #555; background: #1a1e2b; color: white; font-size: 16px; }
        #login-form button { width: 100%; padding: 14px; margin-top: 8px; border-radius: 10px; border: none; background: #4a90e2; color: white; font-size: 16px; font-weight: 600; cursor: pointer; }
        button { padding: 12px 20px; border-radius: 10px; border: none; cursor: pointer; font-size: 15px; font-weight: 500; }
        .approve-btn { background: #4caf50; color: white; }
        .reject-btn { background: #e74c3c; color: white; }
        .photo-item { margin: 10px 0; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 10px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .photo-item img { border-radius: 8px; max-width: 120px; }
        .promote-btn { background: #f39c12; color: white; }
        .tab-bar { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }
        .tab-btn { padding: 12px 16px; background: #1a2a3a; color: #94afcf; border: 1px solid rgba(74,144,226,0.25); border-radius: 10px 10px 0 0; cursor: pointer; font-weight: 600; transition: all 0.2s; font-size: 14px; }
        .tab-btn:hover { background: #1e3050; }
        .tab-btn.active { background: rgba(18,22,30,0.85); color: #eef5ff; border-bottom: 2px solid #4a90e2; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .header-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .header-actions button { flex: 1; min-width: 120px; }
        @media (max-width: 700px) {
            body { margin: 10px; }
            h1 { font-size: 20px; }
            .tab-bar { gap: 2px; }
            .tab-btn { padding: 10px 8px; font-size: 11px; flex: 1; text-align: center; }
            table { font-size: 12px; display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; }
            th, td { padding: 6px 4px; white-space: nowrap; }
            .photo-item { flex-direction: column; align-items: flex-start; }
            .photo-item img { max-width: 100%; }
            #login-form { margin: 20px 10px; }
        }
    </style>
</head>
<body>
    <h1>🚵 Админ-панель — Что с грунтом?</h1>

    <div id="login-form">
        <input type="text" id="email" placeholder="Email">
        <input type="password" id="password" placeholder="Пароль">
        <button onclick="login()">Войти</button>
        <span id="login-error" class="error"></span>
    </div>

    <div id="dashboard" class="hidden">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:15px;">
            <h2 style="margin:0;">🚵 Админ-панель</h2>
            <div class="header-actions">
                <button onclick="refreshAll()" style="background:#4caf50; color:white; font-weight:bold;">🔄 Обновить</button>
                <button onclick="logout()" style="background:#e74c3c; color:white;">Выйти</button>
            </div>
        </div>

        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('metrics', this)">📊 Метрики</button>
            <button class="tab-btn" onclick="switchTab('users', this)">👥 Пользователи</button>
            <button class="tab-btn" onclick="switchTab('parks', this)">🏞️ Парки</button>
            <button class="tab-btn" onclick="switchTab('photos', this)">🖼️ Модерация</button>
        </div>

        <div id="tab-metrics" class="tab-content active"><div id="metrics"></div></div>
        <div id="tab-users" class="tab-content"><div id="users-table"></div></div>
        <div id="tab-parks" class="tab-content"><div id="parks-table"></div></div>
        <div id="tab-photos" class="tab-content"><div id="photos-moderation"></div></div>
    </div>

    <script>
        let token = localStorage.getItem('admin_token') || '';

        function esc(s) {
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function switchTab(tab, btn) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }

        async function login() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password})
            });
            const data = await res.json();
            if (data.ok && data.role === 'admin') {
                token = data.token;
                localStorage.setItem('admin_token', token);
                document.getElementById('login-form').classList.add('hidden');
                document.getElementById('dashboard').classList.remove('hidden');
                loadAll();
            } else {
                document.getElementById('login-error').textContent = 'Неверный email или пароль';
            }
        }

        function logout() {
            token = '';
            localStorage.removeItem('admin_token');
            document.getElementById('login-form').classList.remove('hidden');
            document.getElementById('dashboard').classList.add('hidden');
        }

        async function loadAll() {
            loadMetrics();
            loadUsers();
            loadParks();
            loadPendingPhotos();
        }

        // Авто-логин при загрузке
        if (token) {
            document.getElementById('login-form').classList.add('hidden');
            document.getElementById('dashboard').classList.remove('hidden');
            loadAll();
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
            html += '<div class="card"><b>Пользователи:</b> всего ' + esc(data.users.total) + ', новых за 7 дней: ' + esc(data.users.new_7d) + '</div>';
            html += '<div class="card"><b>Запросы:</b> всего ' + esc(data.requests.total) + ', сегодня: ' + esc(data.requests.today) + '</div>';

            html += '<div class="card"><h3>Последние обновления погоды</h3><table><tr><th>Парк</th><th>Тип</th><th>Статус</th><th>Сообщение</th><th>Дата</th></tr>';
            for (const u of data.last_updates) {
                html += '<tr><td>' + esc(u.park_id) + '</td><td>' + esc(u.update_type) + '</td><td>' + esc(u.status) + '</td><td>' + esc(u.message||'') + '</td><td>' + esc(u.created_at) + '</td></tr>';
            }
            html += '</table></div>';

            if (data.last_errors.length > 0) {
                html += '<div class="card"><h3>Последние ошибки</h3><table><tr><th>Парк</th><th>Тип</th><th>Сообщение</th><th>Дата</th></tr>';
                for (const e of data.last_errors) {
                    html += '<tr><td>' + esc(e.park_id) + '</td><td>' + esc(e.update_type) + '</td><td>' + esc(e.message) + '</td><td>' + esc(e.created_at) + '</td></tr>';
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
                        <td>${esc(u.id)}</td>
                        <td>${esc(u.email)}</td>
                        <td>${esc(u.username || '—')}</td>
                        <td>${esc(u.role)}</td>
                        <td><strong>${esc(u.photo_votes_count || 0)}</strong></td>
                        <td>`;
                    if (!isAdmin) {
                        html += `<button class="promote-btn" onclick="promoteUser(${esc(u.id)})">⭐ Сделать админом</button>`;
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

        async function loadParks() {
            const res = await fetch('/api/admin/parks', {
                headers: {'Authorization': 'Bearer ' + token}
            });
            if (!res.ok) return;
            const parks = await res.json();
            let html = '<div class="card"><h3>🏞️ Парки</h3><table><tr><th>ID</th><th>Название</th><th>Группа</th><th>Трасс</th><th>Грунт</th><th>Лес</th><th>Описание</th><th></th></tr>';
            for (const p of parks) {
                html += `<tr>
                    <td>${esc(p.id)}</td>
                    <td><input type="text" id="name_${esc(p.id)}" value="${esc(p.name)}" style="width:120px;"></td>
                    <td>${esc(p.group_id)}</td>
                    <td><input type="number" id="trails_${esc(p.id)}" value="${esc(p.trails_count || 0)}" style="width:50px;"></td>
                    <td>
                        <select id="soil_${esc(p.id)}">
                            ${p.soil_options.map(s => `<option value="${esc(s)}" ${s === p.soil_type ? 'selected' : ''}>${esc(s)}</option>`).join('')}
                        </select>
                    </td>
                    <td><input type="number" id="forest_${esc(p.id)}" value="${esc(p.forest_coef)}" step="0.05" min="0" max="1" style="width:60px;"></td>
                    <td><input type="text" id="desc_${esc(p.id)}" value="${esc(p.description || '')}" style="width:160px;"></td>
                    <td><button onclick="savePark('${esc(p.id)}')" style="background:#4caf50; color:white; padding:6px 12px; border:none; border-radius:6px;">💾</button></td>
                </tr>`;
            }
            html += '</table></div>';
            document.getElementById('parks-table').innerHTML = html;
        }

        async function savePark(parkId) {
            const name = document.getElementById('name_' + parkId).value;
            const trails = parseInt(document.getElementById('trails_' + parkId).value) || 0;
            const soil = document.getElementById('soil_' + parkId).value;
            const forest = parseFloat(document.getElementById('forest_' + parkId).value) || 0;
            const desc = document.getElementById('desc_' + parkId).value;
            const res = await fetch('/api/admin/parks/' + parkId, {
                method: 'PUT',
                headers: {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                body: JSON.stringify({name, trails_count: trails, soil_type: soil, forest_coef: forest, description: desc})
            });
            if (res.ok) {
                loadParks();
            } else {
                alert('Ошибка сохранения');
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
                            <img src="/photos/${esc(p.park_id)}/${esc(p.filename)}" style="width:100px; height:100px; object-fit:cover; border-radius:8px;">
                            <div>
                                <b>Парк: ${esc(p.park_id)}</b><br>
                                <small>${esc(p.original_name)} (${esc(p.created_at)})</small>
                                ${p.comment ? `<br><span style="font-size:13px; color:#aaa;">💬 ${esc(p.comment)}</span>` : ''}
                            </div>
                            <button class="approve-btn" onclick="approvePhoto(${esc(p.id)})">✅ Одобрить</button>
                            <button class="reject-btn" onclick="rejectPhoto(${esc(p.id)})">❌ Отклонить</button>
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
                    await loadAll();
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