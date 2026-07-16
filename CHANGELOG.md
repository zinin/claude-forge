# Changelog

All notable changes to claude-forge will be documented here.

## [Unreleased]

## [0.1.0] - 2026-07-16

### Added
- Initial release: tools ported from the author's internal ai-tools monorepo (@ ad23588).
- `build-runner` agent — build/test/lint executor for Gradle/Maven/Node.js/Go/Python with JDK auto-detection.
- `build` skill — delegates any build/test/lint task to the `claude-forge:build-runner` agent.
- `deps-update` command — orchestrates dependency updates via the updater skills and sonatype-mcp.
- `gradle-plugin-updater` skill — Gradle Plugin Portal version lookups (bundled helper script).
- `google-maven-updater` skill — maven.google.com version lookups (bundled helper script).
