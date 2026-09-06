# Установка скилла `common-master-prompt`

## Зависимости

- Claude Code (CLI или VS Code / JetBrains расширение).
- Папка `~/.claude/skills/` существует (создаётся Claude Code автоматически при первом запуске).

## Установка

```bash
cp -r $INSTRUMENTS/common-master-prompt-skill \
      ~/.claude/skills/common-master-prompt
```

Или через rsync (удобно при обновлении):

```bash
rsync -a --delete \
  $INSTRUMENTS/common-master-prompt-skill/ \
  ~/.claude/skills/common-master-prompt/
```

## Проверка

```bash
ls ~/.claude/skills/common-master-prompt/
# Ожидается: SKILL.md  INSTALL.md  prompt-framework-v5.md  templates/

diff -r $INSTRUMENTS/common-master-prompt-skill \
        ~/.claude/skills/common-master-prompt
# Ожидается: пустой вывод
```

## Использование

В новой сессии Claude Code в корне любого проекта:

- Slash-команда: `/common-master-prompt`
- Либо естественным языком: «запусти common-master-prompt для проекта X», «новый мастер-промпт», «начать новый спринт».

Скилл первым делом спросит 3 параметра (целевая папка, название спринта, путь к ТЗ или его текст), выведет манифест файлов и только после подтверждения оператора приступит к генерации.

## Обновление при выходе новой версии фреймворка

При появлении `prompt-framework-v5.2.md` / `prompt-framework-v5.md` и т. п. — перекопировать исходник в обе папки (имя файла внутри скилла остаётся прежним для стабильной ссылки из SKILL.md):

```bash
cp $INSTRUMENTS/prompt-framework-v5.md \
   $INSTRUMENTS/common-master-prompt-skill/prompt-framework-v5.md
cp $INSTRUMENTS/prompt-framework-v5.md \
   ~/.claude/skills/common-master-prompt/prompt-framework-v5.md
```

Номер версии фиксируется внутри самого файла (`v4.2`, `v5` и т. д.), имя файла — стабильное.

## Деинсталляция

```bash
rm -rf ~/.claude/skills/common-master-prompt
```
