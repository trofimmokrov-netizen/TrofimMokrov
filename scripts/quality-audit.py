#!/usr/bin/env python3
"""Read-only quality audit for generated static pages. Standard library only."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
BASE = SITE["base_url"].rstrip("/") + "/"
PAGES = sorted(ROOT.glob("*.html")) + sorted((ROOT / "articles").glob("*.html"))
ISSUES = []

class Scanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.current_title = False
        self.canonicals = []
        self.descriptions = []
        self.images = []
        self.links = []
        self.viewport = False
        self.lang = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = bool(a.get("lang"))
        if tag == "title":
            self.current_title = True
        if tag == "meta":
            if a.get("name", "").lower() == "description":
                self.descriptions.append(a.get("content", "").strip())
            if a.get("name", "").lower() == "viewport":
                self.viewport = True
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        if tag == "img":
            self.images.append(a)
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag == "script" and a.get("src", "").lower().startswith("http://"):
            ISSUES.append("insecure external script URL")
    def handle_data(self, data):
        if self.current_title:
            self.title.append(data)
    def handle_endtag(self, tag):
        if tag == "title":
            self.current_title = False

canonical_owners = {}
page_map = {}
for path in PAGES:
    doc = Scanner()
    doc.feed(path.read_text(encoding="utf-8"))
    rel = path.relative_to(ROOT).as_posix()
    page_map[rel] = doc
    if not doc.lang:
        ISSUES.append(f"{rel}: HTML language missing")
    if not doc.viewport:
        ISSUES.append(f"{rel}: viewport missing")
    title = "".join(doc.title).strip()
    if not title or len(title) > 100:
        ISSUES.append(f"{rel}: empty or overly long title")
    if len(doc.descriptions) != 1 or not doc.descriptions[0]:
        ISSUES.append(f"{rel}: expected exactly one non-empty description")
    if len(doc.canonicals) != 1:
        ISSUES.append(f"{rel}: expected exactly one canonical")
    else:
        canonical = doc.canonicals[0]
        wanted = urljoin(BASE, "" if rel == "index.html" else rel)
        if canonical != wanted:
            ISSUES.append(f"{rel}: canonical {canonical!r} differs from {wanted!r}")
        if canonical in canonical_owners:
            ISSUES.append(f"{rel}: duplicate canonical used by {canonical_owners[canonical]}")
        canonical_owners[canonical] = rel
    for img in doc.images:
        if not img.get("alt") and "alt" not in img:
            ISSUES.append(f"{rel}: image has no alt attribute")
        if not img.get("width") or not img.get("height"):
            ISSUES.append(f"{rel}: image dimensions missing ({img.get('src', '')})")
    for href in doc.links:
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        u = urlsplit(href)
        if u.scheme or u.netloc:
            continue
        destination = (path.parent / unquote(u.path or path.name)).resolve()
        if not destination.is_relative_to(ROOT):
            ISSUES.append(f"{rel}: link escapes repository: {href}")
        elif not destination.exists():
            ISSUES.append(f"{rel}: broken internal link: {href}")

for issue in ISSUES:
    print("FAIL:", issue)
print(f"Audited {len(PAGES)} HTML pages; found {len(ISSUES)} quality issues.")
sys.exit(bool(ISSUES))
