# region MODULE_CONTRACT [DOMAIN(8): Testing; CONCEPT(9): AntiLoopProtocol; TECH(8): pytest]
## @modulecontract
## @purpose Provide pytest anti-loop telemetry for lesson_x test runs.
## @scope Session hooks only; tests must not increment counters directly.
## @input None (reads/writes .test_counter.json in lesson root).
## @output Console diagnostics and persisted .test_counter.json.
## @links USES_API(7): json; USES_API(5): pathlib.Path
## @invariants
## - Only session hooks (pytest_sessionstart, pytest_sessionfinish) may mutate anti-loop state.
## @rationale
## Q: Why persist counter to disk instead of memory?
## A: Repeated pytest executions by agents must detect looping across runs.
## @changes
## LAST_CHANGE: [v2.0.0] Migrated to Doxygen semantic markup standard.
## @modulemap
## FUNC 4[Read failed-run counter from disk] => read_counter
## FUNC 5[Persist failed-run counter to disk] => write_counter
## FUNC 6[Print anti-loop diagnostics before test session] => pytest_sessionstart
## FUNC 6[Update anti-loop counter after session] => pytest_sessionfinish
## @usecases
## - [read_counter]: SessionHook -> ReadState -> AttemptCount
## - [write_counter]: SessionHook -> PersistState -> CounterUpdated
## - [pytest_sessionstart]: Pytest -> EmitDiagnostics -> AgentGuidancePrinted
## - [pytest_sessionfinish]: Pytest -> UpdateCounter -> StatePersisted
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: Testing, pytest, anti-loop, telemetry, counter, session hooks, diagnostics
# STRUCTURE: >>> COUNTER_PATH -> read_counter (json.load) / write_counter (json.dump) -> pytest_sessionstart[print guidance] -> pytest_sessionfinish[increment|reset]

from __future__ import annotations

import json
from pathlib import Path

# region BLOCK_CONSTANTS
COUNTER_PATH = Path(__file__).resolve().parents[1] / ".test_counter.json"
CHECKLIST = [
    "Verify imports use package paths and not sys.path.append.",
    "Verify tmp_path is used for config and SQLite files.",
    "Verify [IMP:7-10] logs are printed before final assertions.",
    "Verify Gradio server is not launched in UI tests.",
]
# endregion BLOCK_CONSTANTS


# region FUNC_read_counter [DOMAIN(8): Testing, Diagnostics; CONCEPT(9): AntiLoopProtocol; TECH(7): json]
## @purpose Read current failed-run counter from isolated lesson metadata file, returning 0 if missing or corrupt.
## @uses json.loads, Path.read_text
## @io None -> int
## @complexity 3
def read_counter() -> int:
    if not COUNTER_PATH.exists():
        return 0
    try:
        return int(json.loads(COUNTER_PATH.read_text(encoding="utf-8")).get("failed_attempts", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
# endregion FUNC_read_counter


# region FUNC_write_counter [DOMAIN(8): Testing, Diagnostics; CONCEPT(9): AntiLoopProtocol; TECH(7): json]
## @purpose Persist the current failed-run counter to disk as JSON for cross-session agent awareness.
## @uses json.dumps, Path.write_text
## @io int -> None
## @complexity 2
def write_counter(value: int) -> None:
    COUNTER_PATH.write_text(json.dumps({"failed_attempts": value}, indent=2), encoding="utf-8")
# endregion FUNC_write_counter


# region FUNC_pytest_sessionstart [DOMAIN(8): Testing, Diagnostics; CONCEPT(9): AntiLoopProtocol; TECH(8): pytest.hooks]
## @purpose Print anti-loop status and guidance checklist before tests execute, escalating guidance based on failure count.
## @uses read_counter, print
## @io pytest.Session -> None
## @complexity 4
def pytest_sessionstart(session) -> None:
    attempts = read_counter()
    if attempts <= 0:
        return
    print(f"\nANTI_LOOP_STATUS: previous_failed_attempts={attempts}")
    print("CHECKLIST:")
    for item in CHECKLIST:
        print(f"- {item}")
    if attempts == 3:
        print("Use MCP `tavily` or `Context 7` to find a solution online.")
    elif attempts == 4:
        print("WARNING: Looping risk! Pause and reflect. Are you repeating a failed strategy? Consider alternatives (Superposition).")
    elif attempts >= 5:
        print("CRITICAL ERROR: Agent looping detected. STOP. Formulate a help request for an operator.")
# endregion FUNC_pytest_sessionstart


# region FUNC_pytest_sessionfinish [DOMAIN(8): Testing, Diagnostics; CONCEPT(9): AntiLoopProtocol; TECH(8): pytest.hooks]
## @purpose Reset or increment anti-loop counter after the test session based on exit status.
## @uses read_counter, write_counter
## @io pytest.Session, int -> None
## @complexity 3
def pytest_sessionfinish(session, exitstatus) -> None:
    if exitstatus == 0:
        write_counter(0)
        return
    write_counter(read_counter() + 1)
# endregion FUNC_pytest_sessionfinish
