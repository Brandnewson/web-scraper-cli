"""Generate focused SVG visuals from bm25f_comparison_results.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path("results") / "bm25f_comparison_results.json"
DEFAULT_OUTPUT_DIR = Path("results")


def _load_report(path: Path) -> dict:
    """Load benchmark comparison report JSON."""
    if not path.exists():
        raise ValueError(f"Input file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input is not valid JSON: {path}") from exc


def _svg_macro_quality(report: dict) -> str:
    """Render macro nDCG bar comparison."""
    macro = report["macro_average"]
    bm25f = float(macro["bm25f_ndcg_at_5"])
    baseline = float(macro["baseline_ndcg_at_5"])

    width = 980
    height = 340
    left = 210
    bar_max = 700
    max_value = max(bm25f, baseline, 1.0)
    bm25f_w = int((bm25f / max_value) * bar_max)
    baseline_w = int((baseline / max_value) * bar_max)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#fafafa"/>
  <text x="30" y="42" font-family="Segoe UI, Arial, sans-serif" font-size="28" fill="#111111">BM25F vs Baseline: Macro nDCG@5</text>
  <text x="30" y="72" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#555555">Higher is better</text>

  <text x="30" y="150" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#222222">BM25F</text>
  <rect x="{left}" y="125" width="{bm25f_w}" height="34" fill="#2b8a3e"/>
  <text x="{left + bm25f_w + 12}" y="148" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#222222">{bm25f:.6f}</text>

  <text x="30" y="230" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#222222">Baseline</text>
  <rect x="{left}" y="205" width="{baseline_w}" height="34" fill="#d9480f"/>
  <text x="{left + baseline_w + 12}" y="228" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#222222">{baseline:.6f}</text>

  <text x="30" y="300" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#111111">Delta (BM25F - Baseline): {bm25f - baseline:+.6f}</text>
</svg>
"""


def _svg_macro_runtime(report: dict) -> str:
    """Render macro mean query latency bar comparison."""
    macro = report["macro_average"]
    bm25f = float(macro["bm25f_mean_query_ms"])
    baseline = float(macro["baseline_mean_query_ms"])

    width = 980
    height = 340
    left = 210
    bar_max = 700
    max_value = max(bm25f, baseline, 1.0e-9)
    bm25f_w = int((bm25f / max_value) * bar_max)
    baseline_w = int((baseline / max_value) * bar_max)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#f7f9fc"/>
  <text x="30" y="42" font-family="Segoe UI, Arial, sans-serif" font-size="28" fill="#111111">BM25F vs Baseline: Macro Mean Query Latency (ms)</text>
  <text x="30" y="72" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#555555">Lower is better</text>

  <text x="30" y="150" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#222222">BM25F</text>
  <rect x="{left}" y="125" width="{bm25f_w}" height="34" fill="#2b8a3e"/>
  <text x="{left + bm25f_w + 12}" y="148" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#222222">{bm25f:.6f}</text>

  <text x="30" y="230" font-family="Segoe UI, Arial, sans-serif" font-size="18" fill="#222222">Baseline</text>
  <rect x="{left}" y="205" width="{baseline_w}" height="34" fill="#d9480f"/>
  <text x="{left + baseline_w + 12}" y="228" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#222222">{baseline:.6f}</text>

  <text x="30" y="300" font-family="Segoe UI, Arial, sans-serif" font-size="16" fill="#111111">Delta (BM25F - Baseline): {bm25f - baseline:+.6f} ms</text>
</svg>
"""


def _svg_per_query_delta(report: dict, metric_key: str, title: str, units: str) -> str:
    """Render per-query delta chart with zero-centered bars."""
    rows = report["per_query"]
    deltas = [(f"{row['query_id']} ({row['query_text']})", float(row[metric_key])) for row in rows]
    deltas.sort(key=lambda pair: pair[1], reverse=True)

    width = 1080
    row_h = 44
    top = 88
    height = top + len(deltas) * row_h + 42
    center_x = 560
    bar_max = 440
    max_abs = max((abs(value) for _, value in deltas), default=1.0)
    if max_abs == 0.0:
        max_abs = 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        f'  <text x="30" y="40" font-family="Segoe UI, Arial, sans-serif" font-size="28" fill="#111111">{title}</text>',
        f'  <text x="30" y="66" font-family="Segoe UI, Arial, sans-serif" font-size="14" fill="#555555">Positive means BM25F > Baseline ({units})</text>',
        f'  <line x1="{center_x}" y1="{top - 10}" x2="{center_x}" y2="{height - 20}" stroke="#999999" stroke-width="1"/>',
    ]

    for index, (label, value) in enumerate(deltas):
        y = top + index * row_h
        bar_w = int((abs(value) / max_abs) * bar_max)
        if value >= 0:
            x = center_x
            color = "#2b8a3e"
            text_x = x + bar_w + 10
        else:
            x = center_x - bar_w
            color = "#d9480f"
            text_x = x - 90

        parts.append(
            f'  <text x="20" y="{y + 20}" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="#222222">{label}</text>'
        )
        parts.append(f'  <rect x="{x}" y="{y + 6}" width="{bar_w}" height="16" fill="{color}"/>')
        parts.append(
            f'  <text x="{text_x}" y="{y + 20}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="#222222">{value:+.6f}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _summary_md(report: dict) -> str:
    """Render markdown summary linking generated visuals."""
    row = report["benchmark_row"]
    macro = report["macro_average"]
    return "\n".join(
        [
            "# BM25F Comparison Visual Summary",
            "",
            f"- Benchmark: `{row['benchmark_name']}`",
            f"- nDCG@5 delta (BM25F - baseline): `{macro['delta_ndcg_at_5']:+.6f}`",
            f"- Mean query ms delta (BM25F - baseline): `{macro['delta_mean_query_ms']:+.6f}`",
            "",
            "## Visuals",
            "",
            "- `bm25f_macro_ndcg.svg`",
            "- `bm25f_macro_runtime.svg`",
            "- `bm25f_per_query_ndcg_delta.svg`",
            "- `bm25f_per_query_runtime_delta.svg`",
            "",
        ]
    ) + "\n"


def generate_visuals(input_path: Path, out_dir: Path) -> list[Path]:
    """Generate all comparison visual artifacts."""
    report = _load_report(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []

    macro_ndcg = out_dir / "bm25f_macro_ndcg.svg"
    macro_ndcg.write_text(_svg_macro_quality(report), encoding="utf-8")
    files.append(macro_ndcg)

    macro_runtime = out_dir / "bm25f_macro_runtime.svg"
    macro_runtime.write_text(_svg_macro_runtime(report), encoding="utf-8")
    files.append(macro_runtime)

    ndcg_delta = out_dir / "bm25f_per_query_ndcg_delta.svg"
    ndcg_delta.write_text(
        _svg_per_query_delta(
            report,
            metric_key="delta_ndcg_at_5",
            title="Per-query Delta: nDCG@5 (BM25F - Baseline)",
            units="nDCG@5",
        ),
        encoding="utf-8",
    )
    files.append(ndcg_delta)

    runtime_delta = out_dir / "bm25f_per_query_runtime_delta.svg"
    runtime_delta.write_text(
        _svg_per_query_delta(
            report,
            metric_key="delta_mean_query_ms",
            title="Per-query Delta: Mean Query Latency (BM25F - Baseline)",
            units="ms",
        ),
        encoding="utf-8",
    )
    files.append(runtime_delta)

    summary = out_dir / "bm25f_visual_summary.md"
    summary.write_text(_summary_md(report), encoding="utf-8")
    files.append(summary)

    return files


def _parse_args() -> argparse.Namespace:
    """Parse command-line args."""
    parser = argparse.ArgumentParser(description="Visualize BM25F comparison JSON results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input comparison JSON file.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for visuals.")
    return parser.parse_args()


def main() -> None:
    """Script entrypoint."""
    args = _parse_args()
    created = generate_visuals(args.input, args.out)
    print("Generated files:")
    for path in created:
        print(f"- {path}")


if __name__ == "__main__":
    main()
