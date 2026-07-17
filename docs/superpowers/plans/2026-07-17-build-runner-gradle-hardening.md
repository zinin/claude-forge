# Build-runner Gradle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить «зависания» Gradle-сборок через build-runner: дисциплина таймаутов, протокол фоновых сборок, диагностика инфраструктурных сбоев, процедура восстановления демонов.

**Architecture:** Четыре правки маркдаун-конфигурации: агент `build-runner` получает правила исполнения (timeout, одна сборка за раз, протокол «moved to background») и формат INFRASTRUCTURE FAILURE; скилл `build` — последовательную диспетчеризацию и процедуру восстановления демонов (выполняет главная сессия); README — секцию настроек хоста; CHANGELOG — запись. Код не меняется — только инструкции агента/скилла.

**Tech Stack:** Markdown-файлы плагина Claude Code (frontmatter агента, SKILL.md), git.

**Spec:** `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`

## Global Constraints

- Тексты файлов плагина — на английском, в стиле существующих секций. Кириллицы в `agents/`, `skills/`, `README.md`, `CHANGELOG.md` быть не должно.
- Ветка: `build-runner-hardening` (уже создана и активна). Рабочая директория: `/opt/github/zinin/claude-forge`.
- `docs/gradle-build-runner-hardening-report.md` — untracked, НЕ коммитить; остаётся локальным архивом (после мержа можно удалить). `.gitignore` сознательно не трогаем — личный локальный файл не должен попадать в публичный репозиторий. В `git add` передавать только явные пути файлов, никогда `git add docs/`, `git add -A` или `git commit -am`.
- Агенту build-runner добавляются ТОЛЬКО инертные инструменты: read-only диагностика `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)` и пейсинг ожидания `Bash(sleep:*)`. Никакого `kill` в tools агента.
- Каждое сообщение коммита заканчивается трейлером (отдельной строкой после пустой):
  `Claude-Session: <URL текущей сессии-исполнителя — по правилу харнеса; НЕ переиспользовать URL из этого документа>`
- Метки `INFRASTRUCTURE FAILURE`, `Daemon Recovery Procedure`, `safe to retry` совпадают в обоих файлах дословно. Метка `run daemon recovery procedure first (see build skill)` пишется полностью в отчёте агента; скилл матчит её по префиксу `run daemon recovery procedure first` (хвост «(see build skill)» внутри самого скилла — самоссылка, опускается сознательно). Агенту предписано метки не перефразировать.
- Перед созданием PR (этап finishing, НЕ эти таски): `git rm -r docs/superpowers/` и отдельный коммит — plan/design/review-документы не должны попасть в PR diff (правило пользователя).
- Тестов/сборки в репо нет — верификация каждой правки: `grep` с ожидаемым выводом + вычитка; поведенческие смоук-тесты — до мержа через `claude --plugin-dir` (Task 4).

---

### Task 1: `agents/build-runner.md` — модель, инструменты, правила исполнения, инфра-сбои

**Files:**
- Modify: `agents/build-runner.md`

**Interfaces:**
- Produces: формат отчёта `INFRASTRUCTURE FAILURE` с полями `## Cause`, `## Details`, `## Recommended Action`; значения Recommended Action — дословно `safe to retry` либо `run daemon recovery procedure first (see build skill)`. Task 2 (SKILL.md) обрабатывает именно эти строки.

- [ ] **Step 1: Frontmatter — модель и инструменты**

В `agents/build-runner.md` заменить (Edit, две правки):

Старое:
```
model: haiku
```
Новое:
```
model: sonnet
```

Старое (фрагмент строки tools):
```
Bash(tox:*), Glob, Grep, Read
```
Новое:
```
Bash(tox:*), Bash(jps:*), Bash(jstack:*), Bash(ps:*), Bash(sleep:*), Glob, Grep, Read
```

- [ ] **Step 2: Вставить секцию «Execution Rules (All Stacks)» после Step 0**

Старое:
```
If the task is generic (e.g., "build", "test", "run tests"), proceed to Step 1 to detect the project stack.

## Step 1: Detect Project Stack
```

Новое:
```
If the task is generic (e.g., "build", "test", "run tests"), proceed to Step 1 to detect the project stack.

## Execution Rules (All Stacks)

These rules apply to EVERY build/test/lint command you run — including exact commands passed by the caller in Step 0:

1. **Always set an explicit timeout.** Every Bash call that runs a build/test/lint command — or any other potentially long-running command, including dependency installs (`npm install`, `uv sync`, `poetry install`) — MUST pass `timeout: 600000` (10 minutes). Never rely on the default 120-second timeout — a typical build exceeds it and gets moved to the background mid-run.
2. **One build at a time.** Never start a new build/test/lint command while a previous one is still running — including a command that was moved to the background. Overlapping builds contend for global cache locks and spawn extra daemons.
3. **If a command is moved to the background** (message like `Command did not complete within its 600s timeout and was moved to the background (ID: ...)`):
   - Do NOT re-run the command.
   - Poll instead of re-reading: run `sleep 30`, then Grep the task output file (its path is given in the background notification) for `BUILD SUCCESSFUL|BUILD FAILED|FAILURE:`; repeat the cycle. A completion notification may also arrive between tool calls — treat it as a bonus, not the mechanism.
   - When a completion marker appears, Read the tail of the output file (offset near the end) and report the actual final result — never a guess.
   - Do not end your turn while the build is running and the wait budget below is not exhausted.
   - **Wait budget:** if the build is still running after ~20 minutes of polling, or the output file has not grown for ~10 minutes, stop waiting and report INFRASTRUCTURE FAILURE with Cause `orphaned background build` and Recommended Action `run daemon recovery procedure first (see build skill)` — include the background task ID and the output file path in Details.
4. **Gradle: append `--console=plain` to every `./gradlew` invocation** — including exact commands passed by the caller (unless the caller already passed a `--console` option). Stable non-interactive output for log parsing.
5. **Never manage build daemons yourself.** Do not run `gradlew --stop`, do not kill processes, never delete `*.lock` files. Diagnose and report (see Infrastructure Failures); recovery is the caller's decision.
6. **Ignore daemon registry DEBUG noise.** DEBUG-level lines like `Waiting to acquire shared lock on daemon addresses registry` are routine polling, not errors — do not report them as problems. (An ERROR-level `Timeout waiting to lock daemon addresses registry` IS an infrastructure failure — see Infrastructure Failures.)
7. **If command output is truncated,** locate the root cause in the task output file via Grep/Read — do not assume the visible tail is the cause.

## Step 1: Detect Project Stack
```

- [ ] **Step 3: Неинтерактивный вывод — `--console=plain` (Gradle) и `-B` (Maven)**

Старое:
````
### Build Commands

Standard build:
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew build
```

Without tests (only if explicitly requested):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew build -x test
```

Clean build (if caching issues suspected):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew clean build
```
````

Новое:
````
### Build Commands

Append `--console=plain` to every Gradle invocation — stable non-interactive output for log parsing.

Standard build:
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew build --console=plain
```

Without tests (only if explicitly requested):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew build -x test --console=plain
```

Clean build (if caching issues suspected):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && ./gradlew clean build --console=plain
```
````

Вторая правка — примеры маппинга в Step 0 тоже несут флаг (иначе они противоречат Execution Rule 4):

Старое:
```
Examples (JVM):
- "build the project" → `./gradlew build`
- "assemble debug APK" → `./gradlew assembleDebug`
- "build release AAB" → `./gradlew bundleRelease`
- "run tests" → `./gradlew test`
- "run lint" → `./gradlew lintDebug`
- "run ktlintFormat" → `./gradlew ktlintFormat`
```
Новое:
```
Examples (JVM):
- "build the project" → `./gradlew build --console=plain`
- "assemble debug APK" → `./gradlew assembleDebug --console=plain`
- "build release AAB" → `./gradlew bundleRelease --console=plain`
- "run tests" → `./gradlew test --console=plain`
- "run lint" → `./gradlew lintDebug --console=plain`
- "run ktlintFormat" → `./gradlew ktlintFormat --console=plain`
```

Третья правка — Maven-симметрия (`-B`/batch mode — тот же мотив стабильного неинтерактивного вывода):

Старое:
````
### Build Commands

Standard build with tests:
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn clean package
```

Without tests (only if explicitly requested):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn clean package -DskipTests
```

Compile only (quick syntax check):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn compile
```
````
Новое:
````
### Build Commands

Append `-B` (batch mode) to every Maven invocation — stable non-interactive output for log parsing.

Standard build with tests:
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn -B clean package
```

Without tests (only if explicitly requested):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn -B clean package -DskipTests
```

Compile only (quick syntax check):
```bash
export JAVA_HOME=/usr/lib/jvm/zulu<VERSION> && mvn -B compile
```
````

(Примечание: в файле это обычные ```bash-блоки; при Edit брать old_string дословно из файла.)

- [ ] **Step 4: Подраздел «Infrastructure Failures (Gradle)» перед Maven-секцией**

Старое:
```
- Check `settings.gradle.kts` for project structure if needed
- Report which specific module(s) failed

---

## Maven Stack (maven-java)
```

Новое:
```
- Check `settings.gradle.kts` for project structure if needed
- Report which specific module(s) failed

### Infrastructure Failures (Gradle)

Environment problems are reported differently from code problems (INFRASTRUCTURE FAILURE format below) and are retried differently by the caller. **If unsure whether a failure is infrastructure or code, classify it as BUILD FAILED** — never steer the caller toward daemon recovery on uncertain grounds.

If the build fails with `Timeout waiting to lock <cache> (...). It is currently in use by another Gradle instance. Owner PID: <X>`:

1. Run `ps -fp <X>` to check whether the owning process is alive and what it is (the args column shows the daemon and its project).
2. If useful, capture `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'` (live-daemon snapshot) and, for a live owner, `jstack <X> | head -200`; include the relevant lines in Details. If `jps`/`jstack` are not on PATH, skip them and note that in Details.
3. Report INFRASTRUCTURE FAILURE:
   - Owner PID **dead** or a **zombie** (`Z` state — it no longer holds the lock) → Recommended Action: `safe to retry` (stale locks recover automatically once the owner is gone).
   - Owner PID **alive** → Recommended Action: `run daemon recovery procedure first (see build skill)` — likely a hung daemon holding a global lock.
   - Owner PID **absent from the message**, or `ps` fails → report a regular BUILD FAILED with the key log lines; do not guess.

Other daemon signatures to report as INFRASTRUCTURE FAILURE with Recommended Action `safe to retry`:
- `Gradle build daemon disappeared unexpectedly` (daemon crash or OOM kill)
- `Could not connect to the Gradle daemon`
- `Daemon was stopped to free memory`
- ERROR-level `Timeout waiting to lock daemon addresses registry`

False friends — these are CODE problems, report BUILD FAILED: `Execution failed for task ':...'`, `Could not determine the dependencies of task ...`, `Could not resolve all files for configuration ...` (dependency/network issue, not a daemon problem).

For non-Gradle stacks there is no infrastructure detection yet — report their failures as regular BUILD FAILED.

Never add `--no-daemon`: it does not prevent lock contention and contradicts current Gradle guidance (the daemon is recommended for CI and developer machines alike).

---

## Maven Stack (maven-java)
```

- [ ] **Step 5: Формат INFRASTRUCTURE FAILURE в «Error Reporting Format»**

Старое:
````
## Recommended Actions
1. [First suggested fix]
2. [Second suggested fix if applicable]
```

## Important Guidelines
````

Новое:
````
## Recommended Actions
1. [First suggested fix]
2. [Second suggested fix if applicable]
```

### On Infrastructure Failure (environment problem, not code):
```
INFRASTRUCTURE FAILURE

## Cause
[lock timeout | orphaned background build | other environment issue]

## Details
[Lock file / cache name; Owner PID, its state (alive/dead/zombie) and what it is (ps -fp args); key log lines; jps snapshot if captured]

## Background Task ID (if applicable)
[background task ID and output file path of a build still running]

## Recommended Action
[safe to retry | run daemon recovery procedure first (see build skill)]
```

Use the two Recommended Action phrases verbatim — do not paraphrase them; the calling skill matches on these strings.

## Important Guidelines
````

- [ ] **Step 6: Дополнить Important Guidelines пунктами 13–14**

Старое:
```
12. **For Python lint issues** (ruff/flake8/pylint): Report violations. Mention that `ruff check --fix .` can auto-fix some ruff violations.
```

Новое:
```
12. **For Python lint issues** (ruff/flake8/pylint): Report violations. Mention that `ruff check --fix .` can auto-fix some ruff violations.
13. **Never re-run a build that was moved to the background** — poll per the Execution Rules and report its actual result; if the wait budget is exhausted, report INFRASTRUCTURE FAILURE (orphaned background build) instead.
14. **Distinguish INFRASTRUCTURE FAILURE from BUILD FAILED**: infrastructure failures (lock timeouts, daemon problems) use the INFRASTRUCTURE FAILURE format so the caller can apply recovery and retry etiquette; build failures are code problems and must never trigger daemon recovery.
```

- [ ] **Step 7: Верификация**

Выполнить:
```bash
grep -n "model: sonnet" agents/build-runner.md
grep -n "Bash(jps:\*), Bash(jstack:\*), Bash(ps:\*), Bash(sleep:\*)" agents/build-runner.md
grep -n "## Execution Rules (All Stacks)" agents/build-runner.md
grep -n "### Infrastructure Failures (Gradle)" agents/build-runner.md
grep -c "INFRASTRUCTURE FAILURE" agents/build-runner.md
grep -n '\./gradlew' agents/build-runner.md | grep -v -e 'console=plain' -e '--stop' -e 'auto-fix' || echo OK-all-gradlew-console-plain
grep -n 'mvn ' agents/build-runner.md | grep -v ' -B' || echo OK-all-mvn-batch
grep -n "safe to retry" agents/build-runner.md
grep -n "run daemon recovery procedure first (see build skill)" agents/build-runner.md
sed -n '1,7p' agents/build-runner.md | grep -c 'kill' | grep -qx 0 && echo OK-no-kill-in-frontmatter
grep -n "BUILD SUCCESSFUL" agents/build-runner.md | head -1; grep -n "MIXED PROJECT DETECTED" agents/build-runner.md | head -1
grep -nP '[А-Яа-яЁё]' agents/build-runner.md || echo OK-no-cyrillic
```
Ожидаемо: `model: sonnet` в frontmatter; tools-строка с четырьмя новыми инструментами найдена; обе новые секции найдены; `INFRASTRUCTURE FAILURE` ≥ 5; каждый `./gradlew`-вызов несёт `--console=plain` (легитимные исключения отфильтрованы: упоминание `--stop` в запрете и `ktlintFormat` в подсказках auto-fix — это не команды агента) — иначе grep перечислит нарушителей; каждый `mvn`-вызов несёт `-B`; обе метки Recommended Action найдены; в frontmatter (строки 1–7) нет `kill`; старые форматы `BUILD SUCCESSFUL`/`MIXED PROJECT DETECTED` на месте (регрессий нет); кириллицы нет (`OK-no-cyrillic`).

- [ ] **Step 8: Commit**

```bash
git add agents/build-runner.md
git commit -m "feat: harden build-runner (timeout discipline, background-build protocol, infrastructure failures)

Claude-Session: <URL текущей сессии-исполнителя>"
```

---

### Task 2: `skills/build/SKILL.md` — последовательная диспетчеризация, инфра-ретраи, восстановление демонов

**Files:**
- Modify: `skills/build/SKILL.md`

**Interfaces:**
- Consumes: формат `INFRASTRUCTURE FAILURE` и дословные значения Recommended Action из Task 1 (`safe to retry`, `run daemon recovery procedure first (see build skill)`).
- Produces: секция `## Daemon Recovery Procedure` — на неё ссылается текст агента «(see build skill)».

- [ ] **Step 1: Подраздел «Dispatch discipline» после Step 1**

Старое:
```
**Do not run ANY build/test/lint/type-check command directly — always delegate to build-runner agent. This includes not only the tools listed above, but also vue-tsc, tsc, eslint, prettier, cargo, and any other command whose purpose is building, testing, linting, or verifying code.**

### Step 2: Handle agent result
```

Новое:
```
**Do not run ANY build/test/lint/type-check command directly — always delegate to build-runner agent. This includes not only the tools listed above, but also vue-tsc, tsc, eslint, prettier, cargo, and any other command whose purpose is building, testing, linting, or verifying code.**

### Dispatch discipline

- Strictly one build-runner at a time: never dispatch a new agent while a previous one has not returned its result — including chains like `ktlintFormat` → retry build.
- If an agent returns while its build is still running in the background (protocol violation or agent death), do not dispatch a new build right away: tell the user, and treat the next failure as an INFRASTRUCTURE FAILURE with a live lock owner (run the Daemon Recovery Procedure below before any retry).
- If the user changes or refines the request while a build-runner is working, wait for its report first, then dispatch a new agent with the updated task.

### Step 2: Handle agent result
```

- [ ] **Step 2: Обработчик INFRASTRUCTURE FAILURE в Step 2**

Старое:
```
**Success** — report success, show build time

**Ktlint errors** (gradle-android, gradle-kotlin) —
```

Новое:
```
**Success** — report success, show build time

**INFRASTRUCTURE FAILURE** (lock timeout / daemon problem / orphaned background build, reported by the agent) —
1. Recommended Action `safe to retry` (lock owner dead) — dispatch one retry immediately.
2. Recommended Action `run daemon recovery procedure first` (lock owner alive, or an orphaned background build) — run the Daemon Recovery Procedure below, then dispatch ONE retry.
3. If the retry fails with another INFRASTRUCTURE FAILURE — stop and report to the user; do not loop.
4. Malformed report (INFRASTRUCTURE FAILURE without a recognizable Recommended Action) — treat as BUILD FAILED; never run daemon recovery on uncertain grounds.

**User reports a stuck/hung Gradle build** — run the Daemon Recovery Procedure directly; it does not require a prior agent report.

**Ktlint errors** (gradle-android, gradle-kotlin) —
```

- [ ] **Step 3: Секция «Daemon Recovery Procedure» перед Limitations**

Старое:
```
**Mixed project detected** — report to user that multiple stacks were found, ask which to build

## Limitations
```

Новое:
```
**Mixed project detected** — report to user that multiple stacks were found, ask which to build

## Daemon Recovery Procedure

Run in the MAIN session — the build-runner agent must never kill daemons. The commands below (`./gradlew --stop`, `jps`, `kill`, `jstack`, `sleep`) are recovery commands, not build/test/lint commands: the "always delegate to build-runner" rule does NOT apply to them — run them directly, never dispatch them to build-runner. Use when an INFRASTRUCTURE FAILURE report says the lock owner is alive (or reports an orphaned background build), or when the user reports a stuck build:

1. Run `jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'` and note the list (to compare after `--stop`).
2. Run `./gradlew --stop` in the project directory (stops daemons of the project's Gradle version only). If the project has no `gradlew` wrapper, skip to step 3.
3. Re-check with `jps`; `kill <pid>` each surviving daemon from step 1; run `sleep 15`; `kill -9` any that remain.
4. Run `sleep 20` before retrying — a cancelled daemon is not reused, and an instant retry spawns extra cold daemons.
5. Dispatch ONE retry via build-runner. The retry will be slow (cold Gradle and Kotlin daemons) — slow is not hung. If it hangs again: find the new daemon PID via `jps` and capture `jstack <pid> | head -200`, then report to the user instead of looping.

## Limitations
```

- [ ] **Step 4: Обновить Limitations и Output format**

Старое:
```
## Limitations
- Maximum 3 build attempts
- Each run — new agent with clean context
```

Новое:
```
## Limitations
- Maximum 4 build runs total per skill invocation: up to 3 attempts on build/code errors plus at most 1 retry after an INFRASTRUCTURE FAILURE. Auto-fix commands (`ktlintFormat`, `ruff check --fix .`) do not count as build runs.
- Dispatch is strictly sequential — one build-runner at a time. This protects against self-duplication only: other Claude sessions, IDEs and terminals still share `~/.gradle`.
- Never dispatch long-running/watch commands (`bootRun`, `--continuous`, dev servers) to build-runner — they never finish and break the wait protocol.
- No dispatch timeout: if build-runner itself hangs (harness/model error), the skill cannot detect it — known limitation.
- Each run — new agent with clean context
```

Вторая правка — секция Output format (конец файла), третий статус:

Старое:
```
## Output format
Use format from build-runner agent:
- BUILD SUCCESSFUL + time
- BUILD FAILED + error details
```

Новое:
```
## Output format
Use format from build-runner agent:
- BUILD SUCCESSFUL + time
- BUILD FAILED + error details
- INFRASTRUCTURE FAILURE + cause, details, recommended action (handled per Step 2)
```

- [ ] **Step 5: Верификация**

```bash
grep -n "### Dispatch discipline" skills/build/SKILL.md
grep -c "INFRASTRUCTURE FAILURE" skills/build/SKILL.md
grep -n "## Daemon Recovery Procedure" skills/build/SKILL.md
grep -n "run daemon recovery procedure first" skills/build/SKILL.md
grep -n "safe to retry" skills/build/SKILL.md
grep -n "Maximum 4 build runs total" skills/build/SKILL.md
grep -n "build/test/lint/type-check" skills/build/SKILL.md
sed -n '/## Output format/,$p' skills/build/SKILL.md | grep -c "INFRASTRUCTURE FAILURE"
grep -nP '[А-Яа-яЁё]' skills/build/SKILL.md || echo OK-no-cyrillic
```
Ожидаемо: все строки найдены; `INFRASTRUCTURE FAILURE` ≥ 4 вхождений по файлу и ровно 1 в секции Output format; формулировка `build/test/lint/type-check` сохранена (регрессии `/type-check` нет); кириллицы нет (`OK-no-cyrillic`).

- [ ] **Step 6: Commit**

```bash
git add skills/build/SKILL.md
git commit -m "feat: sequential dispatch, infra-failure retries, daemon recovery in build skill

Claude-Session: <URL текущей сессии-исполнителя>"
```

---

### Task 3: `README.md` — секция Recommended host setup + актуализация заметки о модели

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: значения env-переменных и gradle-настроек из спеки (Изменение 3); факт `model: sonnet` из Task 1.

- [ ] **Step 1: Вставить секцию перед «## Notes»**

Старое:
```
  `mcp__sonatype-mcp__*` tools, so the server name must match)

## Notes
```

Новое:
````
  `mcp__sonatype-mcp__*` tools, so the server name must match)

## Recommended host setup

The plugin cannot set Claude Code environment variables itself — these are user settings.
Unix-like hosts; the background-build protocol relies on Claude Code ≥ 2.1.211 behavior.
For reliable long builds (especially Gradle) configure the host once:

- **Bash tool timeouts** — in `~/.claude/settings.json` (or project `.claude/settings.json`;
  merge the `env` block into your existing file):

  ```json
  { "env": { "BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "1800000" } }
  ```

  Without this any command longer than 2 minutes is moved to the background mid-build
  (the agent handles that, but foreground builds are simpler and more reliable).
- **Gradle daemon idle timeout** — in `~/.gradle/gradle.properties` (add or change the line):

  ```
  org.gradle.daemon.idletimeout=1800000
  ```

  30 minutes instead of the default 3 hours: fewer big idle daemons accumulating in RAM.
  Trade-off: the first build after a long pause pays a cold daemon start.
- **Multi-JDK hosts** — pin toolchain discovery in `~/.gradle/gradle.properties`:

  ```
  org.gradle.java.installations.auto-detect=false
  org.gradle.java.installations.paths=/usr/lib/jvm/zulu17,/usr/lib/jvm/zulu21,/usr/lib/jvm/zulu25
  ```

  Gradle probes every installed JDK with no timeout; one broken JDK can hang builds forever.
  Replace the paths with your actual JDKs; skip this if other projects on this machine rely
  on toolchain auto-detection.
- **Recovery permissions** — the build skill's Daemon Recovery Procedure runs `jps`, `kill`
  and `jstack` in the MAIN session. Allow `Bash(jps:*)`, `Bash(kill:*)`, `Bash(jstack:*)`
  (or confirm the prompts); the procedure is idempotent — safe to restart. The agent's own
  diagnostics call `jps`/`jstack` from PATH — keep a JDK `bin` on PATH.
- **Quick diagnostics** — if a build looks stuck, check by hand:

  ```
  jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'
  ps -fp <pid>
  jstack <pid> | head -100
  ```

  Keep the Gradle daemon enabled — never pass `--no-daemon`: it does not prevent lock
  contention and contradicts current Gradle guidance.

## Notes
````

- [ ] **Step 2: Обновить заметку о модели**

Старое:
```
- `build-runner` runs on `model: haiku` by design (fast, cheap build loops); change the
  frontmatter in a fork if you prefer a stronger model.
```

Новое:
```
- `build-runner` runs on `model: sonnet` for all stacks — reliable handling of long build
  logs and of builds that hit the Bash timeout. It costs more per run than the previous
  `haiku`; change the frontmatter in a fork if you prefer a different model.
```

- [ ] **Step 3: Верификация**

```bash
grep -n "## Recommended host setup" README.md
grep -n "BASH_MAX_TIMEOUT_MS" README.md
grep -n "org.gradle.daemon.idletimeout" README.md
grep -n "Recovery permissions" README.md
grep -n "Quick diagnostics" README.md
grep -n "never pass" README.md
grep -n "model: sonnet" README.md
grep -c "model: haiku" README.md || echo no-haiku-left
```
Ожидаемо: первые семь найдены (`never pass` — строка про `--no-daemon`); `model: haiku` в README отсутствует (grep -c даёт 0 / срабатывает echo).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: recommended host setup; update build-runner model note

Claude-Session: <URL текущей сессии-исполнителя>"
```

---

### Task 4: `CHANGELOG.md` + финальная сверка

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: перечень изменений Task 1–3.

- [ ] **Step 1: Запись в Unreleased**

Старое:
```
## [Unreleased]
```

Новое:
```
## [Unreleased]

### Changed
- `build-runner` agent hardening against hung/slow builds: explicit 10-minute Bash timeout on every build command (dependency installs included), one-build-at-a-time rule, bounded wait protocol for commands moved to the background (sleep+grep polling, wait budget, orphaned-build reporting — never a re-run), `--console=plain` on every Gradle invocation and `-B` on Maven, INFRASTRUCTURE FAILURE report format with lock-owner diagnostics and extended daemon-failure signatures (read-only `ps`/`jps`/`jstack` plus `sleep` pacing), model `haiku` → `sonnet`.
- `build` skill: strictly sequential agent dispatch, infrastructure-failure retry etiquette (recovery first, then at most one retry; at most 4 build runs total), Daemon Recovery Procedure (`--stop` → `jps` → `kill`) executed by the main session, INFRASTRUCTURE FAILURE in the output format.

### Added
- README section "Recommended host setup" (Bash timeout env vars, Gradle daemon idle timeout, multi-JDK toolchain pinning, recovery permissions, quick-diagnostics runbook).
```

- [ ] **Step 2: Финальная кросс-файловая сверка**

```bash
grep -c "INFRASTRUCTURE FAILURE" agents/build-runner.md skills/build/SKILL.md
grep -n "see build skill" agents/build-runner.md
grep -n "## Daemon Recovery Procedure" skills/build/SKILL.md
grep -n "safe to retry" agents/build-runner.md skills/build/SKILL.md
grep -n "run daemon recovery procedure first" agents/build-runner.md skills/build/SKILL.md
grep -nP '[А-Яа-яЁё]' agents/build-runner.md skills/build/SKILL.md README.md CHANGELOG.md || echo OK-no-cyrillic
git status --short
```
Ожидаемо: `INFRASTRUCTURE FAILURE` в обоих файлах (агент ≥ 5, скилл ≥ 4); ссылка «see build skill» из агента существует и целевая секция `## Daemon Recovery Procedure` в скилле есть; обе метки Recommended Action присутствуют в обоих файлах; кириллицы нет (`OK-no-cyrillic`); `git status --short` показывает ровно одну строку `?? docs/gradle-build-runner-hardening-report.md` (отчёт untracked, всё остальное закоммичено).

- [ ] **Step 3: Смоук-тесты до мержа (вручную, из ветки)**

Запустить тестовую сессию с изменённым плагином (`claude --plugin-dir /opt/github/zinin/claude-forge`) на реальном Gradle-проекте и проверить три сценария:

1. Сборка >2 мин: команда агента идёт с `timeout: 600000` и `--console=plain`, завершается в форграунде, отчёт корректен.
2. Сборка >10 мин (или искусственно замедленная): уходит в фон; агент поллит `sleep 30` + Grep, НЕ перезапускает сборку, отчитывается фактическим результатом.
3. Негативный кейс: занять глобальный lock вторым Gradle-процессом → агент отдаёт INFRASTRUCTURE FAILURE с верным Owner PID и Recommended Action; скилл выполняет ровно один ретрай (с recovery при живом владельце).

При провале любого сценария — остановиться и обсудить с пользователем до мержа.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for build-runner hardening

Claude-Session: <URL текущей сессии-исполнителя>"
```
