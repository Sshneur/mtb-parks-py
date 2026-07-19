PARKS = {
    "mtb_parks": {
        "name": "МТБ Парки",
        "parks": [
            {"id": "fili", "name": "Парк Фили", "lat": 55.740384, "lon": 37.441293, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.6, "description": "Большой парк вдоль Москвы-реки. Хорошие грунтовые трассы для кросс-кантри.", "trails_count": 5},
            {"id": "erino", "name": "Байк Парк Ерино", "lat": 55.438771, "lon": 37.504228, "dry_hours": 48, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3, "description": "Специализированный байк-парк с трассами разного уровня.", "trails_count": 8},
            {"id": "chess", "name": "Чесс Парк", "lat": 55.567215, "lon": 37.539429, "dry_hours": 72, "start_date": None, "soil": "clay_heavy", "forest": True, "forest_coef": 0.15, "description": "Глинистый грунт — долго сохнет после дождя.", "trails_count": 4},
            {"id": "kozlovka", "name": "Парк Козловка", "lat": 54.831991, "lon": 38.125463, "dry_hours": 72, "start_date": None, "soil": "clay", "forest": True, "forest_coef": 0.3, "description": "Живописный парк в Подмосковье с лесными трассами.", "trails_count": 3},
            {"id": "krylatskoye", "name": "Крылатские холмы", "lat": 55.767675, "lon": 37.426816, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.6, "description": "Олимпийский велотрек и природные тропы в ООПТ.", "trails_count": 6}
        ]
    },
    "mtb_mountains": {
        "name": "МТБ Горы",
        "parks": [
            {"id": "arkhyz", "name": "Байк Парк Архыз", "lat": 43.562085, "lon": 41.187730, "dry_hours": 72, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3, "description": "Курортный байк-парк в горах Кавказа.", "trails_count": 10},
            {"id": "sober", "name": "Собер Трейл Парк", "lat": 44.704571, "lon": 38.539443, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3, "description": "Трассы в горах Краснодарского края.", "trails_count": 6},
            {"id": "novinki", "name": "Байк Парк Новинки", "lat": 56.196307, "lon": 43.840789, "dry_hours": 24, "start_date": None, "soil": "loam", "forest": True, "forest_coef": 0.3, "description": "Нижегородский байк-парк с современными трассами.", "trails_count": 7}
        ]
    },
    "pamps": {
        "name": "Пампы",
        "parks": [
            {"id": "fukushima", "name": "Памп Трек Фукусима", "lat": 55.625555, "lon": 37.587399, "dry_hours": 1, "start_date": None, "soil": "asphalt", "forest": False, "forest_coef": 1.0, "description": "Асфальтовый памп-трек, сохнет мгновенно.", "trails_count": 1},
            {"id": "yangel", "name": "Памп Янгеля", "lat": 55.597198, "lon": 37.580849, "dry_hours": 1, "start_date": None, "soil": "asphalt", "forest": False, "forest_coef": 1.0, "description": "Асфальтовый памп-трек на юге Москвы.", "trails_count": 1}
        ]
    }
}

SOIL_COEFFICIENTS = {
    "asphalt":     {"k_t": 0.15, "k_w": 0.20, "k_r": 0.002, "k_s": 0.05, "W0": 1.0},
    "sand":        {"k_t": 0.12, "k_w": 0.15, "k_r": 0.0015, "k_s": 0.03, "W0": 1.0},
    "loam":        {"k_t": 0.08, "k_w": 0.06, "k_r": 0.001, "k_s": 0.04, "W0": 1.0},
    "clay":        {"k_t": 0.05, "k_w": 0.03, "k_r": 0.0005, "k_s": 0.06, "W0": 1.0},
    "clay_heavy":  {"k_t": 0.01, "k_w": 0.01, "k_r": 0.0003, "k_s": 0.026, "W0": 1.0},
    "chernozem":   {"k_t": 0.07, "k_w": 0.05, "k_r": 0.001, "k_s": 0.05, "W0": 1.0}
}

FOREST_COEFFICIENT = 0.3
RAIN_HISTORY_HOURS = 144
