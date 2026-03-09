import os
import json
import requests
from typing import Any, Dict, List

# -----------------------------------------
# Configuration
# -----------------------------------------

# Center of Gyumri (approximate)
GYUMRI_LAT = 40.7894
GYUMRI_LON = 43.8475

# Search radius in meters
SEARCH_RADIUS_M = 3000

# Output file
OUTPUT_JSON_PATH = "places_gyumri.json"

def fetch_places_osm(lat: float, lon: float, radius: int) -> List[Dict[str, Any]]:
    """
    Fetches places around a given location using OpenStreetMap Overpass API.
    """
    query = f"""
    [out:json];
    (
      node["tourism"="attraction"](around:{radius},{lat},{lon});
      node["tourism"="viewpoint"](around:{radius},{lat},{lon});
      node["tourism"="museum"](around:{radius},{lat},{lon});
      node["tourism"="gallery"](around:{radius},{lat},{lon});
      node["historic"](around:{radius},{lat},{lon});
      node["amenity"="restaurant"](around:{radius},{lat},{lon});
      node["amenity"="cafe"](around:{radius},{lat},{lon});
      node["amenity"="fast_food"](around:{radius},{lat},{lon});
      node["amenity"="bar"](around:{radius},{lat},{lon});
      node["amenity"="pub"](around:{radius},{lat},{lon});
    );
    out;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    print(f"Fetching from {url}...")
    response = requests.get(url, params={"data": query}, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    places = []
    
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        
        # Determine category based on OSM tags
        category = "other"
        amenity = tags.get("amenity", "")
        tourism = tags.get("tourism", "")
        
        if amenity in ("restaurant", "cafe", "fast_food", "bar", "pub"):
            category = "food"
        elif tourism in ("attraction", "museum", "viewpoint", "gallery"):
            category = "sight"
        elif tags.get("historic"):
            category = "historic_architecture"
            
        places.append({
            "id": f"node/{el['id']}",
            "name_en": tags.get("name:en", tags.get("name", "Unknown")),
            "name_ru": tags.get("name:ru", tags.get("name", "Unknown")),
            "name": tags.get("name", "Unknown"),
            "lat": el.get("lat"),
            "lon": el.get("lon"),
            "category": category,
            "tags": tags,
            "source": "openstreetmap"
        })
        
    return places

def build_gyumri_db() -> List[Dict[str, Any]]:
    """
    Builds the database by fetching places from OSM and saving to JSON.
    """
    places = fetch_places_osm(GYUMRI_LAT, GYUMRI_LON, SEARCH_RADIUS_M)
    
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)
        
    print(f"Saved {len(places)} places to {OUTPUT_JSON_PATH}")
    return places

if __name__ == "__main__":
    build_gyumri_db()