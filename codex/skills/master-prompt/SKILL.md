---
name: master-prompt
description: Compatibility alias for generating Commoncode/Codex master-prompt sprint artifacts. Use when the user says "master prompt", "/master-prompt", "create master prompt", or references the legacy master-prompt skill. This skill delegates to common-master-prompt.
---

# Master Prompt Alias

This is a compatibility wrapper for the legacy `master-prompt` skill name.

When this skill triggers, load and follow:

```
~/.codex/skills/common-master-prompt/SKILL.md
```

Use `common-master-prompt` as the source of truth for intake, manifest generation, artifact creation, templates, and validation.
