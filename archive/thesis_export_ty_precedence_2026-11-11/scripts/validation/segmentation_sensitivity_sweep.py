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

Includes 3 non-Otsu comparison points, each labeled by what it actually is
rather than lumped into one "local/adaptive" data point: an unconfigured
naive local threshold (pathological on this image -- verified via a
connected-component-size check to be a few huge false-positive background
blobs, NOT noise fragmentation, caused by offset=0 pinning the threshold to
exactly the local mean in near-uniform dark background), the same method
with an ad hoc tuned offset (shows the above is a tuning artifact, not a
property of local thresholding -- not a proposed production constant), and
Sauvola's method (a standard local-contrast method needing no manual
offset, which matches Otsu's area within ~9% but still produces far more
edges/junctions -- a real, precise finding about topology noise, not area).

Run from the repo root:

    python3 scripts/validation/segmentation_sensitivity_sweep.py --image PATH [--out PATH]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from skimage.filters import threshold_local, threshold_otsu, threshold_sauvola

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.crackgraph.graph import extract_graph
from src.crackgraph.io_utils import load_image
from src.crackgraph.region import default_corner_crop
from src.crackgraph.skeleton import skeletonize_and_prune

OTSU_PERTURBATIONS_PCT = [-10, -5, 0, 5, 10]
# [PLACEHOLDER] window/block size shared by both local-method comparison
# points below -- not swept itself, tied to no calibrated length scale
# (none exists yet).
LOCAL_WINDOW_PX = 101
# [PLACEHOLDER, illustrative only] threshold_local's offset shifts the
# per-pixel threshold below the local mean (threshold = local_mean -
# offset). offset=0 (skimage's default) sets the threshold to EXACTLY the
# local mean, which is pathological in this image's near-uniform dark
# background (median gray ~1): roughly half of any flat patch sits above
# its own local mean by chance, so large low-contrast regions blow past
# threshold as single giant false-positive blobs -- verified via a
# connected-component-size check, not assumed. -15 is an ad hoc value
# found by manually probing until the result stopped being pathological;
# it is NOT a calibrated constant and is not proposed for production use --
# its only purpose here is to show that the offset=0 blowup is a tuning
# artifact of this specific naive method, not evidence that local/adaptive
# thresholding is unusable in general (see threshold_sauvola below for the
# fairer, no-manual-tuning comparison).
LOCAL_OFFSET_TUNED = -15
# skimage's own published default for threshold_sauvola -- not a value
# picked for this project, so unlike LOCAL_OFFSET_TUNED it needs no
# CALIBRATION.md entry of its own.
SAUVOLA_K = 0.2


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

    # -- Naive local threshold, unconfigured (offset=0 = local mean exactly) --
    local_t0 = threshold_local(gray, block_size=LOCAL_WINDOW_PX, offset=0)
    mask_local0 = gray > local_t0
    row0 = _run_variant(gray, mask_local0)
    row0["variant"] = f"local, offset=0 (unconfigured, block={LOCAL_WINDOW_PX}px)"
    row0["threshold"] = None  # not a single scalar -- per-pixel
    rows.append(row0)

    # -- Same method, ad hoc tuned offset -- shows the above is a tuning
    # artifact, not a property of local thresholding itself --
    local_t1 = threshold_local(gray, block_size=LOCAL_WINDOW_PX, offset=LOCAL_OFFSET_TUNED)
    mask_local1 = gray > local_t1
    row1 = _run_variant(gray, mask_local1)
    row1["variant"] = f"local, offset={LOCAL_OFFSET_TUNED} (ad hoc tuning, illustrative)"
    row1["threshold"] = None
    rows.append(row1)

    # -- Sauvola: standard local-contrast adaptive method, no manual offset --
    sauvola_t = threshold_sauvola(gray, window_size=LOCAL_WINDOW_PX, k=SAUVOLA_K)
    mask_sauvola = gray > sauvola_t
    row2 = _run_variant(gray, mask_sauvola)
    row2["variant"] = f"sauvola, k={SAUVOLA_K} (standard, no manual tuning)"
    row2["threshold"] = None
    rows.append(row2)

    for row in rows:
        row["delta_foreground_px_pct"] = (
            100.0 * (row["foreground_px"] - baseline["foreground_px"]) / baseline["foreground_px"]
        )
        row["delta_n_edges"] = row["n_edges"] - baseline["n_edges"]
        row["delta_n_junctions_deg3"] = row["n_junctions_deg3"] - baseline["n_junctions_deg3"]

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Path to a micrograph to run the sweep against.")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path("outputs/segmentation_sensitivity_data.json")

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
