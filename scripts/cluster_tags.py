"""Weekly tag clustering — merges near-duplicates and suggests better taxonomy."""

import anthropic
import json
import yaml
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
TAGS_FILE = ROOT / "tags.json"
PAPERS_DIR = ROOT / "papers"

SYSTEM_PROMPT = """You are maintaining a tag taxonomy for a personal research knowledge base.
You will receive the current tag vocabulary with usage counts.
Your job: clean it up and return a better version.

Rules:
- Merge near-duplicates (e.g. "llm" + "large-language-models" + "large-language-model" → "large-language-models")
- Keep the most descriptive/specific form as the canonical tag
- Don't merge tags that are genuinely distinct concepts
- Don't create new tags — only merge/rename existing ones
- Lowercase, hyphenated format only

Return ONLY valid JSON in this format:
{
  "merges": {
    "old-tag-1": "canonical-tag",
    "old-tag-2": "canonical-tag",
    "another-old": "its-canonical"
  },
  "reasoning": "brief explanation of main changes"
}

If no changes are needed, return: {"merges": {}, "reasoning": "taxonomy looks clean"}"""


def apply_merges_to_files(merges: dict):
    if not merges:
        return
    for filepath in PAPERS_DIR.glob("*.md"):
        content = filepath.read_text()
        changed = False
        for old_tag, new_tag in merges.items():
            if f"  - {old_tag}" in content:
                content = content.replace(f"  - {old_tag}", f"  - {new_tag}")
                changed = True
        if changed:
            filepath.write_text(content)
            print(f"  Updated tags in: {filepath.name}")


def cluster_tags():
    if not TAGS_FILE.exists():
        print("No tags file found")
        return

    tags_data = json.loads(TAGS_FILE.read_text())
    if len(tags_data["tags"]) < 5:
        print(f"Only {len(tags_data['tags'])} tags — skipping clustering")
        return

    model = CONFIG.get("clustering_model", "claude-sonnet-4-6")
    client = anthropic.Anthropic()

    tag_list = {tag: info["count"] for tag, info in sorted(
        tags_data["tags"].items(), key=lambda x: -x[1]["count"]
    )}

    user_msg = f"Current tag vocabulary (tag: usage count):\n{json.dumps(tag_list, indent=2)}"

    print(f"Clustering {len(tag_list)} tags with {model}...")
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    # Extract JSON even if there's surrounding text
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        print(f"Could not parse response: {raw}")
        return

    result = json.loads(match.group())
    merges = result.get("merges", {})
    reasoning = result.get("reasoning", "")

    print(f"Reasoning: {reasoning}")
    print(f"Merges: {json.dumps(merges, indent=2)}")

    if not merges:
        print("No merges needed")
    else:
        # Update tags_data
        for old_tag, canonical in merges.items():
            if old_tag in tags_data["tags"] and old_tag != canonical:
                old_count = tags_data["tags"].pop(old_tag)["count"]
                if canonical not in tags_data["tags"]:
                    tags_data["tags"][canonical] = {"count": 0, "first_seen": datetime.now(timezone.utc).isoformat()}
                tags_data["tags"][canonical]["count"] += old_count
                # Track alias
                tags_data["aliases"][old_tag] = canonical

        # Apply to paper files
        apply_merges_to_files(merges)

    tags_data["last_clustered"] = datetime.now(timezone.utc).isoformat()
    TAGS_FILE.write_text(json.dumps(tags_data, indent=2, sort_keys=True))
    print(f"Done. Tag vocab now has {len(tags_data['tags'])} tags.")


if __name__ == "__main__":
    cluster_tags()
