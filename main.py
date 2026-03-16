from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from data_gyumri import _haversine_km
import os

from logger_setup import log
from llm import generate_reply, suggest_places_from_preferences
from state import (
    get_user_state,
    update_stage,
    set_language,
    set_style,
    set_raw_preferences,
    set_location,
    set_program,
    save_generated_programs,
    reset_user_state,
    mark_place_visited,
    set_tour_hours
)
from data_gyumri import get_nearby_places, format_places_for_user, get_place_by_id
from routing import generate_programs, format_program_options

load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if TELEGRAM_BOT_TOKEN is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# ── helpers ──────────────────────────────────────────────

def _uid(message_or_cb) -> int:
    """Extract user_id from message or callback."""
    if hasattr(message_or_cb, "from_user"):
        return message_or_cb.from_user.id
    return 0

def _detect_device_language(message: types.Message) -> str:
    """Определяет язык устройства пользователя из Telegram."""
    code = (message.from_user.language_code or "en").lower()
    return "ru" if code.startswith("ru") else "en"


def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

# ── keyboards ────────────────────────────────────────────

def get_style_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Эмоциональный 🎭", callback_data="style_emotional")],
            [InlineKeyboardButton(text="Строгий 📝", callback_data="style_strict")],
            [InlineKeyboardButton(text="Развлекающий 🎉", callback_data="style_fun")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Emotional 🎭", callback_data="style_emotional")],
            [InlineKeyboardButton(text="Strict 📝", callback_data="style_strict")],
            [InlineKeyboardButton(text="Fun 🎉", callback_data="style_fun")]
        ])

def get_hours_keyboard(lang: str) -> InlineKeyboardMarkup:
    options = [(1, "1h"), (2, "2h"), (3, "3h"), (4, "4h"), (6, "6h"), (8, "8h")]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"hours_{val}")]
        for val, label in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_program_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏛 Классический", callback_data="prog_classic")],
            [InlineKeyboardButton(text="🍽 Фуд-тур", callback_data="prog_food")],
            [InlineKeyboardButton(text="🍃 Спокойная прогулка", callback_data="prog_chill")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏛 Classic", callback_data="prog_classic")],
            [InlineKeyboardButton(text="🍽 Food Tour", callback_data="prog_food")],
            [InlineKeyboardButton(text="🍃 Chill Walk", callback_data="prog_chill")]
        ])

def get_on_route_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Следующая точка", callback_data="route_next")],
            [InlineKeyboardButton(text="⏭ Пропустить точку", callback_data="route_skip")],
            [InlineKeyboardButton(text="🗺 Текущий маршрут", callback_data="route_show")],
            [InlineKeyboardButton(text="👀 Что рядом?", callback_data="route_whats_nearby")],
            [InlineKeyboardButton(text="🍽 Где поесть рядом?", callback_data="route_eat_nearby")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Next Place", callback_data="route_next")],
            [InlineKeyboardButton(text="⏭ Skip Place", callback_data="route_skip")],
            [InlineKeyboardButton(text="🗺 Show Route", callback_data="route_show")],
            [InlineKeyboardButton(text="👀 What's nearby?", callback_data="route_whats_nearby")],
            [InlineKeyboardButton(text="🍽 Eat Nearby", callback_data="route_eat_nearby")]
        ])

# ── navigation card ──────────────────────────────────────

async def _send_place_navigation(
    target,
    place: dict,
    state,
    prefix_ru: str = "📍 Следующая точка:",
    prefix_en: str = "📍 Next stop:",
    show_route_kb: bool = True,
):
    uid = state.user_id
    lang = state.language
    name = place.get(f"name_{lang}") or place.get("name_en") or "Unknown"
    desc = place.get(f"short_description_{lang}") or place.get("short_description_en") or ""
    lat = place.get("lat")
    lon = place.get("lon")

    prefix = prefix_ru if lang == "ru" else prefix_en

    log.debug(f"[U:{uid}][NAV] Sending place: {name} (lat={lat}, lon={lon})")

    lines = [f"{prefix} <b>{name}</b>", ""]
    if desc:
        lines.append(desc)
        lines.append("")

    if state.last_location and lat and lon:
        user_lat, user_lon = state.last_location
        dist = _haversine_km(user_lat, user_lon, float(lat), float(lon))
        dist_text = f"~{dist:.1f} км от тебя" if lang == "ru" else f"~{dist:.1f} km from you"
        lines.append(f"📏 {dist_text}")
        log.debug(f"[U:{uid}][NAV] Distance: {dist:.2f} km")

    if lat and lon:
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=walking"
        link_label = "🗺 Открыть в Google Maps (пешком)" if lang == "ru" else "🗺 Open in Google Maps (walking)"
        lines.append(f'<a href="{maps_url}">{link_label}</a>')

    text = "\n".join(lines)
    log.debug(f"[U:{uid}][NAV] Card text:\n{text}")
    kb = get_on_route_keyboard(lang) if show_route_kb else None
    
    # Send photo first if available
    image_url = place.get("image_url")
    if image_url:
        try:
            await target.answer_photo(photo=image_url)
        except Exception as e:
            log.warning(f"[U:{uid}][NAV] Failed to send photo {image_url}: {e}")
            
    await target.answer(text, parse_mode="HTML", reply_markup=kb)

    if lat and lon:
        await target.answer_venue(
            latitude=float(lat),
            longitude=float(lon),
            title=name,
            address=desc[:100] if desc else name,
        )
        log.debug(f"[U:{uid}][NAV] Venue sent")

# ── handlers ─────────────────────────────────────────────

@dp.message(Command("start", "reset"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    log.info(f"[U:{uid}][CMD] /start or /reset")
    reset_user_state(uid)
    device_lang = _detect_device_language(message)
    set_language(uid, device_lang)
    log.debug(f"[U:{uid}][CMD] device_lang={device_lang}")

    if device_lang == "ru":
        await message.answer(
            "Привет! 👋 Я твой виртуальный гид по Гюмри.\n\n"
            "Выбери язык общения:",
            reply_markup=get_language_keyboard()
        )
    else:
        await message.answer(
            "Hi! 👋 I'm your virtual guide in Gyumri.\n\n"
            "Choose your preferred language:",
            reply_markup=get_language_keyboard()
        )
    update_stage(uid, "ASK_LANGUAGE")


@dp.message(Command("style"))
async def cmd_style(message: types.Message):
    uid = message.from_user.id
    state = get_user_state(uid)
    log.info(f"[U:{uid}][CMD] /style (current={state.style})")
    text = "Выбери стиль общения:" if state.language == "ru" else "Choose communication style:"
    await message.answer(text, reply_markup=get_style_keyboard(state.language))


@dp.message(F.text)
async def handle_message(message: types.Message):
    user_input = message.text or ""
    if user_input.startswith("/"):
        return

    uid = message.from_user.id
    state = get_user_state(uid)
    log.info(f"[U:{uid}][MSG] stage={state.stage} lang={state.language} style={state.style}")
    log.debug(f"[U:{uid}][MSG] text: {user_input!r}")
    log.debug(f"[U:{uid}][MSG] location={state.last_location} route={state.current_route} "
              f"visited={state.visited_places} program={state.program_selected}")

    if state.stage == "NEW_USER":
        log.debug(f"[U:{uid}][MSG] NEW_USER → cmd_start")
        await cmd_start(message)
        return

    if state.stage == "ASK_LANGUAGE":
        log.debug(f"[U:{uid}][MSG] ASK_LANGUAGE → prompt buttons")
        msg = "Пожалуйста, выбери язык кнопкой выше." if state.language == "ru" else "Please choose your language using the buttons above."
        await message.answer(msg)
        return

    if state.stage == "ASK_STYLE":
        log.debug(f"[U:{uid}][MSG] ASK_STYLE → prompt buttons")
        msg = "Пожалуйста, выбери стиль кнопкой выше." if state.language == "ru" else "Please choose a style using the buttons above."
        await message.answer(msg)
        return

    if state.stage == "ASK_PREFERENCES":
        log.debug(f"[U:{uid}][MSG] ASK_PREFERENCES → saving: {user_input!r}")
        set_raw_preferences(uid, user_input)

        # Ask the LLM to suggest real matching places from the DB
        suggestion = suggest_places_from_preferences(uid, user_input, state)
        await message.answer(suggestion)

        if state.language == "ru":
            await message.answer(
                "Чтобы построить полный маршрут от твоей позиции, "
                "отправь геолокацию через кнопку 📎 → «Геопозиция»."
            )
        else:
            await message.answer(
                "To build a full route from your position, please send your location "
                "via the 📎 → \u201cLocation\u201d button."
            )
        update_stage(uid, "ASK_LOCATION_REQUIRED")
        return

    if state.stage == "ASK_LOCATION_REQUIRED":
        log.debug(f"[U:{uid}][MSG] ASK_LOCATION_REQUIRED → prompt geo")
        msg = "Пожалуйста, отправь геолокацию." if state.language == "ru" else "Please send your location."
        await message.answer(msg)
        return

    if state.stage == "ASK_HOURS":
        log.debug(f"[U:{uid}][MSG] ASK_HOURS → prompt buttons")
        msg = "Пожалуйста, выбери длительность кнопкой выше." if state.language == "ru" else "Please choose a duration using the buttons above."
        await message.answer(msg)
        return

    if state.stage == "SHOW_PROGRAM_OPTIONS":
        log.debug(f"[U:{uid}][MSG] SHOW_PROGRAM_OPTIONS → prompt buttons")
        msg = "Пожалуйста, выбери маршрут кнопками." if state.language == "ru" else "Please choose a route with the buttons."
        await message.answer(msg)
        return

    # Free chat or On Route
    log.info(f"[U:{uid}][MSG] Calling LLM (stage={state.stage})")
    reply_text = generate_reply(user_id=uid, user_input=user_input, user_state=state)
    log.debug(f"[U:{uid}][MSG] LLM reply (300): {reply_text[:300]!r}")

    if state.stage == "ON_ROUTE":
        await message.answer(reply_text, reply_markup=get_on_route_keyboard(state.language))
    else:
        await message.answer(reply_text)


@dp.callback_query()
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    state = get_user_state(uid)
    data = callback_query.data
    log.info(f"[U:{uid}][CB] data={data!r} stage={state.stage}")
    log.debug(f"[U:{uid}][CB] lang={state.language} style={state.style} "
              f"route={state.current_route} visited={state.visited_places} "
              f"program={state.program_selected} location={state.last_location}")

    if data.startswith("lang_"):
        chosen_lang = data.split("_")[1]  # "ru" or "en"
        log.debug(f"[U:{uid}][CB] language chosen: {chosen_lang}")
        set_language(uid, chosen_lang)
        await callback_query.message.edit_reply_markup(reply_markup=None)

        if chosen_lang == "ru":
            await callback_query.message.answer(
                "Отлично! Теперь выбери стиль общения:",
                reply_markup=get_style_keyboard("ru")
            )
        else:
            await callback_query.message.answer(
                "Great! Now choose the communication style:",
                reply_markup=get_style_keyboard("en")
            )
        update_stage(uid, "ASK_STYLE")

    elif data.startswith("style_"):
        style = data.split("_")[1]
        log.debug(f"[U:{uid}][CB] style → {style}")
        set_style(uid, style)

        await callback_query.message.edit_reply_markup(reply_markup=None)
        if state.stage == "ASK_STYLE":
            if state.language == "ru":
                await callback_query.message.answer(
                    "Отлично, стиль сохранен!\n"
                    "Расскажи, что бы ты хотел увидеть в Гюмри?"
                )
            else:
                await callback_query.message.answer(
                    "Great, style saved!\n"
                    "Tell me what you'd like to see in Gyumri?"
                )
            update_stage(uid, "ASK_PREFERENCES")
        else:
            msg = "Стиль изменен!" if state.language == "ru" else "Style changed!"
            await callback_query.answer(msg)

    elif data.startswith("prog_"):
        prog_id = data.split("_")[1]
        log.info(f"[U:{uid}][CB] program selected: {prog_id}")
        set_program(uid, prog_id)
        update_stage(uid, "ON_ROUTE")

        await callback_query.message.edit_reply_markup(reply_markup=None)
        msg = "Маршрут выбран! Погнали!" if state.language == "ru" else "Route selected! Let's go!"
        await callback_query.answer(msg)

        state = get_user_state(uid)
        log.debug(f"[U:{uid}][CB] route after set_program: {state.current_route}")
        if state.current_route:
            first_place_id = state.current_route[0]
            place = get_place_by_id(first_place_id)
            log.debug(f"[U:{uid}][CB] first place id={first_place_id} found={place is not None}")
            if place:
                await _send_place_navigation(
                    callback_query.message, place, state,
                    prefix_ru="📍 Первая точка:",
                    prefix_en="📍 First stop:",
                )

    elif data.startswith("route_"):
        action = data.split("_", 1)[1]
        log.info(f"[U:{uid}][CB] route action: {action}")
        if action == "next" or action == "skip":
            if state.current_route:
                visited_id = state.current_route.pop(0)
                log.debug(f"[U:{uid}][CB] popped {visited_id} (action={action})")
                if action == "next":
                    mark_place_visited(uid, visited_id)

            log.debug(f"[U:{uid}][CB] remaining route: {state.current_route}")
            if state.current_route:
                next_place_id = state.current_route[0]
                place = get_place_by_id(next_place_id)
                if place:
                    await _send_place_navigation(callback_query.message, place, state)
            else:
                log.info(f"[U:{uid}][CB] route finished")
                text = "🎉 Маршрут закончен!" if state.language == "ru" else "🎉 Route finished!"
                update_stage(uid, "FREE_CHAT")
                await callback_query.message.answer(text)

        elif action == "show":
            log.debug(f"[U:{uid}][CB] show route: {state.current_route}")
            if not state.current_route:
                text = "Маршрут пуст." if state.language == "ru" else "Route is empty."
            else:
                names = []
                for pid in state.current_route:
                    p = get_place_by_id(pid)
                    if p:
                        names.append(p.get(f"name_{state.language}") or p.get("name_en") or "Unknown")
                text = "🗺 Осталось посетить:\n" + "\n".join([f"- {n}" for n in names]) if state.language == "ru" else "🗺 Left to visit:\n" + "\n".join([f"- {n}" for n in names])
            await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))

        elif action == "whats_nearby":
            log.debug(f"[U:{uid}][CB] whats_nearby, location={state.last_location}")
            if state.last_location:
                lat, lon = state.last_location
                nearby = get_nearby_places(lat, lon, max_distance_km=0.1, limit=10)
                log.debug(f"[U:{uid}][CB] places within 100m: {len(nearby)}")
                if nearby:
                    header = "👀 Вот что находится рядом с тобой (в радиусе ~100 м):\n" if state.language == "ru" else "👀 Here's what's around you (~100m radius):\n"
                    text = header + "\n" + format_places_for_user(nearby, state.language)
                else:
                    text = "В радиусе 100 метров ничего не нашлось. Попробуй обновить геолокацию." if state.language == "ru" else "Nothing found within 100m. Try updating your location."
            else:
                text = 'Нужна геопозиция — отправь через 📎 → «Геопозиция».' if state.language == "ru" else 'Location needed — send via 📎 → "Location".'
            await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))

        elif action == "eat_nearby":
            log.debug(f"[U:{uid}][CB] eat_nearby, location={state.last_location}")
            if state.last_location:
                lat, lon = state.last_location
                nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=5, categories={"food"})
                log.debug(f"[U:{uid}][CB] food found: {len(nearby)}")
                if nearby:
                    text = format_places_for_user(nearby, state.language)
                    # Build numbered buttons for each food place + back button
                    buttons = []
                    for idx, p in enumerate(nearby, start=1):
                        name = p.get(f"name_{state.language}") or p.get("name_en") or "?"
                        short = name[:25] + "…" if len(name) > 25 else name
                        buttons.append([InlineKeyboardButton(
                            text=f"{idx}. {short}",
                            callback_data=f"food_{p.get('id', idx)}"
                        )])
                    back_label = "↩️ Вернуться на маршрут" if state.language == "ru" else "↩️ Back to route"
                    buttons.append([InlineKeyboardButton(text=back_label, callback_data="route_back")])
                    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                    await callback_query.message.answer(text, reply_markup=kb)
                else:
                    text = "Еды рядом не найдено." if state.language == "ru" else "No food found nearby."
                    await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))
            else:
                text = "Нужна геопозиция." if state.language == "ru" else "Location needed."
                await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))

        elif action == "back":
            # Return to on-route menu with current place info
            log.debug(f"[U:{uid}][CB] back to route")
            if state.current_route:
                cur_place_id = state.current_route[0]
                place = get_place_by_id(cur_place_id)
                if place:
                    await _send_place_navigation(
                        callback_query.message, place, state,
                        prefix_ru="📍 Текущая точка:",
                        prefix_en="📍 Current stop:",
                    )
                    await callback_query.message.edit_reply_markup(reply_markup=None)
            else:
                text = "Маршрут пуст." if state.language == "ru" else "Route is empty."
                await callback_query.message.answer(text, reply_markup=get_on_route_keyboard(state.language))

    elif data.startswith("food_"):
        place_id = data[5:]  # everything after "food_"
        log.info(f"[U:{uid}][CB] food place selected: {place_id}")
        place = get_place_by_id(place_id)
        if place:
            await callback_query.message.edit_reply_markup(reply_markup=None)
            await _send_place_navigation(
                callback_query.message, place, state,
                prefix_ru="🍽 Идём сюда:",
                prefix_en="🍽 Let's go here:",
            )

    elif data.startswith("hours_"):
        hours = float(data.split("_")[1])
        log.info(f"[U:{uid}][CB] hours chosen: {hours}")
        set_tour_hours(uid, hours)
        update_stage(uid, "SHOW_PROGRAM_OPTIONS")

        await callback_query.message.edit_reply_markup(reply_markup=None)

        state = get_user_state(uid)
        if state.last_location:
            lat, lon = state.last_location
            log.debug(f"[U:{uid}][CB] generating programs for {hours}h")
            programs = generate_programs(
                lat, lon, 
                time_hours=hours, 
                user_id=uid, 
                interests=state.preferences.interests
            )

            programs_ids = {
                prog_id: [p["id"] for p in places]
                for prog_id, places in programs.items()
            }
            log.debug(f"[U:{uid}][CB] program IDs: { {k: len(v) for k, v in programs_ids.items()} }")
            for prog_id, ids in programs_ids.items():
                log.debug(f"[U:{uid}][CB]   {prog_id}: {ids}")
            save_generated_programs(uid, programs_ids)

            text = format_program_options(programs, language=state.language)
            log.debug(f"[U:{uid}][CB] options text:\n{text}")
            await callback_query.message.answer(text, reply_markup=get_program_keyboard(state.language))
        else:
            msg = "Не удалось найти геопозицию. Отправь её снова." if state.language == "ru" else "Location not found. Please send it again."
            update_stage(uid, "ASK_LOCATION_REQUIRED")
            await callback_query.message.answer(msg)

    await callback_query.answer()


@dp.message(F.location)
async def handle_location(message: types.Message):
    uid = message.from_user.id
    state = get_user_state(uid)
    loc = message.location
    if loc is None:
        return

    lat = loc.latitude
    lon = loc.longitude
    log.info(f"[U:{uid}][LOC] lat={lat} lon={lon} stage={state.stage}")
    set_location(uid, lat, lon)

    if state.stage == "ASK_LOCATION_REQUIRED":
        update_stage(uid, "ASK_HOURS")
        if state.language == "ru":
            await message.answer(
                "📍 Геопозиция получена! Сколько у тебя времени на прогулку?",
                reply_markup=get_hours_keyboard(state.language)
            )
        else:
            await message.answer(
                "📍 Location received! How much time do you have for the tour?",
                reply_markup=get_hours_keyboard(state.language)
            )
    else:
        nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=5)
        log.debug(f"[U:{uid}][LOC] nearby found: {len(nearby)}")
        text = format_places_for_user(nearby, language=state.language)
        if state.stage == "ON_ROUTE":
            await message.answer(text, reply_markup=get_on_route_keyboard(state.language))
        else:
            await message.answer(text)


if __name__ == "__main__":
    import asyncio
    from aiogram.types import BotCommand

    async def main():
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать / Start the tour guide"),
            BotCommand(command="reset", description="Сбросить и начать заново / Reset"),
            BotCommand(command="style", description="Сменить стиль общения / Change style"),
        ])
        log.info("=== BOT STARTING (menu commands set) ===")
        await dp.start_polling(bot)

    asyncio.run(main())
