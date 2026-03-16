from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from logger_setup import log


@dataclass
class UserPreferences:
    interests: List[str] = field(default_factory=list)
    time_available_hours: Optional[float] = None
    budget_level: Optional[str] = None  # "low" | "medium" | "high" | None


@dataclass
class UserState:
    user_id: int
    stage: str = "NEW_USER"
    style: str = "emotional"  # "emotional" | "strict" | "fun"
    language: str = "ru"      # "ru" | "en"
    preferences: UserPreferences = field(default_factory=UserPreferences)
    last_location: Optional[Tuple[float, float]] = None
    current_route: List[str] = field(default_factory=list)
    visited_places: List[str] = field(default_factory=list)
    history_summary: Optional[str] = None
    program_selected: Optional[str] = None
    generated_programs: Dict[str, List[str]] = field(default_factory=dict)


_user_states: Dict[int, UserState] = {}


def get_user_state(user_id: int) -> UserState:
    state = _user_states.get(user_id)
    if state is None:
        state = UserState(user_id=user_id)
        _user_states[user_id] = state
        log.debug(f"[U:{user_id}][STATE] Created new state")
    return state


def save_user_state(state: UserState) -> None:
    _user_states[state.user_id] = state


def update_stage(user_id: int, stage: str) -> None:
    state = get_user_state(user_id)
    old = state.stage
    state.stage = stage
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] stage: {old} → {stage}")


def set_style(user_id: int, style: str) -> None:
    state = get_user_state(user_id)
    old = state.style
    state.style = style
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] style: {old} → {style}")


def set_language(user_id: int, language: str) -> None:
    state = get_user_state(user_id)
    state.language = language
    save_user_state(state)
    log.debug(f"[U:{user_id}][STATE] language={language}")


def set_raw_preferences(user_id: int, text: str) -> None:
    state = get_user_state(user_id)
    state.preferences.interests = [text.strip()] if text.strip() else []
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] preferences={state.preferences.interests!r}")


def set_location(user_id: int, lat: float, lon: float) -> None:
    state = get_user_state(user_id)
    state.last_location = (lat, lon)
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] location=({lat}, {lon})")


def set_program(user_id: int, program_id: str) -> None:
    state = get_user_state(user_id)
    state.program_selected = program_id
    if program_id in state.generated_programs:
        state.current_route = list(state.generated_programs[program_id])
        log.info(f"[U:{user_id}][STATE] program={program_id}, route={state.current_route}")
    else:
        log.warning(f"[U:{user_id}][STATE] program={program_id} NOT FOUND in generated_programs!")
    state.visited_places = []
    save_user_state(state)


def set_tour_hours(user_id: int, hours: float) -> None:
    state = get_user_state(user_id)
    state.preferences.time_available_hours = hours
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] tour_hours={hours}")


def save_generated_programs(user_id: int, programs: Dict[str, List[str]]) -> None:
    state = get_user_state(user_id)
    state.generated_programs = programs
    save_user_state(state)
    log.info(f"[U:{user_id}][STATE] generated_programs: { {k: len(v) for k, v in programs.items()} }")


def mark_place_visited(user_id: int, place_id: str) -> None:
    state = get_user_state(user_id)
    if place_id not in state.visited_places:
        state.visited_places.append(place_id)
    save_user_state(state)
    log.debug(f"[U:{user_id}][STATE] visited={state.visited_places}")


def reset_user_state(user_id: int) -> None:
    if user_id in _user_states:
        del _user_states[user_id]
    get_user_state(user_id)
    log.info(f"[U:{user_id}][STATE] RESET")
