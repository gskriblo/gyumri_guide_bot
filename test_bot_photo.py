import asyncio
from main import bot, dp
from aiogram.types import Message, Chat, User
from data_gyumri import get_place_by_id
from state import update_stage, set_language, set_location, set_program, get_user_state
from unittest.mock import AsyncMock

async def main():
    import json
    with open('places_gyumri.json', 'r', encoding='utf-8') as f:
        places = json.load(f)
    print("Places with image_url:")
    for p in places:
        if p.get("image_url"):
            print(f"- {p.get('name_en')} -> {p['image_url']}")

    print("\nSimulating bot sending navigation for Mother Armenia...")
    place = None
    for p in places:
        if "Mother Armenia" in p.get("name_en", ""):
            place = p
            break
            
    if place:
        uid = 12345
        update_stage(uid, "ON_ROUTE")
        set_language(uid, "en")
        set_location(uid, 40.7894, 43.8475)
        set_program(uid, "prog_classic")
        state = get_user_state(uid)
        
        target = AsyncMock()
        await __import__("main")._send_place_navigation(target, place, state)
        
        print("\nCalls made to target (send message/photo):")
        for call in target.mock_calls:
            print(call)
            
if __name__ == "__main__":
    asyncio.run(main())
