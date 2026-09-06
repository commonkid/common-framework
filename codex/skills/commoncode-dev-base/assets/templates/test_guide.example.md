# Test Guide for QA Agent: Lesson X — Parabola Generator

## Input Data
- **Config:** `lesson_x/config.json` — stores `{a, c, x_min, x_max}`
- **Database:** `lesson_x/parabola_x.db` — SQLite with table `points(x REAL, y REAL)`
- **Log:** `lesson_x/app_x.log` — LDD trace (IMP:1-10)

## Test Files
- `tests/test_lesson_x.py` — 3 tests covering all layers

## Test Checklist

### 1. Backend & LDD Test (`test_backend_logic`)
- **Verification SQL:** `SELECT x, y FROM points ORDER BY x`
- **Expected [IMP:9-10] markers in logs:**
  - `[IMP:9][calculate_parabola][RESULT] Generated N points.`
  - `[IMP:9][save_to_db][RESULT] Inserted N rows`
  - `[IMP:9][load_from_db][RESULT] Loaded N rows`
- **Invariant check:** `x` column must be monotonically increasing

### 2. Config Test (`test_config_manager`)
- Round-trip save/load: `save(a=3, c=-2)` → `load()` yields `a==3.0`
- Default fallback: missing config file → `a==1.0, c==0.0`

### 3. UI Headless Test (`test_ui_headless`)
- `handle_generate(a=1, c=0, x_min=-5, x_max=5)` → returns `pd.DataFrame` with 21 rows
- `handle_draw()` → returns `plotly.graph_objects.Figure` with 1 trace
- Overrides paths via `ui.DB_PATH = tmp_path` + `ui._config_mgr.config_dir = tmp_path`

## Running Tests
```bash
python -m pytest tests/test_lesson_x.py -s -v
```
