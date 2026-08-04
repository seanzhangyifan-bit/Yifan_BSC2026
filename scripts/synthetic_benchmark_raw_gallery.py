"""Synthetic-benchmark matrix, step 1: all 9 raw cases + ground truth.

Renders the user's original 9-case matrix (canonical geometries /
structural networks / degradation resilience) as plain grayscale images,
next to each one's own closed-form ground truth where one exists --
computed directly from the generator's construction parameters, not
measured. Deliberately no binarize/skeletonize_and_prune/extract_graph
call anywhere in this script: wiring these through the real pipeline and
comparing measured-vs-expected is a later, separate step, not this one.
The point of this step is purely to eyeball whether the geometry and
proportions look right before anything is wired into the real pipeline --
see the synthetic-benchmark plan.

Cases 7-9 (illumination gradient, JPEG blocking, debris) apply a
composable post-processing pass (src/crackgraph/synthetic_degradation.py)
to a clean base case and show both, with no fabricated ground truth for
the degraded output -- they're lossy/randomized/speculative by
construction (see that module's docstring).

Usage:
    python3 -m scripts.synthetic_benchmark_raw_gallery [--out-dir outputs/synthetic_benchmark_raw]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.crackgraph.synthetic import (
    converging_lines_ground_truth,
    crescent_ground_truth,
    density_gradient_ground_truth,
    generate_converging_lines,
    generate_crescent_scale_pattern,
    generate_density_gradient_field,
    generate_hierarchical_network,
    generate_t_junction,
    generate_tapered_line,
    generate_y_junction,
    hierarchical_network_topology,
    tapered_line_ground_truth,
)
from src.crackgraph.synthetic_degradation import (
    apply_debris,
    apply_illumination_gradient,
    apply_jpeg_blocking,
)


def _row(metric, value):
    return (metric, str(value))


def _render_image(gray, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(gray.shape[1] / 100, gray.shape[0] / 100), dpi=100)
    ax.imshow(gray, cmap="gray", vmin=0, vmax=255)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out_path)
    plt.close(fig)


def case_tapered_line(out_dir: Path) -> dict:
    length, max_t, min_t = 200.0, 16.0, 0.0
    fg_value, tip_value = 230.0, 60.0
    gray = generate_tapered_line(
        length=length, max_thickness=max_t, min_thickness=min_t, fg_value=fg_value, tip_value=tip_value,
    )
    gt = tapered_line_ground_truth(length, max_t, min_t)
    out_path = out_dir / "01_tapered_line.png"
    _render_image(gray, out_path)
    return {
        "name": "tapered_line",
        "title": "1. Tapered line (tip truncation)",
        "image": out_path.name,
        "desc": "A single crack that tapers to a thin, DIM tip at both ends -- fat and bright "
                "(16px, this dataset's real median avg_width_px) at the midpoint, narrowing in "
                "width AND fading in brightness toward each tip (2px, dim), modelling the "
                "partial-volume/PSF-blur effect a real crack tip shows under SEM imaging. Tests "
                "whether a realistic global brightness threshold would truncate the dim tips even "
                "though the geometric taper continues further -- the actual Otsu run is a later, "
                "pipeline-integration step, but the raw pixel values already show the effect.",
        "rows": [
            _row("max_thickness / min_thickness (px)", f"{max_t:.0f} / {min_t:.0f}"),
            _row("fg_value (midpoint) / tip_value (both ends)", f"{fg_value:.0f} / {tip_value:.0f}"),
            _row("length (px)", f"{length:.0f}"),
            _row("width-taper area (px^2, exact)", f"{gt['area_px2']:.1f}"),
            _row("mean width (px, exact)", f"{gt['mean_width_px']:.1f}"),
        ],
    }


def case_t_y_junction(out_dir: Path) -> dict:
    t_img = generate_t_junction()
    y_img = generate_y_junction()
    out_path_a = out_dir / "02a_t_junction.png"
    out_path_b = out_dir / "02b_y_junction.png"
    _render_image(t_img, out_path_a)
    _render_image(y_img, out_path_b)
    return {
        "name": "t_y_junction",
        "title": "2. T / Y-junction",
        "image": out_path_a.name,
        "image_b": out_path_b.name,
        "desc": "Already covered by existing generators (generate_t_junction, generate_y_junction) "
                "and their own tests/validation_gallery.py -- shown "
                "here for completeness against the original 9-case matrix, not as new coverage. "
                "No new generator code and no new ground truth on this page; see "
                "scripts/validation_gallery.py for the actual angle-recovery ground truth these "
                "already carry.",
        "rows": [
            _row("status", "reused from existing generators, not new this step"),
        ],
    }


def case_converging_lines(out_dir: Path) -> dict:
    run_px, thickness, gap_start, gap_end, margin = 250.0, 12, 60.0, 0.0, 25.0
    gray = generate_converging_lines(
        run_px=run_px, thickness=thickness, gap_start_px=gap_start, gap_end_px=gap_end, margin=margin,
    )
    gt = converging_lines_ground_truth(run_px, thickness, gap_start, gap_end, margin)
    out_path = out_dir / "03_converging_lines.png"
    _render_image(gray, out_path)
    return {
        "name": "converging_lines",
        "title": "3. Converging parallel lines (minimum resolvable gap)",
        "image": out_path.name,
        "desc": "Two 12px-thick lines whose gap narrows from 60px to 0px -- the minimum-"
                "resolvable-gap fixture. Nothing in this project's existing generators tests where "
                "two separate cracks stop being separately resolvable and read as one merged shape.",
        "rows": [
            _row("thickness (px)", thickness),
            _row("gap_start_px / gap_end_px", f"{gap_start:.0f} / {gap_end:.0f}"),
            _row("run_px", f"{run_px:.0f}"),
            _row("x_touch_px (exact, gap(x)==thickness)", f"{gt['x_touch_px']:.1f}"),
        ],
    }


def case_hierarchical_network(out_dir: Path) -> dict:
    n_primary_lines, sub_branches_per_primary = 2, 3
    survives = generate_hierarchical_network(sub_branch_length=25.0, sub_branch_thickness=3)
    pruned = generate_hierarchical_network(sub_branch_length=12.0, sub_branch_thickness=3)
    topo = hierarchical_network_topology(n_primary_lines, sub_branches_per_primary)
    out_path_a = out_dir / "04a_hierarchical_network_survives.png"
    out_path_b = out_dir / "04b_hierarchical_network_pruned.png"
    _render_image(survives, out_path_a)
    _render_image(pruned, out_path_b)
    return {
        "name": "hierarchical_network",
        "title": "4. Hierarchical bimodal-width network (primary + sub-branch cracks)",
        "image": out_path_a.name,
        "image_b": out_path_b.name,
        "desc": "A 2x2 primary grid (12px thick) with 3 short 3px-thick sub-branch stubs per "
                "primary line, at two stub lengths straddling skeleton.py's "
                "SPUR_PX_PLACEHOLDER=15px pruning threshold (25px, left -- expected to survive "
                "pruning; 12px, right -- expected to be pruned away). Pre-pruning topology (the "
                "combinatorial ground truth below) is identical for both; whether the stubs "
                "actually survive skeletonize_and_prune is a pipeline-integration question for a "
                "later step.",
        "rows": [
            _row("n_junctions_deg>=4 (primary crossings)", topo["n_junctions_deg_ge4"]),
            _row("n_junctions_deg3 (sub-branch T's, pre-pruning)", topo["n_junctions_deg3"]),
            _row("n_endpoints (pre-pruning)", topo["n_endpoints"]),
            _row("n_edges (pre-pruning)", topo["n_edges"]),
            _row("sub_branch_length: left / right (px)", "25 (expected to survive) / 12 (expected pruned)"),
        ],
    }


def case_crescent_scale_pattern(out_dir: Path) -> dict:
    radius, offset = 70.0, 45.0
    gray = generate_crescent_scale_pattern(radius=radius, offset=offset)
    gt = crescent_ground_truth(radius, offset)
    out_path = out_dir / "05_crescent_scale_pattern.png"
    _render_image(gray, out_path)
    return {
        "name": "crescent_scale_pattern",
        "title": "5. Crescent/lens mesh (fish-scale tiling)",
        "image": out_path.name,
        "desc": "Filled crescent-moon tiles (disk A minus disk B, both radius 70px, centers 45px "
                "apart) tiled on a staggered grid so each crescent's sharp cusps nestle against "
                "neighboring crescents' rounded outer sides -- a fish-scale/roofing-shingle "
                "pattern, filled solid rather than a thin-line outline like every other case here. "
                "That's deliberate: this case tests Otsu's boundary/edge fidelity on a curved 2D "
                "region (perimeter-to-area accuracy), not a 1D crack-line network.",
        "rows": [
            _row("radius (px)", f"{radius:.0f}"),
            _row("offset between disk centers (px)", f"{offset:.0f}"),
            _row("perimeter (px, exact -- always 2*pi*radius, independent of offset)", f"{gt['perimeter_px']:.1f}"),
            _row("area (px^2, exact)", f"{gt['area_px2']:.1f}"),
            _row("cusp-to-cusp chord (px, exact)", f"{gt['cusp_chord_px']:.1f}"),
        ],
    }


def case_density_gradient_field(out_dir: Path) -> dict:
    n_segments_per_zone = (60, 20, 5)
    length_range_px = (30.0, 60.0)
    thickness = 8
    gray = generate_density_gradient_field(
        n_segments_per_zone=n_segments_per_zone, length_range_px=length_range_px, thickness=thickness,
    )
    gt = density_gradient_ground_truth(n_segments_per_zone, length_range_px, thickness)
    out_path = out_dir / "06_density_gradient_field.png"
    _render_image(gray, out_path)
    return {
        "name": "density_gradient_field",
        "title": "6. Non-uniform density field (dense vs. sparse zones)",
        "image": out_path.name,
        "desc": "Independent random line segments placed into 3 column zones at explicit, "
                "different densities (60/20/5 segments) -- tests whether binarize()'s single "
                "global Otsu threshold (and its sanity_band foreground-fraction check) holds up "
                "under strong local density variation within one image. Otsu being global-only is "
                "this pipeline's deliberate design choice, not a bug to discover.",
        "rows": [
            _row("n_segments per zone (left/mid/right)", " / ".join(str(n) for n in n_segments_per_zone)),
            _row("length_range_px", f"{length_range_px[0]:.0f}-{length_range_px[1]:.0f}"),
            _row("thickness (px)", thickness),
            _row(
                "upper-bound area px^2 per zone (no-overlap, exact)",
                " / ".join(f"{a:.0f}" for a in gt["upper_bound_area_px2_per_zone"]),
            ),
        ],
    }


def case_illumination_gradient(out_dir: Path) -> dict:
    base = generate_converging_lines()
    amplitude, direction_deg = 60.0, 0.0
    degraded = apply_illumination_gradient(base, direction_deg=direction_deg, amplitude=amplitude)
    out_path_a = out_dir / "07a_illumination_gradient_clean.png"
    out_path_b = out_dir / "07b_illumination_gradient_degraded.png"
    _render_image(base, out_path_a)
    _render_image(degraded, out_path_b)
    return {
        "name": "illumination_gradient",
        "title": "7. Illumination gradient [speculated]",
        "image": out_path_a.name,
        "image_b": out_path_b.name,
        "desc": "A smooth left-to-right brightness ramp (60 gray levels peak-to-peak) added to "
                "case 3's clean image before binarization would see it -- shown clean (left) vs. "
                "degraded (right). [speculated]: binarize.py's own docstring states these images "
                "have no illumination gradient to compensate for, so this is a worst-case/"
                "precautionary check, not a response to an observed problem. No fabricated ground "
                "truth for the degraded pixel values -- pipeline behavior under this degradation "
                "is a later step.",
        "rows": [
            _row("amplitude (gray levels, peak-to-peak)", f"{amplitude:.0f}"),
            _row("direction_deg", f"{direction_deg:.0f}"),
            _row("base case", "case 3 (converging lines)"),
        ],
    }


def case_jpeg_blocking(out_dir: Path) -> dict:
    base = generate_hierarchical_network(sub_branch_length=25.0)
    quality = 15
    degraded = apply_jpeg_blocking(base, quality=quality)
    out_path_a = out_dir / "08a_jpeg_blocking_clean.png"
    out_path_b = out_dir / "08b_jpeg_blocking_degraded.png"
    _render_image(base, out_path_a)
    _render_image(degraded, out_path_b)
    return {
        "name": "jpeg_blocking",
        "title": "8. Sensor noise (JPEG blocking)",
        "image": out_path_a.name,
        "image_b": out_path_b.name,
        "desc": "A REAL JPEG encode/decode round-trip (Pillow, quality=15) applied to case 4's "
                "clean 'survives pruning' image -- shown clean (left) vs. degraded (right). Closes "
                "a named, already-acknowledged gap: scripts/skeleton_loop_sweep.py:25 states no "
                "synthetic case reproduces JPEG-compression boundary noise. No fabricated ground "
                "truth for the degraded pixel values (lossy by construction) -- pipeline behavior "
                "under this degradation is a later step.",
        "rows": [
            _row("JPEG quality", str(quality)),
            _row("base case", "case 4 (hierarchical network, sub_branch_length=25)"),
        ],
    }


def case_debris(out_dir: Path) -> dict:
    base = generate_hierarchical_network(sub_branch_length=25.0)
    n_specks, radius_range = 40, (1.0, 4.0)
    degraded = apply_debris(base, n_specks=n_specks, speck_radius_range_px=radius_range, rng_seed=0)
    out_path_a = out_dir / "09a_debris_clean.png"
    out_path_b = out_dir / "09b_debris_degraded.png"
    _render_image(base, out_path_a)
    _render_image(degraded, out_path_b)
    return {
        "name": "debris",
        "title": "9. Surface debris / charging [speculated]",
        "image": out_path_a.name,
        "image_b": out_path_b.name,
        "desc": "40 small DARK specks (1-4px radius, well under skeleton.py's "
                "SPUR_PX_PLACEHOLDER=15px) punched into the middle of case 4's already-bright "
                "crack channels -- shown clean (left) vs. degraded (right). Models debris/charging "
                "that interrupts a channel, not new bright material elsewhere -- the "
                "'Channel Fragmentation' failure mode. [speculated]: no evidence of this in the "
                "real dataset either. No fabricated ground truth for the degraded image -- whether "
                "thinning/pruning actually bridges these small interruptions rather than "
                "fragmenting the channel (the falsifiable claim this case sets up) is a "
                "pipeline-integration question for a later step.",
        "rows": [
            _row("n_specks", str(n_specks)),
            _row("speck_radius_range_px", f"{radius_range[0]:.0f}-{radius_range[1]:.0f}"),
            _row("base case", "case 4 (hierarchical network, sub_branch_length=25)"),
        ],
    }


CSS = """
body { font-family: sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.3em; }
.case { margin: 1.5em 0; padding: 1em 1.2em; border: 1px solid #ddd; border-radius: 8px; }
.case img { max-width: 100%; border: 1px solid #eee; margin: 0.3em 0.3em 0.3em 0; }
table { border-collapse: collapse; margin-top: 0.5em; font-size: 0.9em; }
th, td { border: 1px solid #ddd; padding: 0.3em 0.6em; text-align: left; }
th { background: #f5f5f5; }
.note { color: #555; font-size: 0.9em; }
"""


def render_case_html(case: dict) -> str:
    rows_html = "".join(f"<tr><td>{m}</td><td>{v}</td></tr>" for m, v in case["rows"])
    images_html = f'<img src="{case["image"]}" alt="{case["title"]}">'
    if "image_b" in case:
        images_html += f'<img src="{case["image_b"]}" alt="{case["title"]} (second variant)">'
    return f"""
<div class="case">
  <h3>{case['title']}</h3>
  <p class="note">{case['desc']}</p>
  {images_html}
  <table>
    <tr><th>quantity</th><th>ground truth (exact, from construction params)</th></tr>
    {rows_html}
  </table>
</div>"""


def parse_args():
    p = argparse.ArgumentParser(description="Render step-1 raw geometry + ground truth for all 9 synthetic benchmark cases.")
    p.add_argument("--out-dir", type=str, default="outputs/synthetic_benchmark_raw")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = [
        case_tapered_line(out_dir),
        case_t_y_junction(out_dir),
        case_converging_lines(out_dir),
        case_hierarchical_network(out_dir),
        case_crescent_scale_pattern(out_dir),
        case_density_gradient_field(out_dir),
        case_illumination_gradient(out_dir),
        case_jpeg_blocking(out_dir),
        case_debris(out_dir),
    ]

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Synthetic benchmark matrix -- step 1: all 9 raw cases + ground truth</title>
<style>{CSS}</style></head><body>
<h1>Synthetic benchmark matrix -- step 1: all 9 raw cases + ground truth</h1>
<p class="note">No binarize/skeletonize/graph run anywhere on this page -- these are the raw
rasterized generators (cases 7-9 shown clean vs. degraded) next to their own closed-form ground
truth where one exists, for a sanity check on geometry and proportions before anything is wired
into the real pipeline. That wiring (measured-vs-expected via binarize -> skeletonize_and_prune ->
extract_graph) is a later, separate step.</p>
{''.join(render_case_html(c) for c in cases)}
</body></html>
"""
    out_path = out_dir / "report.html"
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote {out_path} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
