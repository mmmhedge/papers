"""Create and optionally Telegram-send a deep technical paper summary."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import yaml
from pypdf import PdfReader

ROOT = Path(__file__).parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yml").read_text())
OUTPUT_DIR = ROOT / "deep_summaries"
TELEGRAM_MAX_LEN = 3800


DEEP_SUMMARY_PROMPT = """You write deep technical paper summaries in the same structure as the GPT-3/VAE post.

Use this exact section order:

1. A plain-language intro naming the paper
2. Background: what came before and why the paper matters
3. Architecture
4. Actual equations
5. Training details
6. Exact hyperparameter and data tables
7. How evaluation works
8. Core finding with concrete numbers
9. Why it works
10. Practical picture: what builds on it
11. Data contamination methodology
12. Precise limitations
13. One-paragraph summary
14. References line

Style rules:
- Lead with intuition and the conceptual point, then move into real technical content.
- Pull actual numbers, tables, equations, methodology, benchmark results, and contamination details from the paper text.
- If the paper does not contain a requested item, say exactly that instead of inventing it.
- Equations must be in plain fenced code blocks. Do not use inline HTML, color spans, or rendered LaTeX.
- Diagrams, if useful, must be Mermaid or plain code blocks.
- Prefer prose over bullets. Use compact tables only where the paper gives actual table-like details.
- Connect explicitly to earlier posts in the chain when relevant. For GPT-3, connect back to the autoregressive post.
- Keep it technically honest: no surface-only summaries, no memory-only claims, no fake values.

Write in Markdown. Keep the summary detailed but readable."""


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value[:90] or "paper"


def resolve_source(source: str) -> tuple[str, str]:
    source_path = Path(source).expanduser()
    if source_path.exists():
        return source_path.resolve().as_uri(), source

    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        if "arxiv.org/abs/" in source:
            arxiv_id = source.rstrip("/").split("/")[-1]
            return f"https://arxiv.org/pdf/{arxiv_id}", source
        return source, source

    arxiv_id = source.strip()
    return f"https://arxiv.org/pdf/{arxiv_id}", arxiv_id


def download_pdf(pdf_url: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix="deep-paper-", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    req = urllib.request.Request(pdf_url, headers={"User-Agent": "papers-deep-summary/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        content_type = response.headers.get("content-type", "")
        data = response.read()

    if not data.startswith(b"%PDF"):
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded content does not look like a PDF: {content_type or 'unknown content type'}")

    tmp_path.write_bytes(data)
    return tmp_path


def extract_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    chunks = []
    for index, page in enumerate(pages, 1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(f"\n\n--- Page {index} ---\n{text.strip()}")
    return "\n".join(chunks).strip()


def trim_paper_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    head = int(max_chars * 0.68)
    tail = max_chars - head
    return (
        text[:head].rstrip()
        + "\n\n--- Middle pages omitted for context length; preserve exact details from visible tables/equations above and below. ---\n\n"
        + text[-tail:].lstrip()
    )


def generate_summary(title_hint: str, source_label: str, paper_text: str, math_depth: str, include_tables: bool) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")

    table_instruction = (
        "Include exact hyperparameter and data tables when present in the paper."
        if include_tables
        else "Mention table values in prose only; do not recreate full tables."
    )
    user_message = f"""Paper source: {source_label}
Title hint: {title_hint or "infer from the paper"}
Math depth: {math_depth}
Tables: {table_instruction}

Paper text extracted from the PDF:

{paper_text}
"""

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=CONFIG.get("deep_summary_model", CONFIG.get("summarization_model", "claude-haiku-4-5-20251001")),
        max_tokens=6000,
        system=DEEP_SUMMARY_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


def telegram_send_plain(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def split_messages(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MAX_LEN:
        return [text]
    parts = []
    while text:
        if len(text) <= TELEGRAM_MAX_LEN:
            parts.append(text)
            break
        split_at = max(
            text.rfind("\n## ", 0, TELEGRAM_MAX_LEN),
            text.rfind("\n\n", 0, TELEGRAM_MAX_LEN),
        )
        if split_at < TELEGRAM_MAX_LEN // 2:
            split_at = TELEGRAM_MAX_LEN
        parts.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return parts


def send_to_telegram(summary: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required to send")

    parts = split_messages(summary)
    print(f"Sending deep summary ({len(parts)} message(s))...")
    for index, part in enumerate(parts, 1):
        result = telegram_send_plain(token, chat_id, part)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram error on part {index}: {result}")
        message_id = result.get("result", {}).get("message_id", "unknown")
        print(f"Part {index}/{len(parts)} sent (message_id={message_id})")


def write_summary(summary: str, title_hint: str, source_label: str, output: Path | None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if output is None:
        stem = slugify(title_hint or source_label)
        output = OUTPUT_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{stem}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(summary + "\n")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a GPT-3/VAE-style deep technical paper summary and optionally send it to Telegram."
    )
    parser.add_argument("source", help="arXiv ID, arXiv abs/pdf URL, PDF URL, or local PDF path")
    parser.add_argument("--title", default="", help="Optional title hint for the output filename and prompt")
    parser.add_argument("--output", type=Path, help="Optional markdown output path")
    parser.add_argument("--max-pages", type=int, default=None, help="Only read the first N PDF pages")
    parser.add_argument("--max-chars", type=int, default=160000, help="Maximum extracted PDF characters sent to Claude")
    parser.add_argument(
        "--math-depth",
        choices=["light", "standard", "heavy"],
        default="heavy",
        help="How math-heavy the summary should be",
    )
    parser.add_argument("--no-tables", action="store_true", help="Do not recreate full tables")
    parser.add_argument("--no-telegram", action="store_true", help="Save locally but do not send to Telegram")
    return parser.parse_args()


def main():
    args = parse_args()
    pdf_url, source_label = resolve_source(args.source)
    pdf_path = Path(args.source).expanduser() if Path(args.source).expanduser().exists() else download_pdf(pdf_url)

    print(f"Reading PDF: {source_label}")
    paper_text = extract_pdf_text(pdf_path, args.max_pages)
    if not paper_text:
        raise RuntimeError("Could not extract text from PDF")

    paper_text = trim_paper_text(paper_text, args.max_chars)
    print(f"Extracted {len(paper_text):,} characters")

    summary = generate_summary(
        title_hint=args.title,
        source_label=source_label,
        paper_text=paper_text,
        math_depth=args.math_depth,
        include_tables=not args.no_tables,
    )
    output = write_summary(summary, args.title, source_label, args.output)
    print(f"Saved: {output}")

    if not args.no_telegram:
        send_to_telegram(summary)


if __name__ == "__main__":
    main()
