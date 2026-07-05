"""Fetch recent AI blog/newsletter posts from RSS feeds."""

from __future__ import annotations

import json
import re
import socket
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

import feedparser
import yaml

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
SEEN_FILE = ROOT / "data" / "seen_blogs.json"
FEED_TIMEOUT_SECONDS = 20


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return text


def parse_entry_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    for attr in ("published", "updated"):
        value = entry.get(attr)
        if value:
            try:
                dt = parsedate_to_datetime(value)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


def post_matches_keywords(title: str, description: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{title} {description}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def fetch_blogs() -> list[dict]:
    socket.setdefaulttimeout(FEED_TIMEOUT_SECONDS)
    seen = load_seen()
    keywords = CONFIG.get("keyword_filters", [])
    feeds = CONFIG.get("blog_feeds", [])
    lookback_days = CONFIG.get("initial_lookback_days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    collected = {}

    for feed in feeds:
        source_name = feed["name"]
        parsed = feedparser.parse(feed["url"])
        if getattr(parsed, "bozo", False) and not parsed.entries:
            print(f"Warning: no usable feed entries for {source_name}: {parsed.bozo_exception}", file=sys.stderr)

        for entry in parsed.entries:
            url = entry.get("link", "").strip()
            if not url or url in seen or url in collected:
                continue

            published = parse_entry_date(entry)
            if published < cutoff:
                continue

            title = strip_html(entry.get("title", ""))
            description = strip_html(entry.get("summary", "") or entry.get("description", ""))
            if not title or not post_matches_keywords(title, description, keywords):
                continue

            collected[url] = {
                "id": url,
                "arxiv_id": "",
                "source_type": "blog",
                "source_name": source_name,
                "title": title,
                "authors": [source_name],
                "abstract": description,
                "categories": [],
                "published": published.astimezone(timezone.utc).isoformat(),
                "url": url,
                "pdf_url": "",
                "trusted": True,
            }

    posts = list(collected.values())
    print(f"Fetched {len(posts)} new blog posts")
    return posts


if __name__ == "__main__":
    posts = fetch_blogs()
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/blogs.json")
    output.write_text(json.dumps(posts, indent=2))
    print(f"Saved to {output}")
