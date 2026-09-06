<!--
Template source: prompt-framework-v5.md §8.1
Rule: if this template conflicts with the framework, the framework wins.
Placeholders: [project], Sprint-NNN, $PROJECT_ROOT.
-->

Структура (7 секций, порядок фиксирован):

```
СЕКЦИЯ 0: МЕТАДАННЫЕ СПРИНТА (НОВОЕ v4)
├── Sprint ID (Sprint-NNN)
├── Sprint Title
├── Date Created
├── Project
├── GitHub Project URL
├── Ссылка на будущий /SprintLog/Sprint-NNN-*.md
└── Блок «Места размещения» — пустой при генерации,
    заполняется после Post-Фаза 0 опроса (НОВОЕ v4.1):
    - Code Repository: [owner/repo]
    - Dev Project: [owner/project-number]
    - Design Project: [owner/project-number или none]
    - SprintLog Directory: [/SprintLog/ по умолчанию]

СЕКЦИЯ 1: РОЛЬ И ПОРЯДОК ДЕЙСТВИЙ
├── Что делает AI (порядок шагов)
├── Таблица: инструкция vs промпт
├── Правило: code blocks с $START/$END — неизменяемы
├── Правило: /SprintLog/ — создать скелет файла в начале (НОВОЕ v4)
└── Правило: после Фазы 0 провести Post-Фаза 0 опрос (НОВОЕ v4.1)

СЕКЦИЯ 2: ИЗУЧЕНИЕ ПРОЕКТА
├── Bash-команды для скана (ls, find, cat package.json)
├── Common Code skills (ls ~/.claude/skills/)
├── Загрузка AppGraph.xml (обязательно первым)
└── Чтение /SprintLog/_index.md и последних 3 спринтов (НОВОЕ v4)

СЕКЦИЯ 3: GITHUB WORKFLOW
├── gh auth + project scope
├── Найти/создать GitHub Project (dev + design) (НОВОЕ v4.1)
├── Создать labels (sprint-NNN, phase-N, design, bug, optimization, enhancement, frontend, backend, infra) ← sprint-NNN и design НОВОЕ v4/v4.1
├── ⚠️ НЕ СОЗДАВАТЬ Issues сразу — сначала Фаза 0
├── ⚠️ НЕ СОЗДАВАТЬ Issues — до Post-Фаза 0 опроса (НОВОЕ v4.1)
├── Формат Issue title: [Sprint-NNN][PHASE M] ... (НОВОЕ v4)
├── Разделение: dev-фазы → dev-project, design-фазы → design-project (НОВОЕ v4.1)
├── Kanban: Backlog → Ready → In Progress → Review → Done
├── Цикл фазы: промпт → разработка → тест → commit/bug → запись в SprintLog (НОВОЕ v4)
├── Формат коммитов: feat(sprint-NNN/phase-N):, fix(sprint-NNN/phase-N):, etc. (НОВОЕ v4)
└── Шаблоны Issues: [BUG], [OPT], [ENH]

СЕКЦИЯ 4: СПРАВОЧНЫЕ МАТЕРИАЛЫ
└── Технические детали, API reference, design tokens — что нужно для фаз

СЕКЦИЯ 5: ПРОМПТЫ НА ВЫПОЛНЕНИЕ
├── ⚠️ Предупреждение: НЕ УДАЛЯТЬ, НЕ МОДИФИЦИРОВАТЬ (кроме $START_LAST_UPDATE)
├── ФАЗА 0: [Анализ проекта + обогащение промптов]
├── ФАЗА 1: [code block с $START/$END маркерами + $START_LAST_UPDATE] (НОВОЕ v4)
├── ФАЗА 2: [code block + $START_LAST_UPDATE]
├── ...
├── ФАЗА N: [code block + $START_LAST_UPDATE]
└── ФАЗА N+1: Design System Snapshot (НОВОЕ v4.2)
    - Финальная фаза перед закрытием спринта
    - Вызов скилла design-system-update по команде оператора
    - Отчёт + обновление SprintLog (раздел Design System Snapshot)
    - Включает снипет END-OF-SPRINT PROTOCOL (см. 11.8)

СЕКЦИЯ 6: НАВИГАЦИОННЫЙ ГРАФ И BELIEF STATE
├── Граф зависимостей (текстовый дубль из XML)
├── Data Flow (текстовый дубль из XML)
└── $START_TODO с фазами [PENDING/COMPLETED]

СЕКЦИЯ 7: ЖУРНАЛ ФАЗЫ 0
├── Место для результатов анализа проекта
├── Обнаруженные связи и зависимости
└── Список дополнений, внесённых в промпты фаз

СЕКЦИЯ 8: ПРАВИЛА ВЕДЕНИЯ SPRINTLOG (НОВОЕ v4)
├── Шаблон /SprintLog/Sprint-NNN-[name].md
├── Когда создавать (начало спринта)
├── Когда обновлять (после каждой фазы)
├── Когда закрывать (после merge в main)
├── Правило навигации: через $START_LAST_UPDATE → sprint_log_ref
├── Обновление /SprintLog/_index.md и /SprintLog/sprint-counter.json
└── Раздел Design System Snapshot в SprintLog (НОВОЕ v4.2) —
    заполняется после вызова design-system-update,
    ПЕРЕД финальным логированием спринта
```

**Ключевое правило секции 5:** промпты лежат внутри code blocks.
Claude Code **НЕ УДАЛЯЕТ и НЕ МОДИФИЦИРУЕТ** их, **за исключением блока
`$START_LAST_UPDATE`**, который обновляется при любом изменении.
Может только **ДОПОЛНЯТЬ** остальное — добавлять текст в конец после изучения проекта.

**Ключевое правило секции 3:** Issues в GitHub Project создаются
**ТОЛЬКО ПОСЛЕ** завершения Фазы 0 и обогащения промптов.
