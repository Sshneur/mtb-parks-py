import base64
import time
from collections import defaultdict

MAX_BASE64_SIZE = 5 * 1024 * 1024
MAX_DECODED_SIZE = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MIME_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

_upload_times: dict[int, list[float]] = defaultdict(list)


def parse_file(file_data: str):
    if not file_data or "," not in file_data:
        return None, "", "Файл не найден"
    if len(file_data) > MAX_BASE64_SIZE:
        return None, "", "Файл слишком большой (максимум 5 МБ)"
    header, encoded = file_data.split(",", 1)
    mime = ""
    if header.startswith("data:") and ";" in header:
        mime = header[5:].split(";", 1)[0]
    try:
        file_bytes = base64.b64decode(encoded, validate=False)
    except Exception:
        return None, "", "Некорректные данные файла"
    if len(file_bytes) > MAX_DECODED_SIZE:
        return None, "", "Файл слишком большой (максимум 5 МБ)"
    if mime not in ALLOWED_MIME or not _magic_ok(file_bytes, mime):
        return None, "", "Недопустимый тип файла"
    return file_bytes, MIME_EXT.get(mime, "jpg"), None


def body_too_large(request) -> bool:
    content_length = request.headers.get("content-length")
    return bool(content_length and content_length.isdigit() and int(content_length) > MAX_BASE64_SIZE + 64 * 1024)


def check_upload_limit(user_id: int, limit: int = 10, window: int = 3600) -> bool:
    now = time.time()
    times = _upload_times[user_id]
    while times and times[0] < now - window:
        times.pop(0)
    if len(times) >= limit:
        return False
    times.append(now)
    return True


def _magic_ok(data: bytes, mime: str) -> bool:
    if mime == "image/jpeg":
        return data[:3] == b"\xff\xd8\xff"
    if mime == "image/png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if mime == "image/gif":
        return data[:6] in (b"GIF87a", b"GIF89a")
    if mime == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False