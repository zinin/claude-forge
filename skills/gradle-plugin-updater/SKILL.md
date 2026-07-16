---
name: gradle-plugin-updater
description: "Search and update Gradle plugins using the official Gradle Plugin Portal (plugins.gradle.org). Use this skill when users need to: (1) Find Gradle plugins by name or functionality, (2) Check the latest version of a specific plugin, (3) Update plugin versions in build.gradle or build.gradle.kts files, (4) Discover all Gradle build files in a project, or (5) Get information about available plugin versions."
---

# Gradle Plugin Updater

This skill helps find, inspect, and update Gradle plugins using the official Gradle Plugin Portal at https://plugins.gradle.org/.

## Types of Gradle Plugins

Not all Gradle plugins are published on the Gradle Plugin Portal. Different plugin types require different version check methods:

| Plugin Type | Examples | Version Check Source |
|-------------|----------|---------------------|
| **Gradle Portal** (3rd party) | `ktlint`, `git-properties` | `gradle_plugin_helper.py` → plugins.gradle.org |
| **Kotlin plugins** | `kotlin("jvm")`, `kotlin("kapt")` | MCP `sonatype-mcp` → Maven Central |
| **Built-in Gradle** | `jacoco` (toolVersion) | MCP `sonatype-mcp` → Maven Central |
| **Spring plugins** | `org.springframework.boot` | `gradle_plugin_helper.py` → plugins.gradle.org |

### Maven Coordinates (PURL) for MCP sonatype-mcp

**Kotlin plugins** (all use the same version):
- PURL: `pkg:maven/org.jetbrains.kotlin/kotlin-gradle-plugin`

**JaCoCo** (toolVersion):
- PURL: `pkg:maven/org.jacoco/org.jacoco.core`

### Checking Versions via MCP sonatype-mcp

For plugins not in Gradle Portal (Kotlin, JaCoCo), use this algorithm:

**Step 1 (REQUIRED): Get latest version via `getLatestComponentVersion`.**
This is the primary source of truth. Compare returned version with current — if newer, update.

```
mcp__sonatype-mcp__getLatestComponentVersion
  packageUrls: ["pkg:maven/org.jetbrains.kotlin/kotlin-gradle-plugin"]
```

**Step 2 (optional): Get security/quality analysis via `getRecommendedComponentVersions`.**
Use only for additional info (CVEs, license, trust score). Do NOT rely on this to decide whether an update exists — `toVersions` can be empty even when a newer version is available.

```
mcp__sonatype-mcp__getRecommendedComponentVersions
  packageUrls: ["pkg:maven/org.jetbrains.kotlin/kotlin-gradle-plugin@2.3.0"]
```

**IMPORTANT:** `getRecommendedComponentVersions` returning empty `toVersions` does NOT mean the current version is the latest. Always check `getLatestComponentVersion` first.

### Where to Find GroupId/ArtifactId

Use only official sources:
- **MCP sonatype-mcp** - can be used for searching and verification
- **Gradle docs** - https://docs.gradle.org/current/userguide/plugin_reference.html
- **Kotlin docs** - https://kotlinlang.org/docs/gradle-configure-project.html
- **Spring docs** - https://docs.spring.io/spring-boot/docs/current/gradle-plugin/reference/html/

## Core Workflow

### 1. Searching for Plugins

To search for plugins by name or keyword:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" search <search-term>
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" search org.liquibase.gradle
```

Returns JSON with matching plugins including their IDs and URLs.

### 2. Getting Plugin Versions

To check available versions for a specific plugin:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" versions <plugin-id>
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" versions org.liquibase.gradle
```

Returns JSON with:
- Latest version
- List of recent versions (up to 10)
- Total number of available versions
- Plugin page URL

### 3. Finding Gradle Build Files

To locate all Gradle build files in a project:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" find-files [path]
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" find-files .
```

Returns paths to all `build.gradle` and `build.gradle.kts` files, excluding common directories like `.git`, `.gradle`, and `build`.

### 4. Updating Plugin Versions

To update a plugin version in a Gradle build file:

1. Use `versions` command to get the latest version
2. Use `view` or `str_replace` to update the build file
3. Look for patterns like:
    - `id 'plugin.id' version '1.0.0'` (Groovy DSL)
    - `id("plugin.id") version "1.0.0"` (Kotlin DSL)
    - `classpath "group:artifact:1.0.0"` (legacy format)

**Groovy DSL Update Example:**
```groovy
// Before
plugins {
    id 'org.liquibase.gradle' version '2.1.0'
}

// After
plugins {
    id 'org.liquibase.gradle' version '2.2.0'
}
```

**Kotlin DSL Update Example:**
```kotlin
// Before
plugins {
    id("org.liquibase.gradle") version "2.1.0"
}

// After
plugins {
    id("org.liquibase.gradle") version "2.2.0"
}
```

**Legacy Format Update Example:**
```groovy
// Before
dependencies {
    classpath "org.liquibase:liquibase-gradle-plugin:2.1.0"
}

// After
dependencies {
    classpath "org.liquibase:liquibase-gradle-plugin:2.2.0"
}
```

## Common Use Cases

### Check and Update a Specific Plugin

1. Get latest version: `python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" versions org.liquibase.gradle`
2. Find build files: `python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" find-files`
3. Update version in each file using `str_replace`

### Search for a Plugin by Functionality

Use descriptive search terms:
- `python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" search docker`
- `python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" search spring boot`
- `python3 "${CLAUDE_SKILL_DIR}/scripts/gradle_plugin_helper.py" search kotlin`

### Audit All Plugins in a Project

1. Find all Gradle files
2. Read each file and extract plugin IDs
3. Check latest version for each plugin
4. Report which plugins can be updated

## Bundled Resources

### Scripts

- `scripts/gradle_plugin_helper.py` - Main helper script for interacting with Gradle Plugin Portal
    - `search` command: Search for plugins
    - `versions` command: Get available versions for a plugin
    - `find-files` command: Find Gradle build files in project

### References

- `${CLAUDE_SKILL_DIR}/references/gradle_plugin_portal.md` - Detailed documentation about:
    - Gradle Plugin Portal structure
    - Search and plugin page formats
    - Common plugin formats in build files
    - Version number patterns
    - Update patterns for both Groovy and Kotlin DSL

## Important Notes

- The script requires network access to plugins.gradle.org
- Returns JSON output for easy parsing
- Handles both `build.gradle` (Groovy) and `build.gradle.kts` (Kotlin) files
- Skips common directories (`.git`, `.gradle`, `build`, `node_modules`)
- Plugin IDs are case-sensitive
- Always verify updates work by running `./gradlew build` after changes

## Error Handling

If the script fails:
- Network errors: Check internet connectivity
- Plugin not found: Verify the plugin ID spelling
- Parse errors: The HTML structure may have changed; manual verification needed

For detailed reference information, see `${CLAUDE_SKILL_DIR}/references/gradle_plugin_portal.md`.