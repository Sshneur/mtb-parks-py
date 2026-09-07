import os
import time
import json
import asyncio
import logging
import httpx
import datetime
from database.connection import get_connection

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TG_ADMIN_ID")
PROXY_URL = os.getenv("PROXY_URL")
_APP_ENV = os.getenv("APP_ENV", "development")
_SERVER_ENV = "БОЕВОЙ" if _APP_ENV == "production" else "ТЕСТ"
_ENV_TAG = "\U0001f6e1\ufe0f [БОЕВОЙ]" if _APP_ENV == "production" else "\U0001f527 [ТЕСТ]"

BASE_URL = os.getenv("APP_URL", "https://gripcheck.ru" if _APP_ENV == "production" else "http://localhost:8000")

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

_sent_photo_ids = set()
_offset = 0
_client = None

_server_start = time.time()


def _get_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(proxy=PROXY_URL, timeout=30)
    return _client


async def _api_call(method, json_data=None):
    client = _get_client()
    url = f"{API_BASE}/{method}"
    try:
        if json_data:
            r = await client.post(url, json=json_data)
        else:
            r = await client.post(url)
        return r.json()
    except Exception as e:
        logger.error(f"Telegram API call failed ({method}): {e}")
        return {"ok": False}


async def send_photo_to_admin(photo):
    photo_id = photo["id"]
    park_id = photo["park_id"]
    filename = photo["filename"]
    original_name = photo.get("original_name", filename)
    created_at = photo.get("created_at", "")
    comment = photo.get("comment", "")

    conn = get_connection()
    try:
        row = conn.execute("SELECT name FROM parks WHERE id = ?", (park_id,)).fetchone()
        park_name = row["name"] if row else park_id
    finally:
        conn.close()

    caption = f"\U0001f5bc\ufe0f Новое фото на модерацию\n\n"
    caption += f"\U0001f3de\ufe0f Парк: {park_name} ({park_id})\n"
    caption += f"\U0001f4c1 Файл: {original_name}\n"
    caption += f"\U0001f550 Загружено: {created_at}"
    if comment:
        caption += f"\n\U0001f4ac Комментарий: {comment}"

    keyboard = {
        "inline_keyboard": [[
            {"text": "\u2705 Одобрить", "callback_data": f"approve:{photo_id}"},
            {"text": "\u274c Отклонить", "callback_data": f"reject:{photo_id}"}
        ]]
    }

    local_path = os.path.join(os.path.dirname(__file__), "data", "photos", park_id, filename)
    if os.path.exists(local_path):
        client = _get_client()
        url = f"{API_BASE}/sendPhoto"
        files = {"photo": (filename, open(local_path, "rb"), "image/jpeg")}
        data = {"chat_id": str(ADMIN_CHAT_ID), "caption": caption, "reply_markup": json.dumps(keyboard)}
        try:
            r = await client.post(url, data=data, files=files)
            result = r.json()
        except Exception as e:
            logger.error(f"Failed to send photo {photo_id} as file: {e}")
            result = {"ok": False}
        finally:
            files["photo"][1].close()
    else:
        result = await _api_call("sendPhoto", {
            "chat_id": ADMIN_CHAT_ID,
            "photo": f"{BASE_URL}/photos/{park_id}/{filename}",
            "caption": caption,
            "reply_markup": keyboard
        })

    if result.get("ok"):
        logger.info(f"Sent photo {photo_id} to admin")
    else:
        logger.warning(f"Failed to send photo {photo_id}: {result}")

    return result.get("ok", False)


async def send_request_to_admin(req):
    """Отправляет админу заявку «Предложи свой парк» с кнопками одобрения/отклонения."""
    caption = f"\U0001f64b Новое предложение парка\n\n"
    caption += f"\U0001f3de\ufe0f Парк: {req['name']}\n"
    caption += f"\U0001f4cd Координаты: {req['lat']}, {req['lon']}\n"
    if req.get("trails_count"):
        caption += f"\U0001f6b5 Трасс: {req['trails_count']}\n"
    if req.get("description"):
        caption += f"\U0001f4dd Описание: {req['description'][:200]}\n"
    if req.get("soil_description"):
        caption += f"\U0001f331 Грунт: {req['soil_description'][:200]}\n"
    if req.get("storm_drain"):
        caption += f"\U0001f4a7 Ливневки: {req['storm_drain'][:200]}\n"
    if req.get("tg_group"):
        caption += f"\U0001f517 Telegram-группа: {req['tg_group'][:200]}\n"
    if req.get("contact_tg"):
        caption += f"\U0001f4f1 Контакт для связи: {req['contact_tg'][:100]}\n"

    keyboard = {
        "inline_keyboard": [[
            {"text": "\u2705 Одобрить (быстро)", "callback_data": f"park_accept:{req['id']}"},
            {"text": "\u274c Отклонить", "callback_data": f"park_reject:{req['id']}"}
        ]]
    }

    result = await _api_call("sendMessage", {
        "chat_id": ADMIN_CHAT_ID,
        "text": caption,
        "reply_markup": keyboard
    })
    return result.get("ok", False)


async def check_pending_photos():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT id, park_id, filename, original_name, created_at, comment
            FROM park_photos
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """).fetchall()

        for row in rows:
            photo = dict(row)
            if photo["id"] not in _sent_photo_ids:
                ok = await send_photo_to_admin(photo)
                if ok:
                    _sent_photo_ids.add(photo["id"])
    finally:
        conn.close()


async def send_tech_monitor():
    conn = get_connection()
    try:
        uptime_sec = int(time.time() - _server_start)
        uptime_str = str(datetime.timedelta(seconds=uptime_sec))

        parks_total = conn.execute("SELECT COUNT(*) FROM parks").fetchone()[0]
        parks_active = conn.execute("SELECT COUNT(*) FROM parks WHERE is_active=1").fetchone()[0]
        parks_fresh = conn.execute(
            "SELECT COUNT(*) FROM parks WHERE last_updated > datetime('now', '-6 hours')"
        ).fetchone()[0]

        pending_photos = conn.execute("SELECT COUNT(*) FROM park_photos WHERE status='pending'").fetchone()[0]
        total_photos = conn.execute("SELECT COUNT(*) FROM park_photos").fetchone()[0]

        errors_24h = conn.execute(
            "SELECT COUNT(*) FROM update_log WHERE status='failed' AND created_at > datetime('now', '-24 hours')"
        ).fetchone()[0]

        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        total_req = conn.execute(
            "SELECT COUNT(DISTINCT ip) FROM request_log WHERE created_at > datetime('now', '-1 hour')"
        ).fetchone()[0]
        new_req = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT ip FROM request_log
                WHERE created_at > datetime('now', '-1 hour')
                GROUP BY ip HAVING MIN(created_at) > datetime('now', '-1 hour')
            )
        """).fetchone()[0]
        return_req = total_req - new_req

        reg_row = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN user_id IS NOT NULL THEN ip END),
                COUNT(DISTINCT CASE WHEN user_id IS NULL THEN ip END)
            FROM request_log WHERE created_at > datetime('now', '-1 hour')
        """).fetchone()
        registered_visitors = reg_row[0]
        anonymous_visitors = reg_row[1]

        new_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-1 hour')"
        ).fetchone()[0]

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        text = (
            f"{_ENV_TAG} \U0001f4a1 *Технический мониторинг*\n"
            f"\U0001f4c5 {now}\n\n"
            f"\U0001f552 *Аптайм:* {uptime_str}\n"
            f"\U0001f4be *БД:* {db_size / 1024:.0f} KB\n"
            f"\U0001f3de\ufe0f *Парки:* {parks_active}/{parks_total} активны\n"
            f"\U0001f504 *Свежих:* {parks_fresh} (<6ч)\n"
            f"\U0001f5bc *Фото:* {total_photos} всего, {pending_photos} ждут\n"
            f"\u26a0\ufe0f *Ошибок за 24ч:* {errors_24h}\n\n"
            f"\U0001f465 *Посетители за час:* {total_req}\n"
            f"  \U0001f195 Новые: {new_req} | \U0001f504 Повторные: {return_req}\n"
            f"  \U0001f464 Зарегистрировано: {registered_visitors}\n"
            f"  \U0001f481 Анонимно: {anonymous_visitors}\n"
            f"\U0001f4dd Новых регистраций: {new_users}"
        )
    except Exception as e:
        text = f"\u26a0\ufe0f *Ошибка мониторинга:* {e}"
    finally:
        conn.close()

    await _api_call("sendMessage", {
        "chat_id": ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })


_last_hourly_report = -1


async def check_hourly_monitor():
    global _last_hourly_report
    now = datetime.datetime.now()
    hour = now.hour
    if 8 <= hour <= 22 and hour != _last_hourly_report:
        _last_hourly_report = hour
        await send_tech_monitor()


async def handle_message(message):
    chat_id = message["from"]["id"]
    if chat_id != ADMIN_CHAT_ID:
        return
    text = message.get("text", "")
    if text == "/start":
        await _api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"\U0001f916 Привет! Я бот модерации фото {_ENV_TAG}.\n\nНовые фото приходят сюда автоматически. Используй кнопки Одобрить/Отклонить."
        })
    elif text == "/stats":
        conn = get_connection()
        try:
            pending = conn.execute("SELECT COUNT(*) FROM park_photos WHERE status='pending'").fetchone()[0]
            approved = conn.execute("SELECT COUNT(*) FROM park_photos WHERE status='approved'").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM park_photos WHERE status='rejected'").fetchone()[0]
        finally:
            conn.close()
        await _api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"{_ENV_TAG} *Статистика модерации:*\n- \u23f3 Ожидают: {pending}\n- \u2705 Одобрено: {approved}\n- \u274c Отклонено: {rejected}",
            "parse_mode": "Markdown"
        })
    elif text == "/monitor" or text == "/tech":
        await send_tech_monitor()


async def handle_callback(callback):
    chat_id = callback["from"]["id"]
    if chat_id != ADMIN_CHAT_ID:
        await _api_call("answerCallbackQuery", {
            "callback_query_id": callback["id"],
            "text": "Нет доступа к модерации"
        })
        return

    data = callback["data"]
    parts = data.split(":")
    action = parts[0]
    message_id = callback["message"]["message_id"]

    if action == "approve":
        photo_id = int(parts[1])
        conn = get_connection()
        try:
            conn.execute("UPDATE park_photos SET status = 'approved' WHERE id = ?", (photo_id,))
            conn.commit()
            text = "\u2705 Фото одобрено"
        except Exception as e:
            logger.error(f"Ошибка одобрения фото {photo_id}: {e}")
            text = "\u26a0\ufe0f Ошибка"
        finally:
            conn.close()
    elif action == "reject":
        photo_id = int(parts[1])
        conn = get_connection()
        try:
            conn.execute("UPDATE park_photos SET status = 'rejected' WHERE id = ?", (photo_id,))
            conn.commit()
            text = "\u274c Фото отклонено"
        except Exception as e:
            logger.error(f"Ошибка отклонения фото {photo_id}: {e}")
            text = "\u26a0\ufe0f Ошибка"
        finally:
            conn.close()
    elif action == "park_accept":
        request_id = int(parts[1])
        try:
            from services.park_requests import approve_park_request
            result = approve_park_request(request_id)
            text = f"\u2705 Заявка одобрена! Парк создан: /park/{result['park_id']}"
        except ValueError as e:
            text = f"\u26a0\ufe0f {e}"
        except Exception as e:
            logger.error(f"Ошибка одобрения заявки {request_id}: {e}")
            text = "\u26a0\ufe0f Ошибка одобрения"
    elif action == "park_reject":
        request_id = int(parts[1])
        try:
            from services.park_requests import reject_park_request
            if reject_park_request(request_id):
                text = "\u274c Заявка отклонена"
            else:
                text = "\u26a0\ufe0f Заявка не найдена"
        except ValueError as e:
            text = f"\u26a0\ufe0f {e}"
        except Exception as e:
            logger.error(f"Ошибка отклонения заявки {request_id}: {e}")
            text = "\u26a0\ufe0f Ошибка отклонения"
    else:
        return

    await _api_call("answerCallbackQuery", {
        "callback_query_id": callback["id"],
        "text": text
    })

    await _api_call("editMessageReplyMarkup", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": []}
    })


async def start_polling():
    global _offset, ADMIN_CHAT_ID

    if not BOT_TOKEN or not ADMIN_CHAT_ID or not PROXY_URL:
        logger.error(
            "Бот не запущен: задайте TG_BOT_TOKEN, TG_ADMIN_ID и PROXY_URL в переменных окружения"
        )
        return

    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

    logger.info("Starting Telegram bot polling...")

    # Закрываем старый polling-коннект (другой сервер или упавший процесс)
    close_result = await _api_call("close")
    if close_result.get("ok"):
        logger.info("Closed previous Telegram polling connection")
    else:
        logger.warning(f"Telegram close result: {close_result}")

    last_check = 0.0
    notified = False

    try:
        while True:
            now = time.monotonic()

            # Отправляем уведомление о старте при первой возможности (не блокируя polling)
            if not notified:
                notified = True
                try:
                    await _api_call("sendMessage", {
                        "chat_id": ADMIN_CHAT_ID,
                        "text": f"\U0001f916 Бот модерации фото запущен {_ENV_TAG}"
                    })
                except Exception:
                    pass

            try:
                if now - last_check > 30:
                    await check_pending_photos()
                    last_check = now
            except Exception as e:
                logger.error(f"Bot check_pending_photos error: {e}")

            try:
                await check_hourly_monitor()
            except Exception as e:
                logger.error(f"Bot hourly monitor error: {e}")

            try:
                result = await _api_call("getUpdates", {
                    "offset": _offset,
                    "timeout": 30,
                    "allowed_updates": ["callback_query", "message"]
                })

                if result.get("ok") and result.get("result"):
                    for update in result["result"]:
                        _offset = update["update_id"] + 1
                        try:
                            if "callback_query" in update:
                                await handle_callback(update["callback_query"])
                            elif "message" in update:
                                await handle_message(update["message"])
                        except Exception as e:
                            logger.error(f"Bot update handler error: {e}")
                elif not result.get("ok") and result.get("error_code") == 409:
                    logger.warning("409 Conflict — closing old connection and retrying")
                    await _api_call("close")
            except Exception as e:
                logger.error(f"Bot getUpdates error: {e}")
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        await _api_call("sendMessage", {
            "chat_id": ADMIN_CHAT_ID,
            "text": f"\U0001f6ab Бот модерации остановлен {_ENV_TAG}"
        })
        if _client:
            await _client.aclose()
