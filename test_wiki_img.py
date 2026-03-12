import requests

def get_wiki_image(title, lang="en"):
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "pageimages",
        "titles": title,
        "format": "json",
        "pithumbsize": 800
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                return page_data["thumbnail"]["source"]
    except Exception as e:
        print(e)
    return None

print(get_wiki_image("Mother Armenia, Gyumri"))
