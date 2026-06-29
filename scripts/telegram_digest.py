"""Send daily Telegram digest with new papers and spaced repetition reminders."""

import os
import json
import yaml
import random
import html
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
    last_key = None
    for line in fm_text.splitlines():
        if ": " in line and not line.startswith(" "):
            k, v = line.split(": ", 1)
            last_key = k.strip()
            result[last_key] = v.strip().strip('"')
        elif line.rstrip().endswith(":") and not line.startswith(" "):
            last_key = line.rstrip()[:-1].strip()
            result[last_key] = []
        elif line.startswith("  - ") and last_key:
            if not isinstance(result[last_key], list):
                result[last_key] = []
            result[last_key].append(line[4:].strip())
    return result


def extract_sections(filepath: Path) -> dict:
    """Extract Summary and Key Takeaway from a paper markdown file."""
    try:
        content = filepath.read_text()
    except Exception:
        return {}
    result = {}
    for section, next_marker in [("Summary", "##"), ("Key Takeaway", "##")]:
        marker = f"## {section}"
        start = content.find(marker)
        if start == -1:
            continue
        start += len(marker)
        end = content.find("\n##", start)
        text = content[start:end].strip() if end != -1 else content[start:].strip()
        result[section.lower().replace(" ", "_")] = text
    return result


def enrich_from_file(paper: dict) -> dict:
    """Add summary and key_takeaway to a paper dict by reading its markdown file."""
    filename = paper.get("filename")
    if filename:
        filepath = PAPERS_DIR / filename
        if filepath.exists():
            paper.update(extract_sections(filepath))
    return paper


def get_papers_added_today(processed_file: Path = None) -> list[dict]:
    if processed_file and processed_file.exists():
        data = json.loads(processed_file.read_text())
        return [enrich_from_file({
            "title": item["paper"]["title"],
            "url": item["paper"]["url"],
            "tags": item.get("tags", []),
            "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "filename": item.get("filename"),
        }) for item in data]
    # Fallback: scan markdown files
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    papers = []
    for f in PAPERS_DIR.glob("*.md"):
        fm = parse_frontmatter(f)
        if fm.get("date_added") == today:
            fm.update(extract_sections(f))
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
            fm.update(extract_sections(f))
            candidates.append(fm)
    if len(candidates) > 3:
        candidates = random.sample(candidates, 3)
    return candidates


def format_paper_line(fm: dict) -> str:
    title = html.escape(fm.get("title", "Unknown"))
    url = fm.get("url", "")

    key_takeaway = fm.get("key_takeaway", "").strip()
    summary = fm.get("summary", "").strip()
    blurb = html.escape(key_takeaway or summary)

    lines = [f'• <a href="{url}"><b>{title}</b></a>']
    if blurb:
        lines.append(f'  {blurb}')
    return "\n".join(lines)


def generate_overview(papers: list[dict]) -> str:
    """Ask Claude for a news-style overview of today's papers, split into short paragraphs."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        import anthropic
        titles_and_takeaways = "\n".join(
            f"- {p.get('title', '')}: {p.get('key_takeaway') or p.get('summary', '')[:120]}"
            for p in papers[:30]
        )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CONFIG.get("summarization_model", "claude-haiku-4-5-20251001"),
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    "Write a news-style overview of today's research papers for a researcher's daily digest. "
                    "Split into 2-3 short paragraphs by theme. Each paragraph: 2-3 sentences. "
                    "For technical topics (e.g. mechanistic interpretability, DeFi, POMDP), briefly say what it is before the finding. "
                    "Be specific and concrete — name actual findings, not just 'researchers explored X'. "
                    "IMPORTANT: plain text only. No markdown, no asterisks, no bullet points, no headers.\n\n"
                    f"{titles_and_takeaways}"
                )
            }]
        )
        return html.escape(msg.content[0].text.strip())
    except Exception as e:
        print(f"Overview generation failed: {e}")
        return ""


def build_digest(new_papers: list[dict], sr_papers: list[dict]) -> str:
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [f"<b>📚 Daily Papers — {today_str}</b>"]

    if new_papers:
        overview = generate_overview(new_papers)
        if overview:
            lines.append(f"\n{overview}")
        lines.append(f"\n<b>New today — {len(new_papers)} papers</b>")
        for fm in new_papers:
            lines.append(format_paper_line(fm))
    else:
        lines.append("\nNo new papers matched your filters today.")

    if sr_papers:
        lines.append(f"\n<b>🔁 Worth revisiting</b>")
        for fm in sr_papers:
            added = fm.get("date_added", "")
            lines.append(format_paper_line(fm) + f"\n  <i>added {added}</i>")

    return "\n".join(lines)


TELEGRAM_MAX_LEN = 4000


def split_messages(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MAX_LEN:
        return [text]
    messages = []
    while text:
        if len(text) <= TELEGRAM_MAX_LEN:
            messages.append(text)
            break
        split_at = text.rfind("\n•", 0, TELEGRAM_MAX_LEN)
        if split_at == -1:
            split_at = TELEGRAM_MAX_LEN
        messages.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return messages


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
    parts = split_messages(digest)
    print(f"Sending digest ({len(parts)} message(s))...")
    for i, part in enumerate(parts, 1):
        result = telegram_send(token, chat_id, part)
        if result.get("ok"):
            print(f"Part {i}/{len(parts)} sent")
        else:
            print(f"Telegram error on part {i}: {result}")
            break


if __name__ == "__main__":
    main()
