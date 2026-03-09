"""
Настройка логирования: дублирование в терминал + файл bot_debug.log.
При каждом запуске файл лога обнуляется.

Уровни:
  NONE  — логирование отключено
  INFO  — INFO, WARNING, ERROR (состояния, маршруты, ключевые события)
  DEBUG — всё, включая дампы текстов, промптов, контекста  (по умолчанию)

Использование:
  python main.py              # DEBUG (максимум)
  python main.py --log INFO
  python main.py --log NONE
"""
import argparse
import logging
import os
import sys
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(_LOG_DIR, f"bot_{_timestamp}.log")

_LEVEL_MAP = {
    "NONE": logging.CRITICAL + 10,   # выше всех → ничего не печатается
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

_logger_instance = None


def _parse_log_level() -> int:
    """Читает --log или позиционный аргумент для уровня логов."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log", type=str, default=None)
    args, _ = parser.parse_known_args()
    
    lvl_str = "DEBUG"
    if args.log:
        lvl_str = args.log.upper()
    elif len(sys.argv) >= 3 and sys.argv[2].upper() in _LEVEL_MAP:
        lvl_str = sys.argv[2].upper()
    elif len(sys.argv) == 2 and sys.argv[1].upper() in _LEVEL_MAP:
        lvl_str = sys.argv[1].upper()
        
    return _LEVEL_MAP.get(lvl_str, logging.DEBUG)


def setup_logger(name: str = "bot") -> logging.Logger:
    global _logger_instance
    if _logger_instance is not None:
        return _logger_instance

    level = _parse_log_level()

    logger = logging.getLogger(name)
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if level <= logging.CRITICAL:
        # File handler — обнуляется при запуске (mode='w')
        fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    else:
        # NONE — пустой лог-файл + никакого вывода
        with open(LOG_FILE, "w"):
            pass

    _logger_instance = logger
    return logger


log = setup_logger("bot")
