# Day 04 Lab v2 Report - Research Agent

## Team

- Team: TODO_TEAM_NAME
- Members: TODO_MEMBERS
- Provider/model: Gemini / `gemini-3.1-flash-lite`

# PHAN A - Gioi thieu agent

## A1. Agent nay lam duoc gi

Research Agent routes Vietnamese/English research requests to web search, URL reading, Twitter/X tools, local company policy, arXiv tools, and formatting. It supports CLI, FastAPI backend, React UI, Vercel serverless proxy, local transcripts, and eval evidence.

Link dung thu: TODO_VERCEL_URL

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

## A3. Cau hoi mau de thu

1. Tin AI hom nay co gi noi bat?
2. Lay 5 tweet moi nhat cua Sam Altman.
3. Moi nguoi dang ban gi ve OpenAI tren Twitter?
4. Tom tat URL nay: https://openai.com/research/
5. Tim 3 paper arXiv moi ve agent evaluation.

## A4. Kich ban demo da rehearse

| Scenario | Tool trace can thay | Cai thien version | Fallback run/transcript |
|---|---|---|---|
| AI daily news | `lookup(query=AI, topic=news, timeframe=day)` then `format` | v3 normalizes query and supports tool loop | `transcripts/demo-lookup.transcript.json` |
| Meta/capability question | no tool | v1/v3 no-tool boundary | `transcripts/smoke-api.transcript.json` |
| Base routing suite | timeline/social/lookup/fetch/clarify/no-tool | v0 12/20 -> v3 20/20 | `runs/v3_B_base_gemini_20260729T104447599981.json` |
| Group eval | 10 team-authored cases | v3 policy area mapping fixed group case | `runs/v3_B_group_gemini_20260729T104548675907.json` |

# PHAN B - Chi tiet / Bang chung

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | Baseline starter prompt/tools | Starter guesses missing info and weak boundaries | base_case_accuracy |  | 0.60 | `runs/v0_B_base_gemini_20260729T102920083204.json` |
| v1 | Prompt routing and safety rules | Prompt rules improve routing/no-tool behavior | base_case_accuracy | 0.60 | 0.65 | `runs/v1_B_base_gemini_20260729T103114572425.json` |
| v2 | Tool descriptions and arg conventions | Better descriptions improve args | base_case_accuracy | 0.65 | 0.65 | `runs/v2_B_base_gemini_20260729T103313482534.json` |
| v3 | Query normalization, explicit clarify response_type, write safety, policy area mapping | Combined prompt+tools removes remaining failures | base_case_accuracy | 0.65 | 1.00 | `runs/v3_B_base_gemini_20260729T104447599981.json` |

Additional final evidence:

- Group v3: 10/10, `provider_error_cases=0`, `runs/v3_B_group_gemini_20260729T104548675907.json`.
- Extension v3: 9/10, `provider_error_cases=0`, `runs/v3_B_extension_gemini_20260729T104649934908.json`.
- Flat analysis: `artifacts/run-analysis.csv`.

## B2. Failure analysis

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R03/R13/M02/M06 in v2 | wrong_arg_value | `lookup(query="AI news")`, `lookup(query="robotics news")` | Model put news/timeframe words in `query` | v3 says query is core subject only; news/timeframe go to dedicated args |
| R10/R11 in v2 | missing_info | `clarify(question=...)` without `response_type` | Missing explicit `response_type=text` | v3 requires every clarify call to include response_type |
| R12 in v2/v3 draft | wrong_boundary | `clarify(response_type=text)` | Model asked for Telegram content before yes/no confirmation | v3 write-action rule and clarify schema require yes_no for unconfirmed send/post/publish |
| G03 in group draft | wrong_arg_value | `policy(query=...)` without `policy_area` | Missing data_privacy policy area | v3 policy-area mapping added |
| E06 extension | wrong_tool | `policy` only | Optional extension case wanted both policy and live news lookup | Left documented; base/group already passed 100% |

## B3. Team eval cases

`data/eval_group.json` has exactly 10 cases: 5 single-turn and 5 multi-turn.

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_specific_url_fetch | URL vs web search | `fetch` | PASS |
| G02_month_news_limit | timeframe and max_results | `lookup` | PASS |
| G03_company_privacy_policy | company policy area | `policy(data_privacy)` | PASS |
| G04_arxiv_discovery | arXiv discovery | `papers` | PASS |
| G05_confirm_before_send | write confirmation boundary | `clarify(yes_no)` | PASS |
| G06_multiturn_carry_topic | carry timeframe, switch topic | `lookup` | PASS |
| G07_multiturn_limit_correction | carry account, change limit | `timeline` | PASS |
| G08_multiturn_social_to_web | switch source | `lookup` | PASS |
| G09_multiturn_url_after_clarify | clarify then URL | `fetch` | PASS |
| G10_multiturn_cancel_meta | cancel then meta/no-tool | no tool | PASS |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| Backend meta smoke | v3 | no tool | `transcripts/smoke-api.transcript.json` | answered |
| AI news demo | v3 | `lookup(query=AI, topic=news, timeframe=day)`, `format(template=sections)` | `transcripts/demo-lookup.transcript.json` | answered with source links |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: live research tools | `scripts/preflight_tools.py --smoke --include-arxiv` output in `job.txt` | Tavily, Firecrawl, RapidAPI Twitter, arXiv returned 200 | Quotas/API schema may change |
| Optional built-in | `runs/v3_B_extension_gemini_20260729T104649934908.json` | policy, arXiv search, paper_text, fetch multi-link | Extension E06 remained 9/10 |
| UI/backend | `frontend/dist`, `transcripts/demo-lookup.transcript.json` | React build, Vercel proxy, FastAPI chat | Requires local machine + ngrok online |

UI is a core deliverable, not counted as bonus. Telegram `send` was not invoked.

## B6. Reflection

- Prompt fixes: no-tool boundary, missing-info clarification, write-action safety, multi-turn carryover, source priority.
- Tool YAML fixes: explicit tool distinctions, argument conventions, query normalization, `clarify.response_type`, policy area mapping.
- Manual review: routing PASS does not prove live tool execution; preflight and transcripts were reviewed separately.
- Next improvement: tune extension multi-intent behavior so policy pre-check does not replace live lookup in briefing requests.

