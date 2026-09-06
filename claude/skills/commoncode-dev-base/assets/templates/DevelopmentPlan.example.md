$START_DEV_PLAN

**PURPOSE:** План разработки учебного приложения Lesson X (Парабола y = ax^2 + c).

---

### 1. Draft Code Graph (Черновой Граф Кода)

```xml
<DraftCodeGraph>
  <config_manager_py FILE="lesson_x/config_manager.py" TYPE="MODULE">
    <annotation>Управление config.json (a, c, x_min, x_max).</annotation>
    <load_config_FUNC NAME="load_config" TYPE="FUNCTION">
      <annotation>Загрузка параметров из JSON.</annotation>
    </load_config_FUNC>
    <save_config_FUNC NAME="save_config" TYPE="FUNCTION">
      <annotation>Сохранение параметров в JSON.</annotation>
    </save_config_FUNC>
  </config_manager_py>

  <db_manager_py FILE="lesson_x/db_manager.py" TYPE="MODULE">
    <annotation>Управление SQLite БД (points.db).</annotation>
    <init_db_FUNC NAME="init_db" TYPE="FUNCTION">
      <annotation>Создание таблицы points.</annotation>
    </init_db_FUNC>
    <save_points_FUNC NAME="save_points" TYPE="FUNCTION">
      <annotation>Сохранение списка точек (x, y).</annotation>
    </save_points_FUNC>
    <get_points_FUNC NAME="get_points" TYPE="FUNCTION">
      <annotation>Получение всех точек из БД.</annotation>
    </get_points_FUNC>
  </db_manager_py>

  <logic_py FILE="lesson_x/logic.py" TYPE="MODULE">
    <annotation>Бизнес-логика расчета параболы.</annotation>
    <calculate_parabola_FUNC NAME="calculate_parabola" TYPE="FUNCTION">
      <annotation>Генерация точек y = ax^2 + c.</annotation>
      <CrossLinks>
        <Link TARGET="db_manager_py_save_points_FUNC" TYPE="CALLS_FUNCTION" />
      </CrossLinks>
    </calculate_parabola_FUNC>
  </logic_py>

  <handlers_py FILE="lesson_x/handlers.py" TYPE="MODULE">
    <annotation>Обработчики UI Gradio.</annotation>
    <handle_generate_FUNC NAME="handle_generate" TYPE="FUNCTION">
      <annotation>Сохраняет конфиг, считает точки, пишет в БД, возвращает DataFrame.</annotation>
      <CrossLinks>
        <Link TARGET="config_manager_py_save_config_FUNC" TYPE="CALLS_FUNCTION" />
        <Link TARGET="logic_py_calculate_parabola_FUNC" TYPE="CALLS_FUNCTION" />
      </CrossLinks>
    </handle_generate_FUNC>
    <handle_draw_FUNC NAME="handle_draw" TYPE="FUNCTION">
      <annotation>Читает БД, строит Plotly Figure.</annotation>
      <CrossLinks>
        <Link TARGET="db_manager_py_get_points_FUNC" TYPE="CALLS_FUNCTION" />
      </CrossLinks>
    </handle_draw_FUNC>
  </handlers_py>

  <app_py FILE="lesson_x/app.py" TYPE="MODULE">
    <annotation>Определение интерфейса Gradio.</annotation>
  </app_py>

  <run_lesson_x_py FILE="run_lesson_x.py" TYPE="ENTRY_POINT">
    <annotation>Точка запуска сервера Gradio.</annotation>
  </run_lesson_x_py>
</DraftCodeGraph>
```

---

### 2. Step-by-step Data Flow (Пошаговый Поток Данных)

1.  **Инициализация:** При запуске `run_lesson_x.py` инициализируется БД через `db_manager.init_db()`.
2.  **Ввод данных:** Пользователь меняет `a`, `c`, `x_min`, `x_max` в Gradio.
3.  **Генерация (Кнопка 1):**
    *   `handle_generate` вызывает `save_config` для обновления `config.json`.
    *   `calculate_parabola` генерирует 100 точек (равномерно по x_min..x_max).
    *   Точки сохраняются в `points.db`.
    *   Возвращается `pandas.DataFrame` для отображения в таблице.
4.  **Визуализация (Кнопка 2):**
    *   `handle_draw` запрашивает данные из `db_manager.get_points()`.
    *   Создается `plotly.graph_objects.Figure`.
    *   График отображается в правой колонке.

---

### 3. Acceptance Criteria (Критерии Приемки)

- [ ] **Критерий 1:** Все файлы содержат семантическую разметку (CONTRACT, MODULE_MAP, LDD логи).
- [ ] **Критерий 2:** Логи пишутся в `lesson_x/app_x.log` с использованием `[IMP:1-10]`.
- [ ] **Критерий 3:** Тест `test_backend.py` проверяет расчет и БД, выводя логи `IMP:7-10`.
- [ ] **Критерий 4:** Тест `test_ui.py` проверяет `handle_generate` и `handle_draw` (Headless).
- [ ] **Критерий 5:** Создан локальный `lesson_x/AppGraph.xml`.

$END_DEV_PLAN
