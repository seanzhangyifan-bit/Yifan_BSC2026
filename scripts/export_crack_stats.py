"""Export a small, standalone crack-statistics table for external consumption.

Deliberately stripped to stage 1-3 only (binarize -> skeletonize -> graph
extraction) -- no junction classification, corner cross-check, anisotropy,
or curvature. Those stages exist for this repo's own ordering/poset work;
this export is for a different consumer (an external agent that doesn't
know this pipeline and shouldn't need to) that only wants area, width,
edge length, and network-connectivity summary stats. See
docs/crack_stats_schema.md for the full column reference this script's
output is documented against -- keep the two in sync if either changes.

Usage:
    python3 -m scripts.export_crack_stats [--out outputs/crack_stats.xlsx]
"""

import argparse
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist

from src.crackgraph.binarize import binarize
from src.crackgraph.cache_io import save_analysis_cache
from src.crackgraph.flaking import cut_adjacent_path_indices, exclude_flaking_regions
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.overlay import render_crack_stats_overlay
from src.crackgraph.skeleton import skeletonize_and_prune

# Source: an external calibration tool (figlib/calibration.py,
# calibration.json) that is NOT part of this repository -- this is a
# hand-carried snapshot of that tool's output, not derived here and not
# re-derived by eye. Valid for the "mm" (full-resolution stitched mosaic)
# tag ONLY -- do not apply to 100x/200x/300x/500x/800x single-tile frames,
# which have their own, different factors. If this repo ever imports that
# tool directly, figlib.calibration.um_per_px("mm") should replace this
# constant as the live source of truth.
UM_PER_PX_MM_TAG = 100 / 164  # 0.609756... um/px

# Filenames confirmed to be mistagged as "mm" but are not the standard
# mosaic capture (would read ~2x too small if calibrated with the factor
# above). This pattern can't actually match RAW_GLOB below (wrong suffix,
# 000000 not 000001) but is kept here, checked explicitly, as a second,
# independent guard rather than relying on the glob suffix alone.
KNOWN_BAD_FRAME_SUBSTRINGS = ["_D_mm000000"]

# The "*_mm000001.jpg" naming convention is NOT a reliable guarantee of "no
# blue scale-bar overlay" -- it's just usually true. Every one of the 13
# mm000001 files was directly viewed (bottom-right corner crop) and exactly
# one had a burned-in blue "100.00um" bar despite matching the naming
# pattern: T5-M_H190_v2_mm000001.jpg. It is excluded entirely below, not
# just calibration-nulled, because it violates the actual selection
# criterion (no scale bar), not just the calibration-scope caveat. If more
# images are ever added to data/raw/, re-verify by eye -- don't trust the
# 000001 suffix alone.
CONFIRMED_SCALE_BAR_IMAGES = ["T5-M_H190_v2_mm000001.jpg"]

# Sample where the default *_mm000001.jpg index is the wrong (undersized) capture --
# this sample's actual mm000000/mm000001 pair is 4429x3322, not the standard ~7300x7600
# every other row has. mm000002/mm000003 are the standard-sized pair; mm000002 carries
# the blue scale bar, mm000003 doesn't (directly verified). See docs/crack_stats_schema.md
# S7b.
ADDITIONAL_IMAGES = ["data/raw/humidity_loading_ptfe/23RH_PTFE_v1_mm000003.jpg"]

RAW_GLOB = "data/raw/**/*_mm000001.jpg"


def median_pixelwise_width_px(skel, graph_result, cut_adjacent: set[int], medial_radius: np.ndarray) -> float:
    """Median of 2 * medial_radius sampled at every skeleton pixel belonging to a
    non-cut-adjacent edge -- a genuine per-pixel width measurement, unlike avg_width_px's
    global area/total-length ratio. Reuses cut_adjacent_path_indices' own exclusion set
    (rather than a second, separately-invented buffer rule) so this stays methodologically
    consistent with avg_width_px/avg_edge_length_px's existing cut-adjacent exclusion.
    Median, not mean, matches compute_reference_width_px's convention in flaking.py: a
    handful of anomalously wide pixels (junction blobs, near-miss flaking) shouldn't drag a
    single summary number around. [interpreted] -- a stated aggregation over [measured]
    per-pixel distance-transform values.
    """
    h, w = medial_radius.shape
    widths = []
    for path_index in graph_result.summary.index:
        if path_index in cut_adjacent:
            continue
        coords = skel.path_coordinates(int(path_index))
        rr = np.clip(np.round(coords[:, 0]).astype(int), 0, h - 1)
        cc = np.clip(np.round(coords[:, 1]).astype(int), 0, w - 1)
        widths.append(2.0 * medial_radius[rr, cc])
    if not widths:
        return float("nan")
    return float(np.median(np.concatenate(widths)))


def median_edge_length_px(summary, cut_adjacent: set[int], node_filter: set | None = None) -> float:
    """Median branch_distance (px) over edges not touching the flaking cut,
    optionally restricted to edges whose endpoints both lie in node_filter
    (used to isolate the giant component). Median rather than
    avg_edge_length_px's mean, for the same reason median_width_px isn't a
    mean: a handful of very long or very short segments (an artery-like
    branch, a tiny spur that survived pruning) shouldn't dominate a single
    summary number. [interpreted] aggregation over [measured] per-edge
    lengths.
    """
    mask = ~summary.index.isin(cut_adjacent)
    if node_filter is not None:
        mask &= summary["node_id_src"].isin(node_filter) & summary["node_id_dst"].isin(node_filter)
    lengths = summary.loc[mask, "branch_distance"]
    if len(lengths) == 0:
        return float("nan")
    return float(lengths.median())


def giant_component_nodes(G: nx.Graph) -> set:
    """Node ids belonging to the connected component with the largest
    total skeleton length -- the same 'giant' definition
    giant_component_fraction already uses (by summed edge length, not node
    count: a component with fewer, longer edges can beat one with more,
    shorter edges). Uses the FULL graph (including cut-adjacent stub
    edges) -- component membership is real topology even where an edge's
    own reported length is untrustworthy.
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


def compute_row(image_path: Path, *, cache_dir: Path | None = None) -> dict:
    """cache_dir is optional and off by default -- when set, also writes
    the six-file analysis cache plus an overlay.png into
    cache_dir/image_path.stem/ (see src/crackgraph/cache_io.py and
    docs/crack_stats_v2_status.md), so a later session can regenerate a
    figure or re-check a number without re-running binarize/skeletonize/
    prune on the full-resolution image. Existing callers that don't pass
    cache_dir see no behavior change."""
    gray, rgb = load_image(image_path)
    full_h, full_w = gray.shape

    binarize_result = binarize(gray)

    # Scout pass: skeletonize the raw mask only to get a width signal for
    # flaking identification. Real pass re-skeletonizes on the corrected
    # mask so flaked/delaminated regions never reach the thinning step --
    # see src/crackgraph/flaking.py.
    scout_skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    flaking_result = exclude_flaking_regions(
        scout_skeleton_result.mask_clean,
        scout_skeleton_result.skel_image,
        scout_skeleton_result.medial_radius,
    )
    if flaking_result.candidates:
        skeleton_result = skeletonize_and_prune(flaking_result.mask_corrected, source_image=gray)
    else:
        skeleton_result = scout_skeleton_result
    graph_result = extract_graph(skeleton_result.skeleton)

    # Edges touching the exclusion cut are truncated by our own correction,
    # not by a real crack arrest -- their length/width are not real
    # measurements, so they're dropped from those two stats specifically
    # (but kept in the connectivity graph below: they're still real
    # topology, just with an untrustworthy length).
    cut_adjacent = cut_adjacent_path_indices(
        skeleton_result.skeleton, graph_result, flaking_result.excluded_mask,
        flaking_result.reference_width_px,
    )
    summary = graph_result.summary
    length_ok_mask = ~summary.index.isin(cut_adjacent)

    crack_area_px2 = float(skeleton_result.mask_clean.sum())
    total_length_px = float(summary.loc[length_ok_mask, "branch_distance"].sum())
    n_edges_for_length = int(length_ok_mask.sum())

    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
    avg_edge_length_px = (
        total_length_px / n_edges_for_length if n_edges_for_length > 0 else float("nan")
    )

    # True per-pixel width, as opposed to avg_width_px's area/length ratio -- see
    # median_pixelwise_width_px's docstring. Cheap: distance_transform_edt is one
    # vectorized call over the same mask_clean already in memory.
    medial_radius = distance_transform_edt(skeleton_result.mask_clean)
    median_width_px = median_pixelwise_width_px(
        skeleton_result.skeleton, graph_result, cut_adjacent, medial_radius
    )

    # crack_area_pct divides by the WHOLE image; this divides by the area we actually have
    # evidence about (whole image minus the flaking exclusion, which could be cracked or not
    # underneath -- we don't know, see flaking.py). Always computed, no calibration factor
    # needed (both numerator and denominator are pixel counts).
    valid_area_px2 = full_w * full_h - flaking_result.excluded_area_px2
    crack_area_pct_excl_flakes = (
        100.0 * crack_area_px2 / valid_area_px2 if valid_area_px2 > 0 else float("nan")
    )

    # Percolation view of the same graph: how many disconnected crack
    # fragments survived stage 2's pruning (fragments/spurs shorter than
    # spur_px_threshold are already gone before this ever runs -- these
    # counts are "components at least that long," not literally every
    # mark in the raw mask), and what share of total crack length belongs
    # to the single largest one. Uses the FULL graph (including
    # cut-adjacent stub edges) -- they're real topology, only their
    # reported length is untrustworthy, not their existence.
    G = nx.from_pandas_edgelist(
        summary, source="node_id_src", target="node_id_dst",
        edge_attr="branch_distance",
    )
    n_components = nx.number_connected_components(G)
    full_total_length_px = float(summary["branch_distance"].sum())
    gc_nodes = giant_component_nodes(G)
    if n_components > 0 and full_total_length_px > 0 and gc_nodes:
        gc_length_px = sum(
            d["branch_distance"] for _, _, d in G.subgraph(gc_nodes).edges(data=True)
        )
        giant_component_fraction = gc_length_px / full_total_length_px
    else:
        giant_component_fraction = float("nan")

    # Structure *within* the giant component (as opposed to just its share of
    # total length above): median segment length on the whole image vs. just
    # within the giant component, and the giant component's own physical
    # spatial reach (straight-line span between its two farthest nodes) --
    # distinguishes a large multi-crack network from a single long crack.
    median_edge_length_px_val = median_edge_length_px(summary, cut_adjacent)
    median_edge_length_gc_px = median_edge_length_px(summary, cut_adjacent, node_filter=gc_nodes)
    node_id_to_coord = dict(zip(graph_result.node_ids.tolist(), graph_result.node_coords))
    gc_coords = (
        np.array([node_id_to_coord[n] for n in gc_nodes]) if gc_nodes else np.zeros((0, 2))
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
        "flaking_n_edges_excluded_near_cut": len(cut_adjacent),
        "n_corner_artifacts_pruned": skeleton_result.n_corner_artifacts_pruned,
    }

    if cache_dir is not None:
        image_stem = image_path.stem
        save_analysis_cache(
            cache_dir, image_stem,
            skeleton_result=skeleton_result, flaking_result=flaking_result, stats_row=stats_row,
        )
        render_crack_stats_overlay(
            rgb, skeleton_result.skeleton, graph_result,
            flaking_result.excluded_mask, cut_adjacent,
            cache_dir / image_stem / "overlay.png",
        )

    return stats_row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=str, default="outputs/crack_stats.xlsx")
    p.add_argument(
        "--cache-dir", type=str, default=None,
        help=(
            "Also write the per-image analysis cache (mask/skeleton/excluded-region arrays, "
            "pruned-branch records, stats.json, overlay.png) here -- see cache_io.py. "
            "Off by default; existing callers see no behavior change."
        ),
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
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
    df.to_excel(out_path, index=False, sheet_name="crack_stats")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
