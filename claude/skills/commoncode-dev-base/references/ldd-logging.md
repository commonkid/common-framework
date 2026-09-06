# LDD 2.0 — Log Driven Development

Лог — не диагностический побочный продукт, а первичный артефакт. Зелёные тесты без
семантического следа исполнения не считаются доказательством корректности: фаза QA
читает лог, чтобы убедиться, что отработал именно тот путь, который был спроектирован.

## Формат записи

```
[IMP:<1-10>][<модуль>][<функция>][<Тип>] <сообщение> [<ИТОГ>]
```

Реальные примеры из базы:

```
[IMP:8][get_logger][INIT] lesson_x LDD logger initialized
[IMP:9][calculate_parabola][RESULT] Generated 21 points.
[IMP:9][save_to_db][RESULT] Inserted 21 rows
[IMP:10][db_service][save_points][Decision] I believe that saving 50 points will succeed
because the schema is pre-verified. [SUCCESS]
```

## Шкала важности

| IMP | Что размечает |
|---|---|
| 1–3 | Технический шум: вход/выход функций, промежуточные значения |
| 4–6 | Штатные операции: файл прочитан, соединение открыто |
| 7–8 | Значимые события: инициализация, границы этапов, обработанные ошибки |
| 9 | **AI Belief State** — ожидание агента перед действием и фактический результат |
| 10 | Решения, меняющие ход исполнения; критические отказы |

Записи 7–10 обязаны выводиться в консоль теста независимо от того, прошёл он или нет —
именно они и есть предмет чтения для QA.

## AI Belief State

На уровнях 9–10 фиксируется не факт, а **гипотеза и её проверка**: что агент ожидал,
на каком основании, и совпало ли. Формулировка `I believe that <X> because <Y>` с
исходом `[SUCCESS]` / `[FAILURE]` в конце.

Это ловит класс ошибок, невидимый для ассертов: код отработал без исключений, но по
ветке, которую никто не планировал.

## Изоляция

Лог модуля пишется в собственный файл внутри его папки (`lesson_X/app_X.log`), а не в
общий. Логгер создаётся одной идемпотентной фабрикой `get_logger()` — повторный вызов
возвращает тот же настроенный экземпляр и не дублирует хендлеры.

Готовый модуль: `assets/templates/logger_setup.template.py`.

Ключевые детали шаблона:

- `logger.propagate = True` — обязательно, иначе pytest-фикстура `caplog` не увидит записи.
- Два хендлера: `FileHandler` в файл модуля и `StreamHandler` в `sys.stdout`.
- Защита от повторной настройки через атрибут-флаг на самом логгере, а не через сравнение
  списка хендлеров.

## Проверка логов в тестах

```python
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
```

и в конце теста — жёсткий ассерт:

```python
assert found_high_belief, "Critical LDD Error: no [IMP:9] AI Belief State log was emitted"
```

## Ключи в логах

API-ключ не попадает в лог даже частично — ни в открытом виде, ни маскированным префиксом.
Логируется факт наличия ключа, не его значение.
