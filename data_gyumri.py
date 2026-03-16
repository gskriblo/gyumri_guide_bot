import json
import math
import os
from typing import Any, Dict, List, Optional, Set, Tuple


_PLACES: List[Dict[str, Any]] = []


def _load_places() -> List[Dict[str, Any]]:
    global _PLACES
    if _PLACES:
        return _PLACES

    base_dir = os.path.dirname(__file__)

    # Default to the OSM dataset
    env_path = os.environ.get("PLACES_JSON")
    candidates = [
        env_path,
        os.path.join(base_dir, "places_gyumri.json"),
    ]

    path = next((p for p in candidates if p and os.path.exists(p)), None)
    if path is None:
        raise FileNotFoundError(
            "Places database not found. Tried PLACES_JSON, places_gyumri.json."
        )

    with open(path, "r", encoding="utf-8") as f:
        _PLACES = json.load(f)

    return _PLACES


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Приближённое расстояние между двумя точками на сфере в километрах.
    Для нашего города этого более чем достаточно.
    """
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def get_nearby_places(
    lat: float,
    lon: float,
    max_distance_km: float = 2.0,
    limit: int = 5,
    categories: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Возвращает ближайшие к пользователю места в пределах max_distance_km.
    """
    places = _load_places()

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for p in places:
        # Compatibility with both OSM and OTM formats
        p_lat = float(p.get("lat", 0))
        p_lon = float(p.get("lon", 0))
        if p_lat == 0 or p_lon == 0:
            continue

        # Extract category (OSM logic)
        cat = p.get("category", "other")
        tags = p.get("tags", {})
        if cat == "other" and isinstance(tags, dict):
            amenity = tags.get("amenity", "")
            tourism = tags.get("tourism", "")
            if amenity in ("restaurant", "cafe", "fast_food", "bar", "pub"):
                cat = "food"
            elif tourism in ("attraction", "museum", "viewpoint", "gallery"):
                cat = "sight"
            elif tags.get("historic"):
                cat = "historic_architecture"
            
        # Temporarily store normalized category in place dict for easier filtering
        p["_normalized_category"] = cat

        if categories is not None and cat not in categories:
            continue

        dist = _haversine_km(lat, lon, p_lat, p_lon)
        if dist <= max_distance_km:
            scored.append((dist, p))

    scored.sort(key=lambda x: x[0])
    top = scored[:limit]

    result: List[Dict[str, Any]] = []
    for dist, p in top:
        copy = dict(p)
        copy["_distance_km"] = round(dist, 2)
        # Ensure category is set
        copy["category"] = p.get("_normalized_category", "other")
        copy["image_url"] = p.get("image_url")
        
        # Normalize names from OSM tags if needed
        if "tags" in p and isinstance(p["tags"], dict):
            tags = p["tags"]
            name = tags.get("name", p.get("name", "Unknown"))
            copy["name_en"] = tags.get("name:en", name)
            copy["name_ru"] = tags.get("name:ru", name)
            
            # Simple description string from tags (OSM doesn't have descriptions usually)
            cuisine = tags.get("cuisine")
            phone = tags.get("phone", tags.get("contact:phone"))
            desc_parts = []
            if cuisine: desc_parts.append(f"Cuisine: {cuisine}")
            if copy["category"] == "food": desc_parts.append("Food & Dining")
            if phone: desc_parts.append(f"Phone: {phone}")
            
            base_desc = " | ".join(desc_parts) if desc_parts else ""
            copy["short_description_en"] = base_desc
            copy["short_description_ru"] = base_desc
        
        result.append(copy)

    return result


def has_real_name(p: dict) -> bool:
    for key in ("name_ru", "name_en", "name"):
        v = p.get(key, "")
        if v and v.strip().lower() != "unknown":
            return True
    return False



def search_places_by_keywords(
    keywords: List[str],
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """
    Returns places whose name / category / tags contain at least one keyword.
    Ranked by number of keyword hits (descending). Falls back to all named
    places if no keyword matches anything.
    """
    places = _load_places()
    kw_lower = [k.lower().strip() for k in keywords if k.strip()]

    # Category aliases so common words map to our category strings
    CATEGORY_ALIASES = {
        "museum": "museum",
        "museums": "museum",
        "музей": "museum",
        "музеи": "museum",
        "sight": "sight",
        "sights": "sight",
        "достопримечательност": "sight",
        "historic": "historic_architecture",
        "history": "historic_architecture",
        "monument": "historic_architecture",
        "monuments": "historic_architecture",
        "памятник": "historic_architecture",
        "памятники": "historic_architecture",
        "architecture": "historic_architecture",
        "church": "sight",
        "cathedral": "sight",
        "food": "food",
        "eat": "food",
        "restaurant": "food",
        "cafe": "food",
        "кафе": "food",
        "ресторан": "food",
        "еда": "food",
        "поесть": "food",
    }

    def _score(p: dict) -> int:
        if not has_real_name(p):
            return -1
        # Build a single searchable string
        searchable = " ".join([
            str(p.get("name", "")),
            str(p.get("name_ru", "")),
            str(p.get("name_en", "")),
            str(p.get("category", "")),
        ]).lower()
        tags = p.get("tags", {})
        if isinstance(tags, dict):
            searchable += " " + " ".join(str(v) for v in tags.values()).lower()

        score = 0
        for kw in kw_lower:
            if kw in searchable:
                score += 1
            # Check category aliases
            cat_match = CATEGORY_ALIASES.get(kw)
            if cat_match and p.get("category") == cat_match:
                score += 1
        return score

    scored = [(p, _score(p)) for p in places]
    # Keep only places with real names and score >= 1
    matched = [(p, s) for p, s in scored if s >= 1]

    if not matched:
        # Fallback: return all named places (top limit by order in file)
        matched = [(p, 0) for p, s in scored if s >= 0]

    matched.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in matched[:limit]]


def get_best_name(p: dict, language: str = "ru") -> str:
    """Helper to get a real name, avoiding 'Unknown' strings or empty values."""
    keys = [f"name_{language}", "name_en", "name_ru", "name"]
    for k in keys:
        v = p.get(k, "")
        if v and v.strip().lower() != "unknown":
            return v
    return str(p.get("id", "Unknown"))


def get_place_by_id(place_id: str) -> Optional[Dict[str, Any]]:
    # place_id might be a name for OSM or an ID for OTM
    places = _load_places()
    for p in places:
        # Match by ID or Name
        if str(p.get("id")) == str(place_id) or str(p.get("name")) == str(place_id):
            return p
    return None


def format_places_for_user(places: List[Dict[str, Any]], language: str) -> str:
    """
    Делает человекочитаемый список мест с учётом языка.
    """
    if not places:
        if language == "ru":
            return "Рядом со тобой я не нашёл подходящих интересных мест в пределах заданного радиуса."
        return "I couldn't find interesting places nearby within the selected radius."

    lines: List[str] = []
    if language == "ru":
        lines.append("Вот несколько мест недалеко от тебя:")
    else:
        lines.append("Here are some places not far from you:")

    for idx, p in enumerate(places, start=1):
        # Handle both OSM and OTM formats safely
        name = get_best_name(p, language)

        desc_key = "short_description_ru" if language == "ru" else "short_description_en"
        descr = p.get(desc_key) or ""
        dist = p.get("_distance_km", "?")

        if language == "ru":
            line = f"{idx}. {name} — примерно {dist} км от тебя.\n{descr}"
        else:
            line = f"{idx}. {name} — about {dist} km from you.\n{descr}"

        lines.append(line)

    return "\n\n".join(lines)

