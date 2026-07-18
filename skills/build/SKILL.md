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

### Dispatch discipline

- Strictly one build-runner at a time: never dispatch a new agent while a previous one has not returned its result — including chains like `ktlintFormat` → retry build.
- If an agent returns while its build is still running in the background (protocol violation or agent death), do not dispatch a new build right away: tell the user, and treat the next failure as an INFRASTRUCTURE FAILURE with a live lock owner (run the Daemon Recovery Procedure below before any retry).
- If the user changes or refines the request while a build-runner is working, wait for its report first, then dispatch a new agent with the updated task.

### Step 2: Handle agent result

(All build-runner dispatches below use the Task tool with `subagent_type: "claude-forge:build-runner"`.)

**Success** — report success, show build time

**INFRASTRUCTURE FAILURE** (lock timeout / daemon problem / orphaned background build, reported by the agent) —
1. Recommended Action `safe to retry` (lock owner dead) — dispatch one retry immediately.
2. Recommended Action `run daemon recovery procedure first` (lock owner alive, or an orphaned background build) — run the Daemon Recovery Procedure below, then dispatch ONE retry.
3. If the retry fails with another INFRASTRUCTURE FAILURE — stop and report to the user; do not loop.
4. Malformed report (INFRASTRUCTURE FAILURE without a recognizable Recommended Action) — treat as BUILD FAILED; never run daemon recovery on uncertain grounds.

**User reports a stuck/hung Gradle build** — run the Daemon Recovery Procedure directly; it does not require a prior agent report.

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

## Daemon Recovery Procedure

Run in the MAIN session — the build-runner agent must never kill daemons. The commands below (`./gradlew --stop`, `jps`, `ps`, `kill`, `jstack`, `sleep`) are recovery commands, not build/test/lint commands: the "always delegate to build-runner" rule does NOT apply to them — run them directly, never dispatch them to build-runner. Use when an INFRASTRUCTURE FAILURE report says the lock owner is alive (or reports an orphaned background build), or when the user reports a stuck build:

1. Run `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'` and note the list (to compare after `--stop`).
2. Run `./gradlew --stop` in the project directory. This sends a graceful stop request to EVERY Gradle daemon of this Gradle version on the host — daemons of other projects and IDEs on the same version included (the daemon is shared by version, not by project). Graceful means a busy daemon finishes its current build before stopping; the only cost to a neighbor is a cold start next time. This is acceptable during recovery: a hung daemon holding a global `~/.gradle` lock already blocks every same-version build sharing it. A hung daemon also does not acknowledge the stop request, so `--stop` can run for minutes — give the call a generous explicit timeout (600000 ms), and if it is moved to the background anyway, do not wait for it: proceed to step 3 (steps 3–4 deal with the unresponsive owner directly). On a shared multi-project host where you would rather not disturb other daemons — and the report names an owner PID — skip `--stop` and go straight to the identity-checked owner kill in steps 3–4. If the project has no `gradlew` wrapper, skip this step.
3. Target ONLY the lock owner from the agent's report: run `ps -o pid,stat,args -p <owner pid>` and confirm it is still a Gradle/Kotlin daemon (guards against PID reuse; the command line does not reveal which project owns it). If it belongs to another project, an IDE, or another session — do NOT kill it; report to the user and ask. If the report has no owner PID (orphaned background build, manual trigger) — skip steps 3–4: `--stop` plus the pause usually suffices, and a persisting hang will surface a lock owner on the retry.
4. If confirmed and still alive: `kill <owner pid>`; run `sleep 15`; if it survives — `kill -9 <owner pid>`.
5. Run `sleep 20` before retrying — a cancelled daemon is not reused, and an instant retry spawns extra cold daemons.
6. Dispatch ONE retry via build-runner. The retry will be slow (cold Gradle and Kotlin daemons) — slow is not hung. If it fails with ANOTHER live lock owner: repeat the identity check from step 3 for the new PID once, then stop — report to the user instead of looping. If it hangs again: find the daemon PID via `jps` and capture `jstack <pid> | head -200`, then report to the user.

## Limitations
- Maximum 4 build runs total per skill invocation: up to 3 attempts on build/code errors plus at most 1 retry after an INFRASTRUCTURE FAILURE. Auto-fix commands (`ktlintFormat`, `ruff check --fix .`) do not count as build runs.
- Dispatch is strictly sequential — one build-runner at a time. This protects against self-duplication only: other Claude sessions, IDEs and terminals still share `~/.gradle`.
- Never dispatch long-running/watch commands (`bootRun`, `--continuous`, dev servers) to build-runner — they never finish and break the wait protocol.
- No dispatch timeout: if build-runner itself hangs (harness/model error), the skill cannot detect it — known limitation.
- Each run — new agent with clean context

## Output format
Use format from build-runner agent:
- BUILD SUCCESSFUL + time
- BUILD FAILED + error details
- INFRASTRUCTURE FAILURE + cause, details, recommended action (handled per Step 2)
