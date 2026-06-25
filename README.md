# Paper Tracker

Automated scientific paper tracker: fetches arXiv papers daily, summarizes them with Claude, stores them as Obsidian-compatible markdown, and sends a Telegram digest.

## Setup

### 1. GitHub Secrets
Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID (see below) |

**Getting your Telegram bot:**
1. Open Telegram → search `@BotFather` → `/newbot`
2. Follow prompts, copy the token
3. Start a chat with your bot, then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Send a message to your bot, refresh the URL, find `"chat":{"id":XXXXXXX}` — that's your chat ID

### 2. GitHub Pages
Go to **Settings → Pages** → Source: **GitHub Actions**

### 3. Obsidian Sync
Install the [Obsidian Git](https://github.com/denolehov/obsidian-git) plugin and point your vault at this repo. Set auto-pull interval to 10–30 minutes. New papers appear automatically after the daily workflow runs.

### 4. Customize Topics
Edit `config.yml` to adjust:
- `arxiv_categories` — which arXiv feeds to pull from
- `keyword_filters` — extra keyword filters applied on top
- `papers_per_category` — volume per day
- `summarization_model` — `claude-haiku-4-5-20251001` (fast/cheap) or `claude-sonnet-4-6` (higher quality)

## How It Works

| Component | When | What |
|-----------|------|------|
| `daily_papers.yml` | 7am UTC daily | Fetch → summarize → Telegram → commit |
| `weekly_cluster.yml` | 8am UTC Sunday | Merge duplicate tags, clean taxonomy |
| `pages.yml` | On push to main | Rebuild web UI at your GitHub Pages URL |

## Structure

```
papers/          ← one .md file per paper (Obsidian notes)
data/            ← seen paper IDs (deduplication)
scripts/         ← Python scripts
web/             ← GitHub Pages UI (index.html + papers.json)
tags.json        ← growing tag vocabulary
config.yml       ← your configuration
```

## Manual Run
Go to **Actions → Daily Paper Tracker → Run workflow** to trigger immediately.
