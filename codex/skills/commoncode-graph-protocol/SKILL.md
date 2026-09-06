---
name: commoncode-graph-protocol
description: PROTOCOL for generating pre-code Conceptual Code Graphs in XML. Used exclusively inside DevelopmentPlan.md (DraftCodeGraph) as a design artifact — when the code does not yet exist. NOT used to produce post-code project graphs (AppGraph.xml is deprecated; post-code architecture is captured by Doxygen XML in target/doxygen_output/xml/).
---

# PROTOCOL: Pre-Code Conceptual Graph (XML)

**Scope (read first):**
This protocol applies to **pre-code design artifacts** only — the `DraftCodeGraph` block inside `DevelopmentPlan.md` produced by `commoncode-mode-architect`. At that moment the code does not yet exist, so Doxygen cannot index it; an explicit XML graph is the Architect's thinking tool.

**Out of scope (deprecated):** producing a post-code `AppGraph.xml` to summarize an already-implemented codebase. That role is replaced by Doxygen-generated XML reports under `<target>/doxygen_output/xml/` (created by `BUILD_DOXYGEN` in `commoncode-mode-code` Step 7). Do not write any `AppGraph.xml` artifact on disk during the flow.

**Objective:**
Provide a strict, parseable XML format for the Conceptual Code Graph the Architect drafts in advance — so subsequent phases (Code, QA) can read the design intent before any source file exists.

## General Graph Structure

1. Wrap the entire graph in a root `<DraftCodeGraph>` tag (matches the section name in `DevelopmentPlan.md`).
2. The first child element must describe the project as a whole (e.g., `<PROJECT_NAME_Version_Info>`).
3. It must contain global `keywords`, `terms`, and `annotation`, plus a `<BusinessScenarios>` section.

## Tag Naming Standards

1. **Uniqueness:** each tag name must be unique.
2. **Formatting:** replace dots (`.`) with underscores (`_`).
3. **Suffixes:** add `_py` (module), `_CLASS` (class), `_FUNC` (function), or `_METHOD` (method).
   - Example: `utils.load_data` -> `<utils_load_data_FUNC>`.
4. **Attributes:** use `FILE="..."` for modules and `NAME="..."` for other entities.

## Entity Structure

1. **TYPE Attribute:** mandatory (e.g., `DATA_PROCESSING_MODULE`, `IS_FUNCTION_OF_MODULE`).
2. **Child Elements:** `<keywords>`, `<terms>`, `<annotation>`.
3. **Hierarchy:** nest entities (module -> class -> method).
4. **Cross-Links:** use `<Link TARGET="Unique_Tag_Name" TYPE="RELATIONSHIP_TYPE" />`.
   - Types: `CALLS_FUNCTION`, `USES_API`, `READS_DATA_FROM`, etc.

## ONE-SHOT EXAMPLE (Abstract)

```xml
<DraftCodeGraph>
  <MyProject_1_0_0_Info TYPE="PROJECT_INFO">
    <keywords>Keywords, Examples</keywords>
    <annotation>Project purpose annotation.</annotation>
    <BusinessScenarios>
      <Scenario NAME="CoreAction">Actor -> Action -> Result</Scenario>
    </BusinessScenarios>
  </MyProject_1_0_0_Info>

  <core_logic_py FILE="src/core_logic.py" TYPE="DATA_PROCESSING_MODULE">
    <process_data_FUNC NAME="process_data" TYPE="BUSINESS_LOGIC">
      <annotation>Transforms input data.</annotation>
    </process_data_FUNC>
  </core_logic_py>

  <main_ui_py FILE="src/main_ui.py" TYPE="UI_MODULE">
    <on_click_handler_FUNC NAME="on_click_handler" TYPE="CONTROLLER">
      <CrossLinks>
        <Link TARGET="core_logic_py_process_data_FUNC" TYPE="CALLS_FUNCTION" />
      </CrossLinks>
    </on_click_handler_FUNC>
  </main_ui_py>

  <ProjectCrossLinks TYPE="MODULE_INTERACTIONS_OVERVIEW">
    <Link TARGET="main_ui_py" TYPE="ORCHESTRATES_FLOW" />
  </ProjectCrossLinks>
</DraftCodeGraph>
```

---

## Lifecycle and replacement

| Stage | Artifact | Producer | Consumer |
|-------|----------|----------|----------|
| Pre-code design | `<DraftCodeGraph>` block inside `DevelopmentPlan.md` | `commoncode-mode-architect` (Step 4 — DESIGN_AND_VALIDATE_SOLUTION) | Code phase, QA phase |
| Post-code architecture index | Doxygen XML at `<target>/doxygen_output/xml/` | `commoncode-mode-code` (Step 7 — BUILD_DOXYGEN, runs `doxygen Doxyfile` inside `<target>`) | All phases (navigation, dependency discovery) |

**Hard rule:** never write a standalone `AppGraph.xml` file as an artifact of the flow. Pre-code design lives **inside** the plan; post-code structure lives **inside** Doxygen output. Two stages, two homes — no third copy.
