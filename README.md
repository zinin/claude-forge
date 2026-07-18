# claude-forge

Claude Code plugin: build/test/lint delegation and JVM/Android dependency
updates (Gradle plugins, Google Maven).

## Features

(Slash commands are namespaced under `claude-forge:` — that is how Claude Code surfaces plugin commands.)

- **`/claude-forge:build`** — run build/test/lint for JVM (Gradle, Maven), Node.js, Go, or Python projects by dispatching the `claude-forge:build-runner` agent (clean context per attempt)
- **`/claude-forge:deps-update`** — update project dependencies: Gradle plugins, AndroidX/Google artifacts, and other libraries via sonatype-mcp
- **`claude-forge:build-runner` agent** — build verification engineer: detects the project stack, picks the JDK, runs the build, reports errors concisely
- **`claude-forge:gradle-plugin-updater` skill** — search plugins and check latest versions on plugins.gradle.org (bundled helper script)
- **`claude-forge:google-maven-updater` skill** — check AndroidX / Firebase / Play Services / Compose BOM versions on maven.google.com (bundled helper script)

## Install

```
/plugin marketplace add zinin/claude-plugins
/plugin install claude-forge@zinin
```

## Dependencies

- Python 3.9+ (`python3` on PATH) — helper scripts of both updater skills use modern type hints
- Network access to `maven.google.com` and `plugins.gradle.org`
- MCP server registered under the name `sonatype-mcp` — used by `deps-update` for non-Google
  libraries and by `gradle-plugin-updater` for Kotlin/JaCoCo versions (the skills call
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

  `BASH_MAX_TIMEOUT_MS` raises the per-call ceiling: the agent always asks for a 30-minute
  timeout, which is silently clamped to this ceiling (10 minutes on an unconfigured host) —
  with this setting long builds stay in the foreground instead of being moved to the
  background. `BASH_DEFAULT_TIMEOUT_MS` covers commands that pass no explicit timeout
  (main-session commands, recovery steps).
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
- **Recovery permissions** — the build skill's Daemon Recovery Procedure runs `jps`, `ps`,
  `kill` and `jstack` in the MAIN session. Allow `Bash(jps:*)`, `Bash(ps:*)`, `Bash(kill:*)`,
  `Bash(jstack:*)` (or confirm the prompts); the procedure is idempotent — safe to restart.
  The agent's own diagnostics call `jps`/`jstack` from PATH — keep a JDK `bin` on PATH.
- **Quick diagnostics** — if a build looks stuck, check by hand:

  ```
  jps -lv | grep -E 'GradleDaemon|KotlinCompileDaemon'
  ps -o pid,stat,args -p <pid>
  jstack <pid> | head -100
  ```

  Keep the Gradle daemon enabled — never pass `--no-daemon`: it does not prevent lock
  contention and contradicts current Gradle guidance.

## Notes

- The `build-runner` agent expects JDKs at the conventional paths
  `/usr/lib/jvm/zulu17|zulu21|zulu25` (Ubuntu + Azul Zulu layout). On a different layout,
  create symlinks (e.g. `/usr/lib/jvm/zulu17 -> /path/to/your/jdk17`), or fork the plugin /
  use `claude --plugin-dir` with an adjusted `agents/build-runner.md` — editing the installed
  marketplace copy does not persist (it lives in a versioned cache and is overwritten on update).
- `build-runner` runs on `model: sonnet` for all stacks — reliable handling of long build
  logs and of builds that hit the Bash timeout. It costs more per run than the previous
  `haiku`; change the frontmatter in a fork if you prefer a different model.
- The updater skills invoke their bundled scripts as
  `python3 "${CLAUDE_SKILL_DIR}/scripts/…"`. Allow that once in your permissions
  (e.g. `Bash(python3:*)` or a narrower rule) to avoid a prompt on every call.

## See also

- [claude-atlassian](https://github.com/zinin/claude-atlassian) — Jira ticket and Confluence page analysis plugin by the same author
