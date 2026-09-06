# region MODULE_CONTRACT [DOMAIN(9): HeadlessUITesting; TECH(8): plotly; CONCEPT(9): AgenticUX]
## @modulecontract
## @purpose Verify lesson_x Gradio handlers without launching browser or server.
## @scope Generate Data and Draw Graph direct function calls with type and side-effect checks.
## @input Pytest fixtures (tmp_path, caplog).
## @output Assertions over DataFrame, config file, SQLite-backed graph Figure, and LDD logs.
## @links USES_API(8): lesson_x.ui_handlers
## @invariants
## - generate_data_handler returns (DataFrame, str) even on invalid input.
## - draw_graph_handler returns a Figure even with no DB rows.
## @rationale
## Q: Why test handlers independently of Gradio?
## A: Agents verify UI behavior without browser automation or server startup.
## @changes
## LAST_CHANGE: [v2.0.0] Migrated to Doxygen semantic markup standard.
## @modulemap
## FUNC 7[Print UI handler LDD trajectory] => print_critical_logs
## FUNC 10[Headless handler acceptance test] => test_generate_data_and_draw_graph_handlers_headless
## FUNC 9[Invalid range error handling test] => test_generate_data_handler_returns_error_dataframe_for_inverted_range
## @usecases
## - [print_critical_logs]: TestHelper -> FilterUILogs -> HighBeliefDetected
## - [test_generate_data_*]: Pytest -> EmulateClick -> FullUIPipelineVerified
## - [test_*error*]: Pytest -> EmulateInvalidRange -> GracefulDegradationVerified
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: Headless UI, testing, handlers, generate data, draw graph, plotly, pytest, AgenticUX

from __future__ import annotations

import json
import logging
import re

import pandas as pd
import plotly.graph_objects as go

from lesson_x.ui_handlers import draw_graph_handler, generate_data_handler


# region FUNC_print_critical_logs [DOMAIN(9): Testing, LDD; CONCEPT(8): LogAnalysis; TECH(7): re]
## @purpose Print UI handler LDD trajectory records with IMP 7-10 and detect IMP:9 AI Belief State presence.
## @uses re.search, print
## @io pytest.LogCaptureFixture -> bool
## @complexity 4
def print_critical_logs(caplog) -> bool:
    found_high_belief = False
    print("\n--- UI LDD TRAJECTORY (IMP:7-10) ---")
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


# region FUNC_test_generate_data_and_draw_graph_handlers_headless [DOMAIN(9): HeadlessUITesting, Integration; CONCEPT(9): AgenticUX; TECH(8): plotly, pandas]
## @purpose Emulate Gradio button clicks by calling handlers directly and verify full pipeline: config persistence, data generation, SQLite round-trip, and Plotly figure construction.
## @uses generate_data_handler, draw_graph_handler, print_critical_logs
## @io tmp_path, caplog -> None
## @complexity 6
def test_generate_data_and_draw_graph_handlers_headless(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "parabola.sqlite3"

    dataframe, status = generate_data_handler(1.5, -2.0, -2.0, 2.0, config_path=config_path, db_path=db_path)
    figure = draw_graph_handler(db_path=db_path)
    found_high_belief = print_critical_logs(caplog)

    persisted_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted_config == {"a": 1.5, "c": -2.0, "x_min": -2.0, "x_max": 2.0}
    assert isinstance(dataframe, pd.DataFrame)
    assert len(dataframe) == 101
    assert list(dataframe.columns) == ["x", "y"]
    assert "Generated 101 rows" in status
    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    assert figure.layout.title.text == "Parabola: y = ax^2 + c"
    assert found_high_belief, "Critical LDD Error: UI handlers emitted no [IMP:9] AI Belief State"
# endregion FUNC_test_generate_data_and_draw_graph_handlers_headless


# region FUNC_test_generate_data_handler_returns_error_dataframe_for_inverted_range [DOMAIN(9): HeadlessUITesting, ErrorHandling; CONCEPT(8): GracefulDegradation; TECH(7): pandas]
## @purpose Reproduce and immunize the UI failure when x_min > x_max: verify empty DataFrame, friendly status, IMP:10 diagnostic, and that the last valid config is preserved.
## @uses generate_data_handler, print_critical_logs
## @io tmp_path, caplog -> None
## @complexity 5
def test_generate_data_handler_returns_error_dataframe_for_inverted_range(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "parabola.sqlite3"

    dataframe, status = generate_data_handler(1.0, 0.0, 10.0, -10.0, config_path=config_path, db_path=db_path)
    found_error_log = print_critical_logs(caplog)

    assert isinstance(dataframe, pd.DataFrame)
    assert list(dataframe.columns) == ["x", "y"]
    assert dataframe.empty
    assert status == "Input error: x_min must be less than or equal to x_max"
    assert not config_path.exists(), "Invalid input must not overwrite the last valid config"
    assert found_error_log, "Critical LDD Error: invalid UI input emitted no [IMP:10] diagnostic"
# endregion FUNC_test_generate_data_handler_returns_error_dataframe_for_inverted_range
