---
name: commoncode-dev-base
description: Практическая база разработки CommonCode — эталонные стандарты кода, которые mode-code и mode-qa обязаны воспроизводить. Семантический экзоскелет в Doxygen-стиле (# region MODULE_CONTRACT, ## @purpose, GREP_SUMMARY, STRUCTURE), логирование LDD 2.0 со шкалой [IMP:1-10] и AI Belief State, изоляция слоёв (config / engine / persistence / handlers / UI), headless-тестирование на pytest и Anti-Loop Protocol через .test_counter.json. Содержит рабочее эталонное приложение, шаблоны conftest/logger/тестов, примеры DevelopmentPlan.md и AppGraph.xml, три готовых технических задания. Применяй, когда пишешь или ревьюишь код по фреймворку CommonCode, размечаешь модуль экзоскелетом, настраиваешь LDD-логи или строишь тестовый слой.
---

# CommonCode Dev Base — практическая база разработки

Скиллы `mode-architect` / `mode-code` / `mode-qa` описывают **процесс**. Этот скилл описывает
**результат**: как физически должен выглядеть код, лог и тест, чтобы фаза считалась закрытой.

Источник: серия итераций обкатки фреймворка на одной и той же учебной задаче (генератор
параболы). Стандарты ниже сняты с самой полной итерации; выдержки из неё — в `assets/templates/`.

## Когда читать что

| Задача | Файл |
|---|---|
| Разметить модуль/функцию | `references/semantic-exoskeleton.md` |
| Настроить логи, выбрать IMP-уровень | `references/ldd-logging.md` |
| Написать тесты, поднять Anti-Loop | `references/testing-protocol.md` |
| Разложить код по слоям | `references/layered-architecture.md` |
| Взять готовое ТЗ на прогон фреймворка | `assets/task-briefs/` |

## Пять обязательных требований

Код, нарушающий любое из них, возвращается фазой QA как Bug Report.

### 1. Семантический экзоскелет (Doxygen v2.0)

Каждый файл открывается блоком `# region MODULE_CONTRACT` c `@purpose`, `@scope`, `@input`,
`@output`, `@links`, `@invariants`, `@rationale` (в форме Q/A), `@changes`, `@modulemap`,
`@usecases`. Сразу за ним — однострочники `# GREP_SUMMARY:` и `# STRUCTURE:`.

Каждая функция оборачивается в `# region FUNC_<имя>` с `@purpose`, `@uses`, `@io`, `@complexity`.

Формат `# START_MODULE_CONTRACT:` из ранних итераций **устарел**; в новом коде только Doxygen-стиль.
Контракты пишутся в парадигме **Zero-Context Survival**: агент, открывший файл без истории
диалога, обязан понять модуль целиком из одной шапки.

### 2. LDD 2.0 — логи как первичный артефакт

Логи пишутся в изолированный файл внутри модуля (`app_X.log`), каждая запись несёт маркер
`[IMP:1-10]`. На уровнях 9–10 фиксируется **AI Belief State** — что агент ожидал и что
произошло фактически:

```
[IMP:10][db_service][save_points][Decision] I believe that saving 50 points will succeed
because the schema is pre-verified. [SUCCESS]
```

Отсутствие записи `[IMP:9]` или `[IMP:10]` в прогоне — **провал теста**, а не косметика.

### 3. Изоляция слоёв

`config_manager` · `engine`/`logic` · `db_manager` · `handlers` · `ui` · точка входа
`run_*.py`. Обработчики UI не знают про SQL, движок расчёта не знает про Gradio,
конфиг читается и пишется ровно одним модулем.

### 4. Headless-тестирование

Обработчики UI вызываются напрямую как функции — без браузера, без запуска сервера.
Проверяются типы возврата (`pd.DataFrame`, `plotly.graph_objects.Figure`), побочные эффекты
(файл конфига обновился, строки легли в БД) и деградация на невалидном вводе.

### 5. Anti-Loop Protocol

`tests/conftest.py` через session-хуки ведёт `.test_counter.json`. На 3-й неудаче подсказывает
искать решение вовне, на 4-й предупреждает о зацикливании, на 5-й — жёсткий стоп с требованием
сформулировать запрос оператору. Шаблон готов: `assets/templates/conftest.template.py`.

## Порядок работы

1. `mode-architect` → `DevelopmentPlan.md` с секциями **Draft Code Graph** и **Data Flow**
   (пример: `assets/templates/DevelopmentPlan.example.md`). Предложить пользователю 2 гипотезы
   реализации и дождаться выбора — «коллапс суперпозиции».
2. `mode-code` → реализация с экзоскелетом, LDD и тестами.
3. `mode-qa` → независимый прогон pytest + Diagnostic Trio (Logs / Code / Data).
4. **Только после зелёных тестов** — локальный `AppGraph.xml`
   (пример: `assets/templates/AppGraph.example.xml`). Корневой граф из фазы кода не трогается.

## Правило окружения

Новые venv не создаются и уже установленные библиотеки не переустанавливаются. Изоляция
достигается инкапсуляцией файлов внутри папки модуля. Единственное исключение, зафиксированное
в базе, — установка `openai>=1.0.0`, если её нет в системе.

## Безопасность ключей

API-ключи не пишутся ни в `config.json`, ни в `.env`, ни в логи — даже частично. Источники
только внешние: аргумент `--api-key`, затем переменные окружения. Отдельный тест проверяет,
что конфиг не содержит поля с ключом.

## Готовые технические задания

`assets/task-briefs/` — три ТЗ, каждое прогоняет фреймворк на своём стеке:

- `gradio-parabola-app.md` — Gradio + Plotly + SQLite, двухколоночный UI, полный цикл.
- `cli-conservative-stack.md` — только stdlib + pandas, CLI на argparse (`init`/`generate`/`view`).
- `openai-tools-plugins.md` — OpenAI-совместимый tools-режим, паттерн Tool = Plugin, 6 схем
  инструментов, мокирование HTTP в тестах.

`references/framework-knowledge-graph.xml` — граф связей фреймворка (роли, фазы, протоколы)
в формате `graph-protocol`.
