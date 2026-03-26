# Project flow chart explanation
_Exported on 3/26/2026 at 12:24:45 GMT+4 from Cursor (2.6.11)_

---

**User**

explain project flow chart

---

**Cursor**

I’ll first scan the repo for the main entrypoint(s) and any existing diagram/README, then I’ll summarize the end-to-end runtime flow as a clear flow chart (and map each step to the relevant files).

I found the likely entrypoint (`main.py`) and several docs, including a README and a file specifically explaining `main.py`. Next I’ll read those and turn them into a project flow chart you can follow.

Now I’ll read the core modules (`llm`, `state`, `routing`, `data_gyumri`) so the flow chart reflects the real control flow: Telegram update → state machine → LLM + place DB → route generation → navigation callbacks.

I’ve now got the full runtime loop: `main.py` is the Telegram “controller”, `state.py` is the per-user state machine, `data_gyumri.py` is the places DB + geo search, `routing.py` builds the 3 route options, and `llm.py` wraps the LLM + conversation memory. Next I’ll grab `prompts.py` and then I’ll present a clean flow chart plus a short “what happens on each user action” mapping.

## Project flow chart (runtime)

```mermaid
flowchart TD
  A[Run: python main.py] --> B[Load .env\nTELEGRAM_BOT_TOKEN / GROQ_API_KEY / DEEPSEEK_API_KEY]
  B --> C[aiogram starts polling\nDispatcher routes updates]

  C -->|/start or /reset| S0[reset_user_state()\nstate.stage=ASK_LANGUAGE\nprompt language buttons]
  C -->|Callback: lang_*| S1[set_language()\nstate.stage=ASK_STYLE\nprompt style buttons]
  C -->|Callback: style_*| S2[set_style()\nstate.stage=ASK_PREFERENCES\nask user preferences text]

  C -->|Text message| T0{state.stage?}
  T0 -->|ASK_PREFERENCES| P0[set_raw_preferences()\nsuggest_places_from_preferences()\n(prompt: send location)\nstate.stage=ASK_LOCATION_REQUIRED]
  T0 -->|ASK_* waiting for buttons| Pwait[Ask user to use buttons]
  T0 -->|ON_ROUTE or FREE_CHAT| L0[generate_reply()\nLLM response + conversation memory]

  C -->|User sends location| G0[set_location()]
  G0 -->|stage==ASK_LOCATION_REQUIRED| H0[state.stage=ASK_HOURS\nshow hours buttons]
  G0 -->|else| N0[get_nearby_places()\nformat_places_for_user()\n(send list)]

  C -->|Callback: hours_*| R0[set_tour_hours()\nstate.stage=SHOW_PROGRAM_OPTIONS]
  R0 --> R1[generate_programs(lat,lon,time,interests)\n(classic/food/chill)]
  R1 --> R2[save_generated_programs()\nformat_program_options()\nshow program buttons]

  C -->|Callback: prog_*| PR0[set_program()\nstate.stage=ON_ROUTE]
  PR0 --> NAV0[_send_place_navigation()\n(photo) + maps link + venue\non-route keyboard]

  C -->|Callback: route_next/skip| NAV1[pop current_route[0]\nmark visited if next\nsend next place or finish]
  C -->|Callback: route_show| NAV2[list remaining places]
  C -->|Callback: route_whats_nearby| NAV3[get_nearby_places(100m)]
  C -->|Callback: route_eat_nearby| NAV4[get_nearby_places(food,2km)\nnumbered buttons]
  C -->|Callback: food_*| NAV5[send navigation to selected food place]
```

## How to read it (file-by-file map)

- **`main.py`**: the “controller” and UX.
  - Defines the **state machine** by checking `state.stage` in `handle_message()` and in callback handlers.
  - Sends messages, keyboards, and navigation cards (`_send_place_navigation()`).

- **`state.py`**: per-user memory (in-process dict).
  - Stores `stage`, `language`, `style`, `preferences`, `last_location`, `generated_programs`, `current_route`, `visited_places`.

- **`data_gyumri.py`**: places “database” + geo helpers.
  - Loads JSON (`PLACES_JSON` env var or `places_gyumri.json` next to the code).
  - Provides `get_nearby_places()`, keyword search, `get_place_by_id()`, distance calc.

- **`routing.py`**: route generation.
  - `generate_programs()` builds **3 candidate programs** (classic/food/chill) from nearby places + optional “pinned” matches from interests.
  - `format_program_options()` renders the options text.

- **`llm.py` + `prompts.py`**: LLM wrapper + prompt.
  - Picks **Groq** or **DeepSeek** based on CLI arg (first argument).
  - `generate_reply()` builds `SystemMessage` from `build_system_prompt(state)`, injects **route context + nearby places**, adds recent chat turns, calls the model, and summarizes old history when it grows.

If you tell me which “flow chart” you mean (user journey vs internal modules vs deployment), I can redraw the diagram to match that exact viewpoint.

---

**User**

describe user iteraction step-by-step. Expecially abut AI call

---

**Cursor**

## User interaction (step-by-step)

### 1) Start / reset
- **User action**: sends `/start` (or `/reset`)
- **Bot does** (`main.py`):
  - Clears state with `reset_user_state(uid)`
  - Detects Telegram device language and sets `state.language`
  - Shows **language buttons**
  - Sets `state.stage = "ASK_LANGUAGE"`

### 2) Choose language (button)
- **User action**: taps `🇷🇺 Русский` or `🇬🇧 English`
- **Bot does** (`main.py` callback `lang_*`):
  - `set_language(uid, "ru"/"en")`
  - Shows **style buttons**
  - Sets `state.stage = "ASK_STYLE"`

### 3) Choose style (button)
- **User action**: taps Emotional / Strict / Fun
- **Bot does** (`main.py` callback `style_*`):
  - `set_style(uid, style)`
  - Asks: “Tell me what you’d like to see in Gyumri?”
  - Sets `state.stage = "ASK_PREFERENCES"`

### 4) Describe preferences (first AI call happens here)
- **User action**: types free text (example: “museums, old architecture, coffee”)
- **Bot does** (`main.py` `handle_message()` when `stage == "ASK_PREFERENCES"`):
  - Saves raw preferences with `set_raw_preferences(uid, user_input)`
  - Calls **AI suggestion**: `suggest_places_from_preferences(uid, user_input, state)`
  - Sends AI’s suggestions to the user
  - Prompts user to **send geolocation**
  - Sets `state.stage = "ASK_LOCATION_REQUIRED"`

#### What exactly the AI call is in this step
Inside `llm.py` `suggest_places_from_preferences()`:
- **DB search first (no LLM yet)**:
  - Splits the user text into keywords
  - `search_places_by_keywords(keywords, limit=15)` returns *real places from your JSON DB*
- **Then the LLM is called once**:
  - **System message**: tells the model “you are a Gyumri guide, pick 3–5 places from the provided list; do not invent; invite user to send location”
  - **Human message**: contains the user’s preference text + the numbered list of matched DB places
  - `response = model.invoke(messages)`
- **Output**: the LLM returns a short curated recommendation list (grounded to DB names you provided)

### 5) Send location
- **User action**: shares Telegram location (📎 → Location)
- **Bot does** (`main.py` `handle_location()`):
  - `set_location(uid, lat, lon)`
  - If `stage == "ASK_LOCATION_REQUIRED"`:
    - Shows **tour duration buttons** (1h, 2h, 3h, …)
    - Sets `state.stage = "ASK_HOURS"`
  - Else (location sent during free chat / on-route):
    - Shows nearby places list (no AI call, just DB query)

### 6) Choose tour duration (button)
- **User action**: taps e.g. `4h`
- **Bot does** (`main.py` callback `hours_*`):
  - `set_tour_hours(uid, hours)`
  - Builds 3 route options (this is *algorithmic*, not LLM):
    - `programs = generate_programs(lat, lon, time_hours=hours, interests=state.preferences.interests)`
  - Saves program → list-of-place-ids with `save_generated_programs(uid, programs_ids)`
  - Sends a formatted list of program options + **program buttons**
  - Sets `state.stage = "SHOW_PROGRAM_OPTIONS"`

### 7) Choose a program (button)
- **User action**: taps Classic / Food / Chill
- **Bot does** (`main.py` callback `prog_*`):
  - `set_program(uid, prog_id)` → sets `state.current_route = generated_programs[prog_id]`
  - Sets `state.stage = "ON_ROUTE"`
  - Sends the **first navigation card** (`_send_place_navigation()`):
    - place name/desc, distance (if location known), Google Maps link, venue card, and on-route keyboard

### 8) Navigate the route (buttons)
- **User action**: taps:
  - **Next**: marks current place visited, advances to next stop, sends next navigation card
  - **Skip**: advances without marking visited
  - **Show Route**: lists remaining stops
  - **What’s nearby / Eat nearby**: queries DB around user and shows options; selecting `food_*` shows navigation card to that place

---

## When the “main AI chat call” happens (and what it sends)

Outside the structured onboarding steps above, any normal user message goes through the general AI chat path.

### Trigger
In `main.py` `handle_message()`:
- If the stage is **not** one of the strict onboarding stages (language/style/preferences/location/hours/program-choice), it does:
  - `reply_text = generate_reply(user_id=uid, user_input=user_input, user_state=state)`
  - Sends that reply (and if `stage == "ON_ROUTE"`, it attaches the on-route keyboard)

### What `generate_reply()` actually sends to the model
In `llm.py` `generate_reply()` the prompt is assembled in this order:

1) **System prompt** (`prompts.py` `build_system_prompt(state)`):
- Base “Gyumri guide” instruction (RU/EN)
- Style hint (emotional/strict/fun)
- If set: user interests text

2) **Route context (only if on a route)**:
- If `user_state.current_route` exists, it appends a message listing upcoming stops with short descriptions pulled from DB (`get_place_by_id()`)

3) **Nearby/top places context** (anti-hallucination grounding):
- If user has location: `get_nearby_places(lat, lon, max_distance_km=2, limit=8)`
- Else: loads DB and takes first 10 places as “top”
- Adds a message: “Use only these places for concrete recommendations; don’t invent others” + enumerated list

4) **Recent conversation turns**:
- Keeps only last `MAX_TURNS_FOR_MODEL` user/assistant messages (default 8 turns)

5) **Single model call**:
- `response = model.invoke(messages_for_model)`

6) **Conversation memory management**:
- Stores history per user in `_user_conversations[user_id]`
- If history grows too large, it does **another LLM call** to summarize older messages (`summarize_dialog()`), then keeps a short summary + a few recent turns

### Model selection (important detail)
At import time in `llm.py`:
- If you run `python main.py DEEPSEEK`, it uses DeepSeek via `ChatOpenAI(... openai_api_base='https://api.deepseek.com')`
- Otherwise it uses **Groq** `ChatGroq(model="llama-3.3-70b-versatile")`

If you want, I can rewrite this as a shorter “user journey” list you can paste into your README (no code terms, just UX steps).

