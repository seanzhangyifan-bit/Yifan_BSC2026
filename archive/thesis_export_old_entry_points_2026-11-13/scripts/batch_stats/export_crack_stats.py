"""Export the per-image crack-statistics table (stages 1-3 only).

Binarize -> skeletonize -> flaking exclusion -> graph -> area, width, edge
length and connectivity stats. No curvature or anisotropy. Column reference: docs/batch_stats/crack_stats_schema.md -- keep
the two in sync.

Flaking: the mask is skeletonized once. Any edge with a pixel inside a
flaked/delaminated region (flaking.flake_touching_path_indices) is omitted
from both the stats and the connectivity graph, so nothing connects through
a region we have no evidence about.

Usage:
    python3 -m scripts.batch_stats.export_crack_stats [--data-dir data/raw]
        [--out outputs/crack_stats.xlsx] [--cache-dir DIR] [--scale-bars-checked]

Every image file under --data-dir (any subfolder) gets a row; choose what to
analyse by what you put there, or upload files in the GUI instead. --data-dir
defaults to data/raw inside this folder (not bundled; for example
--data-dir ../data/raw). Pass --scale-bars-checked only if you have looked at
every image and confirmed none carries a burned-in scale bar.
"""

import argparse
import time
from pathlib import Path
from typing import Callable

import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist

from src.crackgraph.binarize import binarize
from src.crackgraph.cache_io import save_analysis_cache
from src.crackgraph.flaking import exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import extract_graph, path_pixel_indices
from src.crackgraph.io_utils import load_image
from src.crackgraph.overlay import render_crack_stats_overlay
from src.crackgraph.skeleton import skeletonize_and_prune

# Source: an external calibration tool that is NOT part of this repository -- this is not derived here.
# Only applicable for (Zhang 2026)
UM_PER_PX_MM_TAG = 100 / 164  # 0.609756... um/px

# Image files main() picks up under --data-dir (recursively). Which images to
# analyse is the user's choice -- what they put in the folder or upload to the
# GUI -- not something this script infers from file names.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
DEFAULT_DATA_DIR = "data/raw"

# Values for the scale_bar_check column. "Confirmed" is only written when the
# caller vouches that every image was inspected by eye (--scale-bars-checked);
# compute_row never assumes it.
SCALE_BAR_CHECKED = "no blue bar (visually confirmed)"
SCALE_BAR_NOT_CHECKED = "not checked"

# Fixed, ordered stage labels compute_row reports through on_stage -- a module-level
# constant so callers (e.g. app.py's progress bar) can size a progress display
# without running compute_row first.
COMPUTE_ROW_STAGES = ["Binarizing", "Skeletonizing", "Checking for flaking", "Extracting graph", "Computing stats"]


def find_images(data_dir: Path, pattern: str = "**/*") -> list[Path]:
    """Every image file (IMAGE_SUFFIXES) under data_dir matching `pattern`, sorted.
    Exits with a clear message if there are none."""
    image_paths = sorted(
        p for p in data_dir.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not image_paths:
        raise SystemExit(
            f"No images found under {data_dir} (pattern {pattern!r}). "
            "Pass --data-dir to point at your micrograph folder."
        )
    return image_paths


def median_pixelwise_width_px(skel, graph_result, omitted: set[int], medial_radius: np.ndarray) -> float:
    """Median of 2 * medial_radius sampled at every skeleton pixel of every edge not
    in `omitted` -- a genuine per-pixel width measurement, unlike avg_width_px's
    global area/total-length ratio. Median, not mean, matches
    compute_reference_width_px's convention in flaking.py: a handful of anomalously
    wide pixels (junction blobs, near-miss flaking) shouldn't drag a single summary
    number around. [interpreted] -- a stated aggregation over [measured] per-pixel
    distance-transform values.
    """
    widths = []
    for path_index in graph_result.summary.index:
        if path_index in omitted:
            continue
        rr, cc = path_pixel_indices(skel.path_coordinates(int(path_index)), medial_radius.shape)
        widths.append(2.0 * medial_radius[rr, cc])
    if not widths:
        return float("nan")
    return float(np.median(np.concatenate(widths)))


def median_edge_length_px(summary, omitted: set[int], node_filter: set | None = None) -> float:
    """Median branch_distance (px) over edges not in `omitted`, optionally
    restricted to edges whose endpoints both lie in node_filter (used to
    isolate the giant component). Median rather than avg_edge_length_px's
    mean: a handful of very long or very short segments shouldn't dominate a
    single summary number. [interpreted] aggregation over [measured] per-edge
    lengths.
    """
    mask = ~summary.index.isin(omitted)
    if node_filter is not None:
        mask &= summary["node_id_src"].isin(node_filter) & summary["node_id_dst"].isin(node_filter)
    lengths = summary.loc[mask, "branch_distance"]
    if len(lengths) == 0:
        return float("nan")
    return float(lengths.median())


def crack_network_graph(summary: pd.DataFrame) -> nx.MultiGraph:
    """Junction/endpoint nodes joined by one graph edge per skeleton segment.

    A MultiGraph, not a Graph: two different segments can join the same pair
    of junctions (the two sides of a small cell). A plain Graph keeps only one
    of them, so the giant component's length came out short while the total
    length counted both, biasing giant_component_fraction low (by up to 0.007
    on the images checked, 2026-11-11)."""
    return nx.from_pandas_edgelist(
        summary, source="node_id_src", target="node_id_dst",
        edge_attr="branch_distance", create_using=nx.MultiGraph,
    )


def giant_component_nodes(G: nx.Graph) -> set:
    """Node ids belonging to the connected component with the largest
    total skeleton length (by summed edge length, not node count: a
    component with fewer, longer edges can beat one with more, shorter ones).
    """
    components = list(nx.connected_components(G))
    if not components:
        return set()
    lengths = [
        sum(d["branch_distance"] for _, _, d in G.subgraph(c).edges(data=True))
        for c in components
    ]
    return components[int(np.argmax(lengths))]


def giant_component_span_px(node_coords: np.ndarray) -> float:
    """Straight-line distance (px) between the two farthest-apart points
    in node_coords (row, col pairs). The diameter of a point set is
    always realized by two of its convex-hull vertices, so this reduces
    the search to pairs among the hull instead of all-pairs -- relevant
    since a dense network's giant component can have thousands of nodes.
    Falls back to brute force over every point if the hull is degenerate
    (all nodes exactly collinear, e.g. a single isolated crack) -- scipy's
    ConvexHull raises on that input rather than returning a 2-point hull.
    """
    if len(node_coords) < 2:
        return float("nan")
    pts = node_coords
    if len(node_coords) > 3:
        try:
            pts = node_coords[ConvexHull(node_coords).vertices]
        except Exception:
            pts = node_coords
    d = pdist(pts)
    return float(d.max()) if len(d) > 0 else float("nan")


def compute_row(
    image_path: Path,
    *,
    cache_dir: Path | None = None,
    on_stage: Callable[[str], None] | None = None,
    scale_bar_check: str = SCALE_BAR_NOT_CHECKED,
) -> dict:
    """One row of the crack-stats table for one image.

    cache_dir (optional, off by default) also writes the analysis cache plus an
    overlay.png into cache_dir/image_path.stem/ (see src/crackgraph/cache_io.py).
    on_stage, if given, is called once per COMPUTE_ROW_STAGES entry, in order, as
    each stage completes (e.g. for a GUI progress bar). scale_bar_check is written
    verbatim into the row; only a caller that has inspected the image passes
    SCALE_BAR_CHECKED."""
    report = on_stage or (lambda _stage: None)
    t_start = time.perf_counter()
    gray, rgb = load_image(image_path)
    full_h, full_w = gray.shape

    t0 = time.perf_counter()
    binarize_result = binarize(gray)
    t_binarize = time.perf_counter() - t0
    report("Binarizing")

    # Single pass: the flaked region, if any, is skeletonized along with
    # everything else; its interior mesh is dropped below by
    # flake_touching_path_indices.
    t0 = time.perf_counter()
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    t_skeletonize = time.perf_counter() - t0
    report("Skeletonizing")

    t0 = time.perf_counter()
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    t_flaking = time.perf_counter() - t0
    report("Checking for flaking")

    t0 = time.perf_counter()
    graph_result = extract_graph(skeleton_result.skeleton)
    t_graph_extract = time.perf_counter() - t0

    # Any edge with a pixel inside the grown-out flake is dropped entirely --
    # from the stats AND from the connectivity graph.
    t0 = time.perf_counter()
    omitted = flake_touching_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
    )
    t_flaking += time.perf_counter() - t0
    report("Extracting graph")

    t0_stats = time.perf_counter()
    summary = graph_result.summary
    length_ok_mask = ~summary.index.isin(omitted)

    # mask_corrected == mask_clean & ~excluded_mask (see flaking.py): the crack
    # area outside the flaked region.
    crack_area_px2 = float(flaking_result.mask_corrected.sum())
    total_length_px = float(summary.loc[length_ok_mask, "branch_distance"].sum())
    n_edges_for_length = int(length_ok_mask.sum())

    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
    avg_edge_length_px = (
        total_length_px / n_edges_for_length if n_edges_for_length > 0 else float("nan")
    )

    median_width_px = median_pixelwise_width_px(
        skeleton_result.skeleton, graph_result, omitted, skeleton_result.medial_radius,
    )

    # crack_area_pct divides by the WHOLE image; this divides by the area we have
    # evidence about (whole image minus the flaking exclusion, which could be cracked
    # or not underneath -- see flaking.py).
    valid_area_px2 = full_w * full_h - flaking_result.excluded_area_px
    crack_area_pct_excl_flakes = (
        100.0 * crack_area_px2 / valid_area_px2 if valid_area_px2 > 0 else float("nan")
    )

    # Connectivity: build G from only the kept edges, so nothing routes through
    # the flaked region's own (spurious) interior mesh. The total length must be
    # filtered the same way, or the blob's interior mileage would deflate
    # giant_component_fraction. Fragments/spurs shorter than spur_px are already
    # gone before this runs: these are "components at least that long".
    kept_summary = summary.loc[length_ok_mask]
    G = crack_network_graph(kept_summary)
    n_components = nx.number_connected_components(G)
    full_total_length_px = float(kept_summary["branch_distance"].sum())
    gc_nodes = giant_component_nodes(G)
    if n_components > 0 and full_total_length_px > 0 and gc_nodes:
        gc_length_px = sum(
            d["branch_distance"] for _, _, d in G.subgraph(gc_nodes).edges(data=True)
        )
        giant_component_fraction = gc_length_px / full_total_length_px
    else:
        giant_component_fraction = float("nan")

    median_edge_length_px_val = median_edge_length_px(summary, omitted)
    median_edge_length_gc_px = median_edge_length_px(summary, omitted, node_filter=gc_nodes)

    # dgc: sampled from every pixel on every kept edge inside the giant component,
    # not just its node coordinates -- a component that is a single closed loop has
    # one node, so a node-only span would be undefined. Omitted edges contribute no
    # pixels even if both their endpoints are giant-component members.
    gc_edge_mask = (
        summary["node_id_src"].isin(gc_nodes)
        & summary["node_id_dst"].isin(gc_nodes)
        & length_ok_mask
    )
    gc_coords = (
        np.concatenate([
            skeleton_result.skeleton.path_coordinates(int(idx))
            for idx in summary.index[gc_edge_mask]
        ])
        if gc_edge_mask.any() else np.zeros((0, 2))
    )
    giant_component_span_px_val = giant_component_span_px(gc_coords)

    # Calibrated columns assume every image uses UM_PER_PX_MM_TAG; nothing here
    # checks the magnification. The _px columns don't depend on it.
    crack_area_mm2 = crack_area_px2 * (UM_PER_PX_MM_TAG ** 2) / 1e6
    avg_width_um = avg_width_px * UM_PER_PX_MM_TAG
    avg_edge_length_um = avg_edge_length_px * UM_PER_PX_MM_TAG
    median_width_um = median_width_px * UM_PER_PX_MM_TAG
    median_edge_length_um = median_edge_length_px_val * UM_PER_PX_MM_TAG
    median_edge_length_gc_um = median_edge_length_gc_px * UM_PER_PX_MM_TAG
    giant_component_span_um = giant_component_span_px_val * UM_PER_PX_MM_TAG

    t_stats = time.perf_counter() - t0_stats
    t_total = time.perf_counter() - t_start
    report("Computing stats")

    stats_row = {
        "image_filename": image_path.name,
        "source_folder": image_path.parent.name,
        "image_width_px": full_w,
        "image_height_px": full_h,
        "scale_bar_check": scale_bar_check,
        "crack_area_pct": 100.0 * crack_area_px2 / (full_w * full_h),
        "crack_area_pct_excl_flakes": crack_area_pct_excl_flakes,
        "crack_area_mm2": crack_area_mm2,
        "avg_width_px": avg_width_px,
        "avg_width_um": avg_width_um,
        "median_width_px": median_width_px,
        "median_width_um": median_width_um,
        "avg_edge_length_px": avg_edge_length_px,
        "avg_edge_length_um": avg_edge_length_um,
        "median_edge_length_px": median_edge_length_px_val,
        "median_edge_length_um": median_edge_length_um,
        "n_components": n_components,
        "giant_component_fraction": giant_component_fraction,
        "median_edge_length_gc_px": median_edge_length_gc_px,
        "median_edge_length_gc_um": median_edge_length_gc_um,
        "giant_component_span_px": giant_component_span_px_val,
        "giant_component_span_um": giant_component_span_um,
        "flaking_excluded_area_pct": flaking_result.excluded_area_pct,
        "flaking_n_candidates": len(flaking_result.candidates),
        "flaking_n_edges_omitted": len(omitted),
        "n_host_stubs_pruned": skeleton_result.n_host_stubs_pruned,
        "runtime_binarize_s": t_binarize,
        "runtime_skeletonize_s": t_skeletonize,
        "runtime_flaking_s": t_flaking,
        "runtime_graph_extract_s": t_graph_extract,
        "runtime_stats_s": t_stats,
        # Measured independently (whole-function wall clock), not summed from
        # the buckets above -- load_image and dict assembly aren't separately
        # bucketed, so this can exceed their sum by a small margin.
        "runtime_total_s": t_total,
    }

    if cache_dir is not None:
        image_stem = image_path.stem
        save_analysis_cache(
            cache_dir, image_stem,
            skeleton_result=skeleton_result, flaking_result=flaking_result, stats_row=stats_row,
        )
        render_crack_stats_overlay(
            rgb, skeleton_result.skeleton, graph_result,
            flaking_result.excluded_mask, omitted,
            cache_dir / image_stem / "overlay.png",
        )

    return stats_row


def add_batch_args(p: argparse.ArgumentParser) -> None:
    """--data-dir and --scale-bars-checked, shared by every batch export script."""
    p.add_argument(
        "--data-dir", type=str, default=DEFAULT_DATA_DIR,
        help="Folder holding the micrographs (default: data/raw inside this folder).",
    )
    p.add_argument(
        "--scale-bars-checked", action="store_true",
        help=(
            "Record scale_bar_check as visually confirmed. Only pass this if you have "
            "inspected every image for a burned-in scale bar."
        ),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=str, default="outputs/crack_stats.xlsx")
    p.add_argument(
        "--cache-dir", type=str, default=None,
        help=(
            "Also write the per-image analysis cache (mask/skeleton/excluded-region arrays, "
            "pruned-branch records, stats.json, overlay.png) here -- see cache_io.py. Off by default."
        ),
    )
    add_batch_args(p)
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = (repo_root / args.data_dir).resolve()
    image_paths = find_images(data_dir)
    scale_bar_check = SCALE_BAR_CHECKED if args.scale_bars_checked else SCALE_BAR_NOT_CHECKED
    cache_dir = repo_root / args.cache_dir if args.cache_dir else None

    rows = []
    for i, image_path in enumerate(image_paths, 1):
        print(f"[{i}/{len(image_paths)}] {image_path.relative_to(data_dir)}")
        rows.append(compute_row(image_path, cache_dir=cache_dir, scale_bar_check=scale_bar_check))

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, sheet_name="crack_stats")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
