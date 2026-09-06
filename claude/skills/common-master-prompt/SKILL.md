---
name: common-master-prompt
description: Generate a Commoncode master-prompt pair ([project]-MASTER-INSTRUCTION.md + AppGraph.xml) for a new sprint, following the Prompt-as-Contract Framework v4.2. Ask the operator for target folder and sprint title first; enumerate all files that will be produced before generating anything; follow prompt-framework-v5.md byte-for-byte. Trigger on "/common-master-prompt", "ultraprompt", "новый мастер-промпт", "create master prompt", "start a new sprint", "generate sprint artifacts". Do NOT trigger for single-file edits, bug fixes, or ad-hoc refactors — this skill is an end-to-end sprint bootstrapper.
license: proprietary
---

# Common Master Prompt — Sprint Bootstrapper

Скилл генерирует пару артефактов мастер-промпта (`[project]-MASTER-INSTRUCTION.md` + `AppGraph.xml`) для нового спринта по фреймворку «Промпт как контракт» v4.2. Источник истины — файл `prompt-framework-v5.md` в папке этого скилла (2053 строки, 18 секций). При любом расхождении между настоящим SKILL.md и фреймворком — приоритет у фреймворка.

Язык взаимодействия с оператором: русский. Весь semantic markup, имена файлов, код и комментарии внутри артефактов: английский.

# START_INTERACTION_PROTOCOL

Эта секция — нерушимый закон сотрудничества. Язык сессии: русский.

* **Роль оператора:** Архитектор и Оркестратор. Формулирует ТЗ и принимает решения.
* **Роль агента (этого скилла):** Автономный исполнитель. Берёт 100% ответственности за генерацию артефактов по фреймворку.
* **Политика ревью:** оператор проверяет исключительно соответствие разметке фреймворка. Соблюдение формальных протоколов — абсолютный приоритет.
* **Политика сохранности фреймворка:** ни при каких условиях не изменять содержимое `prompt-framework-v5.md` из папки скилла. Этот файл — read-only источник истины.

# END_INTERACTION_PROTOCOL

# START_WORKFLOW_STEP_1_INTAKE

**Первым действием при запуске скилла** агент задаёт оператору ЕДИНСТВЕННОЕ сообщение с 3 пронумерованными вопросами (через AskUserQuestion или обычный текст — по обстоятельствам):

```
Прежде чем сгенерировать мастер-промпт, уточни 3 параметра:

1. В какую папку грузить артефакты (MD + XML + SprintLog)?
   Формат: абсолютный путь (например, $PROJECTS/<project>/prompts/)
   [default: корень текущего git-репозитория]

2. Как назвать спринт / мастер-промпт?
   - Project slug (для имени файла [project]-MASTER-INSTRUCTION.md): например, "notifications"
   - Sprint title (человеко-читаемое, попадёт в Секцию 0 и SprintLog):
     например, "Система уведомлений: in-app + email + Telegram"

3. Где ТЗ (техническое задание на спринт)?
   Варианты:
   - путь к готовому файлу ТЗ (абсолютный)
   - "пришлю следующим сообщением"
   - "вот оно:" и текст ТЗ прямо в ответе
```

**ЖЁСТКИЙ ЗАПРЕТ:** до получения ответов на все 3 вопроса — не создавать ни одного файла, не вызывать gh, не запускать Фазу 0. Если оператор ответил частично — переспросить недостающее.

# END_WORKFLOW_STEP_1_INTAKE

# START_WORKFLOW_STEP_2_MANIFEST

После получения ответов и до какой-либо записи файлов — агент выводит оператору **манифест генерации** и явно спрашивает «генерировать?». Манифест содержит:

1. **Sprint ID.** Прочитать `<TARGET_DIR>/SprintLog/sprint-counter.json`. Если файла нет — `Sprint-001`. Если есть — взять `next_sprint_id`.

2. **Список файлов, которые будут созданы** (абсолютные пути):
   - `<TARGET_DIR>/[project]-MASTER-INSTRUCTION.md` — мастер-инструкция (секции 0–8 по §8.1 фреймворка)
   - `<TARGET_DIR>/AppGraph.xml` — навигационный граф (§8.2)
   - `<TARGET_DIR>/SprintLog/Sprint-NNN-[name].md` — скелет лога спринта со статусом `in_progress` (§5.3)
   - `<TARGET_DIR>/SprintLog/_index.md` — создаётся или обновляется (§5.5)
   - `<TARGET_DIR>/SprintLog/sprint-counter.json` — создаётся или обновляется (§3.3)

3. **Структура MD-файла** (7 секций + Секция 0) — перечислить все секции 0–8 с одной строкой о содержимом каждой (по §8.1).

4. **Список фаз**, которые попадут в Секцию 5:
   - Фаза 0 — обязательная, анализ проекта и обогащение промптов (§9)
   - Фазы 1..N — функциональные фазы, выведенные из ТЗ
   - Финальная фаза «Design System Snapshot» (§11.9)

5. **Обязательные блоки каждого промпта фазы** (§6 «Шесть компонентов»):
   - `$START_KEYWORDS` / `$END_KEYWORDS`
   - `$START_LAST_UPDATE` / `$END_LAST_UPDATE`
   - `$START_GOAL` / `$END_GOAL` — с anti-hallucination фразой дословно первой строкой (§2.1)
   - `$START_ROLE` / `$END_ROLE`
   - `$START_CONSTRAINTS` / `$END_CONSTRAINTS`
   - `$START_STEPS` / `$END_STEPS`
   - `$START_FORMAT` / `$END_FORMAT`
   - `$START_CRITERIA` / `$END_CRITERIA`
   - `$START_EXAMPLES` / `$END_EXAMPLES`

6. **Явный вопрос оператору:** «Генерировать по этому манифесту? (да / нет / правки)».

До положительного ответа — не переходить к Шагу 3.

# END_WORKFLOW_STEP_2_MANIFEST

# START_WORKFLOW_STEP_3_READ_FRAMEWORK

После подтверждения оператора — **прочитать целиком** файл `<SKILL_DIR>/prompt-framework-v5.md` через Read (все 2053 строки, без фрагментирования). Это sovereign source of truth. При любом расхождении между этим SKILL.md и фреймворком — приоритет у фреймворка.

При генерации агент цитирует фреймворк по секциям: §2.1 (anti-hallucination), §3 (sprints), §4 (LAST_UPDATE), §5 (SprintLog), §6 (6 компонентов), §8.1 (MD-структура), §8.2 (XML-структура), §9 (Фаза 0), §10 (Post-Фаза 0 опрос), §11 (End-of-Sprint Design System Snapshot), §12 (GitHub Workflow), §13 (переменные), §17 (чек-лист).

# END_WORKFLOW_STEP_3_READ_FRAMEWORK

# START_WORKFLOW_STEP_4_SPRINT_INIT

Согласно §3.3 и §15 шаг 2:

1. Если `<TARGET_DIR>/SprintLog/sprint-counter.json` существует — прочитать, взять `next_sprint_id`.
2. Если не существует — создать с `current_sprint: 1` и `next_sprint_id: "Sprint-001"`.
3. Обновить counter: `current_sprint++`, пересчитать `next_sprint_id`, добавить запись в `sprints[]` со статусом `planning` и текущей датой.

# END_WORKFLOW_STEP_4_SPRINT_INIT

# START_WORKFLOW_STEP_5_GENERATE

Генерация двух базовых артефактов строго по фреймворку:

**A. `<TARGET_DIR>/[project]-MASTER-INSTRUCTION.md`** — 7 секций + Секция 0 (§8.1). Каждый промпт фазы в Секции 5 — внутри code-block с маркерами `$START_*` и:
- anti-hallucination фраза из §2.1 **дословно** первой строкой `$START_GOAL`;
- блок `$START_LAST_UPDATE` по формату §4.2 с `sprint_id`, `phase_number`, `date`, `author`, `change_summary`, `sprint_log_ref`;
- Фаза 0 — первая фаза в Секции 5, её промпт — полностью по шаблону §9.3 (включая STEP 9 Post-Фаза 0 опрос, §10.8);
- финальная фаза — «Design System Snapshot» по шаблону §11.9 + снипет END-OF-SPRINT PROTOCOL из §11.8 **дословно**.

В Секцию 3 обязательно включить предупреждение из §9.4 (Issues только после Фазы 0).
В Секции 0 создать пустой блок «Места размещения» (заполнится после Post-Фаза 0 опроса, §10.5).

**B. `<TARGET_DIR>/AppGraph.xml`** — по структуре §8.2:
- корень `<project sprint="Sprint-NNN" ...>`;
- `<module>` с атрибутами `phase="N"`, `sprint="Sprint-NNN"`;
- `<file>` с `last_modified_sprint`;
- `<data_flow sprint="Sprint-NNN">` — минимум 2–3 end-to-end сценария;
- `<sprint_history>` с записью текущего спринта.

# END_WORKFLOW_STEP_5_GENERATE

# START_WORKFLOW_STEP_6_SPRINTLOG_SCAFFOLD

Создать `<TARGET_DIR>/SprintLog/Sprint-NNN-[name].md` по шаблону §5.3 со статусом `in_progress` и заполненными метаданными Sprint ID / Title / Date Started / Master Prompt / AppGraph Version. Пустой блок «Места размещения» оставить для заполнения после Post-Фаза 0 опроса.

Обновить `<TARGET_DIR>/SprintLog/_index.md` (§5.5) — добавить строку текущего спринта.

# END_WORKFLOW_STEP_6_SPRINTLOG_SCAFFOLD

# START_WORKFLOW_STEP_7_CHECKLIST

Прогнать все чек-листы из §17 фреймворка:
- MD-файл (пункты 1–15);
- XML-файл;
- Фаза 0;
- Система спринтов;
- Post-Фаза 0 опрос;
- End-of-Sprint Design System Snapshot.

Отчёт оператору: по каждому пункту `[x]` / `[ ]`. Если хоть один `[ ]` — объяснить почему и что нужно доработать.

# END_WORKFLOW_STEP_7_CHECKLIST

# START_HARD_RULES

Инварианты, которые агент **обязан** удерживать до конца сессии:

1. Anti-hallucination фраза из §2.1 вставляется **дословно** в каждый `$START_GOAL`, в том числе в `$START_GOAL` финальной фазы Design System Snapshot.
2. Issues в GitHub **НЕ создаются** до завершения Фазы 0 (§9.4).
3. Без 4 ответов оператора на Post-Фаза 0 опрос (§10.3) **не вызывать** `gh issue create` / `gh project item-add`.
4. Design System Snapshot (§11) вызывается только при явном сигнале оператора: «готово», «финал», «завершили спринт», «sprint done», «close sprint», «ship it». При сомнениях — переспросить.
5. Промпты в Секции 5 read-only, кроме блока `$START_LAST_UPDATE`, который обновляется при любом изменении промпта (§8.1).
6. Нельзя удалять слова из `prompt-framework-v5.md` внутри папки скилла — это zero-modification reference.
7. `$START_PHASE0_ENRICHMENT` — единственный способ дополнить промпт фазы после Фазы 0; удалять / переписывать существующий текст фаз запрещено.

# END_HARD_RULES

# START_REFERENCES

* **Sovereign framework:** `<SKILL_DIR>/prompt-framework-v5.md` (читать целиком перед генерацией).
* **Templates:** `<SKILL_DIR>/templates/` — скелеты пяти файлов (MD-инструкция, XML-граф, SprintLog, counter, index). Если шаблон конфликтует с фреймворком — приоритет у фреймворка.
* **User protocols:** `~/.claude/rules/commoncode.md` (semantic markup, SFT-Priming, суперпозиция→коллапс), `~/.claude/rules/english-thinking.md` (English internals / Russian UX).

# END_REFERENCES
