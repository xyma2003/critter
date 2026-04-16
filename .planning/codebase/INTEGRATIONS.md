# External Integrations

**Analysis Date:** 2026-04-16

## APIs & External Services

**News Sources (fetched in `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`):**

- **Google Trends RSS** — Trending US search topics
  - Endpoint: `https://trends.google.com/trending/rss?geo=US`
  - Auth: None (public RSS feed)
  - Transport: `urllib.request` with SSL verification disabled (`ssl.CERT_NONE`)
  - Result: XML parsed via `re.findall` for `<title>` and `<link>` fields

- **Baidu Realtime Hot Search** — Chinese trending topics
  - Endpoint: `https://top.baidu.com/board?tab=realtime`
  - Auth: None (scraped via User-Agent spoofing)
  - Transport: `urllib.request`, HTML scraped with regex `"query":"([^"]+)".*?"url":"([^"]+)"`
  - Result: Top 10 search queries with URLs

- **Weibo Hot Search** — Chinese social media trending topics
  - Endpoint: `https://weibo.com/ajax/side/hotSearch`
  - Auth: None (public JSON API, `Referer: https://weibo.com/` header required)
  - Transport: `urllib.request`, response parsed as JSON
  - Result: `data.realtime[].word` entries, top 10

**AI / LLM:**

- **Claude CLI** — Conversational AI and batch translation
  - Binary: `/opt/homebrew/bin/claude` (version `2.1.104`)
  - Chat mode: `subprocess.Popen` with flags `--print --output-format stream-json --include-partial-messages --verbose --system-prompt <prompt>`; reads streaming NDJSON lines from stdout, extracts `content_block_delta` text events to build response incrementally in `desktop_pet.py:_stream_pet_ai()`
  - Translation mode: `subprocess.run` with `--print <prompt>`; used in `_translate_titles_with_claude()` to batch-translate English Google Trends headlines to Chinese format `中文（原文）`
  - Auth: Managed by Claude CLI itself (no API key handled in this codebase)

## Data Storage

**Databases:**
- None — no database engine

**File Storage (local JSON files):**
- `~/.openclaw/workspace/desktop-pet/settings.json` — user preferences (`pet_emoji`, `pet_size`, `auto_refresh_min`, `notify_on_refresh`); read at startup, written on settings save
- `~/.openclaw/workspace/desktop-pet/notes.json` — sticky notes data; structure `{"notes": [{"id": int, "content": str, "updated": int}]}`; read/written on every note create/edit/delete
- `~/.openclaw/workspace/desktop-pet/web-pet/news_cache.json` — news content cache; structure `{"content": str, "timestamp": float}`; TTL 1800 seconds, shared between `desktop_pet.py` and `web-pet/server.py`

**Caching:**
- File-based cache only (see `news_cache.json` above); no in-memory cache layer

## Authentication & Identity

**Auth Provider:**
- None — no user authentication; single-user local application

## Monitoring & Observability

**Error Tracking:**
- None — errors are silently swallowed in `except Exception: pass` blocks throughout both `desktop_pet.py` and `fetch_news.py`; SSL errors in news fetching are suppressed via `ssl.CERT_NONE`

**Logs:**
- `web-pet/server.py` suppresses all HTTP access logs (`log_message` overridden to no-op)
- No application-level logging framework

## CI/CD & Deployment

**Hosting:**
- Local macOS desktop only

**CI Pipeline:**
- None

## Environment Configuration

**Required env vars:**
- None — no environment variables used; all configuration is in `settings.json` or hardcoded paths

**Secrets location:**
- No secrets; Claude CLI handles its own authentication externally

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- macOS system notifications sent via `osascript` subprocess:
  - Called from `send_notification()` in `desktop_pet.py` (news push feature)
  - Called from `send_macos_notification()` in `web-pet/server.py` (HTTP `/push` endpoint)
  - Script: `display notification "<body>" with title "<title>" sound name "Blow"`

## External Processes Called

**`/opt/homebrew/bin/claude`** (Claude CLI)
- Used by: `desktop_pet.py` — `_stream_pet_ai()`, `_translate_titles_with_claude()`
- Invocation: `subprocess.Popen` (streaming) and `subprocess.run` (blocking, timeout 30s)

**`python3 <NEWS_SCRIPT>`** (news fetcher)
- Script: `~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py`
- Used by: `desktop_pet.py:fetch_news_raw()`, `news_pet.py:load_news()`, `web-pet/server.py:fetch_news_content()`
- Invocation: `subprocess.run` with `capture_output=True, timeout=30`

**`osascript -e <script>`** (macOS notification)
- Used by: `desktop_pet.py:send_notification()`, `web-pet/server.py:send_macos_notification()`
- Invocation: `subprocess.run`, timeout 5s

**`open <url>`** (browser launch)
- Used by: `desktop_pet.py` news tab click handler (`subprocess.Popen(['open', link])`)
- Opens clicked news article URLs in the system default browser

---

*Integration audit: 2026-04-16*
