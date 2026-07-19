"""Attach an already-generated full-image overlay + precedence graph
(from `python3 -m src.analyze_image <image> --full-image --out-dir outputs`,
stage 4/5) to that image's existing entry in the master HTML report.

Deliberately does not run analyze_image.py itself: this script only wires
already-produced PNGs into the report. The image must already have an
entry (created by scripts/overview_figure.py) and the two PNGs must
already exist at analyze_image.py's standard --full-image naming
convention (outputs/<coating>/<stem>_full_overlay.png and
..._full_precedence.png) before running this.

Usage:
    python3 -m scripts.attach_full_analysis <image_path> [--out-dir outputs]
"""

import argparse
from pathlib import Path

from src.crackgraph.html_report import attach_full_analysis_images


def parse_args():
    p = argparse.ArgumentParser(description="Attach full-image overlay/precedence PNGs to the master HTML report.")
    p.add_argument("image_path", type=str)
    p.add_argument("--out-dir", type=str, default="outputs")
    return p.parse_args()


def main():
    args = parse_args()
    image_path = Path(args.image_path)
    coating = image_path.parent.name
    out_dir = Path(args.out_dir)
    image_out_dir = out_dir / coating

    full_overlay_path = image_out_dir / f"{image_path.stem}_full_overlay.png"
    full_precedence_path = image_out_dir / f"{image_path.stem}_full_precedence.png"
    for p in (full_overlay_path, full_precedence_path):
        if not p.exists():
            raise FileNotFoundError(
                f"{p} does not exist -- run "
                f"`python3 -m src.analyze_image {image_path} --full-image --out-dir {out_dir}` first."
            )

    html_path = attach_full_analysis_images(
        out_dir,
        coating=coating,
        image_stem=image_path.stem,
        full_overlay_png_relpath=str(full_overlay_path.relative_to(out_dir)),
        full_precedence_png_relpath=str(full_precedence_path.relative_to(out_dir)),
    )
    print(f"Attached full overlay/precedence for {image_path.stem} to: {html_path}")


if __name__ == "__main__":
    main()
