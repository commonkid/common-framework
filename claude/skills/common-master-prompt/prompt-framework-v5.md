# Фреймворк: промпт как контракт (v4.2)

> Системная инструкция для генерации промптов.
> Целевая модель: **Claude Opus 4.6** (через Commoncode / Claude Code).
> При каждом вызове `/ultraprompt` или запросе на создание ТЗ для AI-разработки —
> следовать этому фреймворку и генерировать **два файла**.
>
> **Новое в v4:** система нумерованных спринтов, `$START_LAST_UPDATE` в каждом промпте,
> папка `/SprintLog/` для долговременной памяти проекта.
>
> **Новое в v4.1:** обязательный Post-Фаза 0 опрос оператора — агент задаёт 4 вопроса
> о местах размещения кода, задач и логов перед созданием Issues.
>
> **Новое в v4.2:** End-of-Sprint Design System Snapshot — перед закрытием спринта
> и финальным логированием агент обновляет дизайн-систему через 3 скилла
> (`design-system-update`, `design-system-verify`, `design-system-archive`).

---

## 1. Принцип

Промпт — это протокол, не просьба. Каждый ответ на задачу разработки
строится по контракту из 6 компонентов и проходит через фазы.

**Результат ВСЕГДА = два файла:**
1. `[project]-MASTER-INSTRUCTION.md` — мастер-инструкция для Claude Code
2. `AppGraph.xml` — навигационный граф архитектуры

**Плюс при выполнении:**
3. `/SprintLog/Sprint-NNN-[название].md` — создаётся Claude Code после завершения спринта

---

## 2. Обязательная anti-hallucination директива

### 2.1. Точная формулировка (вставлять 1-в-1)

Каждый промпт (каждая фаза, каждый блок `$START_GOAL`) **ОБЯЗАН** содержать
следующую фразу в самом начале, **дословно, без изменений**:

```
Не спеши с выводами, т.к. можешь свалится в локальный оптимум и выбрать не самое оптимальное решение. Используй что-то вроде суперпозиции смыслов с разными гипотезами, коллапс в конкретный вариант сделаем по моей команде. Сначала изучи граф на приложение.
```

### 2.2. Где размещать

Фраза вставляется **первой строкой** внутри `$START_GOAL` каждой фазы:

```
$START_GOAL
Не спеши с выводами, т.к. можешь свалится в локальный оптимум и выбрать не самое оптимальное решение. Используй что-то вроде суперпозиции смыслов с разными гипотезами, коллапс в конкретный вариант сделаем по моей команде. Сначала изучи граф на приложение.

Цель: [конкретная цель фазы]
$END_GOAL
```

### 2.3. Зачем это нужно

Директива решает три задачи:

| Задача | Механизм |
|--------|----------|
| Предотвращение преждевременного коллапса | Модель не генерирует финальный код сразу — она удерживает суперпозицию вариантов |
| Привязка к навигационному графу | Модель сначала читает AppGraph.xml и ориентируется по архитектуре |
| Контроль оператора над коллапсом | Выбор финального варианта происходит только по команде человека |

### 2.4. Правило для генератора промптов

При генерации MD-файла с фазами — **автоматически** вставлять эту фразу
в `$START_GOAL` каждой фазы. Если фраза отсутствует — промпт считается
невалидным и не проходит чек-лист.

---

## 3. Система спринтов (НОВОЕ в v4)

### 3.1. Что такое спринт

**Спринт** — это единица работы, равная одному мастер-промпту на крупную фичу
или группу связанных фич. Каждый вызов `/ultraprompt` = создание нового
пронумерованного спринта.

**Правило:** каждая большая фича или мастер-промпт для определённого проекта =
новый спринт с уникальным номером.

### 3.2. Нумерация спринтов

Задача **генератора промптов** (Commoncode Prompt / ultraprompt):
- Присваивать каждому новому мастер-промпту уникальный номер спринта
- Формат: `Sprint-NNN` где NNN — трёхзначное число с ведущими нулями
- Примеры: `Sprint-001`, `Sprint-002`, `Sprint-015`, `Sprint-127`
- Номера монотонно возрастают в рамках одного проекта (не переиспользуются)

### 3.3. Где хранится текущий номер спринта

В корне проекта файл `/SprintLog/sprint-counter.json`:

```json
{
  "project": "<ProjectName>",
  "current_sprint": 7,
  "next_sprint_id": "Sprint-008",
  "sprints": [
    { "id": "Sprint-001", "title": "Agent Catalog", "status": "completed", "date": "2025-10-15" },
    { "id": "Sprint-002", "title": "Leaderboard & Arena", "status": "completed", "date": "2025-10-28" },
    { "id": "Sprint-007", "title": "Notifications System", "status": "in_progress", "date": "2026-04-18" }
  ]
}
```

**Правило:** перед генерацией нового мастер-промпта генератор **ОБЯЗАН**:
1. Прочитать `sprint-counter.json` (если есть)
2. Взять значение `next_sprint_id`
3. Использовать его как ID нового спринта
4. Обновить `sprint-counter.json` (увеличить `current_sprint`, пересчитать `next_sprint_id`, добавить запись в `sprints`)

Если файла нет — создать с `current_sprint: 1` и `next_sprint_id: "Sprint-001"`.

### 3.4. Нумерация задач в GitHub Project

**Каждая задача (Issue), относящаяся к спринту, получает префикс в названии:**

```
[Sprint-007][PHASE 0] Анализ проекта и обогащение промптов
[Sprint-007][PHASE 1] Модель данных Notification
[Sprint-007][PHASE 2] API endpoints уведомлений
[Sprint-007][PHASE 3] UI компоненты NotificationCenter
```

**Формат названия Issue:**
```
[Sprint-NNN][PHASE M] Краткое описание
```

где:
- `Sprint-NNN` — ID спринта (из мастер-промпта)
- `PHASE M` — номер фазы внутри спринта
- Краткое описание — 3–7 слов

### 3.5. Labels для спринтов

Добавляется новый label `sprint-NNN` (например `sprint-007`) с цветом `#9333ea`.
Каждый Issue получает два label из семейства спринта/фазы:
- `sprint-007`
- `phase-2`

Плюс обычные labels: `frontend`/`backend`/`infra`, `bug`/`enhancement`/`optimization`.

### 3.6. Правила перехода между спринтами

| Ситуация | Правило |
|----------|---------|
| Новая крупная фича | Новый спринт (Sprint-008) |
| Баг из завершённого спринта | Новый Issue с label спринта-источника + label `bug` |
| Оптимизация существующего кода | Новый спринт, если работ на 2+ фазы; иначе отдельный Issue |
| Срочный хотфикс | Issue без спринта, label `hotfix` |
| Продолжение незавершённого спринта | Тот же номер, фазы продолжают нумерацию |

---

## 4. Блок `$START_LAST_UPDATE` (НОВОЕ в v4)

### 4.1. Назначение

В теле **каждого промпта фазы** размещается блок `$START_LAST_UPDATE`,
который фиксирует последнее изменение этого промпта. Цель:

- Трассируемость: видно, когда и в каком спринте промпт был изменён
- Навигация по истории: агент может перейти в `/SprintLog/Sprint-NNN-*.md`
  и посмотреть, что именно было изменено
- Контекст для регенерации: при доработке фичи агент понимает, в рамках
  какого спринта был зафиксирован текущий вариант промпта

### 4.2. Формат блока

Блок размещается **после `$START_KEYWORDS`**, **до `$START_GOAL`**:

```
$START_LAST_UPDATE
sprint_id: Sprint-007
phase_number: 2
date: 2026-04-18
author: AI (Claude Opus 4.6)
change_summary: Добавлен блок $START_PHASE0_ENRICHMENT по результатам анализа проекта. Обнаружены shared types в src/types/notification.ts, добавлена зависимость от middleware/auth.ts.
sprint_log_ref: /SprintLog/Sprint-007-notifications.md#phase-2
$END_LAST_UPDATE
```

### 4.3. Поля блока

| Поле | Тип | Описание |
|------|-----|----------|
| `sprint_id` | string | ID спринта, в котором было последнее изменение |
| `phase_number` | integer | Номер фазы внутри спринта |
| `date` | ISO 8601 date | Дата последнего изменения |
| `author` | string | AI (с указанием модели) или human (с именем) |
| `change_summary` | text | Краткое описание изменения (1–3 предложения) |
| `sprint_log_ref` | path | Ссылка на соответствующий раздел в SprintLog |

### 4.4. Когда обновлять

Блок `$START_LAST_UPDATE` **обязательно** обновляется при:

- Первой генерации промпта (при создании мастер-промпта)
- Обогащении в Фазе 0 (`$START_PHASE0_ENRICHMENT`)
- Любой ручной правке промпта оператором
- Переносе промпта в следующий спринт при доработке

**Правило:** менять нужно только блок `$START_LAST_UPDATE`, не модифицируя
остальное тело промпта (если изменение не затрагивает смысл фазы). Сами
смысловые правки идут через `$START_PHASE0_ENRICHMENT` или новый спринт.

### 4.5. Использование агентом

Claude Code при работе с промптом фазы:

1. Читает блок `$START_LAST_UPDATE`
2. Видит `sprint_id: Sprint-007` и `sprint_log_ref`
3. При необходимости ходит в `/SprintLog/Sprint-007-notifications.md`
4. Берёт оттуда контекст: что было сделано ранее, какие файлы затронуты,
   какие решения приняты
5. Использует этот контекст для более качественной генерации кода

---

## 5. Папка `/SprintLog/` (НОВОЕ в v4)

### 5.1. Назначение

`/SprintLog/` в корне проекта — это **долговременная память проекта**.
После завершения каждого спринта Claude Code записывает туда подробный
MD-файл с описанием всего, что было сделано.

Цель:
- В будущем Claude Code может ходить в эти логи
- Видеть в коде, что последнее изменение было в Sprint-NNN
- Переходить в соответствующий лог и смотреть детали
- Использовать эту информацию для улучшения своей работы

### 5.2. Структура папки

```
/SprintLog/
├── sprint-counter.json          # счётчик спринтов (см. 3.3)
├── Sprint-001-agent-catalog.md
├── Sprint-002-leaderboard.md
├── Sprint-003-notifications.md
├── ...
└── _index.md                    # сводный индекс всех спринтов
```

### 5.3. Шаблон файла `/SprintLog/Sprint-NNN-[name].md`

Claude Code **обязан** создавать файл строго по этому шаблону:

```markdown
# Sprint-007: Notifications System

## Метаданные

- **Sprint ID:** Sprint-007
- **Title:** Система уведомлений (in-app + email + Telegram)
- **Date Started:** 2026-04-18
- **Date Completed:** 2026-04-22
- **Status:** completed | in_progress | blocked | cancelled
- **Master Prompt:** /prompts/notifications-MASTER-INSTRUCTION.md
- **AppGraph Version:** AppGraph.xml v1.3
- **GitHub Project:** https://github.com/orgs/<owner>/projects/<N>
- **Related Issues:** #142, #143, #144, #145, #146

## Верхнеуровневое описание

Что было сделано в этом спринте (2–5 абзацев прозы):
- Какая бизнес-задача решалась
- Какой был подход (высокоуровнево)
- Какие архитектурные решения приняты
- Что осталось на следующие спринты

## Выполненные фазы

### Phase 0 — Анализ проекта и обогащение промптов

**Issue:** #142
**Status:** completed
**Commit(s):** abc1234 (audit(phase-0): enrich notifications prompts)

**Что сделано:**
- Просканированы N файлов в src/
- Обнаружены shared-зависимости: ...
- Обогащены промпты фаз 1–4 блоками $START_PHASE0_ENRICHMENT

**Ключевые находки:**
- ...

---

### Phase 1 — Модель данных Notification

**Issue:** #143
**Status:** completed
**Commit(s):** def5678 (feat(phase-1): add Notification and Preference models)

**Что сделано (верхнеуровнево):**
- Созданы две Prisma-модели: Notification, NotificationPreference
- Добавлены индексы по (userId, createdAt) и (userId, read)
- Мигарция применена, seed-данные добавлены

**Изменения в коде (было → стало):**

#### Создан: `prisma/schema.prisma`

Было: не содержал модели уведомлений.

Стало:
```prisma
model Notification {
  id        String   @id @default(cuid())
  userId    String
  type      NotificationType
  title     String
  body      String
  read      Boolean  @default(false)
  createdAt DateTime @default(now())
  user      User     @relation(fields: [userId], references: [id])

  @@index([userId, createdAt])
  @@index([userId, read])
}
```

#### Изменён: `src/types/notification.ts`

Было:
```typescript
// файл не существовал
```

Стало:
```typescript
export type NotificationType = 'info' | 'warning' | 'success' | 'error';
export interface NotificationDTO { ... }
```

**Затронутые модули AppGraph.xml:**
- NotificationDB (создан)

**Известные проблемы:**
- нет

---

### Phase 2 — API endpoints

[... аналогично Phase 1 ...]

### Phase 3 — UI компоненты

[... аналогично ...]

### Phase 4 — Настройки

[... аналогично ...]

## Сводный список файлов

### Созданные файлы (N)
- `prisma/schema.prisma` (модифицирован — добавлены модели)
- `src/types/notification.ts`
- `src/lib/notifications/email.service.ts`
- `src/lib/notifications/telegram.service.ts`
- `src/app/api/notifications/route.ts`
- `src/app/api/notifications/[id]/route.ts`
- `src/app/api/preferences/route.ts`
- `src/components/notifications/NotificationCenter.tsx`
- `src/components/notifications/NotificationItem.tsx`
- `src/components/notifications/PreferencesPanel.tsx`

### Изменённые файлы (M)
- `src/middleware.ts` — добавлена проверка для /api/notifications
- `src/components/layout/Header.tsx` — добавлена иконка колокольчика

### Удалённые файлы (K)
- нет

## Обновления AppGraph.xml

- Добавлены модули: NotificationDB, NotificationAPI, NotificationService, NotificationUI
- Добавлены data_flow: SendNotification, MarkAsRead, UpdatePreferences
- Добавлены external packages: nodemailer@6.9.x, node-telegram-bot-api@0.64.x

## Decision Log (архитектурные решения)

1. **Push vs Pull для real-time обновлений:**
   Выбран WebSocket (через Supabase Realtime). Альтернатива — SSE — отклонена
   из-за отсутствия двусторонней связи.

2. **Хранение preferences:**
   Выбрана отдельная таблица NotificationPreference, а не JSON-поле в User,
   чтобы упростить миграции и валидацию.

## Known Issues / Tech Debt

- Email-шаблоны захардкожены, нужна вынести в отдельный модуль (Sprint-008)
- Нет rate-limiting на API — отложено на инфра-спринт
- Telegram webhook работает только в production (нужен ngrok для локального тестирования)

## Ссылки

- **Master Instruction:** /prompts/notifications-MASTER-INSTRUCTION.md
- **AppGraph.xml:** /AppGraph.xml (v1.3)
- **PR:** https://github.com/<owner>/<repo>/pull/89
- **Design doc (если есть):** ...
```

### 5.4. Обязательные поля детальных изменений

Для **каждой фазы** Claude Code обязан зафиксировать:

1. **Issue / Commit refs** — связь с трекером
2. **Что сделано** (верхнеуровнево, 2–5 предложений)
3. **Изменения в коде** по формату **было → стало** для каждого файла:
   - Полный diff или ключевые фрагменты (если файл большой — критичные куски)
   - Если файл новый — указать «Было: файл не существовал», дать полный листинг или основные экспорты
   - Если файл удалён — указать «Стало: файл удалён», объяснить почему
4. **Затронутые модули AppGraph.xml** — какие `<module>` были добавлены/изменены
5. **Известные проблемы** — баги, tech debt, TODO

### 5.5. Индексный файл `/SprintLog/_index.md`

Сводная таблица всех спринтов (обновляется Claude Code при создании нового файла):

```markdown
# SprintLog Index

| Sprint | Title | Status | Date | Phases | Key Modules |
|--------|-------|--------|------|--------|-------------|
| Sprint-001 | Agent Catalog | ✅ completed | 2025-10-15 | 0–5 | AgentDB, AgentAPI, AgentUI |
| Sprint-002 | Leaderboard & Arena | ✅ completed | 2025-10-28 | 0–4 | ELO, BenchmarkDB, ArenaUI |
| Sprint-007 | Notifications | 🟡 in_progress | 2026-04-18 | 0–3 | NotificationDB, ... |
```

### 5.6. Когда Claude Code создаёт файл

- **В начале спринта:** создать скелет файла со статусом `in_progress`,
  заполнить метаданные из мастер-промпта
- **После каждой завершённой фазы:** дописать раздел фазы с изменениями
- **После завершения спринта:** поставить статус `completed`, заполнить
  Decision Log, Known Issues, обновить `_index.md` и `sprint-counter.json`

### 5.7. Правило для Claude Code: навигация через SprintLog

Когда Claude Code работает с промптом фазы и видит в теле:

```
$START_LAST_UPDATE
sprint_id: Sprint-005
sprint_log_ref: /SprintLog/Sprint-005-auth.md#phase-2
$END_LAST_UPDATE
```

Он **обязан**:
1. Прочитать `/SprintLog/Sprint-005-auth.md` целиком (или соответствующий раздел)
2. Учесть принятые там архитектурные решения
3. При необходимости сослаться на них в новом промпте

---

## 6. Шесть компонентов промпта-контракта

| # | Компонент | Что это | Маркер |
|---|-----------|---------|--------|
| 1 | PRIMING | Термины домена в первых строках | `$START_KEYWORDS` / `$END_KEYWORDS` |
| 2 | LAST UPDATE | Метаданные последнего изменения (НОВОЕ v4) | `$START_LAST_UPDATE` / `$END_LAST_UPDATE` |
| 3 | ЦЕЛЬ | 1–2 предложения: что получаем | `$START_GOAL` / `$END_GOAL` |
| 4 | ОГРАНИЧЕНИЯ | Что можно, что нельзя | `$START_CONSTRAINTS` / `$END_CONSTRAINTS` |
| 5 | ФОРМАТ | Структура вывода | `$START_FORMAT` / `$END_FORMAT` |
| 6 | КРИТЕРИИ | Как проверить результат | `$START_CRITERIA` / `$END_CRITERIA` |
| 7 | ПРИМЕРЫ | 1–2 образца | `$START_EXAMPLES` / `$END_EXAMPLES` |

Дополнительные маркеры: `$START_ROLE`, `$START_PRIMING`, `$START_STEPS`, `$START_TODO`, `$START_PHASE0_ENRICHMENT`.

---

## 7. Superposition → Collapse

Финальный код **никогда** не генерируется сразу:

1. **PROPOSE** — 2–3 варианта решения без выбора
2. **HOLD** — развить каждый (плюсы, минусы, ограничения)
3. **COLLAPSE** — оценить по критериям, выбрать, обосновать

Планирование и исполнение — всегда в разных фазах.

---

## 8. Двухфайловый вывод (MD + XML)

### 8.1. MD-файл: мастер-инструкция

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

### 8.2. XML-файл: навигационный граф (AppGraph.xml)

Структура:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project name="..." version="..." root="..." sprint="Sprint-NNN">

  <!-- Для каждого модуля (слоя): -->
  <module name="..." layer="data|backend|frontend" phase="N" sprint="Sprint-NNN">

    <!-- Модели данных (если layer=data): -->
    <model name="...">
      <field name="..." type="..." primary="true|false" required="true|false"
             foreign_key="Model.field" indexed="true|false"/>
      <relation type="one-to-many|many-to-one|many-to-many"
                target="..." through="..." field="..."/>
    </model>
    <index model="..." fields="..." comment="..."/>

    <!-- Файлы с экспортами (если layer=backend|frontend): -->
    <file path="..." last_modified_sprint="Sprint-NNN">
      <export name="..." type="route_handler|component|hook|const|function"
              params="..." returns="..." description="..."/>
      <dependency component="..." endpoint="..." external="..."/>
    </file>

    <dependency from="..." to="..." type="..." via="..."/>
  </module>

  <!-- Межмодульные зависимости: -->
  <dependencies>
    <dependency from="Module" to="Module" comment="..."/>
    <phase_order>
      <phase number="N" module="..." blocks="..."/>
    </phase_order>
  </dependencies>

  <!-- Data flows (сценарии): -->
  <data_flow name="..." sprint="Sprint-NNN">
    <step order="N" actor="..." action="..."
          endpoint="..." component="..." trigger="..."
          optimistic="true|false" navigate="..." response="..."
          description="..." comment="..."/>
  </data_flow>

  <!-- Внешние зависимости: -->
  <externals>
    <package name="..." version="..." purpose="..." added_in_sprint="Sprint-NNN"/>
    <resource name="..." path="..." purpose="..."/>
  </externals>

  <!-- Design tokens (если есть): -->
  <design_tokens name="...">
    <token name="..." value="..." description="..."/>
  </design_tokens>

  <!-- История спринтов (НОВОЕ v4): -->
  <sprint_history>
    <sprint id="Sprint-001" title="..." status="completed" date="..."/>
    <sprint id="Sprint-007" title="..." status="in_progress" date="..."/>
  </sprint_history>

</project>
```

**Правила заполнения XML:**
- Каждый `<module>` привязан к фазе через `phase="N"` и к спринту через `sprint="Sprint-NNN"` (НОВОЕ v4)
- Каждый `<file>` содержит реальный путь и `last_modified_sprint` (НОВОЕ v4)
- `<export>` описывает публичный API файла: имя, тип, параметры, возвращаемое значение
- `<dependency>` между модулями показывает, кто от кого зависит
- `<data_flow>` описывает end-to-end сценарий по шагам (actor → action → endpoint)
- `<phase_order>` определяет порядок выполнения и блокирующие зависимости
- `<design_tokens>` — цвета, размеры, шрифты для UI-фаз
- `<sprint_history>` — добавляется каждый новый спринт (НОВОЕ v4)
- **Обновлять по мере работы** — добавлять файлы, менять status, обновлять `last_modified_sprint`

---

## 9. Фаза 0: анализ проекта и обогащение промптов

### 9.1. Суть

Фаза 0 — это **обязательный подготовительный этап**, который выполняется
**ПОСЛЕ** создания мастер-инструкции (MD + XML), но **ДО** создания
Issues в GitHub Project.

Цель Фазы 0: агент (Claude Opus 4.6) полностью анализирует существующий
проект и обогащает промпты фаз дополнительными связями и контекстом,
которые повышают качество выполнения каждой последующей фазы.

**НОВОЕ в v4:** Фаза 0 также читает `/SprintLog/` и учитывает контекст
прошлых спринтов.

### 9.2. Порядок выполнения (pipeline)

```
┌─────────────────────────────────────────────────────┐
│  ЭТАП A: Генерация MD + XML (человек + AI)          │
│  → Получить Sprint-NNN из sprint-counter.json       │
│  → Создать мастер-инструкцию с промптами фаз        │
│  → Создать AppGraph.xml                             │
│  → Заполнить $START_LAST_UPDATE в каждом промпте    │
│  → Issues в GitHub НЕ создаются                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ЭТАП B: Оператор отправляет «Фаза 0»              │
│  → AI запускает полный анализ проекта               │
│  → AI читает /SprintLog/_index.md и последние 3     │
│     спринта                                         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ЭТАП C: AI анализирует + обогащает промпты         │
│  → Читает файловую систему проекта                  │
│  → Сопоставляет с AppGraph.xml                      │
│  → Читает /SprintLog/ для контекста                 │
│  → Находит недостающие связи, зависимости, файлы    │
│  → ДОПОЛНЯЕТ (не удаляет!) промпты фаз              │
│  → Обновляет $START_LAST_UPDATE в каждом промпте    │
│  → Записывает журнал в Секцию 7                     │
│  → Создаёт скелет /SprintLog/Sprint-NNN-*.md        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ЭТАП D: Оператор ревьюит обогащённые промпты       │
│  → Человек проверяет дополнения                     │
│  → Утверждает или корректирует                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ЭТАП E: Создание Issues в GitHub Project           │
│  → Для каждой обогащённой фазы — отдельный Issue    │
│  → Title: [Sprint-NNN][PHASE M] ...                 │
│  → Labels: sprint-NNN + phase-M + frontend/backend  │
│  → Body Issue = полный промпт фазы (обогащённый)    │
│  → Все Issues → Backlog, затем Ready                │
└─────────────────────────────────────────────────────┘
```

### 9.3. Промпт Фазы 0 (шаблон для вставки в секцию 5)

```
$START_KEYWORDS
project-analysis, file-system-scan, dependency-graph, cross-module-relations,
prompt-enrichment, context-injection, AppGraph.xml, code-audit, sprint-log
$END_KEYWORDS

$START_LAST_UPDATE
sprint_id: Sprint-NNN
phase_number: 0
date: YYYY-MM-DD
author: AI (Claude Opus 4.6) — generator
change_summary: Первичная генерация промпта Фазы 0 при создании мастер-инструкции спринта.
sprint_log_ref: /SprintLog/Sprint-NNN-[name].md#phase-0
$END_LAST_UPDATE

$START_GOAL
Не спеши с выводами, т.к. можешь свалится в локальный оптимум и выбрать не самое оптимальное решение. Используй что-то вроде суперпозиции смыслов с разными гипотезами, коллапс в конкретный вариант сделаем по моей команде. Сначала изучи граф на приложение.

Цель: выполнить полный анализ текущего состояния проекта, прочитать
историю прошлых спринтов из /SprintLog/, сопоставить с AppGraph.xml
и обогатить промпты всех фаз (1..N) дополнительными связями,
зависимостями и контекстом, которые позволят максимально улучшить
выполнение каждой фазы.
$END_GOAL

$START_ROLE
Ты — старший архитектор-аудитор. Твоя задача — изучить проект как
forensic-аналитик: каждый файл, каждый импорт, каждую зависимость,
каждый лог прошлого спринта. Затем — обогатить промпты фаз,
НЕ УДАЛЯЯ ни одного слова из оригинальных промптов, а только
ДОПОЛНЯЯ их (за исключением блока $START_LAST_UPDATE — его
обновляешь обязательно).
$END_ROLE

$START_CONSTRAINTS
- НЕ УДАЛЯТЬ и НЕ МОДИФИЦИРОВАТЬ существующий текст промптов фаз
  (ЕДИНСТВЕННОЕ ИСКЛЮЧЕНИЕ: блок $START_LAST_UPDATE обновляется)
- Только ДОПОЛНЯТЬ: добавлять блоки после существующего текста
- Все дополнения оборачивать в маркер:
  $START_PHASE0_ENRICHMENT
  [дополнения]
  $END_PHASE0_ENRICHMENT
- Не генерировать код — только анализ и дополнения к промптам
- Если обнаружено противоречие между промптом и реальностью проекта —
  зафиксировать в журнале (Секция 7), не исправлять молча
- После анализа прошлых спринтов — учесть принятые там решения
  в дополнениях
- Создать скелет /SprintLog/Sprint-NNN-[name].md со статусом in_progress
$END_CONSTRAINTS

$START_STEPS
STEP 1: SPRINT HISTORY — Чтение истории проекта
  - cat /SprintLog/sprint-counter.json
  - cat /SprintLog/_index.md
  - Прочитать последние 3 завершённых спринта целиком
  - Зафиксировать принятые архитектурные решения

STEP 2: SCAN — Полный скан файловой системы проекта
  - ls -la $PROJECT_ROOT
  - find $PROJECT_ROOT -type f -name "*.ts" -o -name "*.tsx" -o -name "*.prisma" | head -200
  - cat $PROJECT_ROOT/package.json
  - cat $PROJECT_ROOT/prisma/schema.prisma (если есть)
  - cat $PROJECT_ROOT/tsconfig.json
  - Построить карту: файл → экспорты → импорты → зависимости

STEP 3: COMPARE — Сопоставление с AppGraph.xml
  - Для каждого <module> в XML: существует ли он в проекте?
  - Для каждого <file> в XML: существует ли файл? Совпадают ли экспорты?
  - Проверить last_modified_sprint каждого файла — нет ли конфликтов
  - Для каждого <data_flow>: прослеживается ли цепочка в коде?
  - Зафиксировать расхождения: [MISSING], [CHANGED], [NEW]

STEP 4: DISCOVER — Обнаружение неучтённых связей
  - Найти импорты, которых нет в графе зависимостей
  - Найти shared-утилиты и хуки, используемые в нескольких модулях
  - Найти env-переменные и конфиги, влияющие на фазы
  - Найти middleware, HOC, провайдеры, обёртки — неявные зависимости
  - Найти типы и интерфейсы, расшаренные между модулями
  - Сопоставить с решениями из прошлых спринтов

STEP 5: ENRICH — Обогащение промптов фаз
  Для каждой фазы (1..N):
  a) Определить, какие обнаруженные связи относятся к этой фазе
  b) Сформировать блок $START_PHASE0_ENRICHMENT с:
     - Дополнительные файлы, которые нужно учитывать
     - Дополнительные зависимости (imports, shared types)
     - Существующие компоненты/функции для переиспользования
     - Env-переменные и конфиги
     - Потенциальные конфликты с другими фазами
     - Рекомендации по порядку реализации внутри фазы
     - Ссылки на решения из прошлых спринтов (если применимы)
  c) Добавить блок в конец промпта фазы (после $END_STEPS,
     но до закрывающего code block)
  d) Обновить $START_LAST_UPDATE с change_summary:
     "Обогащено по результатам Фазы 0 спринта Sprint-NNN"

STEP 6: UPDATE GRAPH — Обновление AppGraph.xml
  - Добавить обнаруженные модули, файлы, экспорты
  - Для обнаруженных существующих файлов — заполнить last_modified_sprint
  - Добавить обнаруженные зависимости
  - Обновить <data_flow> если найдены новые шаги
  - Добавить запись в <sprint_history> о текущем спринте
  - НЕ УДАЛЯТЬ запланированные (ещё не созданные) элементы

STEP 7: SPRINTLOG INIT — Создание скелета лога спринта
  - Создать /SprintLog/Sprint-NNN-[name].md со статусом in_progress
  - Заполнить метаданные (Sprint ID, Title, Date Started, Master Prompt)
  - Добавить заголовки всех фаз (пустые, будут заполнены позже)
  - Обновить /SprintLog/_index.md (добавить строку о текущем спринте)

STEP 8: LOG — Запись журнала в Секцию 7
  - Список всех обнаруженных расхождений
  - Список всех дополнений по каждой фазе
  - Список обновлений AppGraph.xml
  - Выписка принятых решений из прошлых спринтов (релевантных)
  - Рекомендации и предупреждения
$END_STEPS

$START_FORMAT
Результат Фазы 0:
1. Обновлённый MD-файл с обогащёнными промптами (блоки $START_PHASE0_ENRICHMENT)
2. Обновлённые $START_LAST_UPDATE во всех промптах фаз
3. Обновлённый AppGraph.xml (новые модули, файлы, зависимости, sprint_history)
4. Заполненная Секция 7 (журнал анализа)
5. Созданный скелет /SprintLog/Sprint-NNN-[name].md
6. Обновлённый /SprintLog/_index.md
$END_FORMAT

$START_CRITERIA
- Каждый промпт фаз (1..N) содержит блок $START_PHASE0_ENRICHMENT
- Каждый $START_LAST_UPDATE обновлён с учётом Фазы 0
- Ни одно слово оригинальных промптов не удалено и не изменено
  (кроме блока $START_LAST_UPDATE — он обновляется)
- AppGraph.xml обновлён обнаруженными связями и записью sprint_history
- Секция 7 содержит полный журнал с расхождениями и дополнениями
- Все обнаруженные противоречия зафиксированы явно
- /SprintLog/Sprint-NNN-[name].md создан со статусом in_progress
- /SprintLog/_index.md обновлён
$END_CRITERIA

$START_EXAMPLES
Пример дополнения к Фазе 3 (UI компоненты):

  $START_PHASE0_ENRICHMENT
  ## Дополнения Фазы 0 (автоанализ проекта, Sprint-007)

  ### Обнаруженные зависимости:
  - src/hooks/useDebounce.ts — переиспользовать для поиска
    (уже используется в AgentArena, создан в Sprint-002)
  - src/components/ui/AnimatedCard.tsx — базовый компонент
    для карточек, не создавать заново (Sprint-001)
  - src/lib/api/fetcher.ts — единый fetcher с interceptors,
    использовать вместо прямого fetch (Sprint-003)

  ### Shared Types:
  - src/types/notification.ts: NotificationType, NotificationDTO
  - src/types/common.ts: PaginatedResponse<T>, ApiError (Sprint-001)

  ### Env-переменные:
  - NEXT_PUBLIC_API_URL — базовый URL API
  - NEXT_PUBLIC_WS_URL — WebSocket для real-time обновлений

  ### Потенциальные конфликты:
  - Фаза 2 создаёт middleware auth.ts — Фаза 3 зависит от него,
    убедиться что auth middleware готов перед началом Фазы 3

  ### Решения из прошлых спринтов:
  - Sprint-003 (Auth): все API-роуты защищены через middleware,
    используется withAuth HOC — применить аналогично к /api/notifications
  - Sprint-005 (UI Redesign): принят паттерн compound components
    для сложных UI-блоков — использовать для NotificationCenter

  ### Рекомендации:
  - Начать с компонентов, которые не зависят от API (чистый UI)
  - Затем подключить API через существующий fetcher
  $END_PHASE0_ENRICHMENT
$END_EXAMPLES
```

### 9.4. Правило для секции 3 (GitHub Workflow)

В секцию 3 мастер-инструкции **обязательно** включить предупреждение:

```
⚠️ ВАЖНО: НЕ СОЗДАВАТЬ Issues в GitHub Project до завершения Фазы 0.

Порядок действий:
1. Настроить gh auth, labels, project — ДА
2. Создать label sprint-NNN для текущего спринта — ДА
3. Создать Issues для фаз — НЕТ, ЖДАТЬ
4. Получить команду «Фаза 0» от оператора
5. Выполнить анализ проекта (Фаза 0)
6. Обогатить промпты фаз
7. Создать скелет /SprintLog/Sprint-NNN-[name].md
8. Получить подтверждение от оператора
9. ТОЛЬКО ТЕПЕРЬ: создать Issues для каждой обогащённой фазы
   с title [Sprint-NNN][PHASE M] ...
```

### 9.5. Создание Issues после Фазы 0

После завершения Фазы 0 и подтверждения оператора, для каждой фазы:

```bash
# Для каждой фазы (1..N) — Issue с обогащённым промптом
gh issue create \
  --title "[Sprint-007][PHASE 2] API endpoints уведомлений" \
  --body "$(cat enriched-phase-2-prompt.md)" \
  --label "sprint-007,phase-2,backend"

# Добавить в GitHub Project
gh project item-add PROJECT_NUMBER --owner OWNER --url ISSUE_URL

# Перевести в Ready (промпт обогащён → Issue готов к работе)
```

**Формат body Issue:**
- Полный текст промпта фазы из секции 5
- Включая блок `$START_LAST_UPDATE`
- Включая блок `$START_PHASE0_ENRICHMENT`
- Включая anti-hallucination директиву в `$START_GOAL`

---

## 10. Post-Фаза 0 опрос оператора (НОВОЕ в v4.1)

### 10.1. Назначение

После завершения Фазы 0 и ДО создания Issues в GitHub Project
агент (Claude Opus 4.6) **обязан** провести короткий интерактивный
опрос оператора. Цель — получить 4 параметра размещения, без
которых дальнейшая работа невозможна:

1. **GitHub repository** для коммитов кода
2. **GitHub Project** для задач разработки (dev)
3. **GitHub Project** для задач дизайна (design)
4. **Директория** внутри репозитория для SprintLog

Это предотвращает ситуации, когда Issues создаются не в том Project,
код коммитится не в тот репозиторий, а SprintLog уходит мимо места,
где Claude Code будет его потом искать.

### 10.2. Когда задавать вопросы

В строгой точке pipeline:

```
Фаза 0 завершена
    ↓
Промпты обогащены ($START_PHASE0_ENRICHMENT)
    ↓
AppGraph.xml обновлён
    ↓
Скелет /SprintLog/Sprint-NNN-[name].md создан
    ↓
👉 ВОТ ЗДЕСЬ: агент задаёт 4 вопроса оператору
    ↓
Получены и зафиксированы ответы
    ↓
Создание label sprint-NNN и Issues в выбранных Projects
```

**Правило:** без всех 4 ответов агент **не имеет права** выполнять
`gh issue create` или `gh project item-add`. Если оператор не ответил
на один из вопросов — переспросить, не додумывать.

### 10.3. Точные формулировки вопросов

Агент задаёт вопросы **одним сообщением**, пронумерованными,
с предложенными вариантами по умолчанию (если есть):

```
Фаза 0 завершена. Перед созданием Issues в GitHub Project
мне нужно уточнить 4 параметра размещения для Sprint-NNN:

1. В какой GitHub repository коммитить код этого спринта?
   Формат: owner/repo (например, <owner>/<repo>)
   [default: тот же репозиторий, где лежит мастер-инструкция]

2. В какой GitHub Project грузить задачи по разработке (dev)?
   Формат: owner/project-number или URL проекта
   (например, <owner>/<N> или https://github.com/orgs/<owner>/projects/<N>)

3. В какой GitHub Project грузить задачи по дизайну (design)?
   Формат: owner/project-number или URL проекта
   Если отдельного design-проекта нет — напиши "none" или
   укажи тот же project, что и для dev

4. В какую директорию внутри репозитория грузить описание
   спринта и лог изменений (Sprint-NNN-[name].md)?
   [default: /SprintLog/]

После твоих ответов я:
- создам label sprint-NNN в указанном репозитории
- создам Issues для фаз разработки в dev-project
- создам Issues для фаз дизайна в design-project (если указан)
- размещу SprintLog в указанной директории
- зафиксирую все параметры в Секции 0 мастер-инструкции
```

### 10.4. Правила разделения задач dev vs design

Агент определяет, какие фазы относятся к dev, а какие к design,
по содержимому промпта фазы:

| Признак | Куда Issue |
|---------|-----------|
| Фаза работает с кодом (TS/TSX, Prisma, API) | dev-project |
| Фаза работает с UI-компонентами (реализация) | dev-project |
| Фаза описывает макеты, wireframes, design tokens, UX | design-project |
| Фаза смешанная (design + реализация) | два Issue: один в dev, один в design, связанные через `Related to #N` |
| Фаза 0 (анализ) | dev-project |

Если design-project = "none" — все фазы идут в dev-project, но с
label `design` у тех, что содержат дизайн-работу.

### 10.5. Фиксация ответов

После получения ответов агент обязан:

**А. Обновить Секцию 0 мастер-инструкции** — добавить блок:

```markdown
## Секция 0: Метаданные спринта

- **Sprint ID:** Sprint-007
- **Sprint Title:** Система уведомлений
- **Date Created:** 2026-04-18

### Места размещения (заполнено после Фазы 0)

- **Code Repository:** <owner>/<repo>
- **Dev Project:** <owner>/<N> (https://github.com/orgs/<owner>/projects/<N>)
- **Design Project:** <owner>/<M> (https://github.com/orgs/<owner>/projects/<M>)
- **SprintLog Directory:** /SprintLog/
- **Sprint Log File:** /SprintLog/Sprint-007-notifications.md
- **Operator:** [имя оператора из ответа или пусто]
- **Answered At:** 2026-04-18 14:32
```

**Б. Обновить метаданные в `/SprintLog/Sprint-NNN-[name].md`:**

```markdown
## Метаданные

- **Sprint ID:** Sprint-007
- **Code Repository:** <owner>/<repo>
- **Dev Project:** https://github.com/orgs/<owner>/projects/<N>
- **Design Project:** https://github.com/orgs/<owner>/projects/<M>
- **SprintLog Directory:** /SprintLog/
...
```

**В. Обновить `/SprintLog/sprint-counter.json`** — добавить места
размещения в запись спринта:

```json
{
  "sprints": [
    {
      "id": "Sprint-007",
      "title": "Notifications System",
      "status": "in_progress",
      "date": "2026-04-18",
      "placement": {
        "code_repo": "<owner>/<repo>",
        "dev_project": "<owner>/<N>",
        "design_project": "<owner>/<M>",
        "sprintlog_dir": "/SprintLog/"
      }
    }
  ]
}
```

### 10.6. Значения по умолчанию

Если оператор отвечает «по умолчанию» / «как обычно» / пропускает вопрос:

| Вопрос | Default |
|--------|---------|
| Code Repository | Репозиторий, в котором находится мастер-инструкция (определяется через `git remote get-url origin`) |
| Dev Project | Последний использованный dev-project из `sprint-counter.json` (поле `placement.dev_project` последнего спринта) |
| Design Project | `none` (все фазы в dev-project с label `design`) |
| SprintLog Directory | `/SprintLog/` (в корне репозитория) |

Агент **обязан** явно указать, какие default-ы он применил:

```
Применены значения по умолчанию:
- Code Repository: <owner>/<repo> (из git remote)
- Dev Project: <owner>/<N> (последний из sprint-counter.json)
- Design Project: none (все задачи в dev-project с label design)
- SprintLog Directory: /SprintLog/
```

### 10.7. Команды после получения ответов

```bash
# 1. Установить текущий репозиторий
gh repo set-default <owner>/<repo>

# 2. Создать label sprint-NNN в code-repo
gh label create "sprint-007" --color "9333ea" \
  --description "Sprint 007: Notifications" \
  --repo <owner>/<repo>

# 3. Создать dev-Issues в dev-project
gh issue create \
  --repo <owner>/<repo> \
  --title "[Sprint-007][PHASE 2] API endpoints уведомлений" \
  --body "$(cat enriched-phase-2.md)" \
  --label "sprint-007,phase-2,backend"

gh project item-add 3 --owner <owner> --url ISSUE_URL

# 4. Создать design-Issues в design-project (если указан)
gh issue create \
  --repo <owner>/<repo> \
  --title "[Sprint-007][PHASE 3-DESIGN] Макеты NotificationCenter" \
  --body "$(cat enriched-phase-3-design.md)" \
  --label "sprint-007,phase-3,design,frontend"

gh project item-add 5 --owner <owner> --url ISSUE_URL

# 5. Переместить SprintLog в указанную директорию (если не /SprintLog/)
# (скрипт агента копирует файл в нужное место)
```

### 10.8. Интеграция в промпт Фазы 0

В промпте Фазы 0 (секция 5 мастер-инструкции) — добавить
новый STEP 9 после STEP 8 (LOG):

```
STEP 9: OPERATOR QUERY — Опрос оператора о местах размещения
  После завершения анализа и заполнения журнала задать
  оператору 4 вопроса (см. Секцию 10 фреймворка):
  1. GitHub repository для кода
  2. GitHub Project для задач разработки
  3. GitHub Project для задач дизайна
  4. Директория для SprintLog

  НЕ СОЗДАВАТЬ Issues до получения ответов.
  Зафиксировать ответы в:
  - Секции 0 мастер-инструкции
  - Метаданных /SprintLog/Sprint-NNN-[name].md
  - /SprintLog/sprint-counter.json (поле placement)
```

### 10.9. Что если оператор меняет ответы в середине спринта

Сценарий: спринт идёт, несколько фаз завершены, оператор решает
перенести оставшиеся задачи в другой Project.

Правило:
1. Оператор явно командует «Смени dev-project на X»
2. Агент **не переносит** существующие Issues (оставляет их на месте)
3. Создаёт **новые** Issues для ещё не стартовавших фаз в новом Project
4. Обновляет Секцию 0 мастер-инструкции: добавляет историю изменений
   размещения, не удаляя старые значения:

```markdown
### Места размещения

- **Dev Project:** <owner>/<K> (с Phase 4)
  - Previous: <owner>/<N> (Phase 0–3) — changed 2026-04-21 by operator
```

5. Обновляет `sprint-counter.json` — добавляет массив `placement_history`

---

## 11. End-of-Sprint Design System Snapshot (НОВОЕ в v4.2)

### 11.1. Назначение

Перед закрытием спринта и финальным логированием — **обязательный этап**:
обновление дизайн-системы проекта. Все UI-компоненты, которые были
изменены или добавлены в рамках фаз спринта, фиксируются в дизайн-системе
через специализированные скиллы.

Логика: когда все задачи мастер-промпта выполнены, агент проверяет
изменённые компоненты, прогоняет их через скиллы обновления дизайн-системы,
и только **после этого** логирует завершение спринта.

Снапшот — это **сознательное действие оператора в момент завершения**,
а не автоматический хук. Каждый снапшот = одна версия финализированного
состояния UI.

### 11.2. Три скилла и их роли

Скиллы расположены в `~/.claude/skills/`:

| Скилл | Путь | Когда вызывать |
|-------|------|----------------|
| `design-system-update` | `~/.claude/skills/design-system-update/SKILL.md` | **Основной** — полный цикл обновления в конце спринта |
| `design-system-verify` | `~/.claude/skills/design-system-verify/SKILL.md` | Аудит: проверить, что дизайн-система в sync с `src/` без внесения изменений |
| `design-system-archive` | `~/.claude/skills/design-system-archive/SKILL.md` | Только архивация текущего состояния перед рефакторингом, без регенерации |

**Основной скилл** `design-system-update` выполняет 5-step cycle:
1. **Discovery** — найти все компоненты, изменённые в рамках спринта
2. **Generation** — сгенерировать обновлённые описания/превью
3. **Archive** — заархивировать предыдущую версию дизайн-системы
4. **Sync** — синхронизировать с проектом
5. **Output Contract** — зафиксировать output (showcase, version)

Подробности работы скилла — в `$INSTRUMENTS/design-components/PROTOCOL.md`.

### 11.3. Когда вызывать — триггеры и запреты

**✅ Вызывать, когда оператор явно подтвердил закрытие спринта:**

Принимаемые формулировки (любая из них):
- «готово»
- «финал»
- «завершили спринт»
- «sprint done»
- «close sprint»
- «ship it»

**❌ НЕ вызывать:**
- Во время активной разработки фичи
- При mid-iteration UI tweaks (промежуточных правках)
- При проваленных тестах
- При неразрешённых багах
- В любом состоянии, которое оператор **явно не отметил** как финализированное

**⚠️ Если есть сомнения — спросить оператора.** Снапшот наполовину
завершённого состояния засоряет архив и обесценивает весь этап.

### 11.4. Точка в pipeline

```
Все фазы спринта completed
    ↓
Все тесты прошли
    ↓
Всё смержено в main
    ↓
👉 ВОТ ЗДЕСЬ: агент ждёт явное подтверждение оператора
    ↓
Оператор: «готово» / «close sprint» / «ship it»
    ↓
👉 End-of-Sprint Design System Snapshot
    Вызов design-system-update
    Отчёт оператору: версия, компоненты, пути
    ↓
Финальное логирование спринта
    Статус в SprintLog → completed
    Обновление _index.md и sprint-counter.json
    Commit: sprintlog(sprint-NNN): close sprint
```

### 11.5. Отчёт после вызова скилла

После успешного выполнения `design-system-update` агент **обязан**
предоставить оператору отчёт по шаблону:

```markdown
## Design System Snapshot для Sprint-NNN

- **Новая версия:** v7 (предыдущая: v6)
- **Дата снапшота:** 2026-04-22

### Компоненты

**Добавлены:**
- NotificationCenter.tsx
- NotificationItem.tsx
- NotificationBadge.tsx

**Изменены:**
- Header.tsx (добавлена иконка колокольчика)
- UserMenu.tsx (новый пункт "Notification Preferences")

**Удалены:**
- (нет)

### Артефакты

- Showcase: `/design-system/v7/components-showcase.html`
- Архив v6: `/design-system/archive/v6-2026-04-18/`
- Protocol log: `/design-system/v7/update.log`
```

Этот отчёт **дословно** копируется в раздел "Design System Snapshot"
в `/SprintLog/Sprint-NNN-[name].md` (см. 11.6).

### 11.6. Раздел в SprintLog

В шаблон `/SprintLog/Sprint-NNN-[name].md` (см. секцию 5 фреймворка)
добавляется новый раздел **перед** "Known Issues / Tech Debt":

```markdown
## Design System Snapshot

- **Sprint:** Sprint-007
- **Version:** v7 (предыдущая v6)
- **Date:** 2026-04-22
- **Skill Used:** design-system-update
- **Triggered By:** оператор, сигнал "close sprint"

### Components Added (N)
- `NotificationCenter.tsx` — корневой компонент панели уведомлений
- `NotificationItem.tsx` — элемент списка
- `NotificationBadge.tsx` — значок с счётчиком

### Components Modified (M)
- `Header.tsx` — интеграция иконки колокольчика
- `UserMenu.tsx` — пункт Notification Preferences

### Components Removed (K)
- (нет)

### Artifacts
- Showcase: `/design-system/v7/components-showcase.html`
- Previous version archive: `/design-system/archive/v6-2026-04-18/`
- Update log: `/design-system/v7/update.log`

### Verification
- [ ] Прогнан `design-system-verify` после обновления — ✅ sync
```

### 11.7. Сценарии вызова альтернативных скиллов

**Сценарий A: Pre-refactor safety snapshot (не полный апдейт).**
Используется перед крупным рефакторингом, чтобы зафиксировать текущее
состояние. НЕ регенерирует, только архивирует.

```
Оператор: «сделай архив дизайн-системы перед рефакторингом Button»
Агент: → вызывает design-system-archive
Агент: → отчитывается путём к созданному архиву
```

**Сценарий B: Audit — проверить sync без изменений.**
Проверяет, что дизайн-система соответствует `src/` — ничего не переписывает,
только возвращает diff. Можно вызывать в любой момент.

```
Оператор: «проверь, дизайн-система в порядке?»
Агент: → вызывает design-system-verify
Агент: → возвращает список расхождений (или "in sync")
```

**Сценарий C: Full update (основной).**
Только при закрытии спринта с явным подтверждением оператора.

```
Оператор: «close sprint» / «готово»
Агент: → вызывает design-system-update
Агент: → отчитывается по шаблону (11.5)
Агент: → обновляет SprintLog (11.6)
Агент: → только после этого закрывает спринт
```

### 11.8. Снипет для вставки в мастер-промпт

В **каждый мастер-промпт** (в Секцию 5, после последней фазы, перед
финальной частью закрытия спринта) — вставить следующий снипет **дословно**:

````markdown
## END-OF-SPRINT PROTOCOL — Design System Snapshot

**Trigger:** after the user has explicitly confirmed that all UI work
in this sprint is finalized.
Accept any of: "готово", "финал", "завершили спринт", "sprint done",
"close sprint", "ship it".

**Action:**
1. Invoke the skill `design-system-update` (it will load
   `$INSTRUMENTS/design-components/PROTOCOL.md`
   and run the full 5-step cycle: Discovery → Generation → Archive →
   Sync → Output Contract).
2. Report back to the user:
   - version number assigned (e.g. `v7`)
   - list of components added/modified/removed vs previous snapshot
   - path to the new `components-showcase.html`
   - path to the archive folder for the previous version
3. Append the report to `/SprintLog/Sprint-NNN-[name].md` as section
   "Design System Snapshot".

**DO NOT invoke during:**
- active feature development or mid-iteration UI tweaks
- failed test runs or unresolved bugs
- any state the user has not explicitly marked as "finalized"

**If unsure whether the sprint is truly closed — ask the user first.**
Snapshotting a half-finished state pollutes the archive and defeats
the purpose of the phase.

**For pre-refactor safety snapshots** (not full updates): use
`design-system-archive` skill — it only archives the current state
without regenerating.

**For audits** (check that the design-system is still in sync with
`src/` without rewriting anything): use `design-system-verify` skill.

**Only after a successful Design System Snapshot** proceed to the
final sprint closure:
- mark Sprint-NNN status = completed in SprintLog
- update /SprintLog/_index.md
- update /SprintLog/sprint-counter.json
- commit: `sprintlog(sprint-NNN): close sprint`
````

### 11.9. Фаза в промптах — "Design System Update"

Рекомендуется оформлять этот этап как **отдельную финальную фазу**
в секции 5 мастер-промпта (после всех функциональных фаз, перед
закрытием спринта). Пример шапки промпта:

```
$START_KEYWORDS
design-system, component-snapshot, skill-invocation, showcase,
archive, verify, end-of-sprint, ui-components
$END_KEYWORDS

$START_LAST_UPDATE
sprint_id: Sprint-NNN
phase_number: LAST+1 (например, phase_number: 5 если основных фаз было 4)
date: YYYY-MM-DD
author: AI (Claude Opus 4.6) — generator
change_summary: Первичная генерация промпта Design System Snapshot.
sprint_log_ref: /SprintLog/Sprint-NNN-[name].md#design-system-snapshot
$END_LAST_UPDATE

$START_GOAL
Не спеши с выводами, т.к. можешь свалится в локальный оптимум и выбрать
не самое оптимальное решение. Используй что-то вроде суперпозиции
смыслов с разными гипотезами, коллапс в конкретный вариант сделаем
по моей команде. Сначала изучи граф на приложение.

Цель: обновить дизайн-систему проекта всеми UI-компонентами,
изменёнными в рамках текущего спринта, через вызов скилла
design-system-update. Зафиксировать результат в SprintLog.
$END_GOAL

$START_ROLE
Ты — хранитель дизайн-системы. Твоя задача — после полного завершения
всех функциональных фаз спринта и явного подтверждения оператора
(«close sprint») прогнать изменённые компоненты через скилл
design-system-update, составить отчёт, обновить SprintLog.
$END_ROLE

$START_CONSTRAINTS
- Вызывать design-system-update ТОЛЬКО после явного подтверждения
  оператора одним из сигналов: "готово", "финал", "sprint done",
  "close sprint", "ship it"
- Не вызывать при failed tests, mid-iteration, активной разработке
- При сомнениях — переспросить оператора
- После вызова — обязательный отчёт оператору по шаблону (11.5)
- После отчёта — обязательное обновление SprintLog (11.6)
- Использовать design-system-verify / design-system-archive вместо
  update ТОЛЬКО по явной команде оператора (audit / pre-refactor)
$END_CONSTRAINTS

$START_STEPS
STEP 1: WAIT — Дождаться явного подтверждения оператора
STEP 2: PRE-CHECK — Проверить, что все тесты прошли, всё смержено в main
STEP 3: DISCOVER — Определить изменённые/добавленные UI-компоненты
        из SprintLog (разделы "Созданные файлы" и "Изменённые файлы")
STEP 4: INVOKE — Вызвать скилл design-system-update
        (путь: ~/.claude/skills/design-system-update/SKILL.md)
STEP 5: VERIFY — После update опционально вызвать design-system-verify
        для подтверждения sync
STEP 6: REPORT — Составить отчёт оператору (шаблон 11.5)
STEP 7: LOG — Дописать раздел "Design System Snapshot" в SprintLog
        (шаблон 11.6)
STEP 8: COMMIT — feat(sprint-NNN/design-system): snapshot v_N
STEP 9: PROCEED — Передать управление финальному закрытию спринта
$END_STEPS

$START_FORMAT
Результат:
1. Вызван скилл design-system-update, создана новая версия дизайн-системы
2. Отчёт оператору (версия, компоненты add/mod/rem, пути)
3. Обновлён /SprintLog/Sprint-NNN-[name].md — добавлен раздел
   "Design System Snapshot"
4. Commit с префиксом feat(sprint-NNN/design-system):
$END_FORMAT

$START_CRITERIA
- Скилл вызван только после явного подтверждения оператора
- Отчёт содержит все 4 поля: версия, компоненты, showcase path, archive path
- Раздел Design System Snapshot в SprintLog заполнен
- Commit создан
- design-system-verify возвращает sync (если вызван)
$END_CRITERIA

$START_EXAMPLES
Пример отчёта оператору см. п. 11.5 фреймворка.
Пример раздела в SprintLog см. п. 11.6 фреймворка.
$END_EXAMPLES
```

---

## 12. GitHub Workflow (встраивается в каждый MD)

### Kanban

```
Backlog → Ready → In Progress → Review → Done
```

| Колонка | Условие |
|---------|---------|
| Backlog | Задача без промпта |
| Ready | Промпт написан и обогащён Фазой 0 (Issue body = полный промпт) |
| In Progress | AI начал выполнение, скелет SprintLog создан |
| Review | Код написан, тестируется, раздел фазы в SprintLog заполнен |
| Done | Тесты ОК, смержено в main, SprintLog обновлён, status фазы = completed |

### Labels

```
sprint-NNN  (#9333ea)  — привязка к спринту (НОВОЕ v4)
phase-0     (#5319e7)  — анализ проекта и обогащение промптов
phase-N     (#808080)  — привязка к фазе
bug         (#d73a4a)  — баг
optimization (#f9a825) — улучшение
enhancement  (#0075ca) — новая фича
hotfix      (#b60205)  — срочное исправление (НОВОЕ v4)
frontend    (#1d76db)  — frontend
backend     (#0e8a16)  — backend
infra       (#7057ff)  — инфраструктура
```

### Формат названия Issue (НОВОЕ v4)

```
[Sprint-NNN][PHASE M] Краткое описание задачи

Примеры:
[Sprint-007][PHASE 0] Анализ проекта и обогащение промптов
[Sprint-007][PHASE 1] Модель данных Notification
[Sprint-007][PHASE 2] API endpoints уведомлений
[Sprint-007][BUG] Email не отправляется при type=warning
[Sprint-007][OPT] Оптимизировать запрос unread count
```

### Коммиты (НОВОЕ v4 — включаем sprint-NNN)

```
feat(sprint-007/phase-2):     новая фича
fix(sprint-007/phase-2):      исправление
refactor(sprint-007/phase-2): рефакторинг
test(sprint-007/phase-2):     тесты
docs(sprint-007/phase-2):     документация
audit(sprint-007/phase-0):    результаты анализа Фазы 0
sprintlog(sprint-007):        обновление SprintLog
```

### gh CLI команды (включать в MD)

```bash
gh auth refresh -s project
gh project list
gh project create --title "PROJECT_NAME"

# Создание label для спринта (НОВОЕ v4)
gh label create "sprint-007" --color "9333ea" --description "Sprint 007: Notifications"

# Остальные labels
gh label create "phase-2" --color "808080" --description "Phase 2"

# ⚠️ Issues создаются ТОЛЬКО после Фазы 0:
gh issue create \
  --title "[Sprint-007][PHASE 2] API endpoints уведомлений" \
  --body "$(cat enriched-phase-2.md)" \
  --label "sprint-007,phase-2,backend"

gh project item-add PROJECT_NUMBER --owner OWNER --url ISSUE_URL
```

---

## 13. Переменные проекта (включать в каждый MD)

```
$PROJECT_ROOT      = [путь к корню проекта]
$COMPONENT_LIBRARY = $INSTRUMENTS/all-templates
$GITHUB_PROJECT    = [название проекта в GitHub]
$SKILLS_DIR        = ~/.claude/skills/
$SPRINT_ID         = Sprint-NNN  (НОВОЕ v4 — подставляется генератором)
$SPRINT_LOG        = $PROJECT_ROOT/SprintLog/Sprint-NNN-[name].md  (НОВОЕ v4)
$SPRINT_COUNTER    = $PROJECT_ROOT/SprintLog/sprint-counter.json   (НОВОЕ v4)
$DS_UPDATE_SKILL   = ~/.claude/skills/design-system-update/SKILL.md    (НОВОЕ v4.2)
$DS_VERIFY_SKILL   = ~/.claude/skills/design-system-verify/SKILL.md    (НОВОЕ v4.2)
$DS_ARCHIVE_SKILL  = ~/.claude/skills/design-system-archive/SKILL.md   (НОВОЕ v4.2)
$DS_PROTOCOL       = $INSTRUMENTS/design-components/PROTOCOL.md  (НОВОЕ v4.2)
```

---

## 14. Оптимизация под Claude Opus 4.6

### 14.1. Особенности модели

Claude Opus 4.6 — наиболее мощная модель в семействе Claude 4.6.
Следующие принципы учитывают её архитектурные особенности:

| Особенность | Как учитываем |
|-------------|---------------|
| Большое контекстное окно | Можно передавать полные промпты фаз + AppGraph.xml + SprintLog целиком |
| Сильная следование инструкциям | Структурированные маркеры $START/$END работают надёжно |
| Склонность к eager execution | Anti-hallucination директива критически важна для удержания суперпозиции |
| Отличное понимание кода | Фаза 0 (анализ проекта) использует эту силу для обнаружения связей |
| Чувствительность к порядку токенов | Прайминг ($START_KEYWORDS) в начале каждого промпта |
| Долговременная память | Через SprintLog — модель переходит к прошлым спринтам при необходимости (НОВОЕ v4) |

### 14.2. Принципы промптинга для Opus 4.6

1. **Граф как якорь:** AppGraph.xml загружается ПЕРВЫМ. Все рассуждения
   модели привязаны к навигационному графу, а не к абстрактным идеям.

2. **SprintLog как долговременная память:** `$START_LAST_UPDATE` с ссылкой
   `sprint_log_ref` позволяет модели переходить к истории прошлых спринтов
   и подгружать контекст по требованию (НОВОЕ v4).

3. **Явный запрет на преждевременный коллапс:** Opus 4.6 склонен давать
   «правильный» ответ сразу. Anti-hallucination директива заставляет
   модель удерживать множественные варианты.

4. **Ортогональные проекции:** Для каждой сложной задачи — минимум два
   взгляда (dependency graph + data flow). Если они противоречат — это
   пойманная ошибка, а не допустимая неопределённость.

5. **Чёткие фазовые границы:** Planning и Execution НИКОГДА не в одном
   блоке. Opus 4.6 может смешивать уровни абстракции — маркеры это
   предотвращают.

6. **Belief State между шагами:** `$START_TODO` с явными статусами
   [PENDING/IN_PROGRESS/COMPLETED] предотвращает дрейф контекста.

7. **Размер секций:** ~200–500 токенов оптимум. Максимум 2000 токенов.
   При превышении — дробить на подсекции с повторным праймингом.

---

## 15. Полный pipeline создания промптов

```
┌──────────────────────────────────────────────────────┐
│  1. Получение задачи от оператора                    │
│     «Добавь систему X в проект Y»                    │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  2. Инициализация спринта (НОВОЕ v4)                │
│     → Прочитать /SprintLog/sprint-counter.json       │
│     → Взять next_sprint_id (например Sprint-007)     │
│     → Обновить counter: current_sprint++, добавить   │
│       запись в массив sprints со статусом planning   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  3. Генерация двух файлов                            │
│     → [project]-MASTER-INSTRUCTION.md                │
│       - Секция 0: метаданные спринта                 │
│       - Каждый промпт содержит $START_LAST_UPDATE    │
│     → AppGraph.xml (с sprint="Sprint-NNN" в модулях) │
│     Issues в GitHub НЕ создаются                     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  4. Оператор передаёт файлы агенту (Claude Opus 4.6)│
│     Агент читает мастер-инструкцию и AppGraph.xml    │
│     Агент читает /SprintLog/_index.md (НОВОЕ v4)    │
│     Агент настраивает gh auth, labels, project       │
│     Агент создаёт label sprint-NNN                   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  5. Оператор отправляет: «Выполни Фазу 0»           │
│     Агент:                                           │
│     a) Читает /SprintLog/ (последние 3 спринта)      │
│     b) Сканирует файловую систему проекта            │
│     c) Сопоставляет с AppGraph.xml                   │
│     d) Обнаруживает неучтённые связи                 │
│     e) ДОПОЛНЯЕТ промпты фаз блоками обогащения      │
│     f) Обновляет $START_LAST_UPDATE во всех промптах │
│     g) Обновляет AppGraph.xml                        │
│     h) Создаёт /SprintLog/Sprint-NNN-[name].md       │
│     i) Обновляет /SprintLog/_index.md                │
│     j) Заполняет журнал (Секция 7)                   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  6. Оператор ревьюит результаты Фазы 0              │
│     → Проверяет дополнения к промптам                │
│     → Проверяет скелет SprintLog                     │
│     → Утверждает или корректирует                    │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  7. Post-Фаза 0 опрос оператора (НОВОЕ v4.1)        │
│     Агент задаёт 4 вопроса одним сообщением:         │
│     1. В какой GitHub repository коммитить код?      │
│     2. В какой GitHub Project задачи разработки?     │
│     3. В какой GitHub Project задачи дизайна?        │
│     4. В какую директорию грузить SprintLog?         │
│     → Получает ответы оператора                      │
│     → Фиксирует в Секции 0 мастер-инструкции         │
│     → Фиксирует в метаданных SprintLog               │
│     → Обновляет sprint-counter.json (placement)      │
│     БЕЗ ОТВЕТОВ Issues НЕ СОЗДАЮТСЯ                  │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  8. Создание Issues в GitHub Project                 │
│     → Title: [Sprint-NNN][PHASE M] ...               │
│     → Labels: sprint-NNN + phase-M + слой            │
│     → Body = полный промпт с $START_LAST_UPDATE      │
│       и $START_PHASE0_ENRICHMENT                     │
│     → Dev-фазы → dev-project                         │
│     → Design-фазы → design-project (или с label      │
│       design в dev-project если design-project=none) │
│     → Все Issues → Ready (промпт обогащён)           │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  9. Последовательное выполнение фаз (1..N)           │
│     → Оператор: «Выполни Фазу N»                    │
│     → Агент выполняет промпт                         │
│     → Commit с префиксом feat(sprint-NNN/phase-M):   │
│     → После фазы: дополняет раздел в SprintLog       │
│       (фиксирует было → стало по каждому файлу)      │
│     → Обновляет $START_LAST_UPDATE текущей фазы      │
│     → Тестирование → Review → Done                   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  10. End-of-Sprint Design System Snapshot (НОВОЕ v4.2)│
│     → Агент ждёт явное подтверждение оператора:      │
│       «готово» / «close sprint» / «ship it» и т.п.   │
│     → Проверяет: все тесты ОК, всё в main            │
│     → Определяет изменённые UI-компоненты из SprintLog│
│     → Вызывает скилл design-system-update            │
│       (~/.claude/skills/design-system-update/SKILL.md)│
│     → Получает: новую версию, showcase, архив        │
│     → Отчитывается оператору: версия, add/mod/rem,   │
│       пути к showcase и архиву                       │
│     → Дописывает раздел "Design System Snapshot"     │
│       в /SprintLog/Sprint-NNN-[name].md              │
│     → Commit: feat(sprint-NNN/design-system): snapshot│
│     ⚠️ При сомнениях — переспрашивает оператора      │
│     ⚠️ НЕ вызывает при failed tests или mid-iteration│
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  11. Закрытие спринта (НОВОЕ v4)                    │
│     → Все фазы completed                             │
│     → Design System Snapshot выполнен (шаг 10)       │
│     → Статус спринта в SprintLog → completed         │
│     → Заполнен Decision Log и Known Issues           │
│     → Обновлён /SprintLog/_index.md                  │
│     → Обновлён /SprintLog/sprint-counter.json        │
│       (добавить design_system_version: "v7")         │
│     → AppGraph.xml: обновлены last_modified_sprint   │
│     → commit: sprintlog(sprint-NNN): close sprint    │
└──────────────────────────────────────────────────────┘
```

---

## 16. Антипаттерны

| Антипаттерн | Что делать вместо |
|-------------|-------------------|
| Размытая инструкция | Контракт: цель + ограничения + критерии |
| Секция > 2000 токенов | Разбить на подсекции по 200–500 |
| Код сразу без вариантов | PROPOSE → HOLD → COLLAPSE |
| Planning + Execution в одном блоке | Разделять на фазы |
| > 7 шагов без проверки | Промежуточная валидация |
| Один файл вместо двух | MD (инструкция+промпты) + XML (граф) |
| Промпт без GitHub Issues | Каждая фаза = отдельный Issue в Project |
| Issues ДО анализа проекта | Сначала Фаза 0, потом Issues |
| Промпт без anti-hallucination фразы | Вставлять дословно в каждый $START_GOAL |
| Удаление текста промптов при обогащении | Только ДОПОЛНЯТЬ через $START_PHASE0_ENRICHMENT |
| Создание промптов без изучения проекта | Фаза 0 обязательна перед Issues |
| **Спринт без номера** (НОВОЕ v4) | **Всегда брать next_sprint_id из counter** |
| **Issue без префикса [Sprint-NNN]** (НОВОЕ v4) | **Все Issues в рамках спринта имеют префикс** |
| **Промпт без $START_LAST_UPDATE** (НОВОЕ v4) | **Обязательный блок в каждом промпте** |
| **Отсутствие SprintLog после спринта** (НОВОЕ v4) | **Создавать скелет в Фазе 0, заполнять по фазам** |
| **Коммит без sprint-NNN** (НОВОЕ v4) | **Префикс feat(sprint-NNN/phase-M):** |
| **Модификация $START_LAST_UPDATE без реальных изменений** (НОВОЕ v4) | **Обновлять только при реальных изменениях промпта** |
| **Создание Issues без ответов оператора на 4 вопроса** (НОВОЕ v4.1) | **Обязательный Post-Фаза 0 опрос: code repo, dev project, design project, sprintlog dir** |
| **Додумывание мест размещения за оператора** (НОВОЕ v4.1) | **Спросить явно; применять default только с явным уведомлением оператора** |
| **Смешивание dev и design задач в одном Project** (НОВОЕ v4.1) | **Dev-фазы → dev-project; design-фазы → design-project (или label `design` если design-project=none)** |
| **Отсутствие фиксации ответов в Секции 0 и SprintLog** (НОВОЕ v4.1) | **После опроса: обновить Секцию 0 MD, метаданные SprintLog, sprint-counter.json (placement)** |
| **Закрытие спринта без Design System Snapshot** (НОВОЕ v4.2) | **Перед финальным логированием обязательно вызвать design-system-update** |
| **Вызов design-system-update без явного подтверждения оператора** (НОВОЕ v4.2) | **Ждать сигнал "готово" / "close sprint" / "ship it"; при сомнении — переспросить** |
| **Snapshot во время активной разработки или failed tests** (НОВОЕ v4.2) | **Только после merge в main, все тесты зелёные, оператор подтвердил финализацию** |
| **Использование design-system-update вместо verify/archive** (НОВОЕ v4.2) | **update — только при close sprint; verify — для аудита; archive — перед рефакторингом** |
| **Отсутствие отчёта оператору после snapshot** (НОВОЕ v4.2) | **Обязательный отчёт: версия, компоненты add/mod/rem, showcase path, archive path** |
| **Отсутствие раздела Design System Snapshot в SprintLog** (НОВОЕ v4.2) | **После вызова скилла — дописать раздел перед Known Issues** |

---

## 17. Чек-лист перед отправкой

### MD-файл:
- [ ] Секция 0: метаданные спринта (Sprint ID, Title, Date) (НОВОЕ v4)
- [ ] Секция 1: роль + порядок действий + таблица инструкция/промпт?
- [ ] Секция 2: bash-команды скана + skills + AppGraph.xml + чтение SprintLog (НОВОЕ v4)
- [ ] Секция 3: gh CLI команды, labels (включая sprint-NNN), Kanban, коммиты + **предупреждение о Фазе 0** + формат [Sprint-NNN][PHASE M]?
- [ ] Секция 4: справочники по технологиям?
- [ ] Секция 5: **Фаза 0** первой + промпты фаз в code blocks + предупреждение «не удалять» + каждый промпт содержит $START_LAST_UPDATE (НОВОЕ v4)?
- [ ] Секция 6: граф + belief state?
- [ ] Секция 7: шаблон журнала Фазы 0?
- [ ] Секция 8: правила ведения SprintLog (НОВОЕ v4)?
- [ ] Каждый промпт: KEYWORDS, **LAST_UPDATE**, GOAL, ROLE, CONSTRAINTS, FORMAT, CRITERIA, EXAMPLES, STEPS, TODO?
- [ ] **Каждый $START_GOAL содержит anti-hallucination фразу дословно?**
- [ ] **Каждый $START_LAST_UPDATE содержит sprint_id, phase_number, date, author, change_summary, sprint_log_ref?** (НОВОЕ v4)
- [ ] Planning отделено от execution?
- [ ] $COMPONENT_LIBRARY указан во frontend-фазах?
- [ ] $SPRINT_ID, $SPRINT_LOG, $SPRINT_COUNTER в переменных (НОВОЕ v4)?

### XML-файл:
- [ ] Корень `<project>` содержит `sprint="Sprint-NNN"` (НОВОЕ v4)?
- [ ] Каждый модуль привязан к фазе и спринту (НОВОЕ v4)?
- [ ] Каждый `<file>` содержит `last_modified_sprint` (НОВОЕ v4)?
- [ ] Модели данных: поля, типы, relations, indexes?
- [ ] API: файлы + exports с сигнатурами?
- [ ] Компоненты: props + dependencies?
- [ ] Data flows: минимум 2–3 end-to-end сценария (с sprint) (НОВОЕ v4)?
- [ ] Cross-module dependencies?
- [ ] Phase execution order?
- [ ] External packages (с added_in_sprint) (НОВОЕ v4)?
- [ ] Design tokens (если есть UI)?
- [ ] `<sprint_history>` с записью о текущем спринте (НОВОЕ v4)?

### Фаза 0:
- [ ] Промпт Фазы 0 включён в секцию 5 первым?
- [ ] Anti-hallucination фраза присутствует в $START_GOAL Фазы 0?
- [ ] Секция 3 содержит предупреждение: Issues только после Фазы 0?
- [ ] Секция 7 содержит шаблон журнала?
- [ ] $START_PHASE0_ENRICHMENT маркеры описаны в ограничениях?
- [ ] В STEP 1 Фазы 0 указано чтение /SprintLog/ (НОВОЕ v4)?
- [ ] В STEP 7 Фазы 0 указано создание скелета SprintLog (НОВОЕ v4)?

### Система спринтов (НОВОЕ v4):
- [ ] Sprint ID получен из sprint-counter.json (или 001 при первом запуске)?
- [ ] sprint-counter.json обновлён (current_sprint++, запись в sprints)?
- [ ] Все Issues будут иметь формат [Sprint-NNN][PHASE M]?
- [ ] Label sprint-NNN будет создан до Issues?
- [ ] Формат коммитов включает sprint-NNN/phase-M?
- [ ] Скелет /SprintLog/Sprint-NNN-[name].md создаётся в Фазе 0?
- [ ] /SprintLog/_index.md обновляется?
- [ ] Инструкции по закрытию спринта есть в секции 8?

### Post-Фаза 0 опрос (НОВОЕ v4.1):
- [ ] В промпте Фазы 0 добавлен STEP 9 с 4 вопросами?
- [ ] Точные формулировки 4 вопросов присутствуют в секции 10 фреймворка?
- [ ] В Секции 0 MD есть пустой блок «Места размещения» для заполнения после опроса?
- [ ] В шаблоне /SprintLog/Sprint-NNN-[name].md есть поля Code Repository, Dev Project, Design Project, SprintLog Directory?
- [ ] В sprint-counter.json предусмотрено поле `placement` в записи спринта?
- [ ] Описаны правила разделения dev vs design фаз?
- [ ] Описаны default-значения для каждого из 4 вопросов?
- [ ] Указано явно: без 4 ответов Issues не создаются?
- [ ] Описан сценарий смены мест размещения посреди спринта (placement_history)?

### End-of-Sprint Design System Snapshot (НОВОЕ v4.2):
- [ ] В секцию 5 мастер-промпта добавлена финальная фаза Design System Snapshot?
- [ ] В финальной фазе присутствует $START_LAST_UPDATE с корректными полями?
- [ ] В финальной фазе присутствует anti-hallucination фраза в $START_GOAL?
- [ ] Указаны 3 скилла с путями ~/.claude/skills/design-system-{update,verify,archive}/SKILL.md?
- [ ] Определены триггеры: "готово", "финал", "sprint done", "close sprint", "ship it"?
- [ ] Определены запреты: failed tests, mid-iteration, неподтверждённое состояние?
- [ ] Описана разница между update (close sprint), verify (audit), archive (pre-refactor)?
- [ ] Шаблон отчёта оператору (версия, компоненты, showcase, archive) присутствует?
- [ ] Шаблон раздела "Design System Snapshot" в SprintLog присутствует?
- [ ] В шаге 10 pipeline: Design System Snapshot ПОСЛЕ всех фаз, ДО финального логирования?
- [ ] В шаге 11 pipeline добавлена отметка `design_system_version: "vN"` в sprint-counter.json?
- [ ] Снипет END-OF-SPRINT PROTOCOL вставлен в мастер-промпт?
- [ ] Формат коммита feat(sprint-NNN/design-system): snapshot vN указан?

---

## 18. Пример вызова

**Вход:** «Добавь систему уведомлений: in-app + email + Telegram»

**Инициализация спринта:**
- Читаем `/SprintLog/sprint-counter.json` → `current_sprint: 6`, `next_sprint_id: "Sprint-007"`
- Обновляем counter: `current_sprint: 7`, `next_sprint_id: "Sprint-008"`, добавляем запись `Sprint-007` в `sprints[]`

**Выход — 2 файла:**

1. `notifications-MASTER-INSTRUCTION.md`
   - **Секция 0:** Sprint ID = Sprint-007, Title = "Notifications System", Date = 2026-04-18
   - Секция 1: роль + шаги (включая создание SprintLog)
   - Секция 2: скан проекта + чтение /SprintLog/_index.md
   - Секция 3: GitHub workflow для Project "TTS" + **⚠️ Issues после Фазы 0** + формат `[Sprint-007][PHASE M] ...`
   - Секция 4: справочник по WebSocket, email, Telegram Bot API
   - Секция 5:
     - **Фаза 0** (анализ проекта + обогащение промптов) с `$START_LAST_UPDATE` (Sprint-007, phase 0)
     - Фаза 1 (модель данных) — с `$START_LAST_UPDATE` + anti-hallucination фразой
     - Фаза 2 (сервисы) — с `$START_LAST_UPDATE` + anti-hallucination фразой
     - Фаза 3 (UI) — с `$START_LAST_UPDATE` + anti-hallucination фразой
     - Фаза 4 (настройки) — с `$START_LAST_UPDATE` + anti-hallucination фразой
   - Секция 6: граф + belief state
   - Секция 7: шаблон журнала Фазы 0
   - Секция 8: правила ведения SprintLog для Sprint-007

2. `AppGraph.xml`
   - `<project sprint="Sprint-007" ...>`
   - Module "NotificationDB" (models: Notification, NotificationPreference) `sprint="Sprint-007"`
   - Module "NotificationAPI" `sprint="Sprint-007"`
   - Module "NotificationService" `sprint="Sprint-007"`
   - Module "NotificationUI" `sprint="Sprint-007"`
   - Data flows: SendNotification, MarkAsRead, UpdatePreferences (все с `sprint="Sprint-007"`)
   - Dependencies + phase order
   - `<sprint_history>` с записью Sprint-007

**После «Выполни Фазу 0» — ещё два артефакта:**

3. `/SprintLog/Sprint-007-notifications.md` (скелет со статусом in_progress)
4. `/SprintLog/_index.md` (обновлён, добавлена строка Sprint-007)
5. `/SprintLog/sprint-counter.json` (уже обновлён на шаге инициализации)

**После выполнения Фазы 0 — Post-Фаза 0 опрос (НОВОЕ v4.1):**

Агент: «Фаза 0 завершена. Перед созданием Issues уточни 4 параметра:
1. В какой GitHub repository коммитить код? (формат owner/repo)
2. В какой GitHub Project грузить задачи по разработке?
3. В какой GitHub Project грузить задачи по дизайну?
4. В какую директорию грузить SprintLog? [default: /SprintLog/]»

Оператор (пример): «1) <owner>/<repo>, 2) <owner>/<N>, 3) <owner>/<M>, 4) /SprintLog/»

Агент:
- Обновляет Секцию 0 мастер-инструкции: блок «Места размещения»
- Обновляет метаданные `/SprintLog/Sprint-007-notifications.md`:
  ```
  Code Repository: <owner>/<repo>
  Dev Project: https://github.com/orgs/<owner>/projects/<N>
  Design Project: https://github.com/orgs/<owner>/projects/<M>
  SprintLog Directory: /SprintLog/
  ```
- Обновляет `sprint-counter.json`:
  ```json
  {
    "id": "Sprint-007",
    "placement": {
      "code_repo": "<owner>/<repo>",
      "dev_project": "<owner>/<N>",
      "design_project": "<owner>/<M>",
      "sprintlog_dir": "/SprintLog/"
    }
  }
  ```

**Теперь — создание Issues:**

Dev-фазы (Phase 1 — модель, Phase 2 — API, Phase 4 — настройки) →
в `<owner>/<N>` с label `sprint-007,phase-N,backend/frontend`

Design-фазы (Phase 3 — UI макеты `NotificationCenter`) →
в `<owner>/<M>` с label `sprint-007,phase-3,design,frontend`

Смешанная Phase 3 — создаются два связанных Issue:
- `[Sprint-007][PHASE 3-DESIGN] Макеты NotificationCenter` в design-project
- `[Sprint-007][PHASE 3-DEV] Реализация NotificationCenter` в dev-project
  с упоминанием `Related to #<design-issue-number>`

**По ходу выполнения фаз 1..N:**
- После каждой фазы Claude Code дописывает раздел в `Sprint-007-notifications.md`
  с полным `было → стало` по каждому файлу
- Обновляет `$START_LAST_UPDATE` в промпте только что завершённой фазы
- Коммитит с префиксом `feat(sprint-007/phase-M): ...`

**После всех фаз — End-of-Sprint Design System Snapshot (НОВОЕ v4.2):**

Все функциональные фазы завершены, тесты зелёные, всё смержено в main.

Оператор: «close sprint»

Агент:
1. Проверяет условия: тесты ОК, всё в main, нет незакрытых багов
2. Определяет изменённые UI-компоненты из SprintLog:
   - Новые: `NotificationCenter.tsx`, `NotificationItem.tsx`, `NotificationBadge.tsx`
   - Изменённые: `Header.tsx`, `UserMenu.tsx`
3. Вызывает скилл `~/.claude/skills/design-system-update/SKILL.md`
4. Скилл прогоняет 5-step cycle: Discovery → Generation → Archive → Sync → Output
5. Агент отчитывается оператору:
   ```
   Design System Snapshot для Sprint-007 создан:
   - Новая версия: v7 (предыдущая: v6)
   - Добавлены: NotificationCenter, NotificationItem, NotificationBadge
   - Изменены: Header (иконка колокольчика), UserMenu (пункт prefs)
   - Showcase: /design-system/v7/components-showcase.html
   - Архив v6: /design-system/archive/v6-2026-04-18/
   ```
6. Дописывает раздел "Design System Snapshot" в `Sprint-007-notifications.md`
7. Commit: `feat(sprint-007/design-system): snapshot v7`

**По завершении спринта:**
- Статус `Sprint-007-notifications.md` → completed
- Заполнены Decision Log и Known Issues
- Обновлены `_index.md` и AppGraph.xml (`last_modified_sprint` на новых файлах)
- В `sprint-counter.json` добавлено поле `design_system_version: "v7"`
  в записи Sprint-007
- Финальный коммит `sprintlog(sprint-007): close sprint`
