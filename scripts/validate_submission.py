"""Run final submission validation checks and print a pass/fail report."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import main as main_cli


def run_command(command: str, label: str) -> dict:
    """Execute shell command and return normalized check row."""
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
    )
    status = "PASS" if completed.returncode == 0 else "FAIL"
    # Keep report rows compact and video-friendly by showing only the first output line.
    details_source = completed.stdout.strip() if status == "PASS" else completed.stderr.strip()
    details = details_source.splitlines()[0] if details_source else f"exit_code={completed.returncode}"
    return {"check": label, "status": status, "details": details}


def check_required_artifacts(paths: list[Path]) -> list[dict]:
    """Check required artifact presence and return one row per artifact."""
    rows: list[dict] = []
    for artifact_path in paths:
        exists = artifact_path.exists()
        rows.append(
            {
                "check": f"artifact:{artifact_path.name}",
                "status": "PASS" if exists else "FAIL",
                "details": f"found {artifact_path}" if exists else f"missing {artifact_path.name}",
            }
        )
    return rows


def run_live_smoke() -> dict:
    """Run one real-network live smoke flow through build/load/print/find."""
    outputs: list[str] = []
    # Drive the real REPL path so smoke evidence matches marker-facing CLI behavior.
    commands = iter(["build", "load", "print life", "find love", "find good friends", "quit"])

    def input_fn() -> str:
        return next(commands)

    start = time.perf_counter()
    try:
        main_cli.run_repl(input_fn=input_fn, output_fn=outputs.append)
    except Exception as exc:  # pragma: no cover - defensive wrapper around live behavior
        return {
            "check": "live_smoke",
            "status": "FAIL",
            "details": f"exception: {exc}",
        }

    elapsed = time.perf_counter() - start
    checks = [
        any("Index saved to data/index.json." in line for line in outputs),
        any("Loaded index from data/index.json." in line for line in outputs),
        any(line.startswith("Term: life") for line in outputs),
        any('Results for "love"' in line for line in outputs),
        any('Results for "good friends"' in line for line in outputs),
    ]
    if all(checks):
        return {
            "check": "live_smoke",
            "status": "PASS",
            "details": f"build/load/print/find verified in {elapsed:.1f}s",
        }

    return {
        "check": "live_smoke",
        "status": "FAIL",
        "details": "expected build/load/print/find output not all present",
    }


def render_results_table(rows: list[dict]) -> str:
    """Render validation rows as a markdown table."""
    lines = [
        "| check | status | details |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['check']} | {row['status']} | {row['details']} |")
    lines.append("")
    return "\n".join(lines)


def run_validation(live_smoke: bool = False) -> list[dict]:
    """Execute validation checks and return report rows."""
    rows: list[dict] = []
    rows.append(run_command("pytest -q", "pytest"))
    rows.append(run_command("pytest --cov=src --cov-report=term-missing -q", "coverage"))

    required_artifacts = [
        Path("results") / "bm25f_comparison_results.json",
        Path("results") / "bm25f_comparison_table.md",
        Path("results") / "parameter_sweep_results.json",
        Path("results") / "parameter_sweep_table.md",
        Path("results") / "best_bm25f_config.json",
    ]
    rows.extend(check_required_artifacts(required_artifacts))

    if live_smoke:
        rows.append(run_live_smoke())
    return rows


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line args for submission validation."""
    parser = argparse.ArgumentParser(description="Run final submission validation checks.")
    parser.add_argument("--live-smoke", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for submission validation script."""
    args = _parse_args(argv)
    rows = run_validation(live_smoke=args.live_smoke)
    table = render_results_table(rows)
    print(table)
    all_pass = all(row["status"] == "PASS" for row in rows)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
