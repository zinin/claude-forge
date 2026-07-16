---
name: deps-update
description: Update project dependencies (Gradle plugins, Google Maven artifacts, other libraries via sonatype-mcp)
---

Update project dependencies.

## Step 1: Detect stack

Determine project stack by checking CLAUDE.md and project files:
- `pom.xml` → **maven-java**
- `build.gradle(.kts)` + `AndroidManifest.xml` → **gradle-android**
- `build.gradle.kts` + `.kt` files → **gradle-kotlin**
- `build.gradle` + `.java` files → **gradle-java**

## Step 2: Update dependencies

### Gradle projects (gradle-android, gradle-kotlin, gradle-java)

#### 2a. Gradle Plugins
Use skill **claude-forge:gradle-plugin-updater**:
- Check plugins in `build.gradle.kts` and `settings.gradle.kts`
- Update to latest stable versions

#### 2b. AndroidX/Google Libraries (gradle-android only)
Use skill **claude-forge:google-maven-updater**:
- Check AndroidX dependencies (androidx.*, Compose BOM)
- Check Google libraries (Material, Play Services, Firebase)
- Update to latest stable versions

#### 2c. Other Libraries
Use MCP **sonatype-mcp** (getRecommendedComponentVersions):
- Check dependencies in `build.gradle.kts` of all modules
- Update to recommended versions

### Maven projects (maven-java)

#### 2a. All Dependencies
Use MCP **sonatype-mcp** (getRecommendedComponentVersions):
- Check dependencies in `pom.xml` of all modules
- Update to recommended versions

## Files to check

**Gradle:**
- `build.gradle.kts` (root)
- `settings.gradle.kts`
- `**/build.gradle.kts` (all modules)

**Maven:**
- `pom.xml` (root)
- `**/pom.xml` (all modules)

## After update
1. Run `/claude-forge:build` to verify compatibility
2. On errors — rollback problematic dependency

## Output format
```
## Updated plugins (Gradle only)
- plugin-name: old -> new

## Updated libraries
- group:artifact: old -> new

## Not updated (reason)
- ...
```
