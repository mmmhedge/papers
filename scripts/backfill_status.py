"""Add status: unread to all papers that don't have it yet."""

from pathlib import Path

PAPERS_DIR = Path(__file__).parent.parent / "papers"

def backfill():
    updated = 0
    for filepath in sorted(PAPERS_DIR.glob("*.md")):
        text = filepath.read_text()
        if not text.startswith("---"):
            continue
        # Already has status field — skip
        try:
            end = text.index("---", 3)
        except ValueError:
            continue
        fm = text[3:end]
        if "status:" in fm:
            continue
        # Insert status: unread after date_added line
        if "date_added:" in fm:
            new_fm = fm.replace(
                next(l for l in fm.splitlines() if l.startswith("date_added:")),
                next(l for l in fm.splitlines() if l.startswith("date_added:")) + "\nstatus: unread",
                1
            )
        else:
            # Fallback: insert before trusted: or tags:
            for anchor in ("trusted:", "tags:"):
                if anchor in fm:
                    new_fm = fm.replace(anchor, f"status: unread\n{anchor}", 1)
                    break
            else:
                new_fm = fm + "\nstatus: unread\n"
        new_text = "---" + new_fm + "---" + text[end+3:]
        filepath.write_text(new_text)
        updated += 1

    print(f"Backfilled {updated} papers with status: unread")

if __name__ == "__main__":
    backfill()
