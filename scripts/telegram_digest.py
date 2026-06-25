"""Send daily Telegram digest with new papers and spaced repetition reminders."""

import os
import json
import yaml
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request
import urllib.parse

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
PAPERS_DIR = ROOT / "papers"


def telegram_send(token: str, chat_id: str, text: str, parse_mode: str = "HTML"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def parse_frontmatter(filepath: Path) -> dict:
    content = filepath.read_text()
    if not content.startswith("---"):
        return {}
    end = content.index("---", 3)
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.splitlines():
        if ": " in line and not line.startswith(" "):
            k, v = line.split(": ", 1)
            result[k.strip()] = v.strip().strip('"')
        elif line.startswith("  - "):
            last_key = list(result.keys())[-1] if result else None
            if last_key:
                if not isinstance(result[last_key], list):
                    result[last_key] = []
                result[last_key].append(line.strip("  - ").strip())
    return result


def get_papers_added_today(processed_file: Path = None) -> list[dict]:
    # If a processed.json file is passed (from the summarize step), use it directly
    if processed_file and processed_file.exists():
        data = json.loads(processed_file.read_text())
        return [
            {
                "title": item["paper"]["title"],
                "url": item["paper"]["url"],
                "tags": item.get("tags", []),
                "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
            for item in data
        ]
    # Fallback: scan markdown files
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    papers = []
    for f in PAPERS_DIR.glob("*.md"):
        fm = parse_frontmatter(f)
        if fm.get("date_added") == today:
            papers.append(fm)
    return papers


def get_spaced_repetition_papers() -> list[dict]:
    sr_days = CONFIG.get("spaced_repetition_days", [3, 7, 14, 30])
    today = datetime.now(timezone.utc).date()
    candidates = []
    for f in PAPERS_DIR.glob("*.md"):
        fm = parse_frontmatter(f)
        if not fm.get("date_added"):
            continue
        added = datetime.strptime(fm["date_added"], "%Y-%m-%d").date()
        days_ago = (today - added).days
        if days_ago in sr_days:
            candidates.append(fm)
    # Pick up to 3 randomly if too many
    if len(candidates) > 3:
        candidates = random.sample(candidates, 3)
    return candidates


def format_paper_line(fm: dict) -> str:
    title = fm.get("title", "Unknown")
    url = fm.get("url", "")
    tags = fm.get("tags", [])
    if isinstance(tags, list):
        tags_str = " ".join(f"#{t}" for t in tags[:4])
    else:
        tags_str = ""
    return f'• <a href="{url}">{title}</a>\n  {tags_str}'


def build_digest(new_papers: list[dict], sr_papers: list[dict]) -> str:
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [f"<b>📚 Daily Papers — {today_str}</b>\n"]

    if new_papers:
        lines.append(f"<b>New today ({len(new_papers)} papers)</b>")
        for fm in new_papers:
            lines.append(format_paper_line(fm))
    else:
        lines.append("No new papers matched your filters today.")

    if sr_papers:
        lines.append(f"\n<b>🔁 Worth revisiting</b>")
        for fm in sr_papers:
            added = fm.get("date_added", "")
            lines.append(format_paper_line(fm) + f"\n  <i>Added {added}</i>")

    lines.append("\n<i>See all papers in your Obsidian vault or at your GitHub Pages site.</i>")
    return "\n".join(lines)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram")
        return

    import sys
    processed_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    new_papers = get_papers_added_today(processed_file)
    sr_papers = get_spaced_repetition_papers()

    if not new_papers and not sr_papers:
        print("Nothing to send today")
        return

    digest = build_digest(new_papers, sr_papers)
    print("Sending digest...")
    print(digest)
    result = telegram_send(token, chat_id, digest)
    if result.get("ok"):
        print("Digest sent successfully")
    else:
        print(f"Telegram error: {result}")


if __name__ == "__main__":
    main()
