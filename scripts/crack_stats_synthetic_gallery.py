"""Synthetic-mesh validation gallery for the crack_stats pipeline
specifically (stage 1-3 + flaking.py -- the modules
scripts/export_crack_stats.py actually imports), as opposed to
scripts/validation_gallery.py's battery, which covers stage 4
(junction/kink/corner/curvature/anisotropy) and is not part of
crack_stats.xlsx at all.

Runs generate_grid (at several widths), generate_wavy_grid,
generate_hexagonal_grid, and generate_grid_with_flakes (see
src/crackgraph/synthetic.py) through the same binarize -> skeletonize ->
graph chain export_crack_stats.py uses, tinting flaking-excluded regions
with the pipeline's own render_crack_stats_overlay, and compiles an
expected-vs-measured HTML report -- the mesh-network counterpart to
tests/test_grid_synthetic.py, for visual review rather than a bare pytest
pass/fail.

Usage:
    python3 -m scripts.crack_stats_synthetic_gallery [--out-dir outputs/crack_stats_synthetic]
"""

import argparse
from pathlib import Path

import numpy as np
from skimage.draw import disk

from src.crackgraph.binarize import binarize
from src.crackgraph.flaking import cut_adjacent_path_indices, exclude_flaking_regions
from src.crackgraph.graph import extract_graph
from src.crackgraph.overlay import render_crack_stats_overlay
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    generate_grid,
    generate_grid_with_flakes,
    generate_hexagonal_grid,
    generate_wavy_grid,
    grid_topology,
    hex_flower_topology,
    wavy_line_arc_length_px,
)


def _to_rgb_uint8(gray: np.ndarray) -> np.ndarray:
    lo, hi = float(gray.min()), float(gray.max())
    norm = np.zeros_like(gray) if hi - lo < 1e-9 else (gray - lo) / (hi - lo)
    u8 = (norm * 255).astype(np.uint8)
    return np.stack([u8, u8, u8], axis=-1)


def _run_stage123(gray: np.ndarray, spur_px: float = 3.0):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    return binarize_result, skeleton_result, graph_result


def _row(metric, expected, measured):
    return (metric, str(expected), str(measured))


def case_grid_widths(out_dir: Path) -> list[dict]:
    n_lines, margin, thickness = 3, 30.0, 5
    cases = []
    for spacing in (35.0, 70.0, 140.0):
        size = int(2 * margin + spacing * (n_lines + 1))
        gray = generate_grid(size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=thickness)
        _, skel_res, graph_res = _run_stage123(gray)
        expected = grid_topology(n_lines, n_lines)
        name = f"grid_spacing{int(spacing)}"
        out_path = out_dir / f"{name}.png"
        render_crack_stats_overlay(
            _to_rgb_uint8(gray), skel_res.skeleton, graph_res,
            np.zeros(gray.shape, dtype=bool), set(), out_path,
        )
        total_len = float(graph_res.summary["branch_distance"].sum())
        cases.append({
            "name": name,
            "title": f"Rectilinear grid, {int(spacing)}px spacing ({size}x{size}px crop)",
            "image": out_path.name,
            "desc": f"3x3 straight-line mesh at {int(spacing)}px line spacing -- a grid-width sweep, "
                    "since crack_stats.xlsx's n_edges/giant_component_fraction depend on how dense "
                    "the network is, not just whether one junction resolves correctly.",
            "rows": [
                _row("n_endpoints", expected["n_endpoints"], graph_res.n_endpoints),
                _row("n_junctions_deg>=4", expected["n_junctions_deg_ge4"], graph_res.n_junctions_deg_ge4),
                _row("n_junctions_deg3", 0, graph_res.n_junctions_deg3),
                _row("n_edges", expected["n_edges"], graph_res.n_edges),
                _row("total_length_px", "(scales with spacing)", f"{total_len:.1f}"),
            ],
        })
    return cases


def case_wavy_grid(out_dir: Path) -> dict:
    size, n_lines, spacing, margin, thickness = 340, 3, 70.0, 30.0, 5
    amplitude, wavelength = 10.0, 110.0
    gray = generate_wavy_grid(
        size=size, n_lines=n_lines, spacing=spacing, margin=margin, thickness=thickness,
        amplitude=amplitude, wavelength=wavelength,
    )
    _, skel_res, graph_res = _run_stage123(gray)
    out_path = out_dir / "wavy_grid.png"
    render_crack_stats_overlay(
        _to_rgb_uint8(gray), skel_res.skeleton, graph_res,
        np.zeros(gray.shape, dtype=bool), set(), out_path,
    )
    run_px = size - 2 * margin
    horiz_arc = wavy_line_arc_length_px(run_px, amplitude=amplitude, wavelength=wavelength)
    expected_total_len = n_lines * horiz_arc + n_lines * run_px
    measured_total_len = float(graph_res.summary["branch_distance"].sum())
    straight_expected = grid_topology(n_lines, n_lines)
    return {
        "name": "wavy_grid",
        "title": "Wavy grid (sinusoidal horizontal lines, straight verticals)",
        "image": out_path.name,
        "desc": "Same 3x3 crossing layout as the straight grid, but horizontal lines follow a sine "
                "wave. Length recovery still holds against the closed-form arc-length integral; "
                "topology genuinely does not match the straight grid -- any local tilt at a crossing "
                "splits a clean degree-4 point into a pair of degree-3 points, a real structural "
                "instability, not a rendering bug (see synthetic.py's generate_wavy_grid docstring).",
        "rows": [
            _row("total_length_px (closed-form arc+chord)", f"{expected_total_len:.1f}", f"{measured_total_len:.1f}"),
            _row("n_endpoints", straight_expected["n_endpoints"], graph_res.n_endpoints),
            _row("n_junctions total (deg3+deg4+) -- straight-grid baseline", 9, graph_res.n_junctions_deg3 + graph_res.n_junctions_deg_ge4),
            _row("n_edges -- straight-grid baseline", straight_expected["n_edges"], graph_res.n_edges),
        ],
    }


def case_hexagonal_grid(out_dir: Path) -> dict:
    radius = 40.0
    size = int(radius * 7)
    gray = generate_hexagonal_grid(size=size, radius=radius, thickness=5)
    _, skel_res, graph_res = _run_stage123(gray, spur_px=15.0)
    out_path = out_dir / "hexagonal_grid.png"
    render_crack_stats_overlay(
        _to_rgb_uint8(gray), skel_res.skeleton, graph_res,
        np.zeros(gray.shape, dtype=bool), set(), out_path,
    )
    ideal = hex_flower_topology(radius=radius)
    return {
        "name": "hexagonal_grid",
        "title": "Hexagonal honeycomb flower (1 center + 6 neighbors)",
        "image": out_path.name,
        "desc": "The junction valence real crack networks actually favor (Goehring 2012's "
                "rectilinear-to-hexagonal evolution), unlike generate_grid's degree-4 crossings. "
                "The idealized combinatorial ground truth (12 junctions, 18 edges) is not quite what "
                "real skeletonization measures -- 2 of the 12 true vertices render as a locally wider "
                "blob and split into adjacent node pairs, giving 14/21 instead, stable across radius "
                "(see synthetic.py's generate_hexagonal_grid docstring).",
        "rows": [
            _row("n_endpoints", ideal["n_endpoints"], graph_res.n_endpoints),
            _row("n_junctions_deg3 (ideal 12, measured 14 -- verified junction-splitting)", ideal["n_junctions_deg3"], graph_res.n_junctions_deg3),
            _row("n_edges (ideal 18, measured 21)", ideal["n_edges"], graph_res.n_edges),
        ],
    }


def case_grid_with_flakes(out_dir: Path) -> dict:
    n_lines, spacing, margin, thickness = 3, 70.0, 30.0, 5
    row_ys = [margin + spacing * (i + 1) for i in range(n_lines)]
    col_xs = row_ys
    flake_center = (row_ys[1], col_xs[1])
    flake_radius = 26.0

    gray = generate_grid_with_flakes(
        size=340, n_lines=n_lines, spacing=spacing, margin=margin, thickness=thickness,
        flake_centers=[flake_center], flake_radius=flake_radius,
    )
    _, skel_res, graph_res = _run_stage123(gray)
    flaking_result = exclude_flaking_regions(skel_res.mask_clean, skel_res.skel_image, skel_res.medial_radius)

    true_flake_mask = np.zeros(gray.shape, dtype=bool)
    rr, cc = disk(flake_center, flake_radius, shape=gray.shape)
    true_flake_mask[rr, cc] = True
    true_flake_area_px2 = int(true_flake_mask.sum())

    # Second, real skeletonize pass on the corrected mask -- same two-pass
    # shape export_crack_stats.py uses -- so the overlay shows the actual
    # post-exclusion skeleton, not the pre-exclusion scout pass.
    _, skel_res2, graph_res2 = _run_stage123(flaking_result.mask_corrected)
    cut_adjacent = cut_adjacent_path_indices(
        skel_res2.skeleton, graph_res2, flaking_result.excluded_mask, reference_width_px=flaking_result.reference_width_px,
    )

    out_path = out_dir / "grid_with_flakes.png"
    render_crack_stats_overlay(
        _to_rgb_uint8(gray), skel_res2.skeleton, graph_res2,
        flaking_result.excluded_mask, cut_adjacent, out_path,
    )
    return {
        "name": "grid_with_flakes",
        "title": "Grid with one circular flaking/delamination patch",
        "image": out_path.name,
        "desc": "A grid junction overrun by a filled disk (bright, exactly like real delamination "
                "under Otsu thresholding) -- the case flaking.py exists for. True flake area is "
                "measured independently (disk pixels alone, no grid overlap) and compared to "
                "flaking.py's own recovered excluded_area_px2.",
        "rows": [
            _row("n candidates found", 1, len(flaking_result.candidates)),
            _row("true flake area (px^2, disk only)", true_flake_area_px2, flaking_result.excluded_area_px2),
            _row("recovery ratio", "1.00", f"{flaking_result.excluded_area_px2 / true_flake_area_px2:.3f}"),
            _row("n edges dropped from length/width stats (cut-adjacent)", "(see overlay, magenta)", len(cut_adjacent)),
        ],
    }


CSS = """
body { font-family: sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
.case { margin: 1.5em 0; padding: 1em 1.2em; border: 1px solid #ddd; border-radius: 8px; }
.case img { max-width: 100%; border: 1px solid #eee; }
table { border-collapse: collapse; margin-top: 0.5em; font-size: 0.9em; }
th, td { border: 1px solid #ddd; padding: 0.3em 0.6em; text-align: left; }
th { background: #f5f5f5; }
.note { color: #555; font-size: 0.9em; }
"""


def render_case_html(case: dict) -> str:
    rows_html = "".join(f"<tr><td>{m}</td><td>{e}</td><td>{ms}</td></tr>" for m, e, ms in case["rows"])
    return f"""
<div class="case">
  <h3>{case['title']}</h3>
  <p class="note">{case['desc']}</p>
  <img src="{case['image']}" alt="{case['title']}">
  <table>
    <tr><th>metric</th><th>expected / ground truth</th><th>measured</th></tr>
    {rows_html}
  </table>
</div>"""


def parse_args():
    p = argparse.ArgumentParser(description="Run the crack_stats-scoped mesh/network synthetic gallery.")
    p.add_argument("--out-dir", type=str, default="outputs/crack_stats_synthetic")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = case_grid_widths(out_dir)
    cases.append(case_wavy_grid(out_dir))
    cases.append(case_hexagonal_grid(out_dir))
    cases.append(case_grid_with_flakes(out_dir))

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>crack_stats: mesh/network synthetic gallery</title>
<style>{CSS}</style></head><body>
<h1>crack_stats: mesh/network synthetic gallery</h1>
<p class="note">Scoped to exactly what scripts/export_crack_stats.py imports (binarize, skeleton,
graph, flaking) -- no junction/curvature/anisotropy layer. Companion to
tests/test_grid_synthetic.py, for visual review of the same cases.</p>
{''.join(render_case_html(c) for c in cases)}
</body></html>
"""
    out_path = out_dir / "report.html"
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote {out_path} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
