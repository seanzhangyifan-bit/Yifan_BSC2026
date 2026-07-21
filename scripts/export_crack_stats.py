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
import pandas as pd

from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import cut_adjacent_path_indices, exclude_flaking_regions
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
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


def compute_row(image_path: Path) -> dict:
    gray, _rgb = load_image(image_path)
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
    cut_adjacent = cut_adjacent_path_indices(graph_result, flaking_result.excluded_mask)
    summary = graph_result.summary
    length_ok_mask = ~summary.index.isin(cut_adjacent)

    crack_area_px2 = float(skeleton_result.mask_clean.sum())
    total_length_px = float(summary.loc[length_ok_mask, "branch_distance"].sum())
    n_edges_for_length = int(length_ok_mask.sum())

    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
    avg_edge_length_px = (
        total_length_px / n_edges_for_length if n_edges_for_length > 0 else float("nan")
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
    if n_components > 0 and full_total_length_px > 0:
        component_lengths = [
            sum(d["branch_distance"] for _, _, d in G.subgraph(c).edges(data=True))
            for c in nx.connected_components(G)
        ]
        giant_component_fraction = max(component_lengths) / full_total_length_px
    else:
        giant_component_fraction = float("nan")

    is_bad_frame = any(s in image_path.name for s in KNOWN_BAD_FRAME_SUBSTRINGS)
    if is_bad_frame:
        crack_area_mm2 = avg_width_um = avg_edge_length_um = None
    else:
        crack_area_mm2 = crack_area_px2 * (UM_PER_PX_MM_TAG ** 2) / 1e6
        avg_width_um = avg_width_px * UM_PER_PX_MM_TAG
        avg_edge_length_um = avg_edge_length_px * UM_PER_PX_MM_TAG

    return {
        "image_filename": image_path.name,
        "source_folder": image_path.parent.name,
        "image_width_px": full_w,
        "image_height_px": full_h,
        "scale_bar_check": "no blue bar (visually confirmed)",
        "crack_area_pct": 100.0 * crack_area_px2 / (full_w * full_h),
        "crack_area_mm2": crack_area_mm2,
        "avg_width_px": avg_width_px,
        "avg_width_um": avg_width_um,
        "avg_edge_length_px": avg_edge_length_px,
        "avg_edge_length_um": avg_edge_length_um,
        "n_components": n_components,
        "giant_component_fraction": giant_component_fraction,
        "flaking_excluded_area_pct": flaking_result.excluded_area_pct,
        "flaking_n_candidates": len(flaking_result.candidates),
        "flaking_n_edges_excluded_near_cut": len(cut_adjacent),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=str, default="outputs/crack_stats.xlsx")
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

    rows = []
    for i, image_path in enumerate(image_paths, 1):
        print(f"[{i}/{len(image_paths)}] {image_path.relative_to(repo_root)}")
        rows.append(compute_row(image_path))

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, sheet_name="crack_stats")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
