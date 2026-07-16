#!/usr/bin/env python3
"""
Helper script for working with Gradle plugins via plugins.gradle.org
"""

import sys
import json
import re
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser


class PluginVersionParser(HTMLParser):
    """Parse plugin versions from the plugin page"""
    def __init__(self, plugin_id):
        super().__init__()
        self.plugin_id = plugin_id
        self.versions = []
        self.latest_version = None
        self.in_version_section = False
        self.current_version = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        # Look for version links
        if tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            # Version links look like: /plugin/org.liquibase.gradle/3.0.2
            pattern = rf'^/plugin/{re.escape(self.plugin_id)}/(\d+[.\d\w-]*)$'
            match = re.match(pattern, href)
            if match:
                version = match.group(1)
                if version and version not in self.versions:
                    self.versions.append(version)

    def handle_data(self, data):
        # Try to find latest version from page text
        data = data.strip()
        if data and not self.latest_version:
            # Look for version patterns like "2.2.0" or "1.0.0-beta"
            version_pattern = r'\d+\.\d+[\.\d\w-]*'
            match = re.search(version_pattern, data)
            if match and len(self.versions) == 0:
                potential_version = match.group(0)
                # Basic validation - should start with digit
                if potential_version[0].isdigit():
                    self.latest_version = potential_version


class PluginSearchParser(HTMLParser):
    """Parse search results from plugins.gradle.org"""
    def __init__(self):
        super().__init__()
        self.plugins = []
        self.current_plugin = None
        self.in_plugin_name = False
        self.in_plugin_id = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Look for plugin links in search results
        if tag == 'a' and 'href' in attrs_dict:
            href = attrs_dict['href']
            # Plugin links look like: /plugin/org.liquibase.gradle
            if href.startswith('/plugin/') and '/version/' not in href:
                plugin_id = href.replace('/plugin/', '')
                if plugin_id and plugin_id not in [p['id'] for p in self.plugins]:
                    self.plugins.append({'id': plugin_id, 'url': f'https://plugins.gradle.org{href}'})


def search_plugins(search_term):
    """
    Search for Gradle plugins

    Args:
        search_term: Plugin name or ID to search for

    Returns:
        List of matching plugins with their IDs and URLs
    """
    try:
        encoded_term = quote(search_term)
        url = f'https://plugins.gradle.org/search?term={encoded_term}'

        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')

        parser = PluginSearchParser()
        parser.feed(html)

        return {
            'success': True,
            'search_term': search_term,
            'search_url': url,
            'plugins': parser.plugins
        }

    except HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP error {e.code}: {e.reason}',
            'search_term': search_term
        }
    except URLError as e:
        return {
            'success': False,
            'error': f'URL error: {e.reason}',
            'search_term': search_term
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}',
            'search_term': search_term
        }


def get_plugin_versions(plugin_id):
    """
    Get available versions for a specific plugin

    Args:
        plugin_id: The plugin ID (e.g., 'org.liquibase.gradle')

    Returns:
        Dictionary with version information
    """
    try:
        url = f'https://plugins.gradle.org/plugin/{plugin_id}'

        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')

        parser = PluginVersionParser(plugin_id)
        parser.feed(html)

        # Also check for latest version from the special tag (may not be in links)
        latest_pattern = r'<p\s+id="plugin-id-version"[^>]*>(\d+\.\d+[\.\d\w-]*)</p>'
        latest_match = re.search(latest_pattern, html)
        if latest_match:
            latest_from_tag = latest_match.group(1)
            if latest_from_tag not in parser.versions:
                parser.versions.insert(0, latest_from_tag)
            if not parser.latest_version:
                parser.latest_version = latest_from_tag

        # Determine latest version (first version in list from HTML order)
        latest = (parser.versions[0] if parser.versions else None) or parser.latest_version

        return {
            'success': True,
            'plugin_id': plugin_id,
            'plugin_url': url,
            'latest_version': latest,
            'versions': parser.versions[:10],  # Return up to 10 versions
            'total_versions': len(parser.versions)
        }

    except HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP error {e.code}: {e.reason}',
            'plugin_id': plugin_id
        }
    except URLError as e:
        return {
            'success': False,
            'error': f'URL error: {e.reason}',
            'plugin_id': plugin_id
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}',
            'plugin_id': plugin_id
        }


def find_gradle_files(start_path='.'):
    """
    Find all build.gradle and build.gradle.kts files in the directory tree

    Args:
        start_path: Starting directory for search (default: current directory)

    Returns:
        List of paths to Gradle build files
    """
    import os
    gradle_files = []

    for root, dirs, files in os.walk(start_path):
        # Skip common directories that shouldn't contain build files
        dirs[:] = [d for d in dirs if d not in ['.git', '.gradle', 'build', 'node_modules']]

        for file in files:
            if file in ['build.gradle', 'build.gradle.kts']:
                gradle_files.append(os.path.join(root, file))

    return gradle_files


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': 'Usage: gradle_plugin_helper.py <command> [args]',
            'commands': {
                'search': 'Search for plugins - usage: search <term>',
                'versions': 'Get plugin versions - usage: versions <plugin-id>',
                'find-files': 'Find Gradle build files - usage: find-files [path]'
            }
        }, indent=2))
        sys.exit(1)

    command = sys.argv[1]

    if command == 'search':
        if len(sys.argv) < 3:
            result = {'success': False, 'error': 'Search term required'}
        else:
            search_term = ' '.join(sys.argv[2:])
            result = search_plugins(search_term)

    elif command == 'versions':
        if len(sys.argv) < 3:
            result = {'success': False, 'error': 'Plugin ID required'}
        else:
            plugin_id = sys.argv[2]
            result = get_plugin_versions(plugin_id)

    elif command == 'find-files':
        start_path = sys.argv[2] if len(sys.argv) > 2 else '.'
        gradle_files = find_gradle_files(start_path)
        result = {
            'success': True,
            'gradle_files': gradle_files,
            'count': len(gradle_files)
        }

    else:
        result = {
            'success': False,
            'error': f'Unknown command: {command}',
            'available_commands': ['search', 'versions', 'find-files']
        }

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()