"""Sensitivity check for the crack/not-crack decision itself.

binarize.py picks a single global Otsu threshold and its docstring asserts
(but never checks) that adaptive/local thresholding isn't needed because
"these images are already high-contrast." Every other tunable constant in
this project gets a sweep script (window_sweep.py, corner_window_sweep.py)
-- the threshold that decides what counts as crack in the first place never
has. This script is that sweep: it does NOT change binarize.py's production
default (Otsu stays the default, deliberately -- see that file's docstring),
it only measures how sensitive the downstream pipeline is to perturbing it.

Run on a REAL image crop, not a synthetic fixture -- synthetic fixtures use
flat, noiseless fg/bg values (fg_value=230, bg_value=10, no JPEG artifacts),
so any threshold strictly between them gives an identical mask and the sweep
would trivially show zero sensitivity, telling us nothing.

Run from the repo root:

    python3 scripts/segmentation_sensitivity_sweep.py [--image PATH] [--out PATH]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from skimage.filters import threshold_local, threshold_otsu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.region import default_corner_crop
from src.crackgraph.skeleton import skeletonize_and_prune

DEFAULT_IMAGE = "/home/seanzzz/UNI/crack-project/data/raw/T5/T5-M_H95_v1_mm000001.jpg"
OTSU_PERTURBATIONS_PCT = [-10, -5, 0, 5, 10]
# [PLACEHOLDER] block size for the one adaptive/local comparison point --
# not swept itself, just a representative "what if we used local instead of
# global" reference, tied to no calibrated length scale (none exists yet).
LOCAL_BLOCK_SIZE_PX = 101


def _run_variant(gray: np.ndarray, mask: np.ndarray) -> dict:
    skeleton_result = skeletonize_and_prune(mask, source_image=gray, spur_px=3.0)
    graph_result = extract_graph(skeleton_result.skeleton)
    return {
        "foreground_px": int(mask.sum()),
        "n_edges": graph_result.n_edges,
        "n_junctions_deg3": graph_result.n_junctions_deg3,
        "n_junctions_deg_ge4": graph_result.n_junctions_deg_ge4,
        "n_endpoints": graph_result.n_endpoints,
    }


def run_sweep(gray: np.ndarray) -> list[dict]:
    otsu_t = float(threshold_otsu(gray))
    rows = []

    baseline = None
    for pct in OTSU_PERTURBATIONS_PCT:
        t = otsu_t * (1.0 + pct / 100.0)
        mask = gray > t
        result = _run_variant(gray, mask)
        result["variant"] = f"otsu{pct:+d}%" if pct != 0 else "otsu (baseline)"
        result["threshold"] = t
        rows.append(result)
        if pct == 0:
            baseline = result

    local_t = threshold_local(gray, block_size=LOCAL_BLOCK_SIZE_PX)
    mask_local = gray > local_t
    local_result = _run_variant(gray, mask_local)
    local_result["variant"] = f"local/adaptive (block={LOCAL_BLOCK_SIZE_PX}px)"
    local_result["threshold"] = None  # not a single scalar -- per-pixel
    rows.append(local_result)

    for row in rows:
        row["delta_foreground_px_pct"] = (
            100.0 * (row["foreground_px"] - baseline["foreground_px"]) / baseline["foreground_px"]
        )
        row["delta_n_edges"] = row["n_edges"] - baseline["n_edges"]
        row["delta_n_junctions_deg3"] = row["n_junctions_deg3"] - baseline["n_junctions_deg3"]

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(
        "/home/seanzzz/.claude/jobs/1b81a62b/tmp/segmentation_sensitivity_data.json"
    )

    gray_full, _rgb_full = load_image(args.image)
    h, w = gray_full.shape
    region = default_corner_crop(h, w)
    gray = gray_full[region.row_slice, region.col_slice]

    rows = run_sweep(gray)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"image": args.image, "crop_px": list(gray.shape), "rows": rows}, indent=2))
    print(f"Wrote {out_path}")
    for row in rows:
        print(
            f"  {row['variant']:<28} px={row['foreground_px']:>8}  "
            f"edges={row['n_edges']:>3} (Δ{row['delta_n_edges']:+d})  "
            f"junc3={row['n_junctions_deg3']:>3} (Δ{row['delta_n_junctions_deg3']:+d})  "
            f"Δpx%={row['delta_foreground_px_pct']:+.2f}"
        )


if __name__ == "__main__":
    main()
