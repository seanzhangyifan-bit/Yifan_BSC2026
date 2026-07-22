"""Build the schematic-proof + real-example HTML page for this export.

Two independent halves:

1. Synthetic "schematic proof" -- runs two known-ground-truth synthetic
   patterns (a straight line, a T-junction; see `_synthetic.py`) through
   the exact same binarize -> skeletonize -> graph-extract chain
   `export_crack_stats.py` uses, and checks the measured summary numbers
   against hand-computable exact ground truth. Fully reproducible by
   anyone running this script -- no external data required.

2. Real-example panels -- runs 3 real micrographs (already part of this
   project's private raw dataset, spanning sparse/medium/dense crack
   density) through the same chain and shows actual measured numbers.
   NOT reproducible by an external recipient: the raw JPGs are not part
   of this export (see README.md) -- the hardcoded paths in
   `REAL_EXAMPLES` below only resolve on the machine this was built on.
   The already-rendered PNGs and the numbers baked into the HTML are the
   real deliverable; re-running this script elsewhere will still produce
   the (reproducible) schematic half and skip the real half gracefully.

Usage (from within this examples/ folder):
    python3 generate_examples.py
Writes images/*.png and schematic_and_examples.html.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation

THIS_DIR = Path(__file__).resolve().parent
EXPORT_ROOT = THIS_DIR.parent
sys.path.insert(0, str(EXPORT_ROOT))  # so `import crackgraph` resolves
sys.path.insert(0, str(THIS_DIR))  # so `import _synthetic` resolves

from crackgraph.binarize import binarize
from crackgraph.graph import extract_graph
from crackgraph.io_utils import load_image
from crackgraph.skeleton import skeletonize_and_prune
from _synthetic import generate_straight_line, generate_t_junction

IMAGES_DIR = THIS_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Real micrographs this export was demonstrated against -- absolute paths
# into the parent project's private raw-image catalogue, spanning the
# sparse/medium/dense crack-density range already on record for this
# dataset (see docs/crack_stats_schema.md SS7-8). Deliberately NOT bundled
# in this export (see README.md) -- this dict only lets the script
# regenerate these exact panels on a machine that has that private data.
REAL_EXAMPLES = [
    {
        "label": "sparse",
        "path": Path(
            "/home/seanzzz/UNI/crack-project/data/raw/characterization2_ptfe/T5-PTFE_H50_v1_mm000001.jpg"
        ),
        "note": "Lowest crack-area reading in the full 39-row dataset (~0.04%) "
        "-- included to show the method on a near-empty case, not just dense ones.",
    },
    {
        "label": "medium",
        "path": Path("/home/seanzzz/UNI/crack-project/data/raw/T5/T5-M_H190_v1_mm000001.jpg"),
        "note": "This project's own canonical worked example "
        "(docs/crack_stats_schema.md §8) -- ~14.5% crack area, typical mid-range density.",
    },
    {
        "label": "dense",
        "path": Path(
            "/home/seanzzz/UNI/crack-project/data/raw/characterization2_ptfe/T3-PTFE_v1_mm000001.jpg"
        ),
        "note": "~28.7% crack area, essentially fully percolated "
        "(giant_component_fraction > 0.9) -- the dense end of the range.",
    },
]

# Analysis always runs at full resolution; this only controls the display
# size of the saved PNGs. A thin 1px skeleton line naively resampled across
# an ~8x downsample would mostly disappear, so the skeleton is dilated by
# a couple of pixels *before* downsampling (display-only choice, see
# render_panels) -- a deliberately simpler stand-in for the parent
# project's own overlay.py, which instead rescales skeleton *coordinates*
# numerically. That precision isn't needed for this illustrative panel.
DISPLAY_MAX_PX = 900
SKELETON_DILATE_PX = 3


def run_pipeline(gray: np.ndarray):
    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)
    return binarize_result, skeleton_result, graph_result


def summarize(binarize_result, skeleton_result, graph_result, full_h, full_w) -> dict:
    """Same derived quantities `export_crack_stats.py`'s `compute_row`
    emits, computed here directly (not imported) so this script stays
    independent of the entry script's file-glob/argparse machinery."""
    crack_area_px2 = binarize_result.foreground_fraction * full_w * full_h
    total_length_px = float(graph_result.summary["branch_distance"].sum())
    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
    avg_edge_length_px = (
        total_length_px / graph_result.n_edges if graph_result.n_edges > 0 else float("nan")
    )
    return {
        "crack_area_px2": crack_area_px2,
        "avg_width_px": avg_width_px,
        "avg_edge_length_px": avg_edge_length_px,
        "n_edges": graph_result.n_edges,
        "n_endpoints": graph_result.n_endpoints,
        "n_junctions_deg3": graph_result.n_junctions_deg3,
    }


def _resize_rgb(rgb_uint8: np.ndarray, max_px: int, resample) -> np.ndarray:
    h, w = rgb_uint8.shape[:2]
    if max(h, w) <= max_px:
        return rgb_uint8
    scale = max_px / max(h, w)
    new_size = (max(int(round(w * scale)), 1), max(int(round(h * scale)), 1))
    im = Image.fromarray(rgb_uint8)
    return np.asarray(im.resize(new_size, resample))


def render_panels(
    raw_rgb: np.ndarray,
    mask: np.ndarray,
    skel_image: np.ndarray,
    out_path: Path,
    title_prefix: str = "",
) -> None:
    """3-panel figure: input / binary mask / skeleton overlay, all built at
    full resolution then downsampled together for display (see
    DISPLAY_MAX_PX / SKELETON_DILATE_PX docstring above)."""
    mask_rgb = np.zeros((*mask.shape, 3), dtype=np.uint8)
    mask_rgb[mask] = (235, 235, 235)

    skel_wide = binary_dilation(skel_image, iterations=SKELETON_DILATE_PX) if skel_image.any() else skel_image
    overlay_rgb = np.zeros((*mask.shape, 3), dtype=np.uint8)
    overlay_rgb[mask] = (55, 55, 55)
    overlay_rgb[skel_wide] = (0, 230, 90)

    raw_disp = _resize_rgb(raw_rgb, DISPLAY_MAX_PX, Image.LANCZOS)
    mask_disp = _resize_rgb(mask_rgb, DISPLAY_MAX_PX, Image.LANCZOS)
    overlay_disp = _resize_rgb(overlay_rgb, DISPLAY_MAX_PX, Image.LANCZOS)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    axes[0].imshow(raw_disp)
    axes[0].set_title(f"{title_prefix}input")
    axes[1].imshow(mask_disp)
    axes[1].set_title("binary mask (stage 1)")
    axes[2].imshow(overlay_disp)
    axes[2].set_title("skeleton (stage 2–3)")
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def build_schematic_cases() -> list[dict]:
    cases = []

    # Case 1: straight line, known length/thickness, no junction.
    length, thickness, size = 72.0, 7, 120
    gray = generate_straight_line(size=size, thickness=thickness, length=length)
    binarize_result, skeleton_result, graph_result = run_pipeline(gray)
    stats = summarize(binarize_result, skeleton_result, graph_result, size, size)
    expected_area = length * thickness
    gray_rgb = np.stack([gray.astype(np.uint8)] * 3, axis=-1)
    render_panels(gray_rgb, binarize_result.mask, skeleton_result.skel_image,
                  IMAGES_DIR / "schematic_straight_line.png")
    cases.append({
        "title": "Schematic 1: straight line, known length × thickness",
        "image": "images/schematic_straight_line.png",
        "desc": f"A single {length:.0f}×{thickness}px arm, no junction. "
                "Ground truth is exact up to end-cap/pixel-discretization rounding: "
                "one skeleton edge, filled area ≈ length × thickness.",
        "rows": [
            ("n_edges", "1 (exactly)", str(stats["n_edges"])),
            ("crack_area_px2", f"{expected_area:.0f}", f"{stats['crack_area_px2']:.1f}"),
            ("avg_width_px", f"{thickness} (thickness)", f"{stats['avg_width_px']:.2f}"),
            ("avg_edge_length_px", f"≈{length:.0f} (length)", f"{stats['avg_edge_length_px']:.2f}"),
        ],
    })

    # Case 2: T-junction, known topology (3 edges / 1 junction / 3 endpoints).
    size2, thickness2, margin2 = 120, 5, 10
    gray2 = generate_t_junction(size=size2, thickness=thickness2, margin=margin2)
    binarize_result2, skeleton_result2, graph_result2 = run_pipeline(gray2)
    stats2 = summarize(binarize_result2, skeleton_result2, graph_result2, size2, size2)
    gray2_rgb = np.stack([gray2.astype(np.uint8)] * 3, axis=-1)
    render_panels(gray2_rgb, binarize_result2.mask, skeleton_result2.skel_image,
                  IMAGES_DIR / "schematic_t_junction.png")
    cases.append({
        "title": "Schematic 2: T-junction, known topology",
        "image": "images/schematic_t_junction.png",
        "desc": "One straight host line with a second arm meeting it at 90° "
                "from the midpoint (does not cross through). Ground truth: "
                "exactly 3 skeleton edges (host-left, host-right, abutter), "
                "1 degree-3 junction node, 3 endpoints, one connected piece. "
                "(This export computes edge count/topology only — the T-vs-Y "
                "angle classification itself is a separate, unexported part of "
                "the parent project; see README.md.)",
        "rows": [
            ("n_edges", "3 (exactly)", str(stats2["n_edges"])),
            ("n_junctions_deg3", "1 (exactly)", str(stats2["n_junctions_deg3"])),
            ("n_endpoints", "3 (exactly)", str(stats2["n_endpoints"])),
        ],
    })
    return cases


def build_real_cases() -> list[dict]:
    cases = []
    for spec in REAL_EXAMPLES:
        if not spec["path"].exists():
            print(f"[skip] {spec['path']} not found on this machine -- real-example panel not regenerated")
            continue
        gray, rgb = load_image(spec["path"])
        full_h, full_w = gray.shape
        binarize_result, skeleton_result, graph_result = run_pipeline(gray)
        stats = summarize(binarize_result, skeleton_result, graph_result, full_h, full_w)
        crack_area_pct = binarize_result.foreground_fraction * 100

        out_name = f"real_{spec['label']}.png"
        render_panels(rgb, binarize_result.mask, skeleton_result.skel_image,
                      IMAGES_DIR / out_name, title_prefix=f"{spec['label']} — ")
        cases.append({
            "title": f"Real example: {spec['label']} ({spec['path'].name})",
            "image": f"images/{out_name}",
            "desc": spec["note"],
            "rows": [
                ("image size", "—", f"{full_w}×{full_h} px"),
                ("crack_area_pct", "— (real data, no ground truth)", f"{crack_area_pct:.3f}%"),
                ("n_edges", "—", str(stats["n_edges"])),
                ("avg_width_px", "—", f"{stats['avg_width_px']:.2f}"),
                ("avg_edge_length_px", "—", f"{stats['avg_edge_length_px']:.2f}"),
            ],
        })
    return cases


CSS = """
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin: 2rem auto; max-width: 980px; color: #1a1a1a; line-height: 1.5; padding: 0 1rem; }
h1 { font-size: 1.6rem; }
h2 { font-size: 1.2rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }
.case { border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; margin: 1.25rem 0; }
.case img { max-width: 100%; border: 1px solid #eee; border-radius: 4px; }
table { border-collapse: collapse; margin-top: 0.75rem; font-size: 0.92rem; }
th, td { border: 1px solid #ddd; padding: 0.35rem 0.7rem; text-align: left; }
th { background: #f5f5f5; }
.note { color: #555; font-size: 0.9rem; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
.badge.synthetic { background: #e6f4ea; color: #1e7e34; }
.badge.real { background: #eaf1fb; color: #1a56a8; }
"""


def render_case_html(case: dict, badge: str) -> str:
    rows_html = "\n".join(
        f"<tr><td>{k}</td><td>{exp}</td><td>{meas}</td></tr>" for k, exp, meas in case["rows"]
    )
    return f"""
<div class="case">
  <h3>{case['title']} <span class="badge {badge}">{badge}</span></h3>
  <p class="note">{case['desc']}</p>
  <img src="{case['image']}" alt="{case['title']}">
  <table>
    <tr><th>quantity</th><th>expected / ground truth</th><th>measured</th></tr>
    {rows_html}
  </table>
</div>
"""


def main():
    schematic_cases = build_schematic_cases()
    real_cases = build_real_cases()

    real_html = (
        "".join(render_case_html(c, "real") for c in real_cases)
        if real_cases
        else '<p class="note">No real-example panels were regenerated on this run '
        "(private raw dataset not found at the hardcoded paths in this script — "
        "expected, see README.md).</p>"
    )

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>crack_stats: method schematic + real examples</title>
<style>{CSS}</style></head><body>
<h1>crack_stats: method schematic + real examples</h1>
<p>Two independent halves. The <b>schematic</b> cases run known-ground-truth
synthetic patterns through the exact binarize &rarr; skeletonize &rarr;
graph-extract chain <code>export_crack_stats.py</code> uses, and check the
measured numbers against hand-computable exact answers &mdash; this is the
proof that the pipeline measures what it claims to measure, fully
reproducible from <code>examples/generate_examples.py</code> with no
external data. The <b>real</b> cases show the same pipeline on actual
micrographs from this project's private raw dataset (not bundled in this
export &mdash; see README.md); the numbers shown are the pipeline's actual
output on real data, included for illustration, not independently
re-verifiable without that dataset.</p>

<h2>Schematic proof (synthetic, reproducible)</h2>
{''.join(render_case_html(c, "synthetic") for c in schematic_cases)}

<h2>Real examples (sparse / medium / dense)</h2>
{real_html}

</body></html>
"""
    out_path = THIS_DIR / "schematic_and_examples.html"
    out_path.write_text(body, encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Wrote {len(schematic_cases)} schematic + {len(real_cases)} real-example panels to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
