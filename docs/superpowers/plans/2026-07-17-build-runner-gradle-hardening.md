# Build-runner Gradle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить «зависания» Gradle-сборок через build-runner: дисциплина таймаутов, протокол фоновых сборок, диагностика инфраструктурных сбоев, процедура восстановления демонов.

**Architecture:** Четыре правки маркдаун-конфигурации: агент `build-runner` получает правила исполнения (timeout, одна сборка за раз, протокол «moved to background») и формат INFRASTRUCTURE FAILURE; скилл `build` — последовательную диспетчеризацию и процедуру восстановления демонов (выполняет главная сессия); README — секцию настроек хоста; CHANGELOG — запись. Код не меняется — только инструкции агента/скилла.

**Tech Stack:** Markdown-файлы плагина Claude Code (frontmatter агента, SKILL.md), git.

**Spec:** `docs/superpowers/specs/2026-07-17-build-runner-gradle-hardening-design.md`

## Global Constraints

- Тексты файлов плагина — на английском, в стиле существующих секций.
- Ветка: `build-runner-hardening` (уже создана и активна). Рабочая директория: `/opt/github/zinin/claude-forge`.
- `docs/gradle-build-runner-hardening-report.md` — untracked, НЕ коммитить. В `git add` передавать только явные пути файлов, никогда `git add docs/` или `git add -A`.
- Агенту build-runner добавляются ТОЛЬКО read-only инструменты `Bash(jps:*)`, `Bash(jstack:*)`, `Bash(ps:*)`. Никакого `kill` в tools агента.
- Каждое сообщение коммита заканчивается трейлером (отдельной строкой после пустой):
  `Claude-Session: https://claude.ai/code/session_01JTtGLD3y4EAZw6wCXTgRCT`
- Метки, используемые в обоих файлах, должны совпадать дословно: `INFRASTRUCTURE FAILURE`, `Daemon Recovery Procedure`, `safe to retry`, `run daemon recovery procedure first (see build skill)`.
- Тестов/сборки в репо нет — верификация каждой правки: `grep` с ожидаемым выводом + вычитка.

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
Bash(tox:*), Bash(jps:*), Bash(jstack:*), Bash(ps:*), Glob, Grep, Read
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

These rules apply to EVERY build/test/lint command you run:

1. **Always set an explicit timeout.** Every Bash call that runs a build/test/lint command MUST pass `timeout: 600000` (10 minutes). Never rely on the default 120-second timeout — a typical build exceeds it and gets moved to the background mid-run.
2. **One build at a time.** Never start a new build/test/lint command while a previous one is still running — including a command that was moved to the background. Overlapping builds contend for global cache locks and spawn extra daemons.
3. **If a command is moved to the background** (message like `Command did not complete within its 600s timeout and was moved to the background (ID: ...)`):
   - Do NOT re-run the command.
   - Wait for the task-completion notification; while waiting, check interim progress by reading the task output file with Read.
   - Do not end your turn while the build is still running.
   - Report the actual final result from the output file — never a guess.
4. **Never manage build daemons yourself.** Do not run `gradlew --stop`, do not kill processes, never delete `*.lock` files. Diagnose and report (see Infrastructure Failures); recovery is the caller's decision.
5. **Ignore daemon registry DEBUG noise.** Lines like `Waiting to acquire shared lock on daemon addresses registry` are routine polling, not errors — do not report them as problems.

## Step 1: Detect Project Stack
```

- [ ] **Step 3: `--console=plain` в Gradle-командах**

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

Environment problems are reported differently from code problems (INFRASTRUCTURE FAILURE format below) and are retried differently by the caller.

If the build fails with `Timeout waiting to lock <cache> (...). It is currently in use by another Gradle instance. Owner PID: <X>`:

1. Run `ps -p <X>` to check whether the owning process is alive.
2. Report INFRASTRUCTURE FAILURE:
   - Owner PID **dead** → Recommended Action: `safe to retry` (stale locks recover automatically once the owner is gone).
   - Owner PID **alive** → Recommended Action: `run daemon recovery procedure first (see build skill)` — likely a hung daemon holding a global lock.

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
[Lock file / cache name; Owner PID and whether it is alive or dead; key log lines]

## Recommended Action
[safe to retry | run daemon recovery procedure first (see build skill)]
```

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
13. **Never re-run a build that was moved to the background** — wait for its result and report it.
14. **Distinguish INFRASTRUCTURE FAILURE from BUILD FAILED**: infrastructure failures (lock timeouts, daemon problems) use the INFRASTRUCTURE FAILURE format so the caller can apply recovery and retry etiquette; build failures are code problems and must never trigger daemon recovery.
```

- [ ] **Step 7: Верификация**

Выполнить:
```bash
grep -n "model: sonnet" agents/build-runner.md
grep -n "Bash(jps:\*), Bash(jstack:\*), Bash(ps:\*)" agents/build-runner.md
grep -c "console=plain" agents/build-runner.md
grep -n "## Execution Rules (All Stacks)" agents/build-runner.md
grep -n "### Infrastructure Failures (Gradle)" agents/build-runner.md
grep -c "INFRASTRUCTURE FAILURE" agents/build-runner.md
grep -n "kill" agents/build-runner.md | grep -v "never kill\|do not kill" || echo OK-no-kill-tool
```
Ожидаемо: model на строке ~5; tools-строка найдена; `console=plain` — 4 совпадения (заметка + 3 команды); секции найдены; INFRASTRUCTURE FAILURE ≥ 4; последний grep не находит `Bash(kill` (в tools нет kill).

- [ ] **Step 8: Commit**

```bash
git add agents/build-runner.md
git commit -m "feat: harden build-runner (timeout discipline, background-build protocol, infrastructure failures)

Claude-Session: https://claude.ai/code/session_01JTtGLD3y4EAZw6wCXTgRCT"
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
**Do not run ANY build/test/lint command directly — always delegate to build-runner agent. This includes not only the tools listed above, but also vue-tsc, tsc, eslint, prettier, cargo, and any other command whose purpose is building, testing, linting, or verifying code.**

### Step 2: Handle agent result
```

Новое:
```
**Do not run ANY build/test/lint command directly — always delegate to build-runner agent. This includes not only the tools listed above, but also vue-tsc, tsc, eslint, prettier, cargo, and any other command whose purpose is building, testing, linting, or verifying code.**

### Dispatch discipline

- Strictly one build-runner at a time: never dispatch a new agent while a previous one has not returned its result — including chains like `ktlintFormat` → retry build.
- If an agent reports its build was moved to the background and is still running, wait for that build to finish before any new dispatch.

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

**INFRASTRUCTURE FAILURE** (lock timeout / daemon problem, reported by the agent) —
1. Recommended Action `safe to retry` (lock owner dead) — dispatch one retry.
2. Recommended Action `run daemon recovery procedure first` (lock owner alive) — run the Daemon Recovery Procedure below, then dispatch ONE retry.
3. If the retry fails with another INFRASTRUCTURE FAILURE — stop and report to the user; do not loop.

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

Run in the MAIN session — the build-runner agent must never kill daemons. Use only when an INFRASTRUCTURE FAILURE report says the lock owner is alive:

1. Run `./gradlew --stop` in the project directory (stops daemons of the project's Gradle version only).
2. Run `jps`; find surviving `GradleDaemon` / `KotlinCompileDaemon` processes.
3. `kill <pid>` each survivor; wait ~15 seconds; `kill -9` any that remain.
4. Wait 15–30 seconds before retrying — a cancelled daemon is not reused, and an instant retry spawns extra cold daemons.
5. Dispatch ONE retry via build-runner. If it hangs again: capture `jstack <daemon pid>` and report to the user instead of looping.

## Limitations
```

- [ ] **Step 4: Обновить Limitations**

Старое:
```
## Limitations
- Maximum 3 build attempts
- Each run — new agent with clean context
```

Новое:
```
## Limitations
- Maximum 3 build attempts for build/code errors; maximum 1 retry after an INFRASTRUCTURE FAILURE
- Dispatch is strictly sequential — one build-runner at a time
- Each run — new agent with clean context
```

- [ ] **Step 5: Верификация**

```bash
grep -n "### Dispatch discipline" skills/build/SKILL.md
grep -n "INFRASTRUCTURE FAILURE" skills/build/SKILL.md
grep -n "## Daemon Recovery Procedure" skills/build/SKILL.md
grep -n "run daemon recovery procedure first" skills/build/SKILL.md
grep -n "Maximum 3 build attempts for build/code errors" skills/build/SKILL.md
```
Ожидаемо: все строки найдены; «INFRASTRUCTURE FAILURE» ≥ 3 вхождений.

- [ ] **Step 6: Commit**

```bash
git add skills/build/SKILL.md
git commit -m "feat: sequential dispatch, infra-failure retries, daemon recovery in build skill

Claude-Session: https://claude.ai/code/session_01JTtGLD3y4EAZw6wCXTgRCT"
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
For reliable long builds (especially Gradle) configure the host once:

- **Bash tool timeouts** — in `~/.claude/settings.json` (or project `.claude/settings.json`):

  ```json
  { "env": { "BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "1800000" } }
  ```

  Without this any command longer than 2 minutes is moved to the background mid-build
  (the agent handles that, but foreground builds are simpler and more reliable).
- **Gradle daemon idle timeout** — in `~/.gradle/gradle.properties`:

  ```
  org.gradle.daemon.idletimeout=1800000
  ```

  30 minutes instead of the default 3 hours: fewer big idle daemons accumulating in RAM.
- **Multi-JDK hosts** — pin toolchain discovery in `~/.gradle/gradle.properties`:

  ```
  org.gradle.java.installations.auto-detect=false
  org.gradle.java.installations.paths=/usr/lib/jvm/zulu17,/usr/lib/jvm/zulu21,/usr/lib/jvm/zulu25
  ```

  Gradle probes every installed JDK with no timeout; one broken JDK can hang builds forever.

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
- `build-runner` runs on `model: sonnet` — reliable handling of long build logs and of
  builds that hit the Bash timeout; change the frontmatter in a fork if you prefer a
  different model.
```

- [ ] **Step 3: Верификация**

```bash
grep -n "## Recommended host setup" README.md
grep -n "BASH_MAX_TIMEOUT_MS" README.md
grep -n "org.gradle.daemon.idletimeout" README.md
grep -n "model: sonnet" README.md
grep -c "model: haiku" README.md || echo no-haiku-left
```
Ожидаемо: первые четыре найдены; `model: haiku` в README отсутствует (grep -c даёт 0 / срабатывает echo).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: recommended host setup; update build-runner model note

Claude-Session: https://claude.ai/code/session_01JTtGLD3y4EAZw6wCXTgRCT"
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
- `build-runner` agent hardening against hung/slow builds: explicit 10-minute Bash timeout on every build command, one-build-at-a-time rule, protocol for commands moved to the background (wait and report, never re-run), `--console=plain` on Gradle invocations, INFRASTRUCTURE FAILURE report format with lock-owner diagnostics (read-only `ps`/`jps`/`jstack` tools), model `haiku` → `sonnet`.
- `build` skill: strictly sequential agent dispatch, infrastructure-failure retry etiquette (recovery first, then at most one retry), Daemon Recovery Procedure (`--stop` → `jps` → `kill`) executed by the main session.

### Added
- README section "Recommended host setup" (Bash timeout env vars, Gradle daemon idle timeout, multi-JDK toolchain pinning).
```

- [ ] **Step 2: Финальная кросс-файловая сверка**

```bash
grep -c "INFRASTRUCTURE FAILURE" agents/build-runner.md skills/build/SKILL.md
grep -n "see build skill" agents/build-runner.md
grep -n "Daemon Recovery Procedure" skills/build/SKILL.md
git status --short
```
Ожидаемо: метка есть в обоих файлах; ссылка «see build skill» из агента существует, и целевая секция в скилле есть; `git status` показывает только `?? docs/gradle-build-runner-hardening-report.md` (отчёт untracked, всё остальное закоммичено).

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for build-runner hardening

Claude-Session: https://claude.ai/code/session_01JTtGLD3y4EAZw6wCXTgRCT"
```
