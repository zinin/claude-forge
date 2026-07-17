# Changelog

All notable changes to claude-forge will be documented here.

## [Unreleased]

### Changed
- `build-runner` agent hardening against hung/slow builds: explicit 10-minute Bash timeout on every build command (dependency installs included), one-build-at-a-time rule, bounded wait protocol for commands moved to the background (sleep+grep polling, wait budget, orphaned-build reporting — never a re-run), `--console=plain` on every Gradle invocation and `-B` on Maven, INFRASTRUCTURE FAILURE report format with lock-owner diagnostics and extended daemon-failure signatures (read-only `ps`/`jps`/`jstack` plus `sleep` pacing), model `haiku` → `sonnet`.
- `build` skill: strictly sequential agent dispatch, infrastructure-failure retry etiquette (recovery first, then at most one retry; at most 4 build runs total), surgical Daemon Recovery Procedure (`--stop` → identity-checked `kill` of the confirmed lock owner only) executed by the main session, INFRASTRUCTURE FAILURE in the output format.

### Added
- README section "Recommended host setup" (Bash timeout env vars, Gradle daemon idle timeout, multi-JDK toolchain pinning, recovery permissions, quick-diagnostics runbook).

## [0.1.0] - 2026-07-16

### Added
- Initial release: tools ported from the author's internal ai-tools monorepo (@ ad23588).
- `build-runner` agent — build/test/lint executor for Gradle/Maven/Node.js/Go/Python with JDK auto-detection.
- `build` skill — delegates any build/test/lint task to the `claude-forge:build-runner` agent.
- `deps-update` command — orchestrates dependency updates via the updater skills and sonatype-mcp.
- `gradle-plugin-updater` skill — Gradle Plugin Portal version lookups (bundled helper script).
- `google-maven-updater` skill — maven.google.com version lookups (bundled helper script).
