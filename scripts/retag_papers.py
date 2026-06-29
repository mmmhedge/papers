"""One-shot script to trim existing paper tags to 2-4 core topic tags."""

import anthropic
import json
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAPERS_DIR = ROOT / "papers"
TAGS_FILE = ROOT / "tags.json"
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())


ALLOWED_TAGS = [
    "large-language-models", "nlp", "transformers", "reinforcement-learning",
    "mechanistic-interpretability", "alignment", "generative-models", "multi-agent-systems",
    "agents", "deep-learning", "quantitative-finance", "algorithmic-trading",
    "market-microstructure", "derivatives-pricing", "risk-management",
    "computer-vision", "optimization", "graph-neural-networks",
]


def get_new_tags(client, title: str, current_tags: list[str], key_takeaway: str) -> list[str]:
    resp = client.messages.create(
        model=CONFIG.get("summarization_model", "claude-haiku-4-5-20251001"),
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"Paper: {title}\n"
                f"Key takeaway: {key_takeaway}\n\n"
                f"Allowed tags: {ALLOWED_TAGS}\n\n"
                "Pick 1-3 tags from the allowed list that best describe this paper's PRIMARY research area. "
                "Do not use any tag not in the allowed list. "
                "Return ONLY a JSON array, nothing else."
            )
        }]
    )
    try:
        return json.loads(resp.content[0].text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\[.*?\]', resp.content[0].text, re.DOTALL)
        return json.loads(match.group()) if match else current_tags


def update_frontmatter_tags(filepath: Path, new_tags: list[str]) -> bool:
    content = filepath.read_text()
    if not content.startswith("---"):
        return False
    end = content.index("---", 3)
    fm_text = content[3:end]

    # Replace the tags block
    tag_lines = "\n".join(f"  - {t}" for t in sorted(new_tags))
    new_fm = re.sub(r'tags:\n(  - .*\n?)+', f'tags:\n{tag_lines}\n', fm_text)
    filepath.write_text("---" + new_fm + "---" + content[end + 3:])
    return True


def rebuild_tags_json(papers_dir: Path) -> dict:
    tags_data = {"version": 1, "tags": {}, "aliases": {}, "last_clustered": None}
    for f in papers_dir.glob("*.md"):
        content = f.read_text()
        if not content.startswith("---"):
            continue
        end = content.index("---", 3)
        for line in content[3:end].splitlines():
            if line.startswith("  - "):
                tag = line[4:].strip()
                if tag not in tags_data["tags"]:
                    tags_data["tags"][tag] = {"count": 0, "first_seen": ""}
                tags_data["tags"][tag]["count"] += 1
    return tags_data


def main():
    client = anthropic.Anthropic()
    papers = sorted(PAPERS_DIR.glob("*.md"))
    print(f"Retagging {len(papers)} papers...\n")

    for f in papers:
        content = f.read_text()
        if not content.startswith("---"):
            continue
        end = content.index("---", 3)
        fm_text = content[3:end]

        # Parse current tags
        tags = []
        in_tags = False
        for line in fm_text.splitlines():
            if line.strip() == "tags:":
                in_tags = True
                continue
            if in_tags:
                if line.startswith("  - "):
                    tags.append(line[4:].strip())
                else:
                    in_tags = False

        # Parse title and key takeaway
        title_match = re.search(r'^title:\s*"?(.+?)"?\s*$', fm_text, re.MULTILINE)
        title = title_match.group(1) if title_match else f.stem
        kt_match = re.search(r'## Key Takeaway\n(.+?)(?:\n##|$)', content, re.DOTALL)
        key_takeaway = kt_match.group(1).strip()[:200] if kt_match else ""

        new_tags = get_new_tags(client, title, tags, key_takeaway)
        update_frontmatter_tags(f, new_tags)
        print(f"  {f.name[:60]}")
        print(f"    {tags} → {new_tags}")

    tags_data = rebuild_tags_json(PAPERS_DIR)
    TAGS_FILE.write_text(json.dumps(tags_data, indent=2, sort_keys=True))
    print(f"\nDone. Tag vocab: {len(tags_data['tags'])} tags")


if __name__ == "__main__":
    main()
