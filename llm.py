import os
import sys
from typing import Dict, List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from state import UserState
from prompts import build_system_prompt
from data_gyumri import get_nearby_places, get_place_by_id, _load_places, search_places_by_keywords


load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Определение выбранной модели из аргументов
_model_choice = "GROQ"
if len(sys.argv) >= 2:
    if sys.argv[1].upper() in ["GROQ", "DEEPSEEK"]:
        _model_choice = sys.argv[1].upper()

print(f"=== Инициализация LLM: {_model_choice} ===")

if _model_choice == "DEEPSEEK":
    if DEEPSEEK_API_KEY is None:
        raise RuntimeError("DEEPSEEK_API_KEY is not set in environment variables.")
    model = ChatOpenAI(
        model='deepseek-chat', 
        openai_api_key=DEEPSEEK_API_KEY, 
        openai_api_base='https://api.deepseek.com',
        temperature=0.1, # 0.1 - очень точный, 0.7 - креативный
        max_tokens=1000 # Ограничиваем длину, раз вам нужны короткие ответы
    )
else:
    if GROQ_API_KEY is None:
        raise RuntimeError("GROQ_API_KEY is not set in environment variables.")
    # Инициализация модели GROQ по умолчанию
    model = ChatGroq(
        api_key=GROQ_API_KEY, 
        model="llama-3.3-70b-versatile",
        temperature=0.1, # 0.1 - очень точный, 0.7 - креативный
    )

# Настройки контекста
MAX_TURNS_FOR_MODEL = 8          # сколько последних сообщений посылать в модель каждый раз
MAX_STORED_MESSAGES = 40         # после какого размера истории делать суммаризацию
KEEP_RECENT_AFTER_SUMMARY = 6    # сколько последних сообщений оставлять “как есть” рядом с саммари


# Хранилище истории диалогов в памяти процесса:
# ключ — user_id, значение — список сообщений (HumanMessage/AIMessage)
_user_conversations: Dict[int, List] = {}


def summarize_dialog(messages, language: str = "ru"):
    """
    Делает краткую выжимку по длинному диалогу.
    Использует ту же модель, но только один раз на “пакет” старых сообщений.
    """
    if not messages:
        return ""

    if language == "ru":
        prompt_text = (
            "Сделай краткую выжимку предыдущего диалога между пользователем и ассистентом. "
            "Выдели факты, решения и важный контекст, который нужен для продолжения общения. "
            "Ответь одной связной текстовой выжимкой на русском языке без лишних деталей."
        )
    else:
        prompt_text = (
            "Provide a brief summary of the previous conversation between the user and the assistant. "
            "Highlight facts, decisions, and important context needed to continue the conversation. "
            "Respond with a single coherent text summary in English without unnecessary details."
        )

    summary_prompt = [SystemMessage(content=prompt_text)] + messages

    summary_response = model.invoke(summary_prompt)
    return summary_response.content


def _get_name_and_desc(p, lang):
    name = p.get(f"name_{lang}") or p.get("name_en") or p.get("name_ru") or p.get("name") or "Unknown"
    desc = p.get(f"short_description_{lang}") or p.get(f"short_description_en") or ""
    return name, desc

def generate_reply(user_id: int, user_input: str, user_state: UserState) -> str:
    """
    Обновляет историю диалога пользователя и возвращает текст ответа модели.
    """
    # 1. Достаем полную историю этого пользователя и добавляем текущее сообщение
    full_history = _user_conversations.get(user_id, [])
    full_history = full_history + [HumanMessage(content=user_input)]

    # 2. Формируем укороченную историю диалога
    history_for_model = full_history[-MAX_TURNS_FOR_MODEL:]

    # 3. Добавляем системный промпт с учётом языка и стиля
    system_prompt_text = build_system_prompt(user_state)
    # Логирование для отладки
    print("=== LLM DEBUG: system prompt ===")
    print(system_prompt_text)
    print("=== END system prompt ===")
    messages_for_model = [SystemMessage(content=system_prompt_text)]

    # 4. Контекст мест для модели
    # 4.1 Текущий маршрут
    if user_state.current_route:
        lang = user_state.language if user_state.language in ("ru", "en") else "en"
        header = "Пользователь сейчас идет по маршруту. Следующие остановки:\n" if lang == "ru" else "The user is currently on a route. Upcoming stops:\n"
        lines = [header]
        for idx, pid in enumerate(user_state.current_route, start=1):
            p = get_place_by_id(pid)
            if p:
                name, desc = _get_name_and_desc(p, lang)
                lines.append(f"{idx}. {name}\n{desc}")
        route_context_text = "\n".join(lines) + "\n\n"
        messages_for_model.append(HumanMessage(content=route_context_text))

    # 4.2 Ближайшие места или ТОП мест, чтобы не выдумывать
    nearby = []
    if user_state.last_location is not None:
        lat, lon = user_state.last_location
        nearby = get_nearby_places(lat, lon, max_distance_km=2.0, limit=8)
    else:
        # Give top 10 places if no location
        all_places = _load_places()
        nearby = all_places[:10]

    if nearby:
        lang = user_state.language if user_state.language in ("ru", "en") else "en"
        if lang == "ru":
            header = (
                "Вот список доступных мест (поблизости или топ-места), которые ты можешь "
                "использовать в качестве конкретных рекомендаций. "
                "Не придумывай другие объекты, опирайся на этот список:\n\n"
            )
        else:
            header = (
                "Here is the list of available places (nearby or top places) you can use for concrete recommendations. "
                "Do not invent other venues; rely on this list:\n\n"
            )

        lines = [header]
        for idx, p in enumerate(nearby, start=1):
            name, descr = _get_name_and_desc(p, lang)
            dist = p.get("_distance_km")
            if dist is not None:
                if lang == "ru":
                    line = f"{idx}. {name} — примерно {dist} км.\n{descr}"
                else:
                    line = f"{idx}. {name} — about {dist} km.\n{descr}"
            else:
                line = f"{idx}. {name}\n{descr}"
            lines.append(line)

        context_text = "\n\n".join(lines)
        print("=== LLM DEBUG: nearby places context ===")
        print(context_text)
        print("=== END nearby places context ===")
        messages_for_model.append(HumanMessage(content=context_text))

    # 5. Добавляем историю диалога после контекста
    messages_for_model.extend(history_for_model)

    # 6. Прогоняем через модель
    print("=== LLM DEBUG: messages_for_model (types) ===")
    for i, m in enumerate(messages_for_model):
        m_type = type(m).__name__
        snippet = (m.content or "")[:200] if isinstance(m, (HumanMessage, SystemMessage)) else ""
        print(f"{i}. {m_type}: {snippet!r}")
    print("=== END messages_for_model ===")

    response = model.invoke(messages_for_model)
    full_history = full_history + [response]

    # 7. При необходимости — суммаризируем “старую” часть диалога, чтобы не росла бесконечно
    if len(full_history) > MAX_STORED_MESSAGES:
        old_part = full_history[:-KEEP_RECENT_AFTER_SUMMARY]
        recent_part = full_history[-KEEP_RECENT_AFTER_SUMMARY:]

        summary_text = summarize_dialog(old_part, user_state.language)
        
        prefix = "Краткая выжимка предыдущего диалога:" if user_state.language == "ru" else "Brief summary of the previous conversation:"
        summary_message = SystemMessage(
            content=f"{prefix}\n{summary_text}"
        )

        # В истории остаётся одно саммари + несколько последних “сырых” сообщений
        full_history = [summary_message] + recent_part

    # 8. Сохраняем обновлённую историю пользователя
    _user_conversations[user_id] = full_history

    return response.content


def suggest_places_from_preferences(
    user_id: int,
    preferences_text: str,
    user_state: "UserState",
) -> str:
    """
    Called right after the user describes what they want to see.
    Searches the DB for matching places and asks the LLM to suggest
    3-5 of them with a short personalised description.
    """
    from logger_setup import log
    lang = user_state.language if user_state.language in ("ru", "en") else "en"

    # Split preference text into keywords (words longer than 2 chars)
    keywords = [w.strip(".,!?;:") for w in preferences_text.split() if len(w.strip()) > 2]
    log.debug(f"[U:{user_id}][SUGGEST] keywords={keywords}")

    matched_places = search_places_by_keywords(keywords, limit=15)
    log.debug(f"[U:{user_id}][SUGGEST] matched places: {len(matched_places)}")

    if lang == "ru":
        system_text = (
            "Ты виртуальный туристический гид по Гюмри, Армения.\n"
            "Пользователь описал, что хотел бы увидеть или попробовать. "
            "Ниже — реальные места из нашей базы данных, подходящие под его запрос.\n"
            "Выбери 3–5 наиболее подходящих мест и кратко опиши каждое (1-2 предложения). "
            "Не придумывай другие места — используй только список ниже.\n"
            "В конце предложи отправить геолокацию для построения полного маршрута."
        )
        user_pref_msg = f"Пользователь написал: {preferences_text}\n\nДоступные места из базы:"
    else:
        system_text = (
            "You are a virtual tourist guide for Gyumri, Armenia.\n"
            "The user described what they'd like to see or try. "
            "Below are real places from our database that match their request.\n"
            "Pick 3–5 of the most suitable ones and briefly describe each (1-2 sentences). "
            "Do not invent other places — use only the list below.\n"
            "At the end, invite the user to send their location to build a full route."
        )
        user_pref_msg = f"The user said: {preferences_text}\n\nAvailable places from the database:"

    # Build the place list context
    place_lines = []
    for idx, p in enumerate(matched_places, start=1):
        name = p.get(f"name_{lang}") or p.get("name_en") or p.get("name_ru") or p.get("name") or ""
        category = p.get("category", "")
        tags = p.get("tags", {})
        cuisine = tags.get("cuisine", "") if isinstance(tags, dict) else ""
        extra = f" [{cuisine}]" if cuisine else f" [{category}]" if category else ""
        place_lines.append(f"{idx}. {name}{extra}")

    places_block = "\n".join(place_lines)
    full_user_msg = f"{user_pref_msg}\n{places_block}"

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=full_user_msg),
    ]

    log.debug(f"[U:{user_id}][SUGGEST] sending to LLM ({len(matched_places)} places)")
    response = model.invoke(messages)
    log.debug(f"[U:{user_id}][SUGGEST] LLM replied ({len(response.content)} chars)")
    return response.content
