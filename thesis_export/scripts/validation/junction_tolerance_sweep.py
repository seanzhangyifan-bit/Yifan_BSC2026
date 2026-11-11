"""Sensitivity of the T / Y / ambiguous junction census to the classification
cut-offs (Y_ANGLE_TOL_DEG_PLACEHOLDER, T_STRAIGHT_TOL_DEG_PLACEHOLDER,
T_RIGHT_TOL_DEG_PLACEHOLDER in junctions.py), which are 🔴 assumed.

Changing a cut-off doesn't change any measured angle, only how the angles
are sorted into T, Y, or ambiguous. So each image's junction angles are
measured once, with the same pipeline and defaults as src/analyze_image.py,
and then re-sorted under every cut-off setting below.

Settings:
- baseline: the current defaults.
- one-at-a-time: each cut-off moved alone, the other two held at baseline.
- joint: all three scaled together by the same factor.

Outputs (under --out-dir):
- junction_tolerance_sweep_per_image.csv: one row per (image, setting) with
  T/Y/ambiguous/insufficient counts.
- junction_tolerance_sweep_per_condition.csv: the same, summed over the
  replicates of each condition (filename with the _v# replicate tag removed).
- A printed summary: totals per setting, the range of each condition's
  T share across settings, and whether the ranking of conditions by T share
  changes from the baseline (Spearman rank correlation).

By default only the top-left corner crop is measured, about 1.5% of each
image's area (the per-image pipeline's validated default). Counts are a corner
sample, not whole-image totals; every output row records the region and its
area share.

T share = T / (T + Y + ambiguous). Junctions whose angles couldn't be
measured ("insufficient_data") are excluded from it; they don't depend on
the cut-offs.

Usage:
    python3 -m scripts.validation.junction_tolerance_sweep --data-dir ../data/raw
        [--full-image] [--out-dir outputs/junction_tolerance_sweep]
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from scripts.batch_stats.export_crack_stats import DEFAULT_DATA_DIR, find_batch_images
from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import exclude_flaking_regions
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.junctions import (
    T_RIGHT_TOL_DEG_PLACEHOLDER,
    T_STRAIGHT_TOL_DEG_PLACEHOLDER,
    Y_ANGLE_TOL_DEG_PLACEHOLDER,
    classify_from_gaps,
    classify_junctions,
    sector_gaps_deg_from_bearings,
)
from src.crackgraph.region import default_corner_crop
from src.crackgraph.skeleton import skeletonize_and_prune

BASELINE = (Y_ANGLE_TOL_DEG_PLACEHOLDER, T_STRAIGHT_TOL_DEG_PLACEHOLDER, T_RIGHT_TOL_DEG_PLACEHOLDER)
ONE_AT_A_TIME = {
    "y_tol": [5.0, 10.0, 15.0, 20.0, 25.0],
    "t_straight_tol": [10.0, 15.0, 20.0, 25.0, 30.0],
    "t_right_tol": [10.0, 15.0, 20.0, 25.0, 30.0],
}
JOINT_SCALES = [0.5, 0.75, 1.0, 1.25, 1.5]

LABELS = ("T", "Y", "ambiguous")


def sweep_settings() -> list[tuple[str, float, float, float]]:
    """(setting_name, y_tol, t_straight_tol, t_right_tol), baseline first, no duplicates."""
    y0, ts0, tr0 = BASELINE
    settings = [("baseline", y0, ts0, tr0)]
    for value in ONE_AT_A_TIME["y_tol"]:
        settings.append((f"y_tol={value:g}", value, ts0, tr0))
    for value in ONE_AT_A_TIME["t_straight_tol"]:
        settings.append((f"t_straight_tol={value:g}", y0, value, tr0))
    for value in ONE_AT_A_TIME["t_right_tol"]:
        settings.append((f"t_right_tol={value:g}", y0, ts0, value))
    for scale in JOINT_SCALES:
        settings.append((f"joint_x{scale:g}", y0 * scale, ts0 * scale, tr0 * scale))

    unique, seen = [], set()
    for name, *tols in settings:
        key = tuple(round(t, 6) for t in tols)
        if key not in seen:
            seen.add(key)
            unique.append((name, *tols))
    return unique


def condition_of(image_name: str) -> str:
    """Filename with the replicate tag and capture index removed, e.g.
    T5-PTFE_H95_v2_mm000001.jpg -> T5-PTFE_H95. Replicates (v1, v2, ...) are
    physically distinct captures of the same condition."""
    stem = Path(image_name).stem
    stem = re.sub(r"_(mm|lu|ro)\d+$", "", stem)
    return re.sub(r"_v\d+(?=_|$)", "", stem)


def measure_junction_gaps(image_path: Path, *, full_image: bool) -> tuple[list, int, float]:
    """Sector-gap tuples for every degree-3 junction whose angles could be
    measured, the count of junctions that couldn't be, and the analyzed
    region's share of the image area (%). Same stage order and defaults as
    src/analyze_image.py, including the flaking second pass."""
    gray, _ = load_image(image_path)
    full_area = gray.size
    if not full_image:
        region = default_corner_crop(*gray.shape)
        gray = gray[region.row_slice, region.col_slice]

    mask = binarize(gray).mask
    skeleton_result = skeletonize_and_prune(mask, source_image=gray)
    flaking = exclude_flaking_regions(
        skeleton_result.mask_clean, skeleton_result.skel_image, skeleton_result.medial_radius
    )
    if flaking.candidates:
        skeleton_result = skeletonize_and_prune(flaking.mask_corrected, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)
    junctions = classify_junctions(
        skeleton_result.skeleton, graph_result, medial_radius=skeleton_result.medial_radius
    )

    gap_sets, n_insufficient = [], 0
    for c in junctions.classifications:
        if c.label == "insufficient_data":
            n_insufficient += 1
        else:
            gap_sets.append(sector_gaps_deg_from_bearings([ed.bearing_deg for ed in c.edge_directions]))
    return gap_sets, n_insufficient, 100.0 * gray.size / full_area


def census(gap_sets: list, y_tol: float, t_straight_tol: float, t_right_tol: float) -> dict[str, int]:
    """T / Y / ambiguous counts for already-measured junctions under one cut-off setting."""
    counts = dict.fromkeys(LABELS, 0)
    for gaps in gap_sets:
        label, _, _ = classify_from_gaps(gaps, y_tol, t_straight_tol, t_right_tol)
        counts[label] += 1
    return counts


def t_share(n_t: float, n_y: float, n_ambiguous: float) -> float:
    total = n_t + n_y + n_ambiguous
    return n_t / total if total > 0 else float("nan")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR)
    p.add_argument("--out-dir", type=str, default="outputs/junction_tolerance_sweep")
    p.add_argument(
        "--full-image", action="store_true",
        help="Measure the whole image instead of the pipeline's default top-left corner crop.",
    )
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = (repo_root / args.data_dir).resolve()
    out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    image_paths = find_batch_images(data_dir)
    settings = sweep_settings()
    region = "full image" if args.full_image else "top-left corner crop (~1.5% of image area)"

    rows = []
    for i, image_path in enumerate(image_paths, 1):
        gap_sets, n_insufficient, region_area_pct = measure_junction_gaps(image_path, full_image=args.full_image)
        print(f"[{i}/{len(image_paths)}] {image_path.relative_to(data_dir)}: "
              f"{len(gap_sets)} measurable junctions, {n_insufficient} insufficient_data")
        for name, y_tol, ts_tol, tr_tol in settings:
            counts = census(gap_sets, y_tol, ts_tol, tr_tol)
            rows.append({
                "image_filename": image_path.name,
                "condition": condition_of(image_path.name),
                "region": region,
                "region_area_pct": region_area_pct,
                "setting": name,
                "y_tol_deg": y_tol,
                "t_straight_tol_deg": ts_tol,
                "t_right_tol_deg": tr_tol,
                "n_T": counts["T"],
                "n_Y": counts["Y"],
                "n_ambiguous": counts["ambiguous"],
                "n_insufficient_data": n_insufficient,
                "t_share": t_share(counts["T"], counts["Y"], counts["ambiguous"]),
            })

    per_image = pd.DataFrame(rows)
    per_image.to_csv(out_dir / "junction_tolerance_sweep_per_image.csv", index=False)

    count_cols = ["n_T", "n_Y", "n_ambiguous", "n_insufficient_data"]
    per_condition = (
        per_image.groupby(["condition", "setting", "y_tol_deg", "t_straight_tol_deg", "t_right_tol_deg"], sort=False)
        .agg(n_replicates=("image_filename", "nunique"), **{c: (c, "sum") for c in count_cols})
        .reset_index()
    )
    per_condition["t_share"] = [
        t_share(t, y, a) for t, y, a in zip(per_condition.n_T, per_condition.n_Y, per_condition.n_ambiguous)
    ]
    per_condition.to_csv(out_dir / "junction_tolerance_sweep_per_condition.csv", index=False)

    setting_order = [s[0] for s in settings]
    totals = per_image.groupby("setting", sort=False)[count_cols].sum().reindex(setting_order)
    totals["t_share"] = [t_share(t, y, a) for t, y, a in zip(totals.n_T, totals.n_Y, totals.n_ambiguous)]

    pivot = per_condition.pivot(index="condition", columns="setting", values="t_share")[setting_order]
    baseline = pivot["baseline"]
    rank_corr = {
        s: spearmanr(baseline, pivot[s], nan_policy="omit").statistic if s != "baseline" else 1.0
        for s in setting_order
    }
    totals["rank_corr_vs_baseline"] = [rank_corr[s] for s in setting_order]

    with pd.option_context("display.width", 160, "display.max_columns", 20, "display.float_format", "{:.3f}".format):
        print(f"\n=== Totals over {len(image_paths)} images ({region}) ===")
        print(totals)
        spread = pd.DataFrame({
            "baseline_t_share": baseline,
            "min_t_share": pivot.min(axis=1),
            "max_t_share": pivot.max(axis=1),
        })
        spread["range"] = spread.max_t_share - spread.min_t_share
        print("\n=== T share per condition: baseline and range across all settings ===")
        print(spread.sort_values("baseline_t_share"))
    print(f"\nWrote {out_dir / 'junction_tolerance_sweep_per_image.csv'}")
    print(f"Wrote {out_dir / 'junction_tolerance_sweep_per_condition.csv'}")


if __name__ == "__main__":
    main()
