# region MODULE_CONTRACT [DOMAIN(9): BackendTesting; CONCEPT(9): LDD; TECH(8): pytest]
## @modulecontract
## @purpose Verify lesson_x backend business logic and mandatory LDD telemetry.
## @scope Config persistence, parabola calculation, SQLite round trip, and IMP log output.
## @input Pytest fixtures (tmp_path, caplog).
## @output Test assertions and LDD trajectory console output.
## @links USES_API(8): lesson_x.config_manager; USES_API(8): lesson_x.database_manager; USES_API(8): lesson_x.parabola_engine
## @invariants
## - Every test must emit and assert at least one [IMP:9] AI Belief State log.
## @rationale
## Q: Why test LDD logs separately from business logic?
## A: Green tests are insufficient unless semantic traces confirm the execution path.
## @changes
## LAST_CHANGE: [v2.0.0] Migrated to Doxygen semantic markup standard.
## @modulemap
## FUNC 7[Print LDD trajectory with IMP 7-10] => print_critical_logs
## FUNC 10[Backend acceptance: config, calculation, DB, LDD] => test_backend_config_calculation_and_database_ldd
## @usecases
## - [print_critical_logs]: TestHelper -> FilterLogs -> HighBeliefDetected
## - [test_backend_*]: Pytest -> ExerciseBackend -> FullPipelineVerified
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: Backend testing, LDD, config, parabola, database, sqlite, pytest, telemetry

from __future__ import annotations

import logging
import re

import pandas as pd

from lesson_x.config_manager import load_config, save_config
from lesson_x.database_manager import load_points, save_points
from lesson_x.parabola_engine import generate_parabola_points


# region FUNC_print_critical_logs [DOMAIN(9): Testing, LDD; CONCEPT(8): LogAnalysis; TECH(7): re]
## @purpose Print LDD trajectory records with IMP 7-10 for agent-readable diagnostics and detect IMP:9 AI Belief State presence.
## @uses re.search, print
## @io pytest.LogCaptureFixture -> bool
## @complexity 4
def print_critical_logs(caplog) -> bool:
    found_high_belief = False
    print("\n--- LDD TRAJECTORY (IMP:7-10) ---")
    for record in caplog.records:
        match = re.search(r"\[IMP:(\d+)\]", record.getMessage())
        if not match:
            continue
        level = int(match.group(1))
        if level >= 7:
            print(record.getMessage())
        if level >= 9 and "AI Belief State" in record.getMessage():
            found_high_belief = True
    return found_high_belief
# endregion FUNC_print_critical_logs


# region FUNC_test_backend_config_calculation_and_database_ldd [DOMAIN(9): BackendTesting, Integration; CONCEPT(9): LDD; TECH(8): pytest]
## @purpose Verify the complete backend use case from config persistence through parabola calculation to SQLite readback, with mandatory LDD IMP:9 telemetry.
## @uses save_config, load_config, generate_parabola_points, save_points, load_points, print_critical_logs
## @io tmp_path, caplog -> None
## @complexity 6
def test_backend_config_calculation_and_database_ldd(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "parabola.sqlite3"

    saved_config = save_config({"a": 2, "c": 3, "x_min": -1, "x_max": 1}, config_path)
    loaded_config = load_config(config_path)
    dataframe = generate_parabola_points(loaded_config, point_count=3)
    rows_written = save_points(dataframe, db_path)
    persisted_dataframe = load_points(db_path)

    found_high_belief = print_critical_logs(caplog)

    assert saved_config == {"a": 2.0, "c": 3.0, "x_min": -1.0, "x_max": 1.0}
    assert loaded_config == saved_config
    assert rows_written == 3
    assert isinstance(persisted_dataframe, pd.DataFrame)
    assert persisted_dataframe.to_dict("records") == [
        {"x": -1.0, "y": 5.0},
        {"x": 0.0, "y": 3.0},
        {"x": 1.0, "y": 5.0},
    ]
    assert found_high_belief, "Critical LDD Error: no [IMP:9] AI Belief State log was emitted"
# endregion FUNC_test_backend_config_calculation_and_database_ldd
