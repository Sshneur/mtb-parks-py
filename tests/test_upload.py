import base64
import time

from api.upload_utils import parse_file

TINY_JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def _data_uri(fmt, data):
    return f"data:{fmt};base64," + base64.b64encode(data).decode()


def test_parse_valid_jpg():
    bytes_out, ext, err = parse_file(_data_uri("image/jpeg", TINY_JPG))
    assert err is None
    assert ext == "jpg"
    assert bytes_out == TINY_JPG


def test_parse_valid_png():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    bytes_out, ext, err = parse_file(_data_uri("image/png", png))
    assert err is None
    assert ext == "png"
    assert bytes_out == png


def test_parse_rejects_exe():
    exe = b"MZ\x90\x00" + b"\x00" * 64
    _, _, err = parse_file(_data_uri("application/octet-stream", exe))
    assert err == "Недопустимый тип файла"


def test_parse_rejects_fake_jpeg():
    fake = b"notanimage\x00\x00\x00"
    _, _, err = parse_file(_data_uri("image/jpeg", fake))
    assert err == "Недопустимый тип файла"


def test_parse_rejects_oversized():
    big = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024 + 1)
    _, _, err = parse_file(_data_uri("image/jpeg", big))
    assert err == "Файл слишком большой (максимум 5 МБ)"


def test_parse_rejects_bad_base64():
    _, _, err = parse_file("data:image/jpeg;base64,!!!notbase64!!!")
    assert err == "Некорректные данные файла"


def test_parse_rejects_empty():
    _, _, err = parse_file("")
    assert err == "Файл не найден"


def test_upload_photo_endpoint(client):
    email = f"up_{int(time.time())}@t.ru"
    client.post("/api/auth/register", json={"email": email, "password": "password123", "username": "u"})
    login = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/park/fili/photos",
        json={"file": _data_uri("image/jpeg", TINY_JPG), "name": "test.jpg", "vote": "4", "comment": "ok"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True