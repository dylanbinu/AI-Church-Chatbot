# AI Church Chatbot

Multi-tenant AI greeter for church websites. **One chatbot app** serves every church; each church gets its own scraped knowledge bundle.

> **How to deploy & operate in production:** see **[DEPLOY.md](DEPLOY.md)** — start to finish.

---

## How it works

1. Register a church in `code/churches.json`
2. Updater scrapes that church’s site and stores a zip in S3
3. Chat Lambda loads that zip and answers only from that church’s data
4. The same `<church-chatbot church-id="...">` widget is used for every church

### Runtime split (efficient)

| Lambda | Image | Role |
|---|---|---|
| Chat (`server.handler`) | Slim (`Dockerfile.chat`) | Fast answers, no browser |
| Updater (`updater.handler`) | `Dockerfile.updater` | Weekly scrape only |

---

## Local development

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
copy .env.example .env   # set OPENAI_API_KEY
```

```bat
Batch Scripts\data_prep.bat heritage
Batch Scripts\launch_server.bat --setup
```

Open http://127.0.0.1:8004

```bash
pytest code/tests -q
```

---

## Production (summary)

```bat
Batch Scripts\deploy_heritage.bat      :: ship code (chat + updater images)
Batch Scripts\create_updater.bat       :: first time only
Batch Scripts\setup_schedule.bat       :: weekly Monday 3am Detroit
Batch Scripts\setup_schedule.bat --invoke-now
Batch Scripts\status.bat               :: health check
```

Full details, env vars, adding churches, and troubleshooting: **[DEPLOY.md](DEPLOY.md)**

---

## Project layout

```text
code/                  App (API, RAG, scraper, widget, registry)
Dockerfile.chat        Slim chat image
Dockerfile.updater     Updater image (page download, no browser)
Batch Scripts/         Deploy, schedule, status, local helpers
DEPLOY.md              Production operations guide
.runtime/              Local per-church data (gitignored)
```

---

## Embed

```html
<script src="https://YOUR_FUNCTION_URL/church_chatbot.js" defer></script>
<church-chatbot
  api-url="https://YOUR_FUNCTION_URL/chat"
  church-id="heritage"
  title="Church Assistant"
></church-chatbot>
```
