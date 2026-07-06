"""Run the fixed battery of synthetic validation cases (see
src/crackgraph/validation_cases.py) through the real measurement pipeline
and compile the results into one browsable HTML gallery.

Unlike scripts/overview_figure.py or src/analyze_image.py, this script does
not take an image path -- the whole point is a self-contained battery of
known-ground-truth synthetic patterns, not a real micrograph.

Usage:
    python3 -m scripts.validation_gallery [--out-dir outputs/validation]
"""

import argparse
from pathlib import Path

from src.crackgraph.validation_cases import run_all_cases
from src.crackgraph.validation_report import render_validation_report


def parse_args():
    p = argparse.ArgumentParser(description="Run the synthetic-pattern validation gallery.")
    p.add_argument("--out-dir", type=str, default="outputs/validation")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)

    results = run_all_cases(out_dir)
    for r in results:
        print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name} ({r.method})")

    html_path = render_validation_report(results, out_dir / "report.html")
    n_passed = sum(r.passed for r in results)
    print(f"\n{n_passed}/{len(results)} cases pass. Report: {html_path}")


if __name__ == "__main__":
    main()
