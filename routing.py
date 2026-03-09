from typing import Dict, List, Any, Optional
from data_gyumri import get_nearby_places, _load_places
from logger_setup import log


def generate_programs(
    lat: float, lon: float, time_hours: float = 4.0, user_id: Optional[int] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Генерирует 3 варианта программы тура (Classic, Food, Chill walk).
    Возвращает словарь { program_id: [place_dict, ...] }
    """
    tag = f"[U:{user_id}]" if user_id else ""
    target_places_count = max(2, int((time_hours * 60) / 60))
    log.info(f"{tag}[ROUTING] Generating: lat={lat}, lon={lon}, time={time_hours}h, target={target_places_count}")

    nearby_all = get_nearby_places(lat, lon, max_distance_km=10.0, limit=50)
    log.debug(f"{tag}[ROUTING] Total nearby (10km): {len(nearby_all)}")

    cats = {}
    for p in nearby_all:
        c = p.get("category", "unknown")
        cats[c] = cats.get(c, 0) + 1
    log.debug(f"{tag}[ROUTING] Categories: {cats}")

    programs = {"classic": [], "food": [], "chill": []}

    # 1. Classic
    classic_candidates = [p for p in nearby_all if p.get("category") in ("sight", "museum", "historic_architecture")]
    log.debug(f"{tag}[ROUTING] Classic candidates: {len(classic_candidates)}")
    programs["classic"] = classic_candidates[:target_places_count + 1]

    # 2. Food
    food_candidates = [p for p in nearby_all if p.get("category") == "food"]
    log.debug(f"{tag}[ROUTING] Food candidates: {len(food_candidates)}")
    food_program = []
    if food_candidates:
        food_program.append(food_candidates[0])
    if len(classic_candidates) > 0:
        food_program.append(classic_candidates[0])
    if len(food_candidates) > 1:
        food_program.append(food_candidates[1])
    if len(classic_candidates) > 1 and len(food_program) < target_places_count:
        food_program.append(classic_candidates[1])
    programs["food"] = food_program[:target_places_count]

    # 3. Chill walk
    chill_count = max(2, target_places_count - 1)
    chill_candidates = [p for p in nearby_all if float(p.get("_distance_km", 999)) < 1.5]
    log.debug(f"{tag}[ROUTING] Chill candidates (<1.5km): {len(chill_candidates)}")
    programs["chill"] = chill_candidates[:chill_count]

    for prog_id, places in programs.items():
        names = [p.get("name_ru") or p.get("name_en") or p.get("name") or str(p.get("id", "Unknown")) for p in places]
        log.info(f"{tag}[ROUTING] '{prog_id}': {len(places)} places → {names}")

    return programs


def format_program_options(programs: Dict[str, List[Dict[str, Any]]], language: str = "ru") -> str:
    lines = []

    title_map = {
        "classic": {"ru": "🏛 Классический маршрут", "en": "🏛 Classic Route"},
        "food": {"ru": "🍽 Фуд-тур + Прогулка", "en": "🍽 Food Tour + Walk"},
        "chill": {"ru": "🍃 Спокойная прогулка (рядом)", "en": "🍃 Chill Walk (Nearby)"}
    }

    if language == "ru":
        lines.append("Я подготовил несколько вариантов программы специально для тебя:")
    else:
        lines.append("I have prepared several program options just for you:")

    lines.append("")

    for prog_id, places in programs.items():
        if not places:
            log.debug(f"[ROUTING] Skipping empty program '{prog_id}'")
            continue

        title = title_map.get(prog_id, {}).get(language, prog_id)
        place_names = []
        for p in places:
            name = p.get(f"name_{language}") or p.get("name_en") or p.get("name_ru") or p.get("name") or "Unknown"
            place_names.append(name)

        points_str = " -> ".join(place_names)
        lines.append(f"**{title}**")
        lines.append(f"Маршрут: {points_str}" if language == "ru" else f"Route: {points_str}")
        lines.append("")

    if language == "ru":
        lines.append("Какой вариант тебе больше по душе?")
    else:
        lines.append("Which option do you prefer?")

    result = "\n".join(lines)
    log.debug(f"[ROUTING] Formatted options ({len(result)} chars)")
    return result
