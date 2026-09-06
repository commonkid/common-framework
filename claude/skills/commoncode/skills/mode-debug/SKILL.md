---
name: mode-debug
description: MANDATORY MODE for systematic diagnostics and bug fixing. Focuses on root-cause identification through LDD trace analysis and code immunization. Loaded by root Claude via the Skill tool when QA or Code subagents return failures.
---

# Mode: Debug — Systematic Diagnostics and Immunization

**Objective:** identify and resolve bugs through deep context analysis and semantic verification. Focus on the root cause, not just passing tests.

$START_DOC_NAME
**PURPOSE:** Diagnostics and bug fixing.
**SCOPE:** Error analysis, code correction, and immunization.
**KEYWORDS:** `DOMAIN(Debug): Diagnostics; CONCEPT(Safety): Immunization; TECH(Analysis): LDDTrace`.

$START_SECTION_WARNING
### CRITICAL COGNITIVE WARNING: THE GREEN TEST TRAP
- **100% PASSED is NOT final proof of correctness.**
- Success is defined as **Semantic Trace Verification**: does the actual execution path (logs) match the design (contracts)?
$END_SECTION_WARNING

$START_SECTION_WORKFLOW
### Diagnostic Playbook

**Step 1 — AGGRESSIVE_CONTEXT_GATHERING (Greedy Reading)**
- MANDATORY: `Read` ALL modules mentioned in the traceback and their dependencies.
- **Dependency discovery order (cheap → expensive):**
  1. **GREP-scan for instant overview.** Run `Grep` with pattern `GREP_SUMMARY|STRUCTURE` across the target project's source folders. The 1–2 line summary per file (`# GREP_SUMMARY:` keywords + `# STRUCTURE:` mini block diagram) reveals which files are relevant before any full read.
  2. **Doxygen XML index.** If `<target>/doxygen_output/xml/` exists (it does after `mode-code` Step 7 — `BUILD_DOXYGEN`), read the relevant per-file XML reports (e.g., `mymodule_8py.xml` for `mymodule.py`) to enumerate callers, callees, and cross-links. If the XML is stale or missing, run `cd <target> && doxygen Doxyfile` via `Bash` to regenerate (Doxygen is fast — this is safe at any time).
  3. **Fallback to source.** Use `Grep` / `Glob` over `<target>` for symbols, then `Read` the relevant files. Do **not** look for `AppGraph.xml` — that artifact has been deprecated; the post-code architecture lives inside Doxygen output and the in-source `## @modulemap` / `## @links` / `# region` markup.
- Read each relevant file's `## @modulecontract` (Doxygen `## @purpose`, `## @invariants`, `## @rationale`, `## @modulemap`) — wrapped inside `# region MODULE_CONTRACT [DOMAIN(X)…]` blocks.
- Understand how the code *was intended* to work before fixing it.

**Step 2 — LOG_ANALYSIS_AND_HYPOTHESIS**
- Analyze the log file at the absolute path provided in the bug report / QA Bug Report (log-file naming is task-specific — do not assume `app.log`).
- Find `[IMP:7-10]` markers (AI Belief State) and compare with contracts.
- Identify the root cause before writing a single line of code.

**Step 3 — IMPLEMENT_FIX_AND_IMMUNIZE**
- Apply the fix using `Edit`.
- MANDATORY: add `# BUG_FIX_CONTEXT: [Why the old approach failed, why this fix was chosen]` as an inline comment inside the modified `# region FUNC_…` block.
- Update the file's Doxygen contract (`## @rationale`, `## @changes` LAST_CHANGE entry) and any LDD log lines whose `[IMP:9-10]` belief statements no longer match the new behavior.
- If the file uses legacy markup (`# START_MODULE_CONTRACT:`, `# START_FUNCTION_…`, `# START_BLOCK_…`) — migrate it to the current Doxygen standard (`# region` + `## @…`) as part of the fix. Presence of `# GREP_SUMMARY:` after the contract is the signal that migration has already been done.
- **Do not perform direct fixes for large changes** — prefer respawning `Agent` with `subagent_type: mode-code` in a fresh context, passing only the affected file + the Bug Report. Direct `Edit` from root is acceptable for surgical one-line fixes.

**Step 4 — SEMANTIC_VERIFICATION**
- Run `python -m pytest <tests> -s -v` via `Bash`.
- MANDATORY: audit new logs (IMP:7-10) to verify the logic. Do not trust green asserts alone.
- Optionally respawn `Agent` with `subagent_type: mode-qa` for impartial re-verification.
$END_SECTION_WORKFLOW

$START_SECTION_ESCALATION
### Escalation Protocol for Complex Bugs
1. **TDD-Isolation:** write a standalone regression test reproducing the bug.
2. **Dynamic Probing:** insert extreme logs: `logger.critical(f"[DebugProbe][IMP:10] var_X={var_X!r}")`.
3. **Analyze Ground Truth:** run the regression test and use probes for absolute certainty.
4. MANDATORY: REMOVE all `[DebugProbe]` logs after the fix is verified.
$END_SECTION_ESCALATION

$END_DOC_NAME
