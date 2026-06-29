"""Summarize papers using Claude and write Obsidian-style markdown notes."""

import anthropic
import yaml
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
PAPERS_DIR = ROOT / "papers"
TAGS_FILE = ROOT / "tags.json"
SEEN_FILE = ROOT / "data" / "seen_papers.json"

SYSTEM_PROMPT = """You are a research assistant creating structured knowledge notes in Obsidian markdown format.

You will receive a paper's title, abstract, and metadata, and you must produce a rich, insightful note.

CRITICAL — for tags:
- Use 1-3 tags maximum.
- You MUST only use tags from this fixed list — do not invent new ones:
  large-language-models, nlp, transformers, reinforcement-learning,
  mechanistic-interpretability, alignment, generative-models, multi-agent-systems,
  agents, deep-learning, quantitative-finance, algorithmic-trading,
  market-microstructure, derivatives-pricing, risk-management,
  computer-vision, optimization, graph-neural-networks
- Pick the tags that best describe the paper's PRIMARY research area (subdiscipline), not specific techniques or incidental properties.
- Return tags as a JSON array in your response.

FORMAT your response EXACTLY as follows (use these exact section headers):

TAGS_JSON: ["tag1", "tag2", ...]

## Summary
2-3 sentence plain-English summary of what this paper does and why it matters.

## Theoretical Background
What prior work, mathematical frameworks, or conceptual foundations does this paper build on? Write for a smart reader who may not know this subfield. Keep sentences short. Keep technical terms but briefly explain them inline the first time they appear (e.g. "transformers — neural networks that process sequences using attention mechanisms"). Don't assume the reader knows every concept; don't over-explain things that are genuinely common knowledge.

## Core Contributions
What is genuinely new here? Be specific — avoid restating the abstract.

## Connections to Other Work
How does this relate to other approaches, paradigms, or open problems in the field? Use [[wikilink]] style for concepts or papers that might exist as notes (e.g. [[Attention Is All You Need]], [[RLHF]]).

## Practical Applications
Concrete real-world use cases. Be specific and grounded.

## Product & Startup Ideas
3-5 specific product ideas or business applications that could emerge from this research. Think commercially.

## Technical Limitations
What does this paper NOT solve? What assumptions might break in practice? What are the hard constraints?

## Open Questions
What would a follow-up paper need to address? What experiments would you want to see?

## Key Takeaway
One sentence. The single most important thing to remember about this paper."""

def load_tags() -> dict:
    if TAGS_FILE.exists():
        return json.loads(TAGS_FILE.read_text())
    return {"version": 1, "tags": {}, "aliases": {}, "last_clustered": None}


def save_tags(tags_data: dict):
    TAGS_FILE.write_text(json.dumps(tags_data, indent=2, sort_keys=True))


def update_tag_vocab(tags_data: dict, new_tags: list[str]):
    for tag in new_tags:
        if tag not in tags_data["tags"]:
            tags_data["tags"][tag] = {"count": 0, "first_seen": datetime.now(timezone.utc).isoformat()}
        tags_data["tags"][tag]["count"] += 1


def parse_claude_response(response: str) -> tuple[list[str], str]:
    tags = []
    tags_match = re.search(r"TAGS_JSON:\s*(\[.*?\])", response, re.DOTALL)
    if tags_match:
        try:
            tags = json.loads(tags_match.group(1))
        except json.JSONDecodeError:
            tags = []
    # Remove the TAGS_JSON line from the body
    body = re.sub(r"TAGS_JSON:.*?\n", "", response, count=1).strip()
    return tags, body


def paper_to_note(paper: dict, body: str, tags: list[str]) -> str:
    authors_str = ", ".join(paper["authors"][:5])
    if len(paper["authors"]) > 5:
        authors_str += f" et al."
    categories_str = ", ".join(paper.get("categories", []))
    published = paper["published"][:10]

    tag_lines = "\n".join(f"  - {t}" for t in sorted(tags))

    return f"""---
title: "{paper['title'].replace('"', "'")}"
arxiv_id: "{paper['arxiv_id']}"
authors: "{authors_str}"
published: {published}
url: "{paper['url']}"
pdf: "{paper['pdf_url']}"
arxiv_categories: "{categories_str}"
date_added: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
tags:
{tag_lines}
---

# {paper['title']}

**Authors:** {authors_str}
**Published:** {published} | **arXiv:** [{paper['arxiv_id']}]({paper['url']})

{body}
"""


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def summarize_paper(client: anthropic.Anthropic, paper: dict, tags_data: dict, model: str) -> str:
    existing_tags = sorted(tags_data["tags"].keys())
    tag_vocab_str = json.dumps(existing_tags, indent=2) if existing_tags else "[]"

    user_message = f"""Paper title: {paper['title']}

Authors: {', '.join(paper['authors'][:8])}
Published: {paper['published'][:10]}
arXiv categories: {', '.join(paper.get('categories', []))}

Abstract:
{paper['abstract']}

Current tag vocabulary (reuse these when appropriate):
{tag_vocab_str}

Please create the structured note now."""

    last_err = None
    for attempt in range(4):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  -> API error (attempt {attempt+1}/4): {type(e).__name__}: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def process_papers(papers_file: Path):
    papers = json.loads(papers_file.read_text())
    if not papers:
        print("No papers to process")
        return []

    tags_data = load_tags()
    model = CONFIG.get("summarization_model", "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic()
    PAPERS_DIR.mkdir(exist_ok=True)

    seen = load_seen()
    processed = []
    for paper in papers:
        arxiv_id = paper["arxiv_id"]
        safe_title = re.sub(r'[^\w\s-]', '', paper['title'])[:80].strip().replace(' ', '-')
        filename = f"{paper['published'][:10]}-{arxiv_id}-{safe_title}.md"
        filepath = PAPERS_DIR / filename

        if filepath.exists():
            print(f"Skipping (already exists): {filename}")
            seen.add(paper["id"])
            save_seen(seen)
            continue

        print(f"Summarizing: {paper['title'][:60]}...")
        try:
            response = summarize_paper(client, paper, tags_data, model)
            tags, body = parse_claude_response(response)
            update_tag_vocab(tags_data, tags)
            note = paper_to_note(paper, body, tags)
            filepath.write_text(note)
            seen.add(paper["id"])
            save_seen(seen)
            print(f"  -> Saved: {filename}")
            processed.append({"paper": paper, "tags": tags, "filename": filename})
        except Exception as e:
            print(f"  -> Error ({type(e).__name__}): {e}")

    save_tags(tags_data)
    print(f"\nProcessed {len(processed)} papers. Tag vocab size: {len(tags_data['tags'])}")
    return processed


if __name__ == "__main__":
    import sys
    papers_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/papers.json")
    results = process_papers(papers_file)
    output = papers_file.parent / "processed.json"
    output.write_text(json.dumps(results, indent=2, default=str))
    print(f"Results saved to {output}")
