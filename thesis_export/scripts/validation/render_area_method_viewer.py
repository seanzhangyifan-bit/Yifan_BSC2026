"""Render the 4 area-characterization methods (core, exact/watershed, mask
total, ribbon-integral) from edge_metrics.py as 4 highlighted overlay PNGs
over a common base image, plus their numeric bracket -- data for a
hand-authored interactive click-through viewer (built separately as a
Claude Artifact). This script only produces DATA (deterministic, testable
in principle), not the page itself.

Default demo image is the synthetic T-junction fixture already used
throughout tests/test_edge_metrics.py -- 3 clean arms make the 4 methods'
differences legible at a glance, unlike a busy real crack network. Pass
--image PATH to run against a real crop instead.

Run from the repo root:

    python3 scripts/validation/render_area_method_viewer.py [--image PATH] [--out PATH]
"""

import argparse
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.draw import disk
from skimage.io import imread

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.crackgraph.binarize import binarize
from src.crackgraph.edge_metrics import (
    compute_ambiguous_pixel_mask,
    compute_edge_metrics,
    partition_area_by_edge,
)
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_t_junction

MASK_TOTAL_COLOR = np.array([70, 130, 180])  # steelblue -- "everything counted"
RIBBON_COLOR = np.array([220, 20, 60])  # crimson -- overlap darkens via alpha
AMBIGUOUS_GRAY_A = np.array([110, 110, 110])
AMBIGUOUS_GRAY_B = np.array([165, 165, 165])
EDGE_PALETTE = np.array(
    [
        [31, 119, 180],
        [255, 127, 14],
        [44, 160, 44],
        [214, 39, 40],
        [148, 103, 189],
        [140, 86, 75],
        [227, 119, 194],
        [127, 127, 127],
        [188, 189, 34],
        [23, 190, 207],
    ]
)  # matplotlib tab10, reused as raw RGB triples -- no matplotlib dependency needed


def _load_image(image_path: str | None) -> np.ndarray:
    if image_path is None:
        return generate_t_junction(size=220, thickness=9, margin=18, arm_length=85.0)
    gray = imread(image_path, as_gray=True)
    return gray.astype(np.float64) * (255.0 if gray.max() <= 1.0 else 1.0)


def _grayscale_base_rgb(gray: np.ndarray) -> np.ndarray:
    lo, hi = float(gray.min()), float(gray.max())
    norm = (gray - lo) / (hi - lo) if hi > lo else np.zeros_like(gray)
    base = (norm * 255.0).astype(np.uint8)
    return np.stack([base, base, base], axis=-1)


def _composite(base_rgb: np.ndarray, overlay_rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    a = alpha[..., None]
    out = base_rgb.astype(np.float64) * (1.0 - a) + overlay_rgb.astype(np.float64) * a
    return np.clip(out, 0, 255).astype(np.uint8)


def _to_data_uri(rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_overlays(gray: np.ndarray) -> dict:
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3.0)
    graph_result = extract_graph(skeleton_result.skeleton)
    mask_clean = skeleton_result.mask_clean
    medial_radius = skeleton_result.medial_radius

    watershed_result = partition_area_by_edge(
        skeleton_result.skeleton, graph_result.summary, mask_clean, medial_radius
    )
    metrics = compute_edge_metrics(
        skeleton_result.skeleton, graph_result, mask_clean, medial_radius
    )
    ambiguous_mask = compute_ambiguous_pixel_mask(graph_result, mask_clean, medial_radius)

    base_rgb = _grayscale_base_rgb(gray)
    path_indices = sorted(int(i) for i in graph_result.summary.index)
    palette = {
        path_index: EDGE_PALETTE[i % len(EDGE_PALETTE)] for i, path_index in enumerate(path_indices)
    }

    # -- mask total: flat highlight over every foreground pixel --
    mask_total_overlay = np.broadcast_to(MASK_TOTAL_COLOR, (*mask_clean.shape, 3))
    mask_total_alpha = np.where(mask_clean, 0.55, 0.0)
    mask_total_png = _composite(base_rgb, mask_total_overlay, mask_total_alpha)

    # -- exact: per-edge watershed partition, one hue per path_index --
    exact_overlay = np.zeros((*mask_clean.shape, 3))
    exact_alpha = np.zeros(mask_clean.shape)
    for path_index in path_indices:
        sel = watershed_result.labels == path_index + 1
        exact_overlay[sel] = palette[path_index]
        exact_alpha[sel] = 0.6
    exact_png = _composite(base_rgb, exact_overlay, exact_alpha)

    # -- core: same per-edge hues, junction-disk pixels swapped to a
    # neutral diagonal-hatch gray outside the per-edge palette so it can't
    # be misread as a 4th edge --
    rows, cols = np.indices(mask_clean.shape)
    hatch = ((rows + cols) % 6) < 3
    gray_pattern = np.where(hatch[..., None], AMBIGUOUS_GRAY_A, AMBIGUOUS_GRAY_B)
    core_overlay = np.where(ambiguous_mask[..., None], gray_pattern, exact_overlay)
    core_alpha = exact_alpha.copy()
    core_alpha[ambiguous_mask] = 0.6
    core_png = _composite(base_rgb, core_overlay, core_alpha)

    # -- ribbon: per-edge swept-disk footprint, summed across edges so
    # overlap (the double-counting mechanism) reads as higher alpha --
    overlap_count = np.zeros(mask_clean.shape, dtype=int)
    h, w = mask_clean.shape
    for path_index in path_indices:
        coords = skeleton_result.skeleton.path_coordinates(path_index)
        edge_footprint = np.zeros(mask_clean.shape, dtype=bool)
        for r, c in coords:
            r_idx = int(np.clip(round(r), 0, h - 1))
            c_idx = int(np.clip(round(c), 0, w - 1))
            radius = float(medial_radius[r_idx, c_idx])
            rr, cc = disk((r, c), radius, shape=mask_clean.shape)
            edge_footprint[rr, cc] = True
        overlap_count += edge_footprint.astype(int)
    ribbon_overlay = np.broadcast_to(RIBBON_COLOR, (*mask_clean.shape, 3))
    ribbon_alpha = np.clip(0.28 * overlap_count, 0, 0.88)
    ribbon_png = _composite(base_rgb, ribbon_overlay, ribbon_alpha)

    lengths = [m.length_px for m in metrics.per_edge.values()]
    widths_ok = [m.width.mean_px for m in metrics.per_edge.values() if m.width.ok]

    return {
        "images": {
            "core": _to_data_uri(core_png),
            "exact": _to_data_uri(exact_png),
            "mask_total": _to_data_uri(mask_total_png),
            "ribbon": _to_data_uri(ribbon_png),
        },
        "stats": {
            "n_edges": len(path_indices),
            "total_area_core_px2": metrics.total_area_core_px2,
            "total_area_px2": metrics.total_area_px2,
            "mask_clean_total_px2": metrics.mask_clean_total_px2,
            "total_area_ribbon_px2": metrics.total_area_ribbon_px2,
            "n_unassigned_px": metrics.n_unassigned_px,
            "n_zero_core_edges": metrics.n_zero_core_edges,
            "n_ribbon_high": metrics.n_ribbon_high,
            "n_ribbon_low_or_equal": metrics.n_ribbon_low_or_equal,
            # Per-edge summary stats -- aggregated here from EdgeMetricsResult.
            # per_edge, no new pipeline computation. [interpreted]
            "mean_length_px": float(np.mean(lengths)) if lengths else None,
            "median_length_px": float(np.median(lengths)) if lengths else None,
            "n_width_ok": len(widths_ok),
            "mean_width_px": float(np.mean(widths_ok)) if widths_ok else None,
            "median_width_px": float(np.median(widths_ok)) if widths_ok else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=None, help="Path to a real image; default is a synthetic T-junction")
    parser.add_argument("--out", default=None, help="Output JSON path")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path("outputs/area_method_viewer_data.json")
    gray = _load_image(args.image)
    data = build_overlays(gray)

    import json

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KiB)")
    print("Stats:", data["stats"])


if __name__ == "__main__":
    main()
