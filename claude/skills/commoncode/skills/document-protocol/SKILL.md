---
name: document-protocol
description: STRUCTURAL PROTOCOL for project documentation. Mandatory for generating all structured AI-friendly documents (requirements, specifications, etc.). Loaded by mode-architect during document generation.
---

# STRUCTURAL PROTOCOL: AI-Friendly Project Documentation

**Objective:**
Optimize document structure for agentic context windows and hierarchical reasoning. This protocol ensures logic integrity through semantic context switches and explicit intent definition.

## Part 1 — Rationale

This protocol uses three key mechanisms to guide AI reasoning:
1. **Top-Down Detailization:** mandatory `$DOCUMENT_PLAN` to create a skeleton before detailing.
2. **Semantic Context Switchers:** use `$START_...` / `$END_...` tags to focus attention.
3. **Intent Definition:** explicit `$CONTRACT` for every artifact (`PURPOSE`, `RATIONALE`, `ACCEPTANCE_CRITERIA`).

## Part 2 — Document Template

$START_DOC_NAME

**PURPOSE:** [Primary purpose and scope of the document]
**SCOPE:** [Areas covered by the document]
**KEYWORDS:** [Knowledge domains and patterns]

$START_DOCUMENT_PLAN
### Document Plan
<!--
AI-Agent: Generate this entire block before expanding sections.
Format: TYPE [Description] => [Artifact_ID]
-->

**SECTION_GOALS:**
- GOAL [Goal description] => [GOAL_ID]

**SECTION_USE_CASES:**
- USE_CASE [Scenario description] => [SCENARIO_ID]

$END_DOCUMENT_PLAN

$START_SECTION_NAME
### [Section Name]

$START_ARTIFACT_NAME
#### [Artifact Name]

**TYPE:** [GOAL | KEY_RESULT | USE_CASE | PRINCIPLE | DECISION | TOOL | DATA_FORMAT | NFR]
**KEYWORDS:** [Knowledge domains and patterns]

$START_CONTRACT
**PURPOSE:** [WHAT does the artifact do?]
**DESCRIPTION:** [Detailed description. Use AAG notation for USE_CASE.]
**RATIONALE:** [WHY is this artifact important/chosen?]
**ACCEPTANCE_CRITERIA:** [How do we verify correct implementation?]
$END_CONTRACT

$START_BODY
<!-- Specific artifact body. -->
$END_BODY

$START_LINKS
**IMPLEMENTS:** [ID of another artifact]
**IMPACTS:** [ID of another artifact]
**REQUIRES:** [ID of another artifact]
$END_LINKS

$END_ARTIFACT_NAME

$END_SECTION_NAME

$END_DOC_NAME
