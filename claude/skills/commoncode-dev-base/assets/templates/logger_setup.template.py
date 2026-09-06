# region MODULE_CONTRACT [DOMAIN(9): LDD; TECH(8): logging; CONCEPT(8): AI_Belief_State]
## @modulecontract
## @purpose Provide isolated LDD logging for lesson_x modules.
## @scope Logger construction, file/stdout handlers, and safe reuse across tests and UI runs.
## @input None (reads LOGGER_NAME constant).
## @output logging.Logger instance with file and stream handlers attached.
## @links USES_API(8): logging; USES_API(6): sys.stdout
## @invariants
## - get_logger is idempotent: repeated calls return the same configured logger.
## - LOG_PATH parent directory is created on first logger init.
## @rationale
## Q: Why use a flag attribute instead of checking existing handlers?
## A: The flag pattern is simpler and avoids handler-reference comparisons across imports.
## @changes
## LAST_CHANGE: [v2.0.0] Migrated to Doxygen semantic markup standard.
## @modulemap
## FUNC 10[Return configured lesson_x LDD logger] => get_logger
## @usecases
## - [get_logger]: Module/Test -> ObtainLogger -> LDDTelemetryAvailable
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: LDD, logging, logger, file handler, stdout, AI Belief State, idempotent
# STRUCTURE: >>> LOGGER_NAME -> idempotent guard (_configured?) -> create FileHandler + StreamHandler -> _configured=True -> logger

from __future__ import annotations

import logging
import sys
from pathlib import Path

# region BLOCK_CONSTANTS
LESSON_DIR = Path(__file__).resolve().parent
LOG_PATH = LESSON_DIR / "app_x.log"
LOGGER_NAME = "lesson_x"
# endregion BLOCK_CONSTANTS


# region FUNC_get_logger [DOMAIN(9): LDD, Logging; CONCEPT(8): IdempotentInit; TECH(8): logging.FileHandler, logging.StreamHandler]
## @purpose Return the shared lesson logger with deterministic file and stdout handlers, creating them only once.
## @uses logging.getLogger, logging.FileHandler, logging.StreamHandler
## @io None -> logging.Logger
## @complexity 4
def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = True

    if getattr(logger, "_lesson_x_configured", False):
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger._lesson_x_configured = True
    logger.info("[IMP:8][get_logger][INIT] lesson_x LDD logger initialized")
    return logger
# endregion FUNC_get_logger
