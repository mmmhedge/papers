---
title: Reading Dashboard

status: unread
---

# 📚 Reading Dashboard

> **How to use:** When you finish reading a paper, open it and change `status: unread` → `status: read` in the frontmatter.

---

## Unread Papers

```dataview
TABLE date_added AS "Added", tags AS "Topics"
FROM "papers"
WHERE status = "unread" AND file.name != "📚 Reading Dashboard"
SORT date_added DESC
```

---

## Read Papers

```dataview
TABLE date_added AS "Added", tags AS "Topics"
FROM "papers"
WHERE status = "read"
SORT date_added DESC
```

---

## Stats

```dataviewjs
const papers = dv.pages('"papers"').where(p => p.file.name !== "📚 Reading Dashboard");
const read = papers.where(p => p.status === "read").length;
const total = papers.length;
const pct = total > 0 ? Math.round(read / total * 100) : 0;
dv.paragraph(`**${read} / ${total} papers read (${pct}%)**`);
```

---

## Unread by Tag

```dataviewjs
const papers = dv.pages('"papers"').where(p => p.status === "unread" && p.file.name !== "📚 Reading Dashboard");
const tagCount = {};
for (const p of papers) {
    const tags = p.tags ?? [];
    for (const t of tags) tagCount[t] = (tagCount[t] ?? 0) + 1;
}
const sorted = Object.entries(tagCount).sort((a, b) => b[1] - a[1]);
dv.table(["Tag", "Unread"], sorted);
```
