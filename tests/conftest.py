import os
import tempfile

import pytest
from dotenv import load_dotenv

import database.connection as db_conn

# Ключи (JWT_SECRET, YA_*) доступны как в проде, так и в тестах
load_dotenv()

# Свежая изолированная БД для всего тест-ранна, чтобы init_db/seed_parks в
# верхнем уровне main.py не трогали data/weather.db.
_TEST_DIR = tempfile.mkdtemp(prefix="gripcheck_tests_")
db_conn.DB_PATH = os.path.join(_TEST_DIR, "test.db")


def _fresh_db():
    """Инициализирует схему тестовой БД (зеркалит порядок из main.lifespan)."""
    db_conn.init_db()
    from database.crud import seed_parks
    seed_parks()
    from migrations.add_users_and_favorites import migrate as m1
    m1()
    from migrations.add_garage_tables import migrate as m2
    m2()
    from database.crud import apply_park_calibration
    apply_park_calibration()
    from migrations.add_oauth_columns import migrate as m4
    m4()
    from migrations.remove_favorites import migrate as m_rmfav
    m_rmfav()


@pytest.fixture(autouse=True)
def client():
    """Свежая БД + TestClient для каждого теста. Новый файл БД на тест —
    на Windows открытые sqlite-соединения мешают удалению старого файла.
    Lifespan не запускаем, чтобы updater/телеграм-бот не ходили в сеть."""
    db_conn.DB_PATH = os.path.join(_TEST_DIR, f"test_{id(object())}.db")
    _fresh_db()
    from api.limiter import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture()
def mock_open_meteo(monkeypatch):
    """Гард от живых HTTP-запросов: внешний клиент всегда отдаёт пустоту."""
    async def _no_net(*args, **kwargs):
        return {}

    monkeypatch.setattr("services.open_meteo.fetch_with_retry", _no_net)
    monkeypatch.setattr("services.open_meteo.get_forecast", _no_net)
    return _no_net