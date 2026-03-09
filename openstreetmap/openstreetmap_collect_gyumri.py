import requests
import json

lat = 40.7894
lon = 43.8475
radius = 3000

query = f"""
[out:json];
(
  node["tourism"="attraction"](around:{radius},{lat},{lon});
  node["tourism"="viewpoint"](around:{radius},{lat},{lon});
  node["amenity"="restaurant"](around:{radius},{lat},{lon});
  node["amenity"="cafe"](around:{radius},{lat},{lon});
  node["amenity"="fast_food"](around:{radius},{lat},{lon});
);
out;
"""

url = "https://overpass-api.de/api/interpreter"
response = requests.get(url, params={"data": query})
data = response.json()

places = []

for el in data["elements"]:
    places.append({
        "name": el.get("tags", {}).get("name", "Unknown"),
        "lat": el["lat"],
        "lon": el["lon"],
        "tags": el.get("tags", {})
    })

# save file
with open("gyumri_places.json", "w", encoding="utf-8") as f:
    json.dump(places, f, ensure_ascii=False, indent=2)
    print(json.dumps(places, indent=2, ensure_ascii=False))

print("Saved", len(places), "places to gyumri_places.json")