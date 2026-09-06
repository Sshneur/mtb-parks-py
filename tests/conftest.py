import os
import tempfile

import pytest

import database.connection as db_conn

# Переключаем БД ДО импорта main: main на верхнем уровне вызывает init_db/seed_parks,
# и это должно попадать в изолированную тестовую БД, а не в data/weather.db.
TEST_DB_DIR = tempfile.mkdtemp(prefix="gripcheck_tests_")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "test.db")
db_conn.DB_PATH = TEST_DB_PATH


def _fresh_db():
    """Пересоздаёт схему тестовой БД перед каждым тестом."""
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(TEST_DB_PATH + suffix)
        except OSError:
            pass
    db_conn.init_db()
    from database.crud import seed_parks
    seed_parks()
    from migrations.add_users_and_favorites import migrate as m1
    m1()
    from migrations.add_garage_tables import migrate as m2
    m2()
    from database.crud import apply_park_calibration
    apply_park_calibration()


@pytest.fixture(autouse=True)
def client():
    """Свежая БД + TestClient для каждого теста. Lifespan не запускаем,
    чтобы updater/телеграм-бот не ходили в сеть."""
    _fresh_db()
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