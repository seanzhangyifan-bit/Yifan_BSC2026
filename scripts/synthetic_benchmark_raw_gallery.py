"""Synthetic-benchmark matrix, step 1: raw geometry + ground truth only.

Renders the 5 new generators added in src/crackgraph/synthetic.py
(generate_tapered_line, generate_converging_lines,
generate_hierarchical_network, generate_crescent_mesh,
generate_density_gradient_field) as plain grayscale images, next to each
one's own closed-form ground truth -- computed directly from the
generator's construction parameters, not measured. Deliberately no
binarize/skeletonize_and_prune/extract_graph call anywhere in this script:
wiring these through the real pipeline and comparing measured-vs-expected
is a later, separate step, not this one. The point of this step is purely
to eyeball whether the geometry and proportions look right before anything
is wired into the real pipeline -- see the synthetic-benchmark plan.

Usage:
    python3 -m scripts.synthetic_benchmark_raw_gallery [--out-dir outputs/synthetic_benchmark_raw]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.crackgraph.synthetic import (
    arc_tortuosity_ground_truth,
    converging_lines_ground_truth,
    density_gradient_ground_truth,
    generate_converging_lines,
    generate_crescent_mesh,
    generate_density_gradient_field,
    generate_hierarchical_network,
    generate_tapered_line,
    hierarchical_network_topology,
    tapered_line_ground_truth,
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
    length, t_start, t_end = 200.0, 16.0, 2.0
    gray = generate_tapered_line(length=length, thickness_start=t_start, thickness_end=t_end)
    gt = tapered_line_ground_truth(length, t_start, t_end)
    out_path = out_dir / "tapered_line.png"
    _render_image(gray, out_path)
    return {
        "name": "tapered_line",
        "title": "Tapered line (tip truncation)",
        "image": out_path.name,
        "desc": "A single crack tapering linearly from 16px (this dataset's real median "
                "avg_width_px) down to a 2px tip -- tests whether the pipeline keeps tracking a "
                "genuine physical tip all the way down, rather than dropping the last few, "
                "faint-in-area-terms pixels. No junction, one skeleton path.",
        "rows": [
            _row("thickness_start / thickness_end (px)", f"{t_start:.0f} / {t_end:.0f}"),
            _row("length (px)", f"{length:.0f}"),
            _row("trapezoid area (px^2, exact)", f"{gt['area_px2']:.1f}"),
            _row("mean width (px, exact)", f"{gt['mean_width_px']:.1f}"),
        ],
    }


def case_converging_lines(out_dir: Path) -> dict:
    run_px, thickness, gap_start, gap_end, margin = 250.0, 12, 60.0, 0.0, 25.0
    gray = generate_converging_lines(
        run_px=run_px, thickness=thickness, gap_start_px=gap_start, gap_end_px=gap_end, margin=margin,
    )
    gt = converging_lines_ground_truth(run_px, thickness, gap_start, gap_end, margin)
    out_path = out_dir / "converging_lines.png"
    _render_image(gray, out_path)
    return {
        "name": "converging_lines",
        "title": "Converging parallel lines (minimum resolvable gap)",
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
    out_path_a = out_dir / "hierarchical_network_survives.png"
    out_path_b = out_dir / "hierarchical_network_pruned.png"
    _render_image(survives, out_path_a)
    _render_image(pruned, out_path_b)
    return {
        "name": "hierarchical_network",
        "title": "Hierarchical bimodal-width network (primary + sub-branch cracks)",
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


def case_crescent_mesh(out_dir: Path) -> dict:
    arc_half_angle_deg = 40.0
    gray = generate_crescent_mesh(arc_half_angle_deg=arc_half_angle_deg)
    tortuosity = arc_tortuosity_ground_truth(arc_half_angle_deg)
    out_path = out_dir / "crescent_mesh.png"
    _render_image(gray, out_path)
    return {
        "name": "crescent_mesh",
        "title": "Crescent/arc mesh at network scale",
        "image": out_path.name,
        "desc": "3 stacked circular-arc bands (radius=250px, +/-40deg half-angle) crossed by 2 "
                "straight crossbars -- the network-scale generalization of "
                "generate_curved_t_junction's single arc, needed because the curvature/tortuosity "
                "chronometer has only ever been checked on one isolated junction so far.",
        "rows": [
            _row("radius (px)", "250"),
            _row("arc_half_angle_deg", f"{arc_half_angle_deg:.0f}"),
            _row("full-arc tortuosity = arc/chord (exact)", f"{tortuosity:.4f}"),
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
    out_path = out_dir / "density_gradient_field.png"
    _render_image(gray, out_path)
    return {
        "name": "density_gradient_field",
        "title": "Non-uniform density field (dense vs. sparse zones)",
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
        images_html += f'<img src="{case["image_b"]}" alt="{case["title"]} (pruned variant)">'
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
    p = argparse.ArgumentParser(description="Render step-1 raw geometry + ground truth for the synthetic benchmark matrix.")
    p.add_argument("--out-dir", type=str, default="outputs/synthetic_benchmark_raw")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = [
        case_tapered_line(out_dir),
        case_converging_lines(out_dir),
        case_hierarchical_network(out_dir),
        case_crescent_mesh(out_dir),
        case_density_gradient_field(out_dir),
    ]

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Synthetic benchmark matrix -- step 1: raw geometry + ground truth</title>
<style>{CSS}</style></head><body>
<h1>Synthetic benchmark matrix -- step 1: raw geometry + ground truth</h1>
<p class="note">No binarize/skeletonize/graph run anywhere on this page -- these are the raw
rasterized generators next to their own closed-form ground truth, for a sanity check on geometry
and proportions before anything is wired into the real pipeline. That wiring (measured-vs-expected
via binarize -> skeletonize_and_prune -> extract_graph) is a later, separate step.</p>
{''.join(render_case_html(c) for c in cases)}
</body></html>
"""
    out_path = out_dir / "report.html"
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote {out_path} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
