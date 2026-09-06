---
name: version-test
description: Product version manager with custom versioning scheme vX.Y.Za. Runs pre-release checks (git clean, build, tests), validates everything is committed and pushed to master, then bumps the version index. Use when user says "version-test", "check version", "bump version", "release check", "version status", "update version".
---

# /version-test — Product Version Manager

You manage product versions using a custom versioning scheme and gate version bumps behind a full verification pipeline (git state, build, tests).

---

## VERSIONING SCHEME

Format: **`vX.Y.Za`**

```
v1.2.9a
│ │ ││
│ │ │└─ Sub-task letter (a, b, c, d, ...)
│ │ └── Task number within this minor version (1, 2, 3, ... N)
│ └──── Minor version: functional module milestones (increments after passing /version-test)
└────── Major version: fundamental product/engine changes (rare, manual decision)
```

### Version Components

| Component | Name | Increments when | Example transition |
|-----------|------|----------------|-------------------|
| **X** | Major | Fundamental product/engine redesign. Manual decision only. | v1.5.3b → v2.1.1a |
| **Y** | Minor | After `/version-test` passes all checks (build + tests + git clean + pushed to master) | v1.1.22b → v1.2.1a |
| **Z** | Task | New task started within current minor version | v1.2.1a → v1.2.2a |
| **letter** | Sub-task | Sub-division of a task (a=first part, b=second, etc.) | v1.2.3a → v1.2.3b |

### Bump Rules

**On `/version-test` success (minor bump):**
- Y increments by 1
- Z resets to 1
- Letter resets to a
- X stays the same
- Example: `v1.1.22b` → `v1.2.1a`

**On task increment (manual via `/version-test bump-task`):**
- Z increments by 1
- Letter resets to a
- Example: `v1.2.3c` → `v1.2.4a`

**On sub-task increment (manual via `/version-test bump-subtask`):**
- Letter advances to next (a→b, b→c, etc.)
- Example: `v1.2.3a` → `v1.2.3b`

**On major bump (manual via `/version-test bump-major`):**
- X increments by 1
- Y resets to 1
- Z resets to 1
- Letter resets to a
- Example: `v1.5.22b` → `v2.1.1a`

---

## VERSION STORAGE

Version is stored in TWO places for maximum traceability:

### 1. VERSION file (root of project)
```
v1.2.1a
```
Single line, no trailing newline. This is the source of truth read by the skill.

### 2. Git tag
After every version change, create a git tag:
```bash
git tag -a "v1.2.1a" -m "Release v1.2.1a"
```

Tags are NOT pushed automatically — the skill will ask the user whether to push tags.

---

## MODE DETECTION

Parse `the user request`:

| Input | Mode | Action |
|-------|------|--------|
| _(empty)_ or `test` | **Test & Bump Minor** | Run full verification pipeline. On success → bump minor version. |
| `status` | **Status** | Show current version, last 5 tags, uncommitted changes count |
| `bump-task` | **Bump Task** | Increment task number (Z): v1.2.3c → v1.2.4a |
| `bump-subtask` | **Bump Sub-task** | Advance sub-task letter: v1.2.3a → v1.2.3b |
| `bump-major` | **Bump Major** | Increment major version (with confirmation): v1.5.22b → v2.1.1a |
| `init vX.Y.Za` | **Initialize** | Create VERSION file and initial tag |
| `set vX.Y.Za` | **Force Set** | Manually set version to a specific value (with confirmation) |

---

## MODE: TEST & BUMP MINOR (default `/version-test`)

This is the main workflow. Runs a full verification pipeline before allowing a minor version bump.
**If build or tests fail — automatically launches Commoncode agents to diagnose and fix.**

### Step 1 — local file read Current Version

```bash
cat VERSION 2>/dev/null || echo "NO_VERSION_FILE"
```

If no VERSION file exists → ask user to initialize with `/version-test init v1.1.1a`.

Parse the version string into components: major (X), minor (Y), task (Z), subtask (letter).

### Step 2 — Pre-flight Checks

Display a checklist header:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VERSION TEST — v1.2.9a → v1.3.1a (target)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 3 — Run Verification Pipeline

Execute checks sequentially. Git checks (1-4) block immediately on failure — these require manual user action.
Build and test checks (5-6) trigger the **Commoncode Auto-Fix Pipeline** on failure (see Step 3.1).

**Check 1: Git — Clean Working Tree**
```bash
git status --porcelain
```
- PASS: empty output (no uncommitted changes)
- FAIL: list all dirty files, ask user to commit or stash → **STOP**

**Check 2: Git — Current Branch is master/main**
```bash
git branch --show-current
```
- PASS: `main` or `master`
- FAIL: report current branch, ask user to switch and merge → **STOP**

**Check 3: Git — All Commits Pushed**
```bash
git log origin/$(git branch --show-current)..HEAD --oneline
```
- PASS: empty output (no unpushed commits)
- FAIL: list unpushed commits, ask user to push → **STOP**

**Check 4: Git — Remote is Up to Date**
```bash
git fetch origin --dry-run 2>&1
```
- PASS: no new remote commits to pull
- FAIL: warn about diverged branches → **STOP**

**Check 5: Build — Project Compiles**

Auto-detect build system and run:
```bash
# Detection order:
if [ -f "package.json" ]; then
    npm run build 2>&1 || yarn build 2>&1 || pnpm build 2>&1
elif [ -f "Cargo.toml" ]; then
    cargo build --release 2>&1
elif [ -f "go.mod" ]; then
    go build ./... 2>&1
elif [ -f "Makefile" ]; then
    make build 2>&1
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
    python -m py_compile $(find . -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" | head -20) 2>&1
else
    echo "SKIP: No build system detected"
fi
```
- PASS: exit code 0
- FAIL: capture full error output → **proceed to Step 3.1 (Commoncode Auto-Fix)**

**Check 6: Tests — All Pass**

Auto-detect test runner and run:
```bash
if [ -f "package.json" ]; then
    npm test 2>&1 || yarn test 2>&1
elif [ -f "Cargo.toml" ]; then
    cargo test 2>&1
elif [ -f "go.mod" ]; then
    go test ./... 2>&1
elif [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
    pytest 2>&1
elif [ -f "Makefile" ]; then
    make test 2>&1
else
    echo "SKIP: No test runner detected"
fi
```
- PASS: exit code 0
- FAIL: capture full error output → **proceed to Step 3.1 (Commoncode Auto-Fix)**

### Step 3.1 — Commoncode Auto-Fix Pipeline (on Build/Test failure)

When Check 5 or Check 6 fails, **do NOT simply stop**. Instead, ask the user:

```
⚠️  Build/Tests failed. Launch Commoncode agents to diagnose and fix?
```

Via `plain question to the user`:

| Option | Action |
|--------|--------|
| **Auto-fix with Commoncode (Recommended)** | Launch full Commoncode debug → fix → verify pipeline (see below) |
| **Fix manually** | Show errors, STOP. User fixes on their own and re-runs `/version-test` |

**If user chooses Auto-fix — execute the Commoncode pipeline:**

**Phase 1: DEBUG — Root cause analysis**

Load and follow `~/.codex/skills/commoncode-mode-debug/SKILL.md` with the build/test error output as context.

The debug agent will:
1. Analyze the full error log (build errors, stack traces, test failures)
2. Trace errors to source files using LDD log markers (`[FUNCTION_NAME][BLOCK_NAME]`)
3. Identify root cause for each failure
4. Generate a structured Bug Report with:
   - Error classification (build error / test failure / type error / runtime error)
   - Affected files and functions (with exact paths)
   - Root cause analysis
   - Proposed fix strategy

**Phase 2: CODE — Apply fixes**

Load and follow `~/.codex/skills/commoncode-mode-code/SKILL.md` with the Bug Report as input.

The code agent will:
1. Apply fixes following Commoncode semantic markup:
   - `# BUG_FIX_CONTEXT: [why old approach failed, why this fix]` inline annotations
   - Update `# START_CHANGE_SUMMARY` in modified files
   - Maintain `# MODULE_MAP` consistency
2. Write fixes with SFT-priming (docstring before code changes)
3. Add/update tests covering the fixed issue
4. Verify LDD logs at `IMP:7+` for boundary operations

**Phase 3: RE-VERIFY — Run checks again**

After fixes are applied:
1. Re-run the failed check (build or tests)
2. If PASS → commit fixes:
   ```bash
   git add -A
   git commit -m "fix(vX.Y.Za): [brief description of what was fixed]"
   ```
3. If FAIL again → **escalation loop** (max 3 attempts):

**Escalation loop (max 3 iterations):**

| Attempt | Action |
|---------|--------|
| 1 | Re-run `~/.codex/skills/commoncode-mode-debug/SKILL.md` with new error output. Apply fix. Re-verify. |
| 2 | Load `~/.codex/skills/commoncode-mode-debug/SKILL.md` with accumulated context from attempts 1-2. Apply fix. Re-verify. |
| 3 | **STOP.** Display all errors and attempted fixes. Ask user: "3 auto-fix attempts failed. Please review manually and re-run `/version-test`." |

**Anti-Loop protection:** Track attempts via `.test_counter.json` (Commoncode convention):
```json
{"version_test_attempts": 2, "last_error": "TypeError: Cannot read property..."}
```
Reset to 0 on success. At attempt 3+: warn about loop risk.

**Phase 4: QA — Independent verification (optional)**

If `tests/test_guide.md` exists after fixes, load and follow `~/.codex/skills/commoncode-mode-qa/SKILL.md` for independent verification:
1. QA agent runs tests independently
2. Verifies semantic markup integrity (MODULE_CONTRACT, MODULE_MAP)
3. Checks LDD log coverage
4. Produces structured QA Report
5. If QA finds issues → back to Phase 1 (within the 3-attempt limit)

**After successful auto-fix:** Resume the verification pipeline from where it left off.
- If build was fixed → proceed to Check 6 (tests)
- If tests were fixed → proceed to Step 4 (report results)

### Step 4 — Report Results

Display a full report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VERSION TEST RESULTS — v1.2.9a
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Check 1: Clean working tree
  ✅ Check 2: On master branch
  ✅ Check 3: All commits pushed
  ✅ Check 4: Remote up to date
  ✅ Check 5: Build passes
  ✅ Check 6: Tests pass

  ALL CHECKS PASSED (6/6)

  Commits since last version tag (v1.2.1a):
    - abc1234 feat(v1.1.5a): notification system
    - def5678 fix(v1.1.4a): email template path
    - ghi9012 test(v1.1.5a): add notification tests

  Version bump: v1.2.9a → v1.3.1a
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If auto-fix was used, append:
```
  🔧 Auto-fix applied:
    - fix(v1.2.9a): resolved TypeScript strict null check in auth service
    - fix(v1.2.9a): updated test mock for new API response format
    Attempts: 1/3
```

If git checks failed (no auto-fix available):
```
  ❌ Check 3: Unpushed commits
     → 2 commits not pushed to origin/main
     → Run: git push origin main

  BLOCKED: Fix the issues above and re-run /version-test
```

### Step 5 — Bump Version (on all checks passed)

Ask user for confirmation via `plain question to the user`:
```
Version bump: v1.2.9a → v1.3.1a
Proceed?
- Yes, bump version
- No, cancel
```

On confirmation:

1. **Update VERSION file:**
   Write the new version string to the VERSION file in the project root.

2. **Also update package.json** (if it exists):
   Update the `"version"` field to match (without the `v` prefix and letter suffix, adapted to semver: `1.3.1`). Only do this if package.json exists and has a version field.

3. **Commit the version bump:**
   ```bash
   git add VERSION
   git add package.json  # if updated
   git commit -m "chore(release): bump version to v1.3.1a"
   ```

4. **Create git tag:**
   ```bash
   git tag -a "v1.3.1a" -m "Release v1.3.1a — minor version bump after verification"
   ```

5. **Ask about pushing:**
   Via `plain question to the user`:
   - Push commit + tag to remote now
   - Push commit only (tag later)
   - Don't push (I'll do it manually)

   If push requested:
   ```bash
   git push origin main
   git push origin "v1.3.1a"  # if tag push requested
   ```

6. **Display confirmation:**
   ```
   ✅ Version bumped: v1.2.9a → v1.3.1a
   ✅ VERSION file updated
   ✅ Git tag v1.3.1a created
   ✅ Commit: chore(release): bump version to v1.3.1a
   ```

---

## MODE: STATUS

Show version dashboard:

1. local file read current VERSION file
2. List last 5 git tags matching `v*` pattern:
   ```bash
   git tag --sort=-version:refname -l "v*" | head -5
   ```
3. Count commits since last tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline | wc -l
   ```
4. Show uncommitted changes count
5. Show current branch

Output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VERSION STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Current:  v1.2.9a
  Branch:   main
  Clean:    ✅ (no uncommitted changes)
  Pushed:   ✅ (up to date with remote)

  Recent tags:
    v1.2.9a   ← current
    v1.2.8a
    v1.2.7b
    v1.2.7a
    v1.1.22b

  Commits since v1.2.9a: 3
    - abc1234 feat: new feature
    - def5678 fix: bug fix
    - ghi9012 docs: readme
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## MODE: BUMP-TASK

Increment the task number (Z), reset sub-task letter to `a`.

1. local file read VERSION: `v1.2.3c`
2. Compute new: `v1.2.4a`
3. Ask confirmation
4. Update VERSION file
5. Commit: `chore(version): bump task to v1.2.4a`
6. Create git tag `v1.2.4a`

No verification pipeline — this is a lightweight bump for starting a new task within the current minor version.

---

## MODE: BUMP-SUBTASK

Advance the sub-task letter by one position.

1. local file read VERSION: `v1.2.3a`
2. Compute new: `v1.2.3b`
3. Ask confirmation
4. Update VERSION file
5. Commit: `chore(version): bump subtask to v1.2.3b`
6. Create git tag `v1.2.3b`

No verification pipeline — lightweight bump for sub-task progression.

Letter sequence: a → b → c → d → e → f → g → h → i → j → k → l → m → n → o → p → q → r → s → t → u → v → w → x → y → z

If current letter is `z` → warn user that sub-task limit reached, suggest bumping task instead.

---

## MODE: BUMP-MAJOR

Major version bump — fundamental product/engine change. **Requires explicit confirmation.**

1. local file read VERSION: `v1.5.22b`
2. Compute new: `v2.1.1a` (X+1, Y=1, Z=1, letter=a)
3. Show warning:
   ```
   ⚠️  MAJOR VERSION BUMP
   This signifies a fundamental product/engine change.
   v1.5.22b → v2.1.1a

   Are you absolutely sure?
   ```
4. On confirmation → run the FULL verification pipeline (same as default mode)
5. On all checks passed → update VERSION, commit, tag

---

## MODE: INIT

Initialize versioning for a new project.

Parse the version from arguments: `/version-test init v1.1.1a`

1. Check that VERSION file doesn't already exist
2. If it exists → warn and ask to overwrite or cancel
3. Create VERSION file with the specified version
4. Commit: `chore(version): initialize versioning at v1.1.1a`
5. Create git tag
6. Display confirmation

If no version specified in arguments → default to `v1.1.1a`.

---

## MODE: SET (Force Set)

Manually override the version to a specific value.

1. Parse target version from arguments: `/version-test set v2.3.5c`
2. Validate format matches `vX.Y.Za` pattern
3. Show current → target, ask confirmation
4. Update VERSION file
5. Commit: `chore(version): force set version to v2.3.5c`
6. Create git tag

---

## VERSION PARSING

To parse a version string like `v1.2.9a`:

```
Regex: ^v(\d+)\.(\d+)\.(\d+)([a-z])$

Groups:
  1 → major (X): 1
  2 → minor (Y): 2
  3 → task  (Z): 9
  4 → subtask:   a
```

Validation rules:
- Must start with `v`
- X, Y, Z must be positive integers
- Letter must be a single lowercase a-z
- Invalid format → show error with expected format

---

## ERROR HANDLING

| Error | Action |
|-------|--------|
| No VERSION file | Ask user to run `/version-test init` |
| Invalid version format | Show correct format `vX.Y.Za`, ask to fix |
| Not in a git repo | Tell user to initialize git first |
| Not on master/main | Show current branch, ask to switch |
| Uncommitted changes | List dirty files, ask to commit |
| Build fails | Show errors, STOP, do not bump |
| Tests fail | Show failures, STOP, do not bump |
| Unpushed commits | Ask to push first |
| Tag already exists | Append timestamp or ask user to resolve |

---

## INTEGRATION WITH ULTRAPROMPT

`/ultraprompt` uses the same `vX.Y.Za` versioning for all tasks (no more "phase-N").

- Each `/ultraprompt` task is identified by its version: `v1.1.1a`, `v1.1.2a`, etc.
- After each task completion in `/ultraprompt run` → `/version-test bump-task` to increment task number
- After each sub-task within a task → `/version-test bump-subtask`
- After all tasks of a minor version are done → `/version-test` (full pipeline) to bump minor
- GitHub Issues use `[vX.Y.Za]` prefix in titles instead of `[PHASE N]`
- Commits use `feat(vX.Y.Za):` format instead of `feat(phase-N):`

Recommended workflow:
```
/ultraprompt <project>
  → Creates tasks: v1.1.1a, v1.1.2a, v1.1.3a...

/ultraprompt run
  → Task v1.1.1a starts  → complete → /version-test bump-task    → v1.1.2a
  → Task v1.1.2a starts  → subtask  → /version-test bump-subtask → v1.1.2b
  → Task v1.1.2b done    → complete → /version-test bump-task    → v1.1.3a
  → ...
  → All tasks done        → /version-test (full pipeline)         → v1.2.1a ✅
```
