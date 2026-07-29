from __future__ import annotations

from tools.source_quality.tool import classify_source_quality


def test_arxiv_is_academic() -> None:
    result = classify_source_quality("https://arxiv.org/abs/1706.03762")
    assert result["domain"] == "arxiv.org"
    assert result["source_type"] == "academic"
    assert result["confidence"] == "high"


def test_gov_vn_is_official() -> None:
    result = classify_source_quality("https://mic.gov.vn")
    assert result["source_type"] == "official"


def test_x_is_social() -> None:
    result = classify_source_quality("https://x.com/OpenAI")
    assert result["source_type"] == "social"


def test_unknown_domain_is_unknown() -> None:
    result = classify_source_quality("https://example.invalid/path")
    assert result["source_type"] == "unknown"


def test_invalid_url_is_safe() -> None:
    result = classify_source_quality("not a url")
    assert result["source_type"] == "unknown"
    assert result["confidence"] == "low"
    assert "fact-check" in result["scope_note"]
