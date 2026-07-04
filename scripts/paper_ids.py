"""Helpers for stable paper identifiers."""

from __future__ import annotations

import re
from pathlib import Path


ARXIV_VERSION_RE = re.compile(r"v\d+$")


def canonical_arxiv_id(value: str) -> str:
    """Return an arXiv ID without the version suffix."""
    paper_id = value.rstrip("/").split("/")[-1]
    return ARXIV_VERSION_RE.sub("", paper_id)


def canonical_paper_id(value: str) -> str:
    """Normalize a stored arXiv URL or ID for deduplication."""
    return canonical_arxiv_id(value)


def existing_paper_ids(papers_dir: Path) -> set[str]:
    ids = set()
    for filepath in papers_dir.glob("*.md"):
        try:
            content = filepath.read_text()
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        try:
            fm_text = content[3:content.index("---", 3)]
        except ValueError:
            continue
        for line in fm_text.splitlines():
            if line.startswith("arxiv_id:"):
                ids.add(canonical_arxiv_id(line.split(":", 1)[1].strip().strip('"')))
                break
            if line.startswith("url:"):
                ids.add(canonical_paper_id(line.split(":", 1)[1].strip().strip('"')))
                break
    return ids
