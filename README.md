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

## Notes

- The `build-runner` agent expects JDKs at the conventional paths
  `/usr/lib/jvm/zulu17|zulu21|zulu25` (Ubuntu + Azul Zulu layout). On a different layout,
  create symlinks (e.g. `/usr/lib/jvm/zulu17 -> /path/to/your/jdk17`), or fork the plugin /
  use `claude --plugin-dir` with an adjusted `agents/build-runner.md` — editing the installed
  marketplace copy does not persist (it lives in a versioned cache and is overwritten on update).
- `build-runner` runs on `model: haiku` by design (fast, cheap build loops); change the
  frontmatter in a fork if you prefer a stronger model.
- The updater skills invoke their bundled scripts as
  `python3 "${CLAUDE_SKILL_DIR}/scripts/…"`. Allow that once in your permissions
  (e.g. `Bash(python3:*)` or a narrower rule) to avoid a prompt on every call.

## See also

- [claude-atlassian](https://github.com/zinin/claude-atlassian) — Jira ticket and Confluence page analysis plugin by the same author
