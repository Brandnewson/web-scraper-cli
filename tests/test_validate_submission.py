"""Validation-gate tests for final submission checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REQUIRED_OBJECTIVES = {
    "validation_table_output_format",
    "validation_missing_artifact_detection",
    "validation_live_smoke_invocation",
}

REQUIRED_TEST_NAMES = {
    "test_validation_table_contains_required_checks",
    "test_validation_fails_on_missing_artifacts",
    "test_validation_invokes_live_smoke_when_enabled",
}

OBJECTIVE_TRACE = {
    "validation_table_output_format": {"test_validation_table_contains_required_checks"},
    "validation_missing_artifact_detection": {"test_validation_fails_on_missing_artifacts"},
    "validation_live_smoke_invocation": {"test_validation_invokes_live_smoke_when_enabled"},
}


def _load_validation_module() -> object:
    """Load the validation script as a module."""
    script_path = Path("scripts") / "validate_submission.py"
    spec = importlib.util.spec_from_file_location("validate_submission", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load validate_submission module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validation_table_contains_required_checks() -> None:
    """Rendered table contains expected validation rows."""
    module = _load_validation_module()
    rows = [
        {"check": "pytest", "status": "PASS", "details": "ok"},
        {"check": "coverage", "status": "PASS", "details": "92%"},
    ]
    table = module.render_results_table(rows)
    assert "| check | status | details |" in table
    assert "| pytest | PASS | ok |" in table
    assert "| coverage | PASS | 92% |" in table


def test_validation_fails_on_missing_artifacts(tmp_path: Path) -> None:
    """Missing required artifacts are flagged as failed checks."""
    module = _load_validation_module()
    checks = module.check_required_artifacts(
        [
            tmp_path / "missing-one.json",
            tmp_path / "missing-two.md",
        ]
    )
    assert checks[0]["status"] == "FAIL"
    assert "missing-one.json" in checks[0]["details"]
    assert checks[1]["status"] == "FAIL"
    assert "missing-two.md" in checks[1]["details"]


def test_validation_invokes_live_smoke_when_enabled(monkeypatch) -> None:
    """Live-smoke hook is invoked when the option is enabled."""
    module = _load_validation_module()
    called = {"live_smoke": False}

    def fake_run_command(_command: str, _label: str) -> dict:
        return {"check": "fake", "status": "PASS", "details": "ok"}

    def fake_live_smoke() -> dict:
        called["live_smoke"] = True
        return {"check": "live_smoke", "status": "PASS", "details": "ok"}

    monkeypatch.setattr(module, "run_command", fake_run_command)
    monkeypatch.setattr(module, "check_required_artifacts", lambda _paths: [])
    monkeypatch.setattr(module, "run_live_smoke", fake_live_smoke)

    report = module.run_validation(live_smoke=True)
    assert called["live_smoke"] is True
    assert any(row["check"] == "live_smoke" for row in report)


def test_objective_trace_completeness() -> None:
    """All validation objectives map to required tests."""
    assert set(OBJECTIVE_TRACE) == REQUIRED_OBJECTIVES
    mapped_test_names = set().union(*OBJECTIVE_TRACE.values())
    assert mapped_test_names == REQUIRED_TEST_NAMES
