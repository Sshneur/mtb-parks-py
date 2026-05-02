PARKS = {
    "mtb_parks": {
        "name": "МТБ Парки",
        "parks": [
            {"id": "fili", "name": "Парк Фили", "lat": 55.740384, "lon": 37.441293, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.6},
            {"id": "erino", "name": "Байк Парк Ерино", "lat": 55.438771, "lon": 37.504228, "dry_hours": 48, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3},
            {"id": "chess", "name": "Чесс Парк", "lat": 55.567215, "lon": 37.539429, "dry_hours": 72, "start_date": None, "soil": "clay_heavy", "forest": True, "forest_coef": 0.1},
            {"id": "kozlovka", "name": "Парк Козловка", "lat": 54.831991, "lon": 38.125463, "dry_hours": 72, "start_date": None, "soil": "clay", "forest": True, "forest_coef": 0.3}
        ]
    },
    "mtb_mountains": {
        "name": "МТБ Горы",
        "parks": [
            {"id": "arkhyz", "name": "Байк Парк Архыз", "lat": 43.562085, "lon": 41.187730, "dry_hours": 72, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3},
            {"id": "sober", "name": "Собер Трейл Парк", "lat": 44.704571, "lon": 38.539443, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3},
            {"id": "novinki", "name": "Байк Парк Новинки", "lat": 56.196307, "lon": 43.840789, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3}
        ]
    },
    "pamps": {
        "name": "Пампы",
        "parks": [
            {"id": "fukushima", "name": "Памп Трек Фукусима", "lat": 55.625555, "lon": 37.587399, "dry_hours": 1, "start_date": None, "soil": "asphalt", "forest": False, "forest_coef": 1.0},
            {"id": "yangel", "name": "Памп Янгеля", "lat": 55.597198, "lon": 37.580849, "dry_hours": 1, "start_date": None, "soil": "asphalt", "forest": False, "forest_coef": 1.0}
        ]
    }
}

SOIL_COEFFICIENTS = {
    "asphalt":     {"k_t": 0.15, "k_w": 0.20, "k_s": 0.05, "W0": 1.0},
    "sand":        {"k_t": 0.12, "k_w": 0.15, "k_s": 0.03, "W0": 1.0},
    "loam":        {"k_t": 0.08, "k_w": 0.06, "k_s": 0.04, "W0": 1.0},
    "clay":        {"k_t": 0.05, "k_w": 0.03, "k_s": 0.06, "W0": 1.0},
    "clay_heavy":  {"k_t": 0.01, "k_w": 0.01, "k_s": 0.026, "W0": 1.0},
    "chernozem":   {"k_t": 0.07, "k_w": 0.05, "k_s": 0.05, "W0": 1.0}
}

FOREST_COEFFICIENT = 0.3
RAIN_HISTORY_HOURS = 144