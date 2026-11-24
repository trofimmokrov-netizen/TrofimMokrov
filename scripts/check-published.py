#!/usr/bin/env python3
"""Check the deployed Pages site with read-only HTTP requests."""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    '/': ('id="main"', 'contact.html#request-form', 'start=app'),
    '/contact.html': ('id="request-form"', 'data-b24-form=', 'id="telegram"', 'аванса 5 000 ₽'),
    '/services.html': ('id="business-system"', 'id="social-actions"', 'id="work-terms"'),
    '/portfolio.html': ('id="telegram-projects"',),
    '/articles.html': ('id="library-search"', 'id="topic-telegram"', 'id="topic-crm"'),
    '/updates.html': ('class="updates-feed"',),
    '/miniapp/': ('id="services-view"', 'id="request-view"', 'app.js?', 'аванса 5 000 ₽'),
    '/miniapp/app.js': ('loader_25.js', 'site_button/loader_3_gbqxj4.js'),
    '/miniapp/catalog.json': (),
}


def fetch(url):
    request = Request(url, headers={'User-Agent': 'Trofim-site-health/1.0'})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise OSError(f'HTTP {response.status}')
                return response.read(2_000_000).decode('utf-8')
        except HTTPError as error:
            if attempt or (error.code != 429 and error.code < 500):
                raise
        except (URLError, TimeoutError):
            if attempt:
                raise
        time.sleep(2)


def check(base, path, markers):
    url = urljoin(base, path.removeprefix('/'))
    try:
        contents = fetch(url)
        if path.endswith('.json'):
            parsed = json.loads(contents)
            if (not isinstance(parsed, dict) or not isinstance(parsed.get('services'), list)
                    or not parsed['services'] or not isinstance(parsed.get('site'), dict)):
                raise ValueError('incomplete catalogue')
        elif any(marker not in contents for marker in markers):
            raise ValueError('expected page or resource markers are missing')
    except (OSError, ValueError) as error:
        return f'FAIL {path}: {error}', False
    return f'PASS {path}', True


def main():
    site = json.loads((ROOT / 'content/site.json').read_text())
    base = site['base_url'].rstrip('/') + '/'
    if urlsplit(base).scheme != 'https' or not urlsplit(base).hostname:
        raise SystemExit('No canonical HTTPS site configured for the public checks.')
    # Pages and the health workflow can start concurrently on a push to main.
    deadline = time.monotonic() + (90 if os.environ.get('GITHUB_EVENT_NAME') == 'push' else 0)
    pending = CHECKS
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        while pending:
            checks = {path: executor.submit(check, base, path, markers) for path, markers in pending.items()}
            results.update((path, result.result()) for path, result in checks.items())
            pending = {path: CHECKS[path] for path in pending if not results[path][1]}
            if not pending or time.monotonic() >= deadline:
                break
            time.sleep(min(8, max(0, deadline - time.monotonic())))
    for message, _ in results.values():
        print(message)
    return 0 if all(success for _, success in results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
