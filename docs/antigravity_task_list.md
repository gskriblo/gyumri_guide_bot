# Gyumri Tour Bot MVP Implementation Tasks

## 1. FSM and Stage Management
- [ ] Implement `SHOW_PROGRAM_OPTIONS` stage
- [ ] Implement `ROUTE_SELECTED` / `ON_ROUTE` stages
- [ ] Add `/start` and `/reset` commands
- [ ] Add ability to change style

## 2. Program Generation (Routing Engine)
- [ ] Create `routing.py` module
- [ ] Generate "Classic" program (architecture/museums/history)
- [ ] Generate "Food" program (food + 1-2 sights)
- [ ] Generate "Chill walk" program (shorter distances, fewer places)
- [ ] Integrate generation logic into [main.py](file:///home/me23/FREELANCE/NEW/%D0%94%D0%B0%D0%B2%D0%B8%D0%B4%20%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/langchain_version_2/main.py) when location is received

## 3. UI/UX Improvements (Inline Keyboards)
- [ ] Add InlineKeyboard for style selection
- [ ] Add InlineKeyboard for program selection (A/B/C)
- [ ] Add InlineKeyboard for on-route actions ("Next", "Skip", "What's nearby", "Eat nearby")

## 4. Route Navigation Logic
- [ ] Save selected route to `UserState`
- [ ] Handle "Next" to serve next place on route
- [ ] Track `visited_places`
- [ ] Handle "Skip" to skip current place

## 5. LLM Integration Updates
- [ ] Send top-10 places as context if no location is available, or handle appropriately
- [ ] Integrate dynamic prompt info for active route

***
Я закончил внедрение всех этапов MVP, описанных в task.md.

Что было сделано:

✅ routing.py: Создан модуль, генерирующий 3 варианта: Классика (Classic), Фуд-тур (Food) и Спокойная прогулка (Chill walk) с учетом ближайших мест.
✅ state.py: Добавлены поля program_selected, generated_programs для хранения вариантов, и необходимые хелперы для отслеживания текущего маршрута и посещенных точек.
✅ main.py: Полностью переработан: добавлены Inline ключи (кнопки выбора стиля, выбора варианта маршрута, а также "Следующая", "Пропустить", "Показать маршрут", "Поесть рядом"). Полная поддержка FSM-состояний (ASK_STYLE, ASK_LOCATION_REQUIRED, SHOW_PROGRAM_OPTIONS, ON_ROUTE). Внедрены команды /start и /reset.
✅ llm.py: В контекст LLM теперь передаётся информация о текущем активном маршруте пользователя (если он на маршруте), а также fallback-список ТОП-10 мест для рекомендации при отсутствии геолокации, чтобы избежать галлюцинаций.