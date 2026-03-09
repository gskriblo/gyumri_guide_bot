import os
import json
import math
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# -----------------------------------------
# Настройки
# -----------------------------------------

load_dotenv()

OPENTRIPMAP_API_KEY = os.getenv("OPENTRIPMAP_API_KEY")

if not OPENTRIPMAP_API_KEY:
    raise RuntimeError("OPENTRIPMAP_API_KEY is not set in environment variables.")

# Центр Гюмри (приблизительно)
GYUMRI_LAT = 40.7893
GYUMRI_LON = 43.8476

# Радиус поиска в км (подбери по вкусу)
SEARCH_RADIUS_KM = 5.0

# Фильтры OpenTripMap по "kinds".
# Важно: значение kinds должно быть составлено из существующих категорий OTM.
# Например: interesting_places, museums, architecture, historic, cultural, monuments, foods.
# (Категории "sights" и "museum" у OTM НЕ существуют — будут 400.)
#
# Для MVP отдельно забираем "foods", иначе еда часто почти не попадает в выдачу.
SIGHT_KINDS = "interesting_places,museums,architecture,historic,cultural,monuments"
FOOD_KINDS = "foods"

# Минимальная популярность/рейтинг (см. docs: 1..3 и варианты *h)
SIGHT_RATE = "2h"  # чуть более качественные/"называемые" объекты + наследие
FOOD_RATE = "1"    # для еды лучше брать шире, иначе будет мало результатов

# Файл для сохранения результата (двуязычный JSON)
OUTPUT_JSON_PATH = "places_gyumri.json"

# Лимиты / настройки
MAX_SIGHT_PLACES = 180   # сколько POI запрашивать для sightseeing
MAX_FOOD_PLACES = 200    # сколько POI запрашивать для еды
REQUEST_SLEEP_SEC = 0.2  # пауза между запросами, чтобы не душить API


# -----------------------------------------
# Вспомогательные функции
# -----------------------------------------

def km_to_radius_m(km: float) -> int:
    """OpenTripMap принимает радиус в метрах."""
    return int(km * 1000)


def fetch_places_list(
    lat: float,
    lon: float,
    radius_km: float,
    limit: int = 150,
    lang: str = "en",
    kinds: Optional[str] = None,
    rate: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Берёт список мест вокруг заданной точки.
    Использует API OpenTripMap: /places/radius
    Документация: https://opentripmap.io/docs
    """
    radius_m = km_to_radius_m(radius_km)

    url = f"https://api.opentripmap.com/0.1/{lang}/places/radius"
    params = {
        "apikey": OPENTRIPMAP_API_KEY,
        "lat": lat,
        "lon": lon,
        "radius": radius_m,
        "limit": limit,
        "format": "json",
    }

    # kinds и rate — опциональные фильтры
    if kinds:
        params["kinds"] = kinds
    if rate:
        params["rate"] = rate

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # data — это список мест (каждый — dict c id / xid / point и т.д.)
    return data


def fetch_place_details(xid: str, lang: str = "en") -> Optional[Dict[str, Any]]:
    """
    Детальная информация по месту.
    /places/xid/{xid}
    """
    url = f"https://api.opentripmap.com/0.1/{lang}/places/xid/{xid}"
    params = {
        "apikey": OPENTRIPMAP_API_KEY,
    }

    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        print(f"Failed to fetch details for xid={xid}: {resp.status_code}")
        return None

    return resp.json()


def normalize_place_bilingual(raw_en: Dict[str, Any], raw_ru: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Приводим сырые данные OpenTripMap к нашему двуязычному формату Place.
    Берём координаты/технические поля из EN, а текст — из EN и RU.
    """

    xid = raw_en.get("xid") or raw_ru.get("xid")
    if not xid:
        return None

    # Координаты (берём из EN-ответа, при необходимости можно добавить более умную логику)
    point = raw_en.get("point") or raw_en.get("geometry", {}).get("coordinates") \
        or raw_ru.get("point") or raw_ru.get("geometry", {}).get("coordinates")
    if isinstance(point, dict):
        lat = point.get("lat")
        lon = point.get("lon")
    elif isinstance(point, list) and len(point) == 2:
        lon, lat = point
    else:
        lat = lon = None

    if lat is None or lon is None:
        return None

    # Названия на двух языках
    name_en = raw_en.get("name") or raw_en.get("title") or f"Place {xid}"
    name_ru = raw_ru.get("name") or raw_ru.get("title") or name_en

    # Категория / тип
    kinds = raw_en.get("kinds", "") or raw_ru.get("kinds", "")
    kinds_list = [k.strip() for k in kinds.split(",") if k.strip()]

    kinds_set = {k.lower() for k in kinds_list}

    def _has_any_substr(substrings: List[str]) -> bool:
        return any(any(s in k for s in substrings) for k in kinds_set)

    # Черновое отнесение к категориям (учитываем, что kinds бывают иерархические типа "catering.restaurant")
    if _has_any_substr(["food", "restaurant", "cafe", "bar", "fast_food"]):
        category = "food"
    elif _has_any_substr(["museum"]):
        category = "museum"
    elif _has_any_substr(["sight", "architecture", "historic", "interesting_places"]):
        category = "sight"
    else:
        category = "other"

    # Описания на двух языках (берём, что есть)
    raw_desc_en = (
        raw_en.get("wikipedia_extracts", {}).get("text")
        or raw_en.get("info", {}).get("descr")
        or ""
    )
    raw_desc_ru = (
        raw_ru.get("wikipedia_extracts", {}).get("text")
        or raw_ru.get("info", {}).get("descr")
        or ""
    )

    short_description_en = raw_desc_en.strip().split("\n")[0][:300] if raw_desc_en else ""
    short_description_ru = raw_desc_ru.strip().split("\n")[0][:300] if raw_desc_ru else ""

    # Рейтинг (в OpenTripMap это "rate" / "popularity", не классический рейтинг)
    rating = raw_en.get("rate") or raw_ru.get("rate")

    # Ссылка-источник
    otm_url = raw_en.get("otm") or raw_en.get("url") or raw_ru.get("otm") or raw_ru.get("url")

    place = {
        "id": xid,
        "name_en": name_en,
        "name_ru": name_ru,
        "lat": lat,
        "lon": lon,
        "category": category,
        "tags": kinds_list,
        "short_description_en": short_description_en,
        "short_description_ru": short_description_ru,
        "long_description_en": "",        # потом можно заполнить LLM или руками
        "long_description_ru": "",
        "typical_duration_min": None,     # оценим позже
        "price_level": None,              # для sight обычно None
        "rating": rating,
        "source": "opentripmap",
        "source_url": otm_url,
        "photo_urls": [],                 # можно донаполнить другим API или руками
    }
    return place


# -----------------------------------------
# Основной билд-процесс
# -----------------------------------------

def build_gyumri_db() -> List[Dict[str, Any]]:
    """
    Собирает двуязычную базу мест по Гюмри (EN + RU) и сохраняет в places_gyumri.json.

    Важно: OTM по умолчанию возвращает interesting_places, и еда часто почти не попадает.
    Поэтому для MVP отдельно забираем список foods и затем объединяем.
    """
    print("Fetching places list from OpenTripMap (EN) for sights...")
    raw_sights_en = fetch_places_list(
        GYUMRI_LAT,
        GYUMRI_LON,
        SEARCH_RADIUS_KM,
        limit=MAX_SIGHT_PLACES,
        lang="en",
        kinds=SIGHT_KINDS,
        rate=SIGHT_RATE,
    )
    print(f"Got {len(raw_sights_en)} raw sights (EN)")

    print("Fetching places list from OpenTripMap (EN) for foods...")
    raw_foods_en = fetch_places_list(
        GYUMRI_LAT,
        GYUMRI_LON,
        SEARCH_RADIUS_KM,
        limit=MAX_FOOD_PLACES,
        lang="en",
        kinds=FOOD_KINDS,
        rate=FOOD_RATE,
    )
    print(f"Got {len(raw_foods_en)} raw foods (EN)")

    # Объединяем списки по xid (чтобы не было дублей)
    items_by_xid: Dict[str, Dict[str, Any]] = {}
    for item in raw_sights_en:
        xid = item.get("xid")
        if xid:
            items_by_xid.setdefault(xid, item)
    for item in raw_foods_en:
        xid = item.get("xid")
        if xid:
            # Если объект попал и в sights, и в foods, лучше оставить foods-версию
            items_by_xid[xid] = item

    xids = list(items_by_xid.keys())
    print(f"Total unique xids to fetch details for: {len(xids)}")

    detailed_en: Dict[str, Dict[str, Any]] = {}
    detailed_ru: Dict[str, Dict[str, Any]] = {}

    # Для каждого места запросим детали на EN и RU
    for i, xid in enumerate(xids, start=1):
        item_en = items_by_xid[xid]
        print(f"[{i}/{len(xids)}] Fetching details for xid={xid} (EN/RU)")

        details_en = fetch_place_details(xid, lang="en")
        details_ru = fetch_place_details(xid, lang="ru")
        if details_en is None or details_ru is None:
            continue

        merged_en = {**item_en, **details_en}
        merged_ru = {**item_en, **details_ru}
        detailed_en[xid] = merged_en
        detailed_ru[xid] = merged_ru

        time.sleep(REQUEST_SLEEP_SEC)

    print(f"Got detailed info for {len(detailed_en)} places (EN/RU)")

    # Нормализация в двуязычный формат
    places: List[Dict[str, Any]] = []
    for xid, raw_en in detailed_en.items():
        raw_ru = detailed_ru.get(xid)
        if not raw_ru:
            continue

        place = normalize_place_bilingual(raw_en, raw_ru)
        if place:
            places.append(place)

    print(f"Normalized {len(places)} bilingual places")

    # Сохранение в JSON
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(places)} places to {OUTPUT_JSON_PATH}")
    return places


if __name__ == "__main__":
    build_gyumri_db()