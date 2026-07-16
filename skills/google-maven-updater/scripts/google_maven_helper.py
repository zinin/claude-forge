#!/usr/bin/env python3
"""
Google Maven Repository Helper

Fetches artifact information from Google's Maven Repository
(https://maven.google.com) using their XML index files.

API Structure:
- master-index.xml: List of all groups
- {group-path}/group-index.xml: Artifacts and versions in a group

Usage:
    python3 google_maven_helper.py groups                    # List all groups
    python3 google_maven_helper.py search <term>             # Search groups
    python3 google_maven_helper.py artifacts <group>         # List artifacts in group
    python3 google_maven_helper.py versions <group> <artifact>  # Get versions
    python3 google_maven_helper.py latest <group> <artifact>    # Get latest stable version
"""

import sys
import json
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Optional

BASE_URL = "https://dl.google.com/dl/android/maven2"


def fetch_xml(url: str) -> Optional[ET.Element]:
    """Fetch and parse XML from URL."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return ET.fromstring(response.read())
    except urllib.error.HTTPError as e:
        return None
    except Exception as e:
        return None


def get_all_groups() -> list[str]:
    """Get all available groups from master-index.xml."""
    root = fetch_xml(f"{BASE_URL}/master-index.xml")
    if root is None:
        return []

    groups = []
    for child in root:
        # Tag name is the group with '.' replaced by nothing in XML
        # But the actual format is the tag text or attribute
        group_name = child.tag.replace("/", ".")
        groups.append(group_name)

    return sorted(groups)


def search_groups(term: str) -> list[str]:
    """Search groups by term (case-insensitive)."""
    groups = get_all_groups()
    term_lower = term.lower()
    return [g for g in groups if term_lower in g.lower()]


def get_group_artifacts(group: str) -> dict:
    """Get all artifacts and their versions in a group."""
    # Convert group to path: androidx.core -> androidx/core
    group_path = group.replace(".", "/")
    url = f"{BASE_URL}/{group_path}/group-index.xml"

    root = fetch_xml(url)
    if root is None:
        return {"success": False, "error": f"Group not found: {group}"}

    artifacts = {}
    for child in root:
        artifact_name = child.tag
        versions_str = child.get("versions", "")
        versions = [v.strip() for v in versions_str.split(",") if v.strip()]
        artifacts[artifact_name] = versions

    return {
        "success": True,
        "group": group,
        "artifacts": artifacts
    }


def parse_version(version: str) -> tuple:
    """Parse version string for sorting. Returns tuple for comparison."""
    # Handle versions like: 1.15.0, 1.0.0-alpha01, 2026.01.00, 1.0.0-rc01

    # Check for pre-release suffixes
    pre_release_order = {
        "dev": 0,
        "alpha": 1,
        "beta": 2,
        "rc": 3,
        "": 4,  # stable
    }

    # Extract base version and pre-release
    match = re.match(r'^([\d.]+)(?:[-.]?(dev|alpha|beta|rc)(\d*))?$', version, re.IGNORECASE)
    if not match:
        # Fallback: treat as string
        return (0, version, 0, 4, 0)

    base = match.group(1)
    pre_type = (match.group(2) or "").lower()
    pre_num = int(match.group(3)) if match.group(3) else 0

    # Parse base version numbers
    parts = [int(p) for p in base.split(".")]
    # Pad to ensure consistent comparison
    while len(parts) < 4:
        parts.append(0)

    pre_order = pre_release_order.get(pre_type, 4)

    return (1, tuple(parts), pre_order, pre_num)


def filter_stable_versions(versions: list[str]) -> list[str]:
    """Filter to only stable versions (no alpha, beta, rc, dev)."""
    pre_release_pattern = re.compile(r'(alpha|beta|rc|dev)', re.IGNORECASE)
    return [v for v in versions if not pre_release_pattern.search(v)]


def get_latest_version(group: str, artifact: str, stable_only: bool = True) -> dict:
    """Get the latest version of an artifact."""
    result = get_group_artifacts(group)
    if not result.get("success"):
        return result

    artifacts = result.get("artifacts", {})
    if artifact not in artifacts:
        return {
            "success": False,
            "error": f"Artifact not found: {artifact}",
            "available_artifacts": list(artifacts.keys())
        }

    versions = artifacts[artifact]
    if stable_only:
        stable_versions = filter_stable_versions(versions)
        if stable_versions:
            versions = stable_versions

    if not versions:
        return {
            "success": False,
            "error": "No versions found"
        }

    # Sort versions and get latest
    sorted_versions = sorted(versions, key=parse_version, reverse=True)

    return {
        "success": True,
        "group": group,
        "artifact": artifact,
        "latest_version": sorted_versions[0],
        "recent_versions": sorted_versions[:10],
        "total_versions": len(artifacts[artifact]),
        "stable_only": stable_only
    }


def get_artifact_versions(group: str, artifact: str) -> dict:
    """Get all versions of an artifact."""
    result = get_group_artifacts(group)
    if not result.get("success"):
        return result

    artifacts = result.get("artifacts", {})
    if artifact not in artifacts:
        return {
            "success": False,
            "error": f"Artifact not found: {artifact}",
            "available_artifacts": list(artifacts.keys())
        }

    versions = artifacts[artifact]
    sorted_versions = sorted(versions, key=parse_version, reverse=True)
    stable_versions = filter_stable_versions(sorted_versions)

    return {
        "success": True,
        "group": group,
        "artifact": artifact,
        "latest_stable": stable_versions[0] if stable_versions else None,
        "latest_any": sorted_versions[0] if sorted_versions else None,
        "stable_versions": stable_versions[:10],
        "all_versions": sorted_versions[:20],
        "total_versions": len(versions)
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "No command provided",
            "usage": {
                "groups": "List all available groups",
                "search <term>": "Search groups by name",
                "artifacts <group>": "List artifacts in a group",
                "versions <group> <artifact>": "Get all versions of artifact",
                "latest <group> <artifact>": "Get latest stable version"
            }
        }, indent=2))
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "groups":
        groups = get_all_groups()
        print(json.dumps({
            "success": True,
            "total": len(groups),
            "groups": groups
        }, indent=2))

    elif command == "search":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "error": "Search term required"}))
            sys.exit(1)
        term = sys.argv[2]
        matches = search_groups(term)
        print(json.dumps({
            "success": True,
            "term": term,
            "total": len(matches),
            "groups": matches
        }, indent=2))

    elif command == "artifacts":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "error": "Group name required"}))
            sys.exit(1)
        group = sys.argv[2]
        result = get_group_artifacts(group)
        print(json.dumps(result, indent=2))

    elif command == "versions":
        if len(sys.argv) < 4:
            print(json.dumps({"success": False, "error": "Group and artifact required"}))
            sys.exit(1)
        group = sys.argv[2]
        artifact = sys.argv[3]
        result = get_artifact_versions(group, artifact)
        print(json.dumps(result, indent=2))

    elif command == "latest":
        if len(sys.argv) < 4:
            print(json.dumps({"success": False, "error": "Group and artifact required"}))
            sys.exit(1)
        group = sys.argv[2]
        artifact = sys.argv[3]
        # Check for --include-prerelease flag
        stable_only = "--include-prerelease" not in sys.argv
        result = get_latest_version(group, artifact, stable_only)
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({
            "success": False,
            "error": f"Unknown command: {command}"
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
