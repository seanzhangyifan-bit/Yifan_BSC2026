"""Run the curvature/anisotropy slice of the pipeline (binarize ->
skeletonize -> graph -> curvature -> anisotropy -- NOT junctions/kinks/
corner-cross-check, which this overview figure doesn't need) across a
coarse grid of sections of one full image, plus once on the whole image,
and compile every resulting rose diagram + curvature histogram into a
single overview figure. Also updates one master HTML report (one page for
all coatings/images, see crackgraph/html_report.py) with this image's
section.

This is deliberately a separate script from src/analyze_image.py: that CLI
runs the *full* stage 1-5 pipeline (junctions, kinks, corner cross-check,
optional xlsx export) on exactly one region per invocation. Pulling those
stages into this script would be scope creep the overview figure doesn't
need.

Usage:
    python3 -m scripts.overview_figure <image_path> [--n-rows 4] [--n-cols 4] [--out-dir outputs]

Output layout (mirrors analyze_image.py's per-coating nesting):
    outputs/<coating>/<image_stem>_overview.png   -- this run's figure
    outputs/report.html                            -- master report (all coatings)
    outputs/report_data.json                       -- its backing registry
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

from src.crackgraph.anisotropy import compute_anisotropy
from src.crackgraph.binarize import binarize
from src.crackgraph.curvature import compute_edge_curvature
from src.crackgraph.graph import extract_graph
from src.crackgraph.html_report import update_master_report
from src.crackgraph.io_utils import load_image
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.summary_plots import render_overview_figure
from src.crackgraph.tiling import grid_tiles


def parse_args():
    p = argparse.ArgumentParser(description="Multi-section anisotropy/curvature overview figure.")
    p.add_argument("image_path", type=str)
    p.add_argument("--n-rows", type=int, default=4)
    p.add_argument("--n-cols", type=int, default=4)
    p.add_argument("--out-dir", type=str, default="outputs")
    return p.parse_args()


def _run_pipeline_slice(gray):
    binarize_result = binarize(gray, sanity_band=(0.01, 0.15))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)
    curvature_result = compute_edge_curvature(skeleton_result.skeleton, graph_result)
    anisotropy_result = compute_anisotropy(skeleton_result.skeleton, graph_result)
    return curvature_result, anisotropy_result


def main():
    args = parse_args()
    image_path = Path(args.image_path)
    gray_full, _ = load_image(image_path)
    h, w = gray_full.shape

    print(f"=== Overview figure: {image_path.name} ({w} x {h} px) ===")

    t0 = time.perf_counter()
    whole_curv, whole_aniso = _run_pipeline_slice(gray_full)
    whole_elapsed = time.perf_counter() - t0
    print(f"Whole-image pipeline runtime: {whole_elapsed:.2f}s")

    tiles = grid_tiles(h, w, args.n_rows, args.n_cols)
    sections = []
    t1 = time.perf_counter()
    for tile in tiles:
        gray_tile = gray_full[tile.row_slice, tile.col_slice]
        curv, aniso = _run_pipeline_slice(gray_tile)
        sections.append((tile.label, aniso, curv))
    sections_elapsed = time.perf_counter() - t1
    print(
        f"{len(tiles)} sections ({args.n_rows}x{args.n_cols} grid) runtime: "
        f"{sections_elapsed:.2f}s total, {sections_elapsed / len(tiles):.2f}s/section"
    )

    # Nest under the image's source subfolder, same convention as
    # analyze_image.py (data/raw/T5, data/raw/humidity_loading, ...).
    coating = image_path.parent.name
    out_dir = Path(args.out_dir) / coating
    out_dir.mkdir(parents=True, exist_ok=True)
    overview_png_path = out_dir / f"{image_path.stem}_overview.png"
    render_overview_figure(sections, ("whole image", whole_aniso, whole_curv), overview_png_path)
    print(f"Overview figure saved to: {overview_png_path}")

    master_dir = Path(args.out_dir)
    html_path = update_master_report(
        master_dir,
        coating=coating,
        image_stem=image_path.stem,
        overview_png_relpath=str(overview_png_path.relative_to(master_dir)),
        whole_image_runtime_s=whole_elapsed,
        n_sections=len(tiles),
        tiling_desc=f"{args.n_rows}x{args.n_cols} grid",
        timestamp_iso=datetime.now().isoformat(),
    )
    print(f"Master HTML report updated: {html_path}")


if __name__ == "__main__":
    main()
