"""Fetch recent papers from arXiv based on config."""

import arxiv
import yaml
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
SEEN_FILE = ROOT / "data" / "seen_papers.json"


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def paper_matches_keywords(paper: arxiv.Result, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = (paper.title + " " + paper.summary).lower()
    return any(kw.lower() in text for kw in keywords)


def fetch_papers() -> list[dict]:
    seen = load_seen()
    keywords = CONFIG.get("keyword_filters", [])
    per_cat = CONFIG.get("papers_per_category", 5)
    categories = CONFIG.get("arxiv_categories", [])
    lookback_days = CONFIG.get("initial_lookback_days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    client = arxiv.Client()
    collected = {}

    for category in categories:
        query = f"cat:{category}"
        search = arxiv.Search(
            query=query,
            max_results=per_cat * 4,  # fetch more, filter down
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        count = 0
        for result in client.results(search):
            if result.published < cutoff:
                break
            if result.entry_id in seen:
                continue
            if not paper_matches_keywords(result, keywords):
                continue

            paper_id = result.entry_id
            if paper_id not in collected:
                collected[paper_id] = {
                    "id": paper_id,
                    "arxiv_id": result.entry_id.split("/")[-1],
                    "title": result.title,
                    "authors": [a.name for a in result.authors],
                    "abstract": result.summary.replace("\n", " ").strip(),
                    "categories": result.categories,
                    "published": result.published.isoformat(),
                    "url": result.entry_id,
                    "pdf_url": result.pdf_url,
                }
                seen.add(paper_id)
                count += 1
                if count >= per_cat:
                    break

    # Don't save seen here — summarize.py saves seen only after successful write
    papers = list(collected.values())
    print(f"Fetched {len(papers)} new papers")
    return papers


if __name__ == "__main__":
    import sys
    papers = fetch_papers()
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/papers.json")
    output.write_text(json.dumps(papers, indent=2))
    print(f"Saved to {output}")
