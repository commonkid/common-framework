<!--
Template source: prompt-framework-v5.md §5.3 (Sprint-NNN-[name].md skeleton)
                 plus §11.6 (Design System Snapshot section inserted before Known Issues / Tech Debt).
Rule: if this template conflicts with the framework, the framework wins.
Placeholders: Sprint-NNN, notifications, dates, commits, etc.
-->

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

## Known Issues / Tech Debt

- Email-шаблоны захардкожены, нужна вынести в отдельный модуль (Sprint-008)
- Нет rate-limiting на API — отложено на инфра-спринт
- Telegram webhook работает только в production (нужен ngrok для локального тестирования)

## Ссылки

- **Master Instruction:** /prompts/notifications-MASTER-INSTRUCTION.md
- **AppGraph.xml:** /AppGraph.xml (v1.3)
- **PR:** https://github.com/<owner>/<repo>/pull/89
- **Design doc (если есть):** ...
