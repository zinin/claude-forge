---
name: google-maven-updater
description: "Use when checking or updating AndroidX, Firebase, Google Play Services, or other Google Maven dependencies. Use this skill to: (1) Find latest versions of androidx.* libraries, (2) Check Compose BOM versions, (3) Search for Google/Android libraries by name, (4) Get version history for any artifact in maven.google.com."
---

# Google Maven Updater

Fetches artifact versions from Google's Maven Repository (maven.google.com) using their XML index API.

## When to Use

- Checking/updating AndroidX dependencies (androidx.*)
- Checking Compose BOM versions (sonatype-mcp doesn't index these)
- Checking Firebase, Play Services, Material Design versions
- Any dependency from maven.google.com

**For non-Google libraries:** Use MCP `sonatype-mcp` instead.

## API Structure

Google Maven uses XML index files:
- `master-index.xml` — all available groups
- `{group-path}/group-index.xml` — artifacts and versions in a group

Base URL: `https://dl.google.com/dl/android/maven2`

## Commands

### Search Groups

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" search <term>
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" search compose
# Returns: androidx.compose, androidx.compose.ui, androidx.compose.material3, etc.
```

### List Artifacts in Group

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" artifacts <group>
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" artifacts androidx.core
# Returns: core, core-ktx, core-splashscreen, etc. with all versions
```

### Get Latest Version

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" latest <group> <artifact>
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" latest <group> <artifact> --include-prerelease
```

Example:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" latest androidx.compose compose-bom
# Returns: latest_version: "2026.01.01", recent_versions: [...]
```

### Get All Versions

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" versions <group> <artifact>
```

Returns both stable and pre-release versions, sorted by version number.

## Common Dependencies

| Dependency | Group | Artifact |
|------------|-------|----------|
| Compose BOM | androidx.compose | compose-bom |
| Core KTX | androidx.core | core-ktx |
| Lifecycle | androidx.lifecycle | lifecycle-runtime-ktx |
| Activity Compose | androidx.activity | activity-compose |
| Navigation Compose | androidx.navigation | navigation-compose |
| DataStore | androidx.datastore | datastore-preferences |
| Hilt Navigation | androidx.hilt | hilt-navigation-compose |
| Material | com.google.android.material | material |

## Workflow: Update Dependencies

1. **Check current versions** in `build.gradle.kts`
2. **Get latest versions:**
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" latest androidx.core core-ktx
   python3 "${CLAUDE_SKILL_DIR}/scripts/google_maven_helper.py" latest androidx.compose compose-bom
   ```
3. **Update versions** in build file
4. **Run build** to verify: `./gradlew build`

## Version Filtering

- By default, `latest` returns only stable versions (no alpha/beta/rc/dev)
- Use `--include-prerelease` to include pre-release versions
- `versions` command shows both stable and pre-release

## Error Handling

- **Group not found:** Check spelling, use `search` to find correct group name
- **Artifact not found:** Use `artifacts <group>` to list available artifacts
- **Network errors:** Check internet connectivity
