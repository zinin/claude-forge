# Gradle Plugin Portal Reference

## Overview

The Gradle Plugin Portal (https://plugins.gradle.org/) is the official repository for Gradle plugins. This reference describes how to interact with it programmatically.

## Search API

### Search for Plugins

**URL Format:**
```
https://plugins.gradle.org/search?term={search_term}
```

**Example:**
```
https://plugins.gradle.org/search?term=org.liquibase.gradle
```

The search page returns HTML with plugin links in the format:
```html
<a href="/plugin/org.liquibase.gradle">Liquibase Gradle Plugin</a>
```

## Plugin Page API

### Get Plugin Information

**URL Format:**
```
https://plugins.gradle.org/plugin/{plugin_id}
```

**Example:**
```
https://plugins.gradle.org/plugin/org.liquibase.gradle
```

The plugin page shows:
- Latest version prominently displayed
- List of all available versions with links
- Usage instructions for both Groovy and Kotlin DSL

### Version Links Format

```html
<a href="/plugin/{plugin_id}/version/{version}">version</a>
```

Example:
```html
<a href="/plugin/org.liquibase.gradle/version/2.2.0">2.2.0</a>
```

## Common Plugin Formats in build.gradle

### Groovy DSL (build.gradle)

**Using plugins DSL (recommended):**
```groovy
plugins {
    id 'org.liquibase.gradle' version '2.2.0'
}
```

**Using legacy apply:**
```groovy
buildscript {
    repositories {
        maven {
            url "https://plugins.gradle.org/m2/"
        }
    }
    dependencies {
        classpath "org.liquibase:liquibase-gradle-plugin:2.2.0"
    }
}

apply plugin: "org.liquibase.gradle"
```

### Kotlin DSL (build.gradle.kts)

**Using plugins DSL:**
```kotlin
plugins {
    id("org.liquibase.gradle") version "2.2.0"
}
```

## Common Plugin IDs

- `org.springframework.boot` - Spring Boot
- `io.spring.dependency-management` - Dependency management
- `com.google.protobuf` - Protocol Buffers
- `org.liquibase.gradle` - Liquibase database migrations
- `org.jetbrains.kotlin.jvm` - Kotlin JVM
- `com.github.johnrengelman.shadow` - Shadow/fat JAR
- `org.flywaydb.flyway` - Flyway database migrations
- `com.gradle.enterprise` - Gradle Enterprise

## Update Patterns

### Pattern 1: Simple Version Update
```groovy
// Before
id 'org.liquibase.gradle' version '2.1.0'

// After
id 'org.liquibase.gradle' version '2.2.0'
```

### Pattern 2: Legacy Format Update
```groovy
// Before
classpath "org.liquibase:liquibase-gradle-plugin:2.1.0"

// After  
classpath "org.liquibase:liquibase-gradle-plugin:2.2.0"
```

## Version Number Formats

Common version formats:
- Standard: `1.0.0`, `2.1.5`
- Pre-release: `1.0.0-alpha`, `2.0.0-beta.1`, `1.5.0-RC1`
- Snapshot: `1.0.0-SNAPSHOT`
- With qualifier: `1.0.0.RELEASE`, `2.1.0.Final`

## Tips for Finding Plugins

1. Search by plugin ID for exact matches
2. Search by functionality keywords (e.g., "docker", "kubernetes")
3. Check plugin page for official documentation links
4. Verify plugin compatibility with your Gradle version
5. Read release notes before updating to new versions