# Deploy & Manage — AI Church Chatbot

This app is **multi-tenant**: one chatbot serves every church; each church has its own scraped data bundle in S3.

There are **two Lambda functions** and **two Docker images**:

| Piece | Name (default) | Image tag | Handler | Purpose |
|---|---|---|---|---|
| Chat | `church-bot-heritage` | `:chat` (also `:latest`) | `server.handler` | Answers questions (slim, no browser) |
| Updater | `church-bot-updater` | `:updater` | `updater.handler` | Weekly scrape → S3 zip |

Data lives in S3: `s3://YOUR_BUCKET/{church_id}.zip`

---

## Prerequisites

- Docker Desktop running  
- AWS CLI logged in (`aws sts get-caller-identity`)  
- Repo checked out with your latest code  
- `.env` only needed for **local** runs (Lambda uses console env vars)

---

## First-time setup (do once)

### 1. Deploy code images

```bat
Batch Scripts\deploy_heritage.bat
```

This builds:

- **Slim chat image** → pushes `:chat` + `:latest` → updates `church-bot-heritage`
- **Updater image** → pushes `:updater` → updates updater if it exists

Wait until you see `SUCCESS`.

### 2. Create the updater Lambda (first time only)

```bat
Batch Scripts\create_updater.bat
```

Creates `church-bot-updater` (900s, 3008 MB) from `:updater`, copies env from chat, adds S3 + invalidate permissions.

### 3. Turn on the weekly schedule

```bat
Batch Scripts\setup_schedule.bat
Batch Scripts\setup_schedule.bat --invoke-now
```

- Schedule: **Monday 3:00 AM America/Detroit**  
- Payload: `{"task":"weekly_update","church_id":"heritage"}`  
- `--invoke-now` runs one update immediately (can take several minutes)

### 4. Confirm health

```bat
Batch Scripts\status.bat
```

Or open:

`https://YOUR_FUNCTION_URL/health?church_id=heritage`

You want `"ready": true` and a sensible `"pages"` count.

### 5. Embed on a church site

```html
<script src="https://YOUR_FUNCTION_URL/church_chatbot.js" defer></script>
<church-chatbot
  api-url="https://YOUR_FUNCTION_URL/chat"
  church-id="heritage"
  title="Heritage Church Assistant"
></church-chatbot>
```

`church-id` must match `code/churches.json` and the S3 zip key (`heritage.zip`).

---

## Day-to-day management

### Deploy new **code** (API, widget, prompts, bugfixes)

```bat
Batch Scripts\deploy_heritage.bat
```

Does **not** re-scrape websites.

### Refresh **church website data**

**Option A — scheduled:** wait for Monday (automatic).

**Option B — on demand from your PC:**

```bat
Batch Scripts\weekly_update.bat heritage
```

(Requires `S3_BUCKET_NAME` + `OPENAI_API_KEY` in your local `.env`, and AWS credentials.)

**Option C — invoke updater Lambda:**

```bat
Batch Scripts\setup_schedule.bat --invoke-now
```

After a successful update, chat Lambdas recycle via `DATA_VERSION` so they load the new zip.

### Check if things are healthy

```bat
Batch Scripts\status.bat
```

Manual checks:

```bat
aws lambda get-function --region us-east-1 --function-name church-bot-heritage --query Configuration.LastUpdateStatus --output text
curl https://YOUR_FUNCTION_URL/health?church_id=heritage
```

### Watch logs

- Chat: CloudWatch → `/aws/lambda/church-bot-heritage`  
- Updater: CloudWatch → `/aws/lambda/church-bot-updater`

---

## Adding another church

1. Edit `code/churches.json`:

```json
"grace": {
  "name": "Grace Church",
  "domain": "grace.example",
  "start_url": "https://grace.example",
  "max_pages": 400,
  "preferred_keyword": null,
  "allowed_origins": ["https://grace.example", "https://www.grace.example"]
}
```

2. Deploy code (registry is baked into the image):

```bat
Batch Scripts\deploy_heritage.bat
```

3. Build that church’s data:

```bat
set CHURCH_ID=grace
Batch Scripts\weekly_update.bat grace
```

Or invoke updater with payload `{"task":"weekly_update","church_id":"grace"}`.

4. Embed the **same** widget with `church-id="grace"`.

5. Optional: create another EventBridge schedule for `grace`.

---

## Environment variables

### Chat Lambda (`church-bot-heritage`)

| Variable | Required | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | yes | OpenAI access |
| `S3_BUCKET_NAME` | yes | Your church data bucket |
| `CHURCH_ID` | no | Default if widget omits id (`heritage`) |
| `API_KEYS` | no | Comma-separated keys; if set, require `X-API-Key` |
| `ALLOWED_ORIGINS` | no | Override CORS allowlist |
| `DATA_VERSION` | auto | Bumped by updater after publish |

### Updater Lambda (`church-bot-updater`)

| Variable | Required | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | yes | Embeddings during ingest |
| `S3_BUCKET_NAME` | yes | Where to write `{id}.zip` |
| `CHURCH_ID` | no | Default church for schedule |
| `CHAT_FUNCTION_NAME` | yes | Chat function to invalidate (`church-bot-heritage`) |
| `MIN_PAGES` / `REGRESSION_RATIO` | no | Publish safety gates |

---

## What each script does

| Script | When to use |
|---|---|
| `deploy_heritage.bat` | Ship code changes |
| `create_updater.bat` | First-time updater Lambda |
| `setup_schedule.bat` | Weekly schedule (+ optional invoke) |
| `weekly_update.bat` | Local data refresh → S3 |
| `status.bat` | Quick health check |
| `data_prep.bat` / `launch_server.bat` | Local development only |

---

## Architecture (runtime)

```text
Church website
    │  (weekly)
    ▼
Updater Lambda
    scrape → ingest → validate → s3://bucket/{church_id}.zip
    bump DATA_VERSION on chat Lambda
    │
    ▼
Chat Lambda (slim image)
    download zip → /tmp/{church_id}/
    answer /chat using that church only
    │
    ▼
<script> + <church-chatbot church-id="...">
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Widget: “trouble connecting” | Chat error / CORS / bad deploy | `status.bat` + CloudWatch chat logs |
| `/health` 503 | Missing/corrupt S3 zip | Run updater / `weekly_update.bat` |
| Updater fails gates | Scrape too small vs last week | Check site/start_url; inspect logs |
| Old answers after update | Warm container not recycled | Confirm `CHAT_FUNCTION_NAME` on updater; check `DATA_VERSION` |
| Deploy can’t find function | Wrong function name | Defaults are `church-bot-heritage` / `church-bot-updater` |

---

## Cost note

- **Chat** (slim): billed per visitor question  
- **Updater**: ~once/week (or on demand) — page download + embeddings  
- Idle Lambdas: **$0**  
- OpenAI is usually the largest line item
