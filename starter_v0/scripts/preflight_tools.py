from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from env_loader import load_lab_env


REQUIRED_ENV = ["GEMINI_API_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "RAPIDAPI_KEY"]


def configured(key: str) -> str:
    return "configured" if os.getenv(key) else "missing"


def sanitize_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {str(exc)}"
    for key in REQUIRED_ENV + ["NGROK_AUTHTOKEN", "BACKEND_SHARED_SECRET"]:
        value = os.getenv(key)
        if value:
            text = text.replace(value, "<redacted>")
    return text[:500]


def tavily_smoke(timeout: int) -> dict[str, Any]:
    response = requests.post(
        "https://api.tavily.com/search",
        json={"query": "OpenAI", "topic": "general", "max_results": 1, "search_depth": "basic"},
        headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
        timeout=timeout,
    )
    return {"ok": response.ok, "status_code": response.status_code}


def firecrawl_smoke(timeout: int) -> dict[str, Any]:
    response = requests.post(
        "https://api.firecrawl.dev/v1/scrape",
        json={"url": "https://example.com", "formats": ["markdown"]},
        headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
        timeout=timeout,
    )
    return {"ok": response.ok, "status_code": response.status_code}


def rapidapi_smoke(timeout: int) -> dict[str, Any]:
    host = os.getenv("RAPIDAPI_TWITTER_HOST", "twitter-api45.p.rapidapi.com")
    headers = {"x-rapidapi-key": os.environ["RAPIDAPI_KEY"], "x-rapidapi-host": host}
    checks = []
    for path, params in [
        ("/timeline.php", {"screenname": "elonmusk"}),
        ("/search.php", {"query": "OpenAI", "search_type": "Latest"}),
    ]:
        response = requests.get(f"https://{host}{path}", params=params, headers=headers, timeout=timeout)
        checks.append({"path": path, "status_code": response.status_code, "ok": response.ok or response.status_code == 429})
    return {
        "ok": all(item["ok"] for item in checks),
        "status_code": max(item["status_code"] for item in checks),
        "checks": checks,
        "note": "HTTP 429 means the Twitter API is reachable but rate-limited.",
    }


def arxiv_smoke(timeout: int) -> dict[str, Any]:
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": "all:agent", "max_results": 1},
        headers={"User-Agent": os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0")},
        timeout=timeout,
    )
    return {"ok": response.ok, "status_code": response.status_code}


def run_smoke(name: str, fn: Any, timeout: int) -> dict[str, Any]:
    try:
        result = fn(timeout)
        return {"name": name, **result}
    except Exception as exc:
        return {"name": name, "ok": False, "error": sanitize_error(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight configured research tool APIs without printing secrets.")
    parser.add_argument("--smoke", action="store_true", help="Run one small live request per configured required API.")
    parser.add_argument("--include-arxiv", action="store_true", help="Also smoke-test the public arXiv API.")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    load_lab_env(ROOT)
    env_file = os.getenv("DAY04_ENV_FILE") or str(ROOT / ".env")
    statuses = {key: configured(key) for key in REQUIRED_ENV}
    statuses["RAPIDAPI_TWITTER_HOST"] = configured("RAPIDAPI_TWITTER_HOST")
    statuses["ARXIV_USER_AGENT"] = configured("ARXIV_USER_AGENT")
    print(json.dumps({"env_file": env_file, "env": statuses}, ensure_ascii=False, indent=2))

    missing = [key for key in REQUIRED_ENV if not os.getenv(key)]
    if missing:
        print(json.dumps({"error": "missing_required_env", "keys": missing}, ensure_ascii=False))
        raise SystemExit(1)

    if not args.smoke:
        return

    checks = [
        run_smoke("tavily", tavily_smoke, args.timeout),
        run_smoke("firecrawl", firecrawl_smoke, args.timeout),
        run_smoke("rapidapi_twitter", rapidapi_smoke, args.timeout),
    ]
    if args.include_arxiv:
        checks.append(run_smoke("arxiv", arxiv_smoke, args.timeout))
    print(json.dumps({"smoke": checks}, ensure_ascii=False, indent=2))
    failed = [item for item in checks if not item.get("ok")]
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
