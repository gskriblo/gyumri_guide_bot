# Adding Photos to Places (Walkthrough)

## Changes Made
- Added a new [resolve_image_url](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py#91-109) function to **[build_db.py](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py)** that can dynamically pull images from:
  1. Direct OpenStreetMap [image](file:///C:/Users/401-15/Desktop/python/langchain_version_3/test_wiki_img.py#3-22) tags
  2. Wikimedia Commons tags via the Wikimedia API
  3. Wikipedia tags via the Wikipedia Summary API 
  4. Wikidata `P18` claims via the Wikidata API
- Regenerated **[places_gyumri.json](file:///c:/Users/401-15/Desktop/python/langchain_version_3/places_gyumri.json)** to include an [image_url](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py#91-109) property for any place with matching tags (around 30+ places now have photos).
- Updated **[data_gyumri.py](file:///c:/Users/401-15/Desktop/python/langchain_version_3/data_gyumri.py)** to forward the [image_url](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py#91-109) property so the Telegram handler can see it.
- Updated **[main.py](file:///C:/Users/401-15/Desktop/python/langchain_version_3/main.py)** to check for [image_url](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py#91-109) when sending a navigation card (e.g., when you hit `➡️ Следующая точка` or start a route). If an image is present, the bot will use `bot.send_photo` right before sending the text description!

## What Was Tested
- **API Resolving:** Created a test script to ensure we can successfully parse images from Wikipedia, Wikidata, and Wikimedia Commons.
- **Bot Behavior:** Re-ran [build_db.py](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py) to ensure it populates the database JSON file correctly with [image_url](file:///c:/Users/401-15/Desktop/python/langchain_version_3/build_db.py#91-109) values.
- **Bot UI Logic:** Verified through unit testing that [_send_place_navigation](file:///C:/Users/401-15/Desktop/python/langchain_version_3/main.py#103-161) cleanly calls `bot.send_photo` when an image is present, and gracefully cascades to just text when one is not.

Everything works great! The app is now much more visual.
