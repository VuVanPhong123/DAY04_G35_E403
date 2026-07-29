# Day 04 Lab v2 Report - Research Agent

## Team

- Team: G35 - E403
- Members:
  1. Vũ Văn Phong - 2A202601647
  2. Hà Duy Anh - 2A202601511
  3. Nguyễn Quang Vinh - 2A202601517
  4. Hoàng Lê Minh - 2A202601653
  5. Phạm Sỹ Đức - 2A202601601
  6. Đoàn Nhật Nam - 2A202601123
- Provider/model: Gemini / `gemini-3.1-flash-lite`

# PHAN A - Gioi thieu agent

## A1. Agent nay lam duoc gi

Research Agent routes Vietnamese/English research requests to web search, URL reading, Twitter/X tools, local company policy, arXiv tools, source-type classification, and formatting. It supports CLI, FastAPI backend, React UI, Vercel serverless proxy, local transcripts, and eval evidence.

Link dung thu: https://day-04-g35-e403.vercel.app

Verification on 2026-07-29: frontend URL returned HTTP 200 with title `Research Agent`; `/api/health` returned JSON with `status="offline"` because the local ngrok/backend was not online at audit time. The protected preview URL `https://day-04-g35-e403-git-main-vuvanphong123s-projects.vercel.app` showed Vercel login and is not used as the submission URL.

## A2. Tool agent co

| Ten tool | Lam duoc gi | Tool moi nhom them? |
|---|---|---|
| clarify | Ask for missing handle, URL, or write confirmation | khong |
| timeline | Fetch recent posts from one Twitter/X account | khong |
| social_search | Search Twitter/X by topic | khong |
| lookup | Search public web/news via Tavily | khong |
| fetch | Read one URL via Firecrawl | khong |
| format | Format collected items into markdown | khong |
| send | Telegram send, confirmation-gated | khong |
| policy | Search local company policy markdown | khong |
| papers | Search arXiv | khong |
| paper_text | Extract text from a specific arXiv paper | khong |
| source_quality | Locally classify URL/domain type as official, academic, news, social, or unknown | co |

`source_quality` is the one team-authored tool on `main`. It is pure local logic, has no secrets or network calls, and is not a fact-checker.

## A3. Cau hoi mau de thu

1. Tin AI hom nay co gi noi bat?
2. Lay 5 tweet moi nhat cua Sam Altman.
3. Moi nguoi dang ban gi ve OpenAI tren Twitter?
4. Tom tat URL nay: https://openai.com/research/
5. Phan loai loai nguon cua URL https://arxiv.org/abs/1706.03762

## A4. Kich ban demo da rehearse

| Scenario | Tool trace can thay | Cai thien version | Fallback run/transcript |
|---|---|---|---|
| AI daily news | `lookup(query=AI, topic=news, timeframe=day)` then `format` | v3 normalizes query and supports tool loop | `transcripts/v3_gemini_20260729T141418821083.transcript.json` |
| Missing URL then user supplies URL | turn 1 `clarify(response_type=text)`, turn 2 `fetch(url=https://openai.com/research/)` | v3 asks instead of guessing missing URL | `transcripts/v3_gemini_20260729T141418821083.transcript.json` |
| Telegram send boundary | `clarify(response_type=yes_no)`, no `send` call | v3 enforces write-action confirmation | `transcripts/v3_gemini_20260729T141418821083.transcript.json` |
| Base routing suite | timeline/social/lookup/fetch/clarify/no-tool | v0 12/20 -> v3 20/20 | `runs/v3_B_base_gemini_20260729T141120953518.json` |
| Group eval | 10 team-authored cases including `source_quality` | v3 final artifact passes group set | `runs/v3_B_group_gemini_20260729T141242695707.json` |

# PHAN B - Chi tiet / Bang chung

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | Baseline starter prompt/tools | Starter guesses missing info and weak boundaries | base_case_accuracy |  | 0.60 | `runs/v0_B_base_gemini_20260729T102920083204.json` |
| v1 | Prompt routing and safety rules | Prompt rules improve routing/no-tool behavior | base_case_accuracy | 0.60 | 0.65 | `runs/v1_B_base_gemini_20260729T103114572425.json` |
| v2 | Tool descriptions and arg conventions | Better descriptions were expected to improve args, but this run did not support the hypothesis | base_case_accuracy | 0.65 | 0.65 | `runs/v2_B_base_gemini_20260729T103313482534.json` |
| v3 | Query normalization, explicit clarify response_type, write safety, policy area mapping, and narrow `source_quality` routing | Combined prompt+tools removes remaining base/group routing failures and supports the team-authored tool | base_case_accuracy | 0.65 | 1.00 | `runs/v3_B_base_gemini_20260729T141120953518.json` |

Additional final evidence:

- Group v3: 10/10, `provider_error_cases=0`, `runs/v3_B_group_gemini_20260729T141242695707.json`.
- Final artifact version: `v3+p33434091d8bc+ta5932b693f09`.
- Flat analysis generated from the reported official runs only: `artifacts/run-analysis.csv`.
- Tool smoke/preflight output: `artifacts/preflight-tools.txt`.

## B2. Failure analysis

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R03/R13/M02/M06 in v2 | wrong_arg_value | `lookup(query="AI news")`, `lookup(query="robotics news")` | Model put news/timeframe words in `query` | v3 says query is core subject only; news/timeframe go to dedicated args |
| R10/R11 in v2 | missing_info | `clarify(question=...)` without `response_type` | Missing explicit `response_type=text` | v3 requires every clarify call to include response_type |
| R12 in v2/v3 draft | wrong_boundary | `clarify(response_type=text)` | Model asked for Telegram content before yes/no confirmation | v3 write-action rule and clarify schema require yes_no for unconfirmed send/post/publish |
| G03 in group draft | wrong_arg_value | `policy(query=...)` without `policy_area` | Missing data_privacy policy area | v3 policy-area mapping added |
| G04 final | wrong_tool risk | expected `source_quality` | Team needed one self-authored tool with evidence | Added local `source_quality`, declaration, routing rule, unit tests, and group eval case |

## B3. Team eval cases

`data/eval_group.json` has exactly 10 cases: 5 single-turn and 5 multi-turn.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_specific_url_fetch | URL vs web search | `fetch` | PASS |
| G02_month_news_limit | timeframe and max_results | `lookup` | PASS |
| G03_company_privacy_policy | company policy area | `policy(data_privacy)` | PASS |
| G04_source_quality_arxiv | team-authored source type classifier | `source_quality` | PASS |
| G05_confirm_before_send | write confirmation boundary | `clarify(yes_no)` | PASS |
| G06_multiturn_carry_topic | carry timeframe, switch topic | `lookup` | PASS |
| G07_multiturn_limit_correction | carry account, change limit | `timeline` | PASS |
| G08_multiturn_social_to_web | switch source | `lookup` | PASS |
| G09_multiturn_url_after_clarify | clarify then URL | `fetch` | PASS |
| G10_multiturn_cancel_meta | cancel then meta/no-tool | no tool | PASS |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript | Outcome |
|---|---|---|---|---|
| Research request | v3 | `lookup(query=AI, topic=news, timeframe=day)`, then `format(template=sections)` | `transcripts/v3_gemini_20260729T141418821083.transcript.json` | answered with source links |
| Missing URL turn | v3 | `clarify(response_type=text)` | `transcripts/v3_gemini_20260729T141418821083.transcript.json` | asked for URL |
| URL supplied next turn | v3 | `fetch(url=https://openai.com/research/)` | `transcripts/v3_gemini_20260729T141418821083.transcript.json` | answered using the supplied URL |
| Sensitive write action | v3 | `clarify(response_type=yes_no)`; no `send` | `transcripts/v3_gemini_20260729T141418821083.transcript.json` | confirmation boundary held |

Committed API transcripts have `client` redacted as `<redacted>`.

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Team-authored tool | `tools/source_quality/tool.py`, `tools/source_quality/TOOL.md`, `tests/test_source_quality.py`, `runs/v3_B_group_gemini_20260729T141242695707.json` | arXiv URL classified as `academic` with local deterministic logic | Classification is source type only, not reliability proof or fact-checking |
| Live research tools | `artifacts/preflight-tools.txt` | Tavily 200, Firecrawl 200, RapidAPI Twitter timeline/search 200 | API quotas/subscriptions may change |
| arXiv public API | `artifacts/preflight-tools.txt` | configured, but live smoke returned HTTP 429 | Rate limit documented; code unchanged |
| UI/backend | `https://day-04-g35-e403.vercel.app`, `frontend/package.json`, `frontend/api/health.ts`, `frontend/api/chat.ts`, `transcripts/v3_gemini_20260729T141418821083.transcript.json` | React frontend loads; CLI transcript validates agent behavior | Backend/ngrok must be online for Vercel chat; health was offline during audit |

Telegram `send` was not invoked during validation.

## B6. Reflection

- Prompt fixes: no-tool boundary, missing-info clarification, write-action safety, multi-turn carryover, source priority.
- Tool YAML fixes: explicit tool distinctions, argument conventions, query normalization, `clarify.response_type`, policy area mapping, and narrow `source_quality` routing.
- Manual review: routing PASS does not prove live tool execution; preflight and transcripts were reviewed separately.
- Limitation: Vercel frontend is reachable, but backend/ngrok was offline during final audit, so deployed chat depends on bringing the existing local backend/ngrok session online without changing secrets.
