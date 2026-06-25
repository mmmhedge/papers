"""Build papers.json for the web UI from markdown files."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAPERS_DIR = ROOT / "papers"
WEB_DIR = ROOT / "web"


def parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    content = filepath.read_text()
    if not content.startswith("---"):
        return {}, content
    try:
        end = content.index("---", 3)
    except ValueError:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end+3:].strip()
    result = {}
    current_key = None
    for line in fm_text.splitlines():
        if line.startswith("  - ") and current_key:
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(line.strip()[2:].strip())
        elif ": " in line and not line.startswith(" "):
            k, v = line.split(": ", 1)
            current_key = k.strip()
            result[current_key] = v.strip().strip('"')
        elif line.endswith(":") and not line.startswith(" "):
            current_key = line.rstrip(":").strip()
            result[current_key] = []
    return result, body


def extract_summary(body: str) -> str:
    match = re.search(r'## Summary\n+(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if match:
        return match.group(1).strip()[:400]
    return ""


def build_web():
    papers = []
    for filepath in sorted(PAPERS_DIR.glob("*.md"), reverse=True):
        fm, body = parse_frontmatter(filepath)
        if not fm:
            continue
        papers.append({
            "title": fm.get("title", filepath.stem),
            "authors": fm.get("authors", ""),
            "published": fm.get("published", ""),
            "url": fm.get("url", ""),
            "pdf": fm.get("pdf", ""),
            "tags": fm.get("tags", []),
            "summary": extract_summary(body),
            "date_added": fm.get("date_added", ""),
        })

    WEB_DIR.mkdir(exist_ok=True)
    output = WEB_DIR / "papers.json"
    output.write_text(json.dumps(papers, indent=2, ensure_ascii=False))
    print(f"Built papers.json with {len(papers)} papers")


if __name__ == "__main__":
    build_web()
