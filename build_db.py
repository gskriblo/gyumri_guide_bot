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

def get_wikimedia_image(filename: str) -> str | None:
    if not filename.startswith('File:'):
        filename = 'File:' + filename
    url = 'https://en.wikipedia.org/w/api.php'
    params = {
        'action': 'query',
        'titles': filename,
        'prop': 'imageinfo',
        'iiprop': 'url',
        'format': 'json',
    }
    headers = {'User-Agent': 'GyumriGuideBot/1.0 (https://github.com/ssriblo/telegrambot_langchain_grok)'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()
        pages = data.get('query', {}).get('pages', {})
        for page_id, page_data in pages.items():
            if 'imageinfo' in page_data and len(page_data['imageinfo']) > 0:
                return page_data['imageinfo'][0]['url']
    except Exception as e:
        print(f"Error getting wikimedia image for {filename}: {e}")
    return None

def get_wikipedia_thumbnail(wikipedia_tag: str) -> str | None:
    """Handles both 'en:Title' and 'Title' formats"""
    parts = wikipedia_tag.split(':', 1)
    if len(parts) == 2:
        lang, title = parts
    else:
        lang, title = 'en', wikipedia_tag
        
    url = f'https://{lang}.wikipedia.org/w/api.php'
    params = {
        'action': 'query',
        'prop': 'pageimages',
        'titles': title,
        'format': 'json',
        'pithumbsize': 800
    }
    headers = {'User-Agent': 'GyumriGuideBot/1.0 (https://github.com/ssriblo/telegrambot_langchain_grok)'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()
        pages = data.get('query', {}).get('pages', {})
        for page_id, page_data in pages.items():
            if 'thumbnail' in page_data:
                return page_data['thumbnail']['source']
    except Exception as e:
        print(f"Error getting config thumbnail for {title}: {e}")
    return None

def get_wikidata_image(wikidata_id: str) -> str | None:
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbgetclaims',
        'entity': wikidata_id,
        'property': 'P18', # Image property
        'format': 'json'
    }
    headers = {'User-Agent': 'GyumriGuideBot/1.0 (https://github.com/ssriblo/telegrambot_langchain_grok)'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        data = r.json()
        claims = data.get('claims', {}).get('P18', [])
        if claims:
            filename = claims[0]['mainsnak']['datavalue']['value']
            return get_wikimedia_image(filename)
    except Exception as e:
         print(f"Error getting wikidata image for {wikidata_id}: {e}")
    return None

def resolve_image_url(tags: Dict[str, Any]) -> str | None:
    """Attempts to resolve an image URL from OSM tags."""
    if "image" in tags and tags["image"].startswith("http"):
        return tags["image"]
        
    if "wikimedia_commons" in tags:
        url = get_wikimedia_image(tags["wikimedia_commons"])
        if url: return url
        
    if "wikipedia" in tags:
        url = get_wikipedia_thumbnail(tags["wikipedia"])
        if url: return url
        
    if "wikidata" in tags:
        url = get_wikidata_image(tags["wikidata"])
        if url: return url
        
    return None

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
            "source": "openstreetmap",
            "image_url": resolve_image_url(tags)
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