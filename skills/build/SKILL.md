---
name: build
description: "Run build/test/lint tasks for JVM (Gradle, Maven), Node.js (npm, yarn, pnpm, bun), Go (go, golangci-lint, make), or Python (pytest, ruff, mypy, uv, poetry) by dispatching build-runner agent. NEVER run build tools directly — always delegate."
---

# Build

Run build, test, or lint tasks by dispatching the **build-runner** agent.

## Protocol

### Step 1: Dispatch build-runner agent

Launch the `build-runner` agent via the Task tool with `subagent_type: "claude-forge:build-runner"`.

Pass the user's requested task in the prompt. Examples:

**JVM projects:**
- User says "build" → prompt: "Run ./gradlew build"
- User says "build debug APK" → prompt: "Run ./gradlew assembleDebug"
- User says "build release AAB" → prompt: "Run ./gradlew bundleRelease"
- User says "run tests" → prompt: "Run ./gradlew test"
- User says "run lint" → prompt: "Run ./gradlew lintDebug"

**Node.js projects:**
- User says "build" → prompt: "Run build"
- User says "run tests" → prompt: "Run tests"
- User says "run lint" → prompt: "Run lint"
- User says "npm test" → prompt: "Run npm test"
- User says "bun test" → prompt: "Run bun test"
- User says "type check" (Vue project) → prompt: "Run npx vue-tsc --noEmit"

**Go projects:**
- User says "build" → prompt: "Run go build ./..."
- User says "run tests" → prompt: "Run go test ./..."
- User says "run lint" → prompt: "Run golangci-lint run"
- User says "run vet" → prompt: "Run go vet ./..."
- User says "make build" → prompt: "Run make build"

**Python projects:**
- User says "run tests" → prompt: "Run pytest"
- User says "run lint" → prompt: "Run ruff check ."
- User says "run type check" → prompt: "Run mypy ."
- User says "pytest -k test_foo" → prompt: "Run pytest -k test_foo"
- User says "tox" → prompt: "Run tox"

**Unknown project type or generic request:**
- User says "build" (no obvious stack) → prompt: "Build the project"
- User says "run tests" (no obvious stack) → prompt: "Run tests"

The agent will auto-detect the project stack. If you know the stack from context, include it in the prompt for faster execution.

**Do not run ANY build/test/lint/type-check command directly — always delegate to build-runner agent. This includes not only the tools listed above, but also vue-tsc, tsc, eslint, prettier, cargo, and any other command whose purpose is building, testing, linting, or verifying code.**

### Step 2: Handle agent result

(All build-runner dispatches below use the Task tool with `subagent_type: "claude-forge:build-runner"`.)

**Success** — report success, show build time

**Ktlint errors** (gradle-android, gradle-kotlin) —
1. Dispatch new build-runner agent with `./gradlew ktlintFormat`
2. If fixed — dispatch build-runner agent again to retry build
3. If not fixed — show remaining errors

**Checkstyle/style errors** (gradle-java) —
1. Show style violations
2. Do not attempt to auto-fix

**Compilation errors** (all stacks) — show errors, do not attempt to fix

**Test failures** (all stacks) — show failed tests with reason

**Dependency issues** (go) — suggest `go mod tidy`

**Lint errors** (golangci-lint) — show violations, do not attempt to auto-fix

**Dependency issues** (python) — suggest install command for detected package manager

**Lint errors** (ruff) —
1. Dispatch new build-runner agent with `ruff check --fix .`
2. If fixed — dispatch build-runner agent again to retry lint
3. If not fixed — show remaining errors

**Type errors** (mypy/pyright) — show errors, do not attempt to fix

**Mixed project detected** — report to user that multiple stacks were found, ask which to build

## Limitations
- Maximum 3 build attempts
- Each run — new agent with clean context

## Output format
Use format from build-runner agent:
- BUILD SUCCESSFUL + time
- BUILD FAILED + error details
