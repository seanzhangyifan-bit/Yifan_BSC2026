"""Quantify the doubled-skeleton-line artifact across the real dataset,
instead of just asserting "this happens on some images."

Background: `skeletonize_and_prune` (skeleton.py) prunes short dead-end
spurs and isolated fragments (skan branch_type 0/1), but its pruning is
structurally blind to branch_type 2 (junction-to-junction) and 3 (cycle)
edges, regardless of `spur_px`. Visual inspection of dense-crack samples
(e.g. T3-PTFE) showed a real, pervasive artifact: `skeletonize()`'s pixel-
erosion thinning sometimes traces both edges of a locally wide or slightly
irregular crack band for a short stretch before merging, leaving a small
closed loop instead of one clean centerline. This is not a `spur_px`-
tunable problem -- the two strands of a loop are both anchored to the
graph at each end, so they're never dead ends or isolated fragments.

Metric: for each image, the share of ALL graph edges that are (a)
junction-to-junction (branch_type 2) AND (b) shorter than that image's own
average crack width (`crack_area_px2 / total_skeleton_length_px`). A
junction-to-junction edge shorter than the crack it belongs to is the
fingerprint of this artifact -- a real crack segment between two genuine
T-junctions has no particular reason to be shorter than the crack itself
is wide, but a doubled-line loop segment does.

This is a real-data audit, not a synthetic ground-truth sweep like
window_sweep.py/corner_window_sweep.py -- there's no synthetic case that
reproduces JPEG-compression boundary noise on a real crack band, so the
claim here is checked against the actual 39-image dataset instead.

Run from the repo root:

    python3 scripts/skeleton_loop_sweep.py [--out outputs/skeleton_loop_sweep.csv]

Deterministic: no randomness anywhere in this script or the pipeline
stages it calls (Otsu threshold, Zhang thinning, skan graph extraction are
all deterministic given a fixed input image), so re-running reproduces
the exact same table.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.skeleton import skeletonize_and_prune

RAW_GLOB = "data/raw/**/*_mm000001.jpg"

# Same folder->substrate mapping already established for this dataset (see
# docs/crack_stats_schema.md S3): T5/, aquivion_t2_membran/,
# characterization2_membran/, humidity_loading/ are Membran; everything
# with "_ptfe" in the folder name is PTFE.
MEMBRAN_FOLDERS = {"T5", "aquivion_t2_membran", "characterization2_membran", "humidity_loading"}


def sweep_one(image_path: Path) -> dict:
    gray, _rgb = load_image(image_path)
    full_h, full_w = gray.shape

    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)

    summary = graph_result.summary
    crack_area_px2 = binarize_result.foreground_fraction * full_w * full_h
    total_length_px = float(summary["branch_distance"].sum())
    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")

    junction_to_junction = summary[summary["branch_type"] == 2]
    short_jj = junction_to_junction[junction_to_junction["branch_distance"] < avg_width_px]
    pct_short_jj_edges = 100 * len(short_jj) / len(summary) if len(summary) > 0 else float("nan")

    substrate = "Membran" if image_path.parent.name in MEMBRAN_FOLDERS else "PTFE"

    return {
        "image_filename": image_path.name,
        "source_folder": image_path.parent.name,
        "substrate": substrate,
        "avg_width_px": round(avg_width_px, 2),
        "n_edges": len(summary),
        "pct_short_jj_edges": round(pct_short_jj_edges, 1),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=str, default="outputs/skeleton_loop_sweep.csv")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    image_paths = sorted(repo_root.glob(RAW_GLOB))
    if not image_paths:
        raise SystemExit(f"No images matched {RAW_GLOB!r} under {repo_root}")

    rows = []
    for i, path in enumerate(image_paths, 1):
        row = sweep_one(path)
        print(f"[{i}/{len(image_paths)}] {row['image_filename']} "
              f"({row['substrate']}, w={row['avg_width_px']:.1f}px) "
              f"-> {row['pct_short_jj_edges']:.1f}% short junction-to-junction edges")
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("avg_width_px")
    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print(f"\nWrote {out_path}\n")
    print("=== by substrate ===")
    print(out.groupby("substrate")["pct_short_jj_edges"].describe())
    print()
    corr = out["avg_width_px"].corr(out["pct_short_jj_edges"])
    print(f"correlation (avg_width_px vs pct_short_jj_edges): {corr:.3f}")


if __name__ == "__main__":
    main()
