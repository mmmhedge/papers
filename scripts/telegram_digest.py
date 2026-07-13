"""Send daily Telegram digest with new papers and spaced repetition reminders."""

from __future__ import annotations

import os
import json
import yaml
import random
import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {e.code}: {body}") from e


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


def get_papers_added_today(processed_files: list[Path] = None) -> list[dict]:
    if processed_files:
        papers = []
        for processed_file in processed_files:
            if not processed_file.exists():
                continue
            data = json.loads(processed_file.read_text())
            papers.extend(enrich_from_file({
                "title": item["paper"]["title"],
                "url": item["paper"]["url"],
                "tags": item.get("tags", []),
                "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "source": item["paper"].get("source_type", "arxiv"),
                "source_name": item["paper"].get("source_name", ""),
                "filename": item.get("filename"),
            }) for item in data)
        return papers
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
    source = fm.get("source", "arxiv")
    source_name = html.escape(fm.get("source_name", ""))

    key_takeaway = fm.get("key_takeaway", "").strip()
    summary = fm.get("summary", "").strip()
    blurb = html.escape(simplify_blurb(key_takeaway or summary))

    label = f" [{source_name or 'blog'}]" if source == "blog" else ""
    safe_url = html.escape(url, quote=True)
    lines = [f'• <a href="{safe_url}"><b>{title}</b></a>{label}']
    if blurb:
        lines.append(f'  {blurb}')
    return "\n".join(lines)


def simplify_blurb(text: str, max_words: int = 22, max_chars: int = 180) -> str:
    """Make digest blurbs lighter without changing the underlying note."""
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`>#]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    sentence_match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    if sentence_match:
        text = sentence_match.group(1).strip()

    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(".,;:") + "..."
    elif len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:") + "..."
    return text


def generate_overview(papers: list[dict]) -> str:
    """Ask Claude for a news-style run overview with trends and context."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        import anthropic
        titles_and_takeaways = "\n".join(
            (
                f"- [{p.get('source', 'arxiv')}] {p.get('title', '')} "
                f"(tags: {', '.join(p.get('tags', [])) or 'none'}): "
                f"{p.get('key_takeaway') or p.get('summary', '')[:180]}"
            )
            for p in papers[:30]
        )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=CONFIG.get("summarization_model", "claude-haiku-4-5-20251001"),
            max_tokens=700,
            messages=[{
                "role": "user",
                "content": (
                    "Write the opening overview for a researcher's daily AI/ML digest. "
                    "Start with one concise sentence summarizing the run: how many items arrived and the dominant themes. "
                    "Then write 2 short paragraphs grouped by theme. Highlight overall trends across the items, "
                    "not just individual papers. Briefly explain background concepts a smart reader might not know "
                    "(for example, agentic RL, mechanistic interpretability, RoPE, DeFi, POMDP, or market microstructure) "
                    "when they are central to the trend. Be specific and concrete: name representative findings or posts. "
                    "Mention blog posts when they help explain the broader ecosystem signal. "
                    "IMPORTANT: plain text only. No markdown, no asterisks, no bullet points, no headers. "
                    f"Today's digest contains {len(papers)} new item(s).\n\n"
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
        message = "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise RuntimeError(message)
        print(f"{message} — skipping Telegram")
        return

    import sys
    processed_files = [Path(arg) for arg in sys.argv[1:]] if len(sys.argv) > 1 else None
    new_papers = get_papers_added_today(processed_files)
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
            message_id = result.get("result", {}).get("message_id", "unknown")
            print(f"Part {i}/{len(parts)} sent (message_id={message_id})")
        else:
            raise RuntimeError(f"Telegram error on part {i}: {result}")


if __name__ == "__main__":
    main()
