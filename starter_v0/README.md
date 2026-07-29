# Day 04 Lab v2 - Research Agent

Research Agent is a Gemini-powered tool-routing agent for web news, URL reading, Twitter/X signals, local company policy, arXiv discovery, arXiv PDF text extraction, source-type classification, and formatting.

## Team Members

| Member | MSSV | Main Responsibility |
|---|---|---|
| Vũ Văn Phong | 2A202601647 | Backend orchestration, Gemini provider, Vercel/ngrok integration |
| Hà Duy Anh | 2A202601511 | React UI, chat experience, responsive layout |
| Nguyễn Quang Vinh | 2A202601517 | Tool integration, RapidAPI Twitter, Tavily/Firecrawl checks |
| Hoàng Lê Minh | 2A202601653 | Eval design, group cases, run analysis |
| Phạm Sỹ Đức | 2A202601601 | Documentation, deployment guide, report evidence |
| Đoàn Nhật Nam | 2A202601123 | QA, security review, transcript and smoke testing |

## Architecture

```text
CLI / FastAPI / React UI
  -> shared agent_runtime.py tool loop
  -> Gemini structured function calling
  -> local Python tools
  -> Tavily / Firecrawl / RapidAPI Twitter / arXiv / local policy files
```

For Vercel:

```text
React on Vercel
  -> Vercel function /api/chat
  -> ngrok HTTPS URL
  -> FastAPI localhost:8000
  -> Gemini/Tavily/Firecrawl/RapidAPI/arXiv
```

## Tools

- `clarify`: ask for missing handle, URL, or write-action confirmation.
- `timeline`: fetch recent tweets/posts from one account.
- `social_search`: search Twitter/X by topic.
- `lookup`: search public web/news via Tavily.
- `fetch`: read one provided URL via Firecrawl.
- `format`: format already collected items.
- `send`: Telegram send action, only after explicit confirmation.
- `policy`: search local company policy markdown.
- `papers`: search arXiv.
- `paper_text`: download and extract text from a specific arXiv paper.
- `source_quality`: classify a URL/domain as official, academic, news, social, or unknown.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` with real values. Keep secrets only in `.env` or deployment secret stores.

Recommended Gemini model:

```env
GEMINI_MODEL=gemini-3.1-flash-lite
```

## Preflight

```powershell
python scripts/preflight_provider.py --provider gemini
python scripts/preflight_tools.py
python scripts/preflight_tools.py --smoke --include-arxiv --timeout 20
```

Preflight prints only `configured/missing` and HTTP status, never secret values.

## CLI

```powershell
python chat.py --provider gemini --version v3 --model gemini-3.1-flash-lite
```

## Eval

```powershell
python run_eval.py --phase B --suite base --version v3 --provider gemini --model gemini-3.1-flash-lite --system-prompt artifacts/versions/v3/system_prompt.md --tools artifacts/versions/v3/tools.yaml --eval-cases data/eval_base.json --case-delay 3
python run_eval.py --phase B --suite group --version v3 --provider gemini --model gemini-3.1-flash-lite --system-prompt artifacts/versions/v3/system_prompt.md --tools artifacts/versions/v3/tools.yaml --eval-cases data/eval_group.json --case-delay 3
python scripts/parse_runs.py runs --output artifacts/run-analysis.csv
```

## FastAPI Backend

Optional `.env`:

```env
BACKEND_SHARED_SECRET=replace-with-a-local-secret
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://day-04-g35-e403.vercel.app
```

Run locally:

```powershell
$env:ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,https://day-04-g35-e403.vercel.app"
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Smoke:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

If `BACKEND_SHARED_SECRET` is set, `POST /api/chat` requires `X-Internal-API-Key`.
The UI first tries `POST /api/chat/stream` for SSE status updates and falls back to `POST /api/chat`.

## Ngrok

Do not put ngrok tokens in source code or Vercel.

```powershell
ngrok config add-authtoken <REAL_TOKEN>
ngrok http 8000
```

If `ngrok` is not on PATH, this local machine also has:

```powershell
& 'C:\Users\ADMIN\Personal_proj\chatbot\app\BE\venv\Lib\site-packages\pyngrok\bin\ngrok.exe' http 8000
```

Copy the HTTPS forwarding URL and set it as Vercel `BACKEND_ORIGIN`.

## React UI

```powershell
cd frontend
npm install
npm run dev
```

For local dev proxy, create `frontend/.env`:

```env
BACKEND_ORIGIN=http://127.0.0.1:8000
BACKEND_SHARED_SECRET=replace-with-the-same-secret-as-backend
```

Build:

```powershell
npm run build
npm run lint
```

## Vercel Deploy

- Import the repository.
- Set Root Directory to `frontend`.
- Framework preset: Vite.
- Add server-side environment variables:
  - `BACKEND_ORIGIN=https://your-ngrok-domain.ngrok-free.app`
  - `BACKEND_SHARED_SECRET=replace-with-the-same-secret-as-backend`
- Do not add `NGROK_AUTHTOKEN` to Vercel.
- Do not prefix backend secret variables with `VITE_`.

## Security Notes

- `.env` is gitignored.
- React client never receives Gemini, Tavily, Firecrawl, RapidAPI, ngrok, or backend shared secret values.
- Vercel functions are fixed proxies to `BACKEND_ORIGIN`; clients cannot choose target URLs.
- Backend does not accept client-supplied system prompts, tools, providers, or models.
- Transcript files store messages, tool calls, sanitized tool events, status, and timestamps without raw provider responses or secrets.
- `send` is guarded by explicit confirmation and was not invoked during validation.

## Troubleshooting

- 401 from backend: set matching `BACKEND_SHARED_SECRET` on backend and proxy; send `X-Internal-API-Key`.
- CORS: set `ALLOWED_ORIGINS` to local UI or deployed Vercel URL.
- ngrok offline: keep the personal machine awake with backend and ngrok running.
- Gemini 429: use `GEMINI_MODEL=gemini-3.1-flash-lite` and eval `--case-delay 3`.
- Tavily/Firecrawl/RapidAPI quota: run `scripts/preflight_tools.py --smoke`; inspect sanitized HTTP status.
- RapidAPI schema change: update `tools/timeline/tool.py` or `tools/social_search/tool.py` item extraction.
- Vercel function timeout: shorten backend tool loops or increase backend speed; Vercel proxy has a 90s abort.
- Invalid Gemini model: run `scripts/preflight_provider.py --provider gemini --model <candidate>`.
