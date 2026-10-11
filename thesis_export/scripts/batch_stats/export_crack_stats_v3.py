"""crack_stats_v3: a simplified, single-pass variant of
scripts/export_crack_stats.py's flaking exclusion. Does NOT modify or
replace that script -- both pipelines coexist, produce separate outputs,
and are independently runnable. See docs/batch_stats/crack_stats_schema.md
section 10 for the full methodology writeup and rationale.

v1 (export_crack_stats.py) excludes a flaked/delaminated region by
physically subtracting it from the mask and re-skeletonizing a SECOND
time on the corrected mask, then drops any edge that still ends up within
a reference-crack-width buffer of the exclusion boundary
(flaking.cut_adjacent_path_indices) from length/width stats only -- such
edges are deliberately KEPT in the connectivity graph, since in that
two-pass design they are real truncated stubs at an actual mask boundary.

v3 skips the second skeletonize pass entirely: it skeletonizes the raw,
uncorrected mask ONCE, then omits any edge with at least one pixel
physically inside the grown-out flake (flaking.flake_touching_path_indices
-- no buffer margin beyond the flake itself) from BOTH the stats AND the
connectivity graph. The "also from the connectivity graph" part is not
optional here the way it safely is for v1: a delaminated blob's own
un-corrected skeleton is inherently multi-branched and its
junction-to-junction edges are structurally un-prunable by
skeletonize_and_prune's spur/fragment pruning (see flaking.py's and
skeleton.py's module docstrings) -- left in the connectivity graph, they
would falsely bridge two real crack networks that only "connect" through
a region we have zero evidence about.

Usage:
    python3 -m scripts.batch_stats.export_crack_stats_v3 [--out outputs/crack_stats_v3.xlsx]
"""

import argparse
import time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from src.crackgraph.binarize import binarize
from src.crackgraph.cache_io import save_analysis_cache
from src.crackgraph.flaking import exclude_flaking_regions, flake_touching_path_indices
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.overlay import render_crack_stats_overlay
from src.crackgraph.skeleton import skeletonize_and_prune

from scripts.batch_stats.export_crack_stats import (
    ADDITIONAL_IMAGES,
    CONFIRMED_SCALE_BAR_IMAGES,
    KNOWN_BAD_FRAME_SUBSTRINGS,
    RAW_GLOB,
    UM_PER_PX_MM_TAG,
    giant_component_nodes,
    giant_component_span_px,
    median_edge_length_px,
    median_pixelwise_width_px,
)


def compute_row(image_path: Path, *, cache_dir: Path | None = None) -> dict:
    """See module docstring for how this differs from
    export_crack_stats.compute_row: one skeletonize pass instead of two,
    and omitted (any pixel inside the grown-out flake) instead of
    cut_adjacent (any pixel within a buffer of it) -- applied to the
    connectivity graph as well as the stats, not just the stats."""
    t_start = time.perf_counter()
    gray, rgb = load_image(image_path)
    full_h, full_w = gray.shape

    t0 = time.perf_counter()
    binarize_result = binarize(gray)
    t_binarize = time.perf_counter() - t0

    # Single pass -- no scout/real split. The flaked region, if any, is
    # skeletonized along with everything else; its interior mesh is
    # dropped below by flake_touching_path_indices, not by a second pass
    # that removes it from the mask beforehand.
    t0 = time.perf_counter()
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    t_skeletonize = time.perf_counter() - t0

    t0 = time.perf_counter()
    flaking_result = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius,
    )
    t_flaking = time.perf_counter() - t0

    t0 = time.perf_counter()
    graph_result = extract_graph(skeleton_result.skeleton)
    t_graph_extract = time.perf_counter() - t0

    # Omit-by-membership: any edge with a pixel inside the grown-out flake
    # is dropped entirely -- from stats AND from the connectivity graph.
    t0 = time.perf_counter()
    omitted = flake_touching_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
    )
    t_flaking += time.perf_counter() - t0

    t0_stats = time.perf_counter()
    summary = graph_result.summary
    length_ok_mask = ~summary.index.isin(omitted)

    # mask_corrected == mask_clean & ~excluded_mask (see flaking.py) -- it
    # is not used to build the skeleton in v3 (unlike v1), but it is still
    # exactly the crack-area figure we want, and reusing it avoids
    # re-deriving the same subtraction by hand. Unlike v1's crack_area_px2
    # (which comes from a SECOND skeletonize_and_prune call and is
    # therefore re-despeckled after the flake is carved out), this value
    # is not re-cleaned post-subtraction -- v1 and v3 area numbers on
    # flaked images are not expected to be bit-identical even given the
    # same source image. See docs/batch_stats/crack_stats_schema.md section 10.
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

    valid_area_px2 = full_w * full_h - flaking_result.excluded_area_px2
    crack_area_pct_excl_flakes = (
        100.0 * crack_area_px2 / valid_area_px2 if valid_area_px2 > 0 else float("nan")
    )

    # Connectivity: build G from only the non-omitted edges, so nothing
    # routes through the flaked region's own (spurious) interior mesh.
    # full_total_length_px must ALSO be filtered here, unlike v1 -- v1 can
    # sum its full (unfiltered) summary safely because its mask_corrected
    # already physically removed the flake before skeletonizing, so no
    # fake mileage exists there. v3's full summary DOES contain the
    # blob's own spurious interior mileage when candidates exist, so an
    # unfiltered sum would silently deflate giant_component_fraction.
    kept_summary = summary.loc[~summary.index.isin(omitted)]
    G = nx.from_pandas_edgelist(
        kept_summary, source="node_id_src", target="node_id_dst",
        edge_attr="branch_distance",
    )
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

    # gc_edge_mask ALSO gets an explicit ~omitted filter here, unlike v1's
    # giant_component_span_px call -- v1 deliberately keeps cut-adjacent
    # stub edges in its span calculation because a truncated stub's pixel
    # position is still real even though its length isn't trustworthy. v3
    # has no such "trustworthy stub" concept: an edge is either fully kept
    # or fully omitted, so an omitted edge must not contribute pixels here
    # even if both its endpoints happen to be giant-component members via
    # other, kept paths.
    gc_edge_mask = (
        summary["node_id_src"].isin(gc_nodes)
        & summary["node_id_dst"].isin(gc_nodes)
        & ~summary.index.isin(omitted)
    )
    gc_coords = (
        np.concatenate([
            skeleton_result.skeleton.path_coordinates(int(idx))
            for idx in summary.index[gc_edge_mask]
        ])
        if gc_edge_mask.any() else np.zeros((0, 2))
    )
    giant_component_span_px_val = giant_component_span_px(gc_coords)

    is_bad_frame = any(s in image_path.name for s in KNOWN_BAD_FRAME_SUBSTRINGS)
    if is_bad_frame:
        crack_area_mm2 = avg_width_um = avg_edge_length_um = median_width_um = None
        median_edge_length_um = median_edge_length_gc_um = giant_component_span_um = None
    else:
        crack_area_mm2 = crack_area_px2 * (UM_PER_PX_MM_TAG ** 2) / 1e6
        avg_width_um = avg_width_px * UM_PER_PX_MM_TAG
        avg_edge_length_um = avg_edge_length_px * UM_PER_PX_MM_TAG
        median_width_um = median_width_px * UM_PER_PX_MM_TAG
        median_edge_length_um = median_edge_length_px_val * UM_PER_PX_MM_TAG
        median_edge_length_gc_um = median_edge_length_gc_px * UM_PER_PX_MM_TAG
        giant_component_span_um = giant_component_span_px_val * UM_PER_PX_MM_TAG

    t_stats = time.perf_counter() - t0_stats
    t_total = time.perf_counter() - t_start

    stats_row = {
        "image_filename": image_path.name,
        "source_folder": image_path.parent.name,
        "image_width_px": full_w,
        "image_height_px": full_h,
        "scale_bar_check": "no blue bar (visually confirmed)",
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
        "n_corner_artifacts_pruned": skeleton_result.n_corner_artifacts_pruned,
        "runtime_binarize_s": t_binarize,
        "runtime_skeletonize_s": t_skeletonize,
        "runtime_flaking_s": t_flaking,
        "runtime_graph_extract_s": t_graph_extract,
        "runtime_stats_s": t_stats,
        # Measured independently (whole-function wall clock), not summed from
        # the buckets above -- load_image and dict/DataFrame assembly aren't
        # separately bucketed, so this can exceed their sum by a small margin.
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=str, default="outputs/crack_stats_v3.xlsx")
    p.add_argument(
        "--cache-dir", type=str, default=None,
        help=(
            "Also write the per-image analysis cache (mask/skeleton/excluded-region arrays, "
            "pruned-branch records, stats.json, overlay.png) here -- see cache_io.py. Use a "
            "directory distinct from any v1/v2 cache dir: this pipeline's mask_corrected.npz "
            "does not correspond to what was actually skeletonized (see "
            "docs/batch_stats/crack_stats_schema.md section 10). Off by default."
        ),
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    all_image_paths = sorted(repo_root.glob(RAW_GLOB)) + [
        repo_root / p for p in ADDITIONAL_IMAGES
    ]
    if not all_image_paths:
        raise SystemExit(f"No images matched {RAW_GLOB!r} under {repo_root}")

    image_paths = [p for p in all_image_paths if p.name not in CONFIRMED_SCALE_BAR_IMAGES]
    skipped = [p for p in all_image_paths if p.name in CONFIRMED_SCALE_BAR_IMAGES]
    for p in skipped:
        print(f"[skip] {p.relative_to(repo_root)} -- confirmed blue scale-bar overlay, excluded")

    cache_dir = repo_root / args.cache_dir if args.cache_dir else None

    rows = []
    for i, image_path in enumerate(image_paths, 1):
        print(f"[{i}/{len(image_paths)}] {image_path.relative_to(repo_root)}")
        rows.append(compute_row(image_path, cache_dir=cache_dir))

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, sheet_name="crack_stats_v3")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
