from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


OFFICIAL_DOMAINS = {
    "europa.eu",
    "openai.com",
    "who.int",
    "un.org",
}

ACADEMIC_DOMAINS = {
    "arxiv.org",
    "acm.org",
    "ieee.org",
    "pubmed.ncbi.nlm.nih.gov",
    "scholar.google.com",
}

SOCIAL_DOMAINS = {
    "x.com",
    "twitter.com",
    "facebook.com",
    "reddit.com",
    "linkedin.com",
}

NEWS_DOMAINS = {
    "bbc.com",
    "cnn.com",
    "reuters.com",
    "apnews.com",
    "nytimes.com",
    "theguardian.com",
    "techcrunch.com",
    "theverge.com",
    "vnexpress.net",
    "tuoitre.vn",
}


def _domain_from_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _matches_domain(domain: str, known_domain: str) -> bool:
    return domain == known_domain or domain.endswith(f".{known_domain}")


def _classify_domain(domain: str) -> tuple[str, str, str]:
    if not domain or "." not in domain:
        return "unknown", "low", "Input is not a valid URL or domain."
    if domain.endswith((".gov", ".gov.vn", ".go.jp")) or any(_matches_domain(domain, item) for item in OFFICIAL_DOMAINS):
        return "official", "high", f"Domain belongs to an official government or organization domain: {domain}."
    if domain.endswith(".edu") or any(_matches_domain(domain, item) for item in ACADEMIC_DOMAINS):
        return "academic", "high", f"Domain belongs to an academic or scholarly source: {domain}."
    if any(_matches_domain(domain, item) for item in SOCIAL_DOMAINS):
        return "social", "high", f"Domain belongs to a social platform: {domain}."
    if any(_matches_domain(domain, item) for item in NEWS_DOMAINS) or "news" in domain:
        return "news", "medium", f"Domain matches a known publisher or news-like pattern: {domain}."
    return "unknown", "low", "Domain was not matched to an official, academic, news, or social category."


def classify_source_quality(url: str = "") -> dict[str, Any]:
    domain = _domain_from_url(url)
    source_type, confidence, reason = _classify_domain(domain)
    return {
        "tool": "source_quality",
        "url": url,
        "domain": domain,
        "source_type": source_type,
        "confidence": confidence,
        "reason": reason,
        "scope_note": "This tool classifies source type only; it does not fact-check claims or prove reliability.",
    }
