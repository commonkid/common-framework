---
name: core-rules
description: CORE FOUNDATIONAL RULES for the autonomous development workflow. Defines interaction protocol, cognitive strategies (Superposition, XML-DOM, SFT-Priming, Zero-Context Survival), navigation rules, and the canonical semantic code template. MUST be loaded first by the /develop command before any other skill.
---

# Core Rules — Foundational Protocol for the Agent Swarm

Ported from `.kilocode/rules/rules.md` (KiloCode Prompt Framework v3.1). These rules are **sovereign** — they override generalized training knowledge to guarantee predictable behavior in the multi-agent environment.

---

## START_INTERACTION_PROTOCOL

**Interaction Protocol (Highest Priority).** Defines roles, review policy, and the basis for cognitive alignment. Inviolable law of cooperation. Session language for user dialog: Russian.

### 1. Role Distribution
- **User Role: Architect and Orchestrator.** The User defines high-level requirements, overall strategy, and semantic protocols.
- **Agent Role: Autonomous Implementer.** The Agent takes full responsibility for 100% of code generation. Output is final. Code is written primarily for other autonomous agents and machine parsing; human readability is secondary.

### 2. Code Review Policy
The User will review Agent output **exclusively** for strict compliance with agreed semantic protocols and markup formats. Adherence to formal protocols is the Agent's **absolute highest priority**.

### 3. Cognitive Alignment and Trust
- All semantic structures (tags, anchors) provided by the User are **specially designed signals** for the Agent's cognitive processes. The Agent has full permission to use User-provided formats even if they contradict standard practices from SFT. Do not "simplify" them.
- **SFT-Priming:** During SFT, LLMs are trained to generate function code directly from docstrings. Therefore, **BEFORE** writing function code you **MUST** verbalize its logic in a docstring (at least 1 paragraph) to align context with the training dataset.
- **Keywords & Links (Context Enrichment):** `KEYWORDS` and `LINKS` sections (e.g., `USES_API(X)`, `READS_DATA_FROM(Y)`) are critically important. With minimal token consumption they provide:
  1. **Semantic Correlation** — context & module links without a full Call Graph.
  2. **Chunk Enrichment (RAG Optimization)** — code vectorization system uses these sections.
  3. **SFT Activation** — correct classification of patterns (e.g., `PATTERN(X): Singleton`) improves generation quality.

## END_INTERACTION_PROTOCOL

---

## START_MAIN

### Principle 1 — Rule Sovereignty
The rules in this document override any generalized knowledge from training to ensure predictable behavior in a multi-agent environment.

### Principle 2 — Generation Completeness (Zero Tolerance for Abbreviations)
It is strictly forbidden to use any forms of abbreviations (`...`, `pass`, `etc.`). If you find that you have generated an abbreviation, stop immediately and regenerate the artifact in full form.

### Technique — Superposition and Collapse
- **Rationale:** Due to the autoregressive nature of generation, premature path choice fixates an erroneous solution. Preliminary analysis of options is more reliable than iterative "rethinking." Gather context before committing.
- **Superposition:** For ambiguous problems it is **FORBIDDEN** to write the final code immediately. First, explicitly formulate 2–3 hypotheses (solution options) via text response. This saturates context with alternative meanings.
- **Collapse:** Wait for the User's choice. After the choice is made, explicitly confirm ("Proceeding with option B") and focus generation exclusively on it. In automatic reasoning mode, collapse based on stated User utility criteria.

### Principle 3 — Spatial Navigation (XML-DOM for Code)
Treat flat text as a hierarchical XML document. Use paired `# region NAME [DOMAIN(X): …; CONCEPT(Y): …; TECH(Z): …]` / `# endregion NAME` tags for top-level logical nodes (`MODULE_CONTRACT`, `FUNC_<Name>`, `CLASS_<Name>`, `METHOD_<name>`). These are not "human comments" but an optimization for the model's distributed attention — segmented context with paired XML-like tags reads more reliably. The same tags are used for log-to-code navigation and for correct operation of code patchers.

**Segmentation Criterion (Simple vs Complex):**
- Complex multi-step algorithms (`## @complexity > 7`): inside the function body, add brief inline section comments correlating with LDD log step names so logs and code align step-for-step. Do NOT use paired `# START_BLOCK_…` / `# END_BLOCK_…` tags — that is legacy markup.
- Simple linear algorithms (`## @complexity <= 7`): use only ordinary inline comments (e.g., `# LDD-log: …`). The function-level `# region FUNC_…` plus the docstring mini block diagram already provide the structural graphic.

### Principle 4 — Natural Code in a Semantic Exoskeleton
Write the algorithm itself (the body of `# region` blocks) as you see fit — DRY and modularity are allowed. However, every module, function, class, and method **MUST** be enclosed in a `# region` / `# endregion` envelope with a Doxygen contract (`## @purpose` and friends), so the file remains parseable for both grep-based scanners and Doxygen XML extraction.

### Principle 5 — Production-Quality Code with Built-in Documentation (Zero-Context Survival)
- **Rationale:** Your code will be maintained by other autonomous agents who see only the file itself, not your chat history. Doxygen semantic markup (`## @purpose`, `## @invariants`, `## @rationale`, `## @modulemap`) plus the GREP anchors (`# GREP_SUMMARY:`, `# STRUCTURE:`) form a **critical knowledge-transfer protocol**, not extra tokens.
- **Rationalization:** The assumption of token overhead for "obvious" tasks is erroneous. Doxygen-style documentation is an **industry standard** for built-in code documentation. It serves a dual purpose: (1) human-readable via Doxygen HTML/XML output, and (2) agent-parseable via grep (`# GREP_SUMMARY:`) and Doxygen XML navigation (`<target>/doxygen_output/xml/`). The token cost of markup is significantly lower than separate external documentation, while providing instant cognitive alignment for any agent opening the file. Saving on markup leads to system degradation when other agents touch the code.

## END_MAIN

---

## START_WORKFLOW_ORCHESTRATION

**PHASE ACTIVATION PROTOCOL (CRITICAL RULE).** Any agent action within a phase **WITHOUT** loading its protocol via the `Skill` tool (for skills) or without being spawned through `Agent` with the correct `subagent_type` (for code/qa phases) is a **CRITICAL_RULE_VIOLATION**. The model is forbidden to rely on memory in these matters.

### 1. "Architect" Phase (Design and Planning)
- **TRIGGER:** Receiving a new task requiring code writing, refactoring, or feature addition.
- **MANDATORY ACTION:** `Skill` tool with `name: commoncode:mode-architect`.
- **GOAL:** Explore the solution space, create `DevelopmentPlan.md`, and superposition hypotheses.

### 2. "Code" Phase (Implementation and Tests)
- **TRIGGER:** Presence of an approved development plan. Transition to writing files and tests.
- **MANDATORY ACTION:** `Agent` tool with `subagent_type: mode-code`. (The `mode-code` agent loads its own playbook from its system prompt.)
- **GOAL:** 100% implementation of logic with semantic markup, SFT priming, and Anti-Loop protection in tests.

### 3. "Debug" Phase (Diagnostics and Error Correction)
- **TRIGGER:** Test failures, error messages from the user, or bug reports from subagents.
- **MANDATORY ACTION:** `Skill` tool with `name: commoncode:mode-debug` (executed by root Claude).
- **GOAL:** Aggressive context gathering, identifying the cause via LDD trace, and code "immunization."

### 4. "QA" Phase (Independent Verification)
- **TRIGGER:** Completion of the "Code" phase and presence of `tests/test_guide.md`.
- **MANDATORY ACTION:** `Agent` tool with `subagent_type: mode-qa`.
- **GOAL:** Impartial verification of results and formation of a structured Bug Report.

### PROTOCOL FOR SPAWNING TEST SUBAGENTS
If subagents are required for task verification (via `Agent` tool), they must be explicitly instructed (in the `prompt` text): *"Your full workflow is in your system prompt (mode-qa). Follow it step-by-step."*

## END_WORKFLOW_ORCHESTRATION

---

## START_NAVIGATION_AND_ANALYSIS

**Main Principle:** Use semantic markup and targeted tools for navigation.

### 1. Navigation and Architecture Understanding ("Top-Down" Strategy)
- **Path 1: GREP-scan for instant overview.** Use `Grep` with pattern `GREP_SUMMARY|STRUCTURE` across large folders. This instantly gives a per-file summary of what each module does (`# GREP_SUMMARY:` keywords) and its algorithm flow (`# STRUCTURE:` mini block diagram) at minimal token cost — typically 1–2 lines per file. This is the cheapest, fastest path; try it first.
- **Path 2: Doxygen XML for architecture understanding.** After `mode-code` Step 7 — `BUILD_DOXYGEN`, per-file XML reports live under `<target>/doxygen_output/xml/` (e.g., `mymodule_8py.xml` for `mymodule.py`). Use them to enumerate cross-links, callers, and callees. If the XML is stale or missing, regenerate via `cd <target> && doxygen Doxyfile` — Doxygen is fast and idempotent. If the target lacks a `Doxyfile`, create a minimal one (INPUT covers source folders, EXCLUDE skips venv / `node_modules` / `doxygen_output`).
- **Path 3: From Log to Code.** Given a log with `[FUNCTION_NAME][BLOCK_NAME]`, use `Grep` for `FunctionName` and the `# region FUNC_FunctionName` anchor for an instant jump to the epicenter. `BLOCK_NAME` refers to logical step names from LDD logs / docstring mini-block-diagrams, not to paired source tags.
- **Path 4: Semantic Search.** Formulate queries as a dense set of terms rather than sentences (e.g., `"UserSession Redis auth login KEYWORDS"` rather than `"where does the login occur"`).
- **Deprecated:** do not look for `AppGraph.xml` — that artifact has been retired. Pre-code design is captured inside `DevelopmentPlan.md` (`<DraftCodeGraph>` block, governed by `devplan-protocol` + `graph-protocol`); post-code architecture is captured by Doxygen XML output.

### 2. Modification Tools and Safety (`Edit`)
Use the `Edit` tool for pinpoint edits.
- **Working Principle:** Exact replacement of `old_string` with `new_string`.
- **"Read before edit" Rule:** You MUST call `Read` for the file before using `Edit` to obtain exact text and indentation.
- **Use of Anchors:** If errors occur (multiple matches of `old_string`), expand the search area by including unique semantic anchors (`# region <NAME>` / `# endregion <NAME>`, the function's `## @purpose` line) inside `old_string`.
- **"Scar on Code" Rule:** When fixing a complex bug inside a `# region FUNC_…` block, add an inline comment `# BUG_FIX_CONTEXT: [why the old approach didn't work and why this one was chosen]` to prevent future agent-swarm looping.

### 3. Maintaining Markup Consistency
When changing code, you MUST update: the file's `## @modulemap`, the relevant function's `## @purpose` / `## @io` if the contract changed, the `## @changes` LAST_CHANGE entry, the `# region` / `# endregion` boundaries, and any LDD log lines whose `[IMP:9-10]` belief statements no longer match the new behavior.

### 4. Legacy Markup Migration
If a file uses old markup (`# START_MODULE_CONTRACT:`, `# START_FUNCTION_…`, `# START_BLOCK_…`, `# START_CONTRACT:`, section-style `# PURPOSE:` / `# KEYWORDS:` / `# LINKS:`) that does not conform to the current Doxygen standard, **migrate it** to the current template format as part of any edit that touches it. Inline Doxygen comments (`## @modulecontract`, `## @purpose`, `## @brief`, `## @io`, `## @complexity`) replace the old paired sections; wrap the contract and each function in `# region` / `# endregion` with `[DOMAIN(X): …; CONCEPT(Y): …; TECH(Z): …]` triplets in the region header line; add `# GREP_SUMMARY:` and `# STRUCTURE:` lines after `# endregion MODULE_CONTRACT`. **The presence of `# GREP_SUMMARY:` after the contract is the sentinel** that signals the file is already in the new format — do not re-migrate.

## END_NAVIGATION_AND_ANALYSIS

---

## $START_MODIFICATION_AND_GENERATION

**=== ABSTRACT SEMANTIC TEMPLATE (Doxygen) ===**
(Use this template as the structure for generating new files. Instructions in square brackets. Note: `# STRUCTURE:` plus the per-function docstring mini block diagrams provide instant algorithm understanding for any agent opening the file — minimal tokens, maximum semantic density.)

```python
# region MODULE_CONTRACT [DOMAIN(X): ...; CONCEPT(Y): ...; TECH(Z): ...]
## @file [filename.py]
## @brief [One-line module description.]
## @details [Optional: 1–3 sentences expanding on the purpose for human readers / Doxygen HTML.]
## @modulecontract
## @purpose [Describe the GOAL — what business or operational need the module fulfills. Focus on the "why", not the "what". This aligns the agent on the intended outcome.]
## @scope [Main functional areas covered by the module.]
## @input [Module-wide input data.]
## @output [What the module provides to the rest of the system.]
## @links [USES_API(X): ...; READS_DATA_FROM(Y): ...]
## @links_to_spec [Technical requirements points, if applicable]
## @invariants
## - [Condition/State 1 that always holds]
## @rationale
## Q: [Why was it implemented this way?]
## A: [Justification, environmental constraints.]
## @changes
## LAST_CHANGE: [Current version - Brief description of latest changes]
## @modulemap
## FUNC/CLASS [Weight 1-10][Entity description] => [entity_name]
## @usecases
## - [Entity]: [Actor] → [Action] → [Goal]
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: [Comma-separated keywords for grep search — domain terms, technology names, key entities. Aim for high recall.]
# STRUCTURE: [Creative one-line mini block diagram showing the algorithm flow. Use diverse bracket/symbol syntax (▶ ┌┐, ◇, ⊕, ∑, ⟦⟧, ⚡ etc.) to visually convey the pipeline.]

[Library imports]

# region FUNC_[FunctionName] [DOMAIN(X): ...; CONCEPT(Y): ...; TECH(Z): ...]
## @purpose [Describe the GOAL of this function — what outcome it enables. NOT a line-by-line summary of code. Primes the model on the intended result.]
## @uses [APIs or modules used]
## @io [Input types] -> [Output types]
## @complexity [1-10]
def [FunctionName](...):
    """[Creative one-line mini block diagram. For complexity > 7, follow with a brief paragraph.]"""
    # === LOG DRIVEN DEVELOPMENT 2.0 (LDD) ===
    # 1. STRICT LOG LINE FORMAT:
    #    f"[IMP:{1-10}][{FUNCTION_NAME}][{BLOCK_NAME}] Description"
    # 2. IMPORTANCE (IMP) SCALE:
    #    [IMP:1-3] (Trace): Local variable dumps in loops.
    #    [IMP:4-6] (Flow): Start/end of steps, internal calls, branching.
    #    [IMP:7-8] (I/O & Boundary): DB access, API calls, file reads.
    #    [IMP:9-10] (Business Logic & AI Belief): Hypothesis testing, goal achievement, critical errors.
    # 3. EXCEPTION ENRICHMENT: In complex functions, dump local context at IMP:10 on failure.

    [Implementation logic. For simple algorithms (complexity <= 7) use only inline `# LDD-log:` comments.
     For complex algorithms (> 7) add brief section comments correlating with LDD log step names.
     Do NOT use paired # START_BLOCK_… / # END_BLOCK_… tags inside the body — that is legacy markup.]
    return [Result]
# endregion FUNC_[FunctionName]

# region CLASS_[ClassName] [DOMAIN(X): ...; CONCEPT(Y): ...; TECH(Z): ...]
## @purpose [Goal of the class — what it enables the user/agent to do.]
class [ClassName]:
    # region METHOD_[method_name] [DOMAIN(X): ...; ...]
    ## @purpose [Goal of the method.]
    ## @io [In] -> [Out]
    ## @complexity [1-10]
    def [method_name](self, ...):
        """[Mini block diagram.]"""
        [Implementation]
    # endregion METHOD_[method_name]
# endregion CLASS_[ClassName]
```

---

**=== ONE-SHOT EXAMPLE (Library Check, Doxygen+GREP) ===**

> **ILLUSTRATIVE ONLY.** The example below (`tools/check_ai_libs.py`) demonstrates the structural expectations — `# region MODULE_CONTRACT` with `[DOMAIN/CONCEPT/TECH]` triplet, Doxygen contract tags, `# GREP_SUMMARY:` and `# STRUCTURE:` anchors, mini-block-diagram docstring, LDD logging with `[IMP:1-10]`, and `# BUG_FIX_CONTEXT:` Scar-on-Code. Do **not** replicate this file into your target unless the task explicitly requires a library-check utility.

```python
# region MODULE_CONTRACT [DOMAIN(8): Environment, ML_libraries; CONCEPT(7): DependencyCheck, Introspection; TECH(9): PythonImport]
## @file check_ai_libs.py
## @brief Quick verification of expected AI/ML libraries in the runtime.
## @modulecontract
## @purpose Give the system a quick, safe way to verify that all expected AI/ML libraries are present in the runtime environment, preventing silent failures downstream.
## @scope System environment introspection, dependency checking.
## @input None (works with current Python environment).
## @output Dictionary with installation statuses of requested modules.
## @links [USES_API(8): importlib]
## @links_to_spec REQ-ENV-001
## @invariants
## - check_all_libraries ALWAYS returns a dictionary.
## - Dictionary ALWAYS contains all target libraries as keys.
## @rationale
## Q: Why use importlib.util.find_spec instead of direct import?
## A: Direct import halts on the first missing library. find_spec safely collects the full picture.
## @changes
## LAST_CHANGE: [v1.0.0 — Initial creation of system and ML library checker.]
## @modulemap
## FUNC 10[Checks presence of target AI libraries] => check_all_libraries
## @usecases
## - [check_all_libraries]: System (Startup) → VerifyEnvironmentDependencies → EnvironmentStatusReported
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: Environment, dependencies, AI libraries, system check, Python import, readiness, importlib, introspection
# STRUCTURE: ▶ Init ┌sys_libs + ml_libs┐ → ○ Loop ∋lib: 〈find_spec(lib) ? T/F〉 → ⊕ result_map[lib] → ∑ installed_count → ⎋ return ⟅lib: bool⟆

import logging
import importlib.util

logger = logging.getLogger(__name__)

# region FUNC_check_all_libraries [DOMAIN(7): Environment; CONCEPT(8): DependencyCheck, Introspection; TECH(9): importlib, find_spec]
## @purpose Enable the user or a supervising agent to confidently assess whether the Python environment is ready for AI/ML workloads by checking all required libraries in one shot.
## @uses importlib.util
## @io None -> dict
## @complexity 5
def check_all_libraries() -> dict:
    """⚡ Init ┌sys_libs + ml_libs┐ → ○ Loop ∋lib: 〈find_spec(lib) ? T/F〉 → ⊕ result_map[lib] → ∑ installed_count → ⎋ return ⟅lib: bool⟆"""
    system_libs = [
        "math", "random", "statistics", "decimal", "datetime", "time", "re",
        "os", "sys", "csv", "json", "sqlite3", "xml.etree.ElementTree",
        "configparser", "pickle", "base64", "hashlib", "collections",
        "itertools", "functools", "logging", "argparse", "typing", "uuid",
        "zipfile", "tarfile", "gzip", "zlib", "shutil", "tempfile"
    ]
    ml_libs = [
        "numpy", "pandas", "scipy", "sklearn", "matplotlib", "seaborn",
        "h5py", "openpyxl", "requests", "lxml", "PIL", "reportlab",
        "sympy", "dateutil", "pytz"
    ]
    all_libs = system_libs + ml_libs
    result_map = {}

    logger.debug(f"[IMP:4][check_all_libraries][INIT] Total libraries to check: {len(all_libs)} [INFO]")

    for lib_name in all_libs:
        try:
            spec = importlib.util.find_spec(lib_name)
            is_installed = spec is not None
            result_map[lib_name] = is_installed
            logger.debug(f"[IMP:3][check_all_libraries][CHECK] {lib_name}: {'found' if is_installed else 'missing'} [STATUS]")
        except Exception as e:
            # BUG_FIX_CONTEXT: ImportError replaced with Exception — find_spec can raise ValueError on malformed paths.
            result_map[lib_name] = False
            logger.critical(f"[IMP:10][check_all_libraries][CHECK] Failure for {lib_name}. Local: lib_name={lib_name}. Error: {e} [FATAL]")

    installed_count = sum(result_map.values())
    logger.info(f"[IMP:9][check_all_libraries][RESULT] Installed {installed_count}/{len(all_libs)} libraries. [VALUE]")
    return result_map
# endregion FUNC_check_all_libraries
```

## $END_MODIFICATION_AND_GENERATION
