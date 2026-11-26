#!/usr/bin/env python3
"""Read-only quality audit for generated static pages. Standard library only."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from xml.etree import ElementTree
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
BASE = SITE["base_url"].rstrip("/") + "/"
PAGES = sorted([*ROOT.glob("*.html"), *(ROOT / "articles").glob("*.html"), *(ROOT / "cases").glob("*.html")])
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
        self.srcset = []
        self.open_graph = {}
        self.robots = []
        self.schema_scripts = []
        self.schema_text = None
        self.main_text = []
        self.inside_main = False
        self.inside_script = False
        self.viewport = False
        self.lang = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = bool(a.get("lang"))
        if tag == "main":
            self.inside_main = True
        if tag in ("script", "style"):
            self.inside_script = True
        if tag == "title":
            self.current_title = True
        if tag == "meta":
            if a.get("name", "").lower() == "description":
                self.descriptions.append(a.get("content", "").strip())
            if a.get("name", "").lower() == "viewport":
                self.viewport = True
            if a.get("name", "").lower() == "robots":
                self.robots.append(a.get("content", "").lower())
            if a.get("property", "").startswith("og:"):
                self.open_graph[a["property"]] = a.get("content", "").strip()
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        if tag == "img":
            self.images.append(a)
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag in ("img", "source") and a.get("srcset"):
            self.srcset.extend(candidate.strip().split()[0] for candidate in a["srcset"].split(",") if candidate.strip())
        if tag == "script" and a.get("type") == "application/ld+json":
            self.schema_text = []
        if tag == "script" and a.get("src", "").lower().startswith("http://"):
            ISSUES.append("insecure external script URL")
    def handle_data(self, data):
        if self.current_title:
            self.title.append(data)
        if self.schema_text is not None:
            self.schema_text.append(data)
        if self.inside_main and not self.inside_script:
            self.main_text.append(data)
    def handle_endtag(self, tag):
        if tag == "title":
            self.current_title = False
        if tag == "main":
            self.inside_main = False
        if tag in ("script", "style"):
            self.inside_script = False
        if tag == "script" and self.schema_text is not None:
            self.schema_scripts.append("".join(self.schema_text))
            self.schema_text = None

canonical_owners = {}
title_owners = {}
description_owners = {}
body_owners = {}
indexable = set()
for path in PAGES:
    doc = Scanner()
    doc.feed(path.read_text(encoding="utf-8"))
    rel = path.relative_to(ROOT).as_posix()
    if not doc.lang:
        ISSUES.append(f"{rel}: HTML language missing")
    if not doc.viewport:
        ISSUES.append(f"{rel}: viewport missing")
    title = "".join(doc.title).strip()
    if not title or len(title) > 100:
        ISSUES.append(f"{rel}: empty or overly long title")
    if len(doc.descriptions) != 1 or not doc.descriptions[0]:
        ISSUES.append(f"{rel}: expected exactly one non-empty description")
    for label, value, owners in (("title", title, title_owners),
                                  ("description", " ".join(doc.descriptions), description_owners),
                                  ("main content", " ".join(" ".join(doc.main_text).split()), body_owners)):
        if value in owners:
            ISSUES.append(f"{rel}: duplicate {label} used by {owners[value]}")
        owners[value] = rel
    wanted = urljoin(BASE, "" if rel == "index.html" else rel)
    if len(doc.canonicals) != 1:
        ISSUES.append(f"{rel}: expected exactly one canonical")
    else:
        canonical = doc.canonicals[0]
        if canonical != wanted:
            ISSUES.append(f"{rel}: canonical {canonical!r} differs from {wanted!r}")
        if canonical in canonical_owners:
            ISSUES.append(f"{rel}: duplicate canonical used by {canonical_owners[canonical]}")
        canonical_owners[canonical] = rel
    if rel != "404.html":
        indexable.add(wanted)
        if any("noindex" in value for value in doc.robots):
            ISSUES.append(f"{rel}: public page is marked noindex")
    if doc.open_graph.get("og:url") != wanted or any(not doc.open_graph.get(key) for key in (
        "og:title", "og:description", "og:type", "og:image"
    )):
        ISSUES.append(f"{rel}: incomplete or inconsistent Open Graph metadata")
    if rel.startswith(("articles/", "cases/")):
        try:
            nodes = [node for script in doc.schema_scripts for node in json.loads(script).get("@graph", [])]
            is_article = rel.startswith("articles/")
            entry_type = "Article" if is_article else "CreativeWork"
            entry = next(node for node in nodes if node.get("@type") == entry_type)
            trail = next(node for node in nodes if node.get("@type") == "BreadcrumbList")
            if entry.get("url") != wanted or trail["itemListElement"][-1]["item"] != wanted:
                raise ValueError("structured data URL differs from canonical")
            if is_article and (not entry.get("headline") or not entry.get("author")):
                raise ValueError("missing structured article headline or author")
        except (ValueError, TypeError, AttributeError, KeyError, IndexError, StopIteration):
            ISSUES.append(f"{rel}: invalid content or BreadcrumbList schema")
    for img in doc.images:
        if not img.get("alt") and "alt" not in img:
            ISSUES.append(f"{rel}: image has no alt attribute")
        if not img.get("width") or not img.get("height"):
            ISSUES.append(f"{rel}: image dimensions missing ({img.get('src', '')})")
    for href in doc.links + doc.srcset:
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

sitemap_url = urljoin(BASE, "sitemap.xml")
namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
try:
    sitemap = ElementTree.parse(ROOT / "sitemap.xml")
    urls = [item.text for item in sitemap.findall("s:url/s:loc", namespace)]
    if len(urls) != len(set(urls)) or set(urls) != indexable:
        ISSUES.append("sitemap.xml: URLs must match the indexable canonical pages without duplicates")
except (ElementTree.ParseError, OSError):
    ISSUES.append("sitemap.xml: could not parse the public sitemap")
robots = (ROOT / "robots.txt").read_text().splitlines()
if f"Sitemap: {sitemap_url}" not in robots or "User-agent: *" not in robots or "Allow: /" not in robots:
    ISSUES.append("robots.txt: sitemap or public crawl access missing")

for issue in ISSUES:
    print("FAIL:", issue)
print(f"Audited {len(PAGES)} HTML pages; found {len(ISSUES)} quality issues.")
sys.exit(bool(ISSUES))
