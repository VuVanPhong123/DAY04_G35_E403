from __future__ import annotations

from pathlib import Path

from run_eval import load_cases, load_tool_declarations, validate_expected_tools


ROOT = Path(__file__).resolve().parents[1]


def test_eval_group_schema_and_expected_tools() -> None:
    cases = load_cases(ROOT / "data" / "eval_group.json", "B")
    declarations = load_tool_declarations(ROOT / "artifacts" / "tools.yaml")
    validate_expected_tools(cases, declarations, ROOT / "data" / "eval_group.json")
    assert len([case for case in cases if "query" in case]) == 5
    assert len([case for case in cases if "turns" in case]) == 5

