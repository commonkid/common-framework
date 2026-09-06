# Семантический экзоскелет (Doxygen v2.0)

Разметка, делающая исходник самодостаточным для агента с пустым контекстом
(**Zero-Context Survival**). Действующий стандарт — Doxygen-стиль из `lesson_x`.
Формат `# START_MODULE_CONTRACT:` / `# START_CONTRACT` из ранних итераций устарел.

## Контракт модуля

Открывает файл, до импортов.

```python
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
```

### Заголовок региона

`[DOMAIN(n): …; TECH(n): …; CONCEPT(n): …]` — измерения с весом 1–10. Вес задаёт
приоритет при семантическом поиске: `DOMAIN(9)` означает, что модуль является ядром
этой предметной области, `TECH(5)` — что технология используется вспомогательно.

### Теги

| Тег | Содержание |
|---|---|
| `@purpose` | Одно предложение: зачем модуль существует |
| `@scope` | Границы ответственности — что модуль делает и чего принципиально не делает |
| `@input` / `@output` | Что принимает и что отдаёт наружу |
| `@links` | Внешние зависимости в форме `USES_API(вес): имя` |
| `@invariants` | Условия, истинные всегда; их нарушение — баг |
| `@rationale` | Пара Q/A: почему выбрано это решение, а не очевидная альтернатива |
| `@changes` | `LAST_CHANGE: [версия] описание` |
| `@modulemap` | `FUNC вес[что делает] => имя` для каждой публичной функции |
| `@usecases` | `- [функция]: Актор -> Действие -> Результат` |

Пустышка `def _module_contract(): pass` нужна, чтобы блок оставался валидным Python
и не съедался форматтерами как висячий комментарий.

### Якоря поиска

- `# GREP_SUMMARY:` — плоский список ключевых слов через запятую. Точка входа для `grep`
  агента, который ещё не знает структуру проекта.
- `# STRUCTURE:` — поток исполнения одной строкой: `>>> A -> B[условие] -> C`.

## Контракт функции

```python
# region FUNC_read_counter [DOMAIN(8): Testing, Diagnostics; CONCEPT(9): AntiLoopProtocol; TECH(7): json]
## @purpose Read current failed-run counter from isolated lesson metadata file, returning 0 if missing or corrupt.
## @uses json.loads, Path.read_text
## @io None -> int
## @complexity 3
def read_counter() -> int:
    ...
# endregion FUNC_read_counter
```

- `@uses` — конкретные вызываемые API, а не модули целиком.
- `@io` — сигнатура в семантической форме: `tmp_path, caplog -> None`.
- `@complexity` — субъективная оценка 1–10. Значение выше 6 — сигнал архитектору, что
  функцию пора делить.

## Сегментация тела

Константы и логические куски внутри функции обрамляются регионами:

```python
# region BLOCK_CONSTANTS
COUNTER_PATH = Path(__file__).resolve().parents[1] / ".test_counter.json"
# endregion BLOCK_CONSTANTS
```

В старом формате той же цели служили `# START_BLOCK` / `# END_BLOCK`.

## Чего разметка добивается

1. **Навигация без чтения кода** — `@modulemap` и `GREP_SUMMARY` дают карту раньше, чем
   агент потратит контекст на тело файла.
2. **SFT-приминг** — развёрнутая формулировка назначения перед кодом активирует нужные
   веса модели до генерации.
3. **Защита от эрозии** — `@invariants` и `@rationale` фиксируют, почему код такой;
   без них следующий агент «упрощает» решение и ломает инвариант.
