"""A fixed battery of synthetic test cases with known ground truth, run
through the real measurement pipeline, for visual review rather than a bare
pytest pass/fail.

Every numeric tolerance used for the PASS/FAIL verdicts here already exists
as an assertion in the corresponding `tests/test_*.py` file; this module
does not invent new tolerances, it packages the same checks (plus the
synthetic image and the pipeline's own overlay/rose rendering) into a
`ValidationCaseResult` that `validation_report.py` can render as one card in
a browsable page. Constants are duplicated (not imported) from the test
files with a cross-reference comment, since tests are not a dependency of
`src/` -- keep them in sync by hand if a test's tolerance changes.

Ground truth for each case lives in the same generator arguments passed to
synthetic.py (angle_deg, radius, turn_deg, bearings_deg, ...) -- mirroring
every existing pytest file, `synthetic.py` itself returns only the image,
not a bundled expected-value record.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .anisotropy import compute_anisotropy
from .binarize import binarize
from .curvature import compute_edge_curvature
from .graph import extract_graph
from .overlay import render_overlay
from .skeleton import skeletonize_and_prune
from .summary_plots import render_orientation_rose
from .synthetic import (
    generate_curved_t_junction,
    generate_oriented_segment_field,
    generate_t_junction,
)

# -- Tolerances, mirrored from the existing pytest suite --------------------
STRAIGHT_TORTUOSITY_MAX = 1.02  # tests/test_curvature.py::STRAIGHT_TORTUOSITY_MAX
STRAIGHT_MEAN_CURVATURE_MAX_PX_INV = 0.002  # tests/test_curvature.py::STRAIGHT_MEAN_CURVATURE_MAX_PX_INV
CURVATURE_RECOVERY_REL_TOL = 0.25  # tests/test_curvature.py::CURVATURE_RECOVERY_REL_TOL
TORTUOSITY_RECOVERY_REL_TOL = 0.10  # tests/test_curvature.py::TORTUOSITY_RECOVERY_REL_TOL
ANISOTROPY_LOW_TOL = 0.15  # tests/test_anisotropy.py::ANISOTROPY_LOW_TOL
ANISOTROPY_HIGH_MIN = 0.8  # tests/test_anisotropy.py::ANISOTROPY_HIGH_MIN
CIRCULAR_BEARING_TOL_DEG = 10.0  # tests/test_anisotropy.py::CIRCULAR_BEARING_TOL_DEG


@dataclass
class ValidationCaseResult:
    name: str
    method: str  # "curvature" | "anisotropy" -- report section grouping
    description: str
    image_relpath: str  # relative to the report's own directory
    rows: list[tuple[str, str, str, bool]]  # (metric, expected, measured, passed)
    passed: bool  # all(row.passed)


def _axial_diff_deg(a: float, b: float) -> float:
    """Smallest difference between two axial angles (period 180 deg), as in
    tests/test_anisotropy.py::_circular_diff_deg."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _row(metric: str, expected: str, measured: str, passed: bool) -> tuple[str, str, str, bool]:
    return (metric, expected, measured, passed)


def _to_rgb_uint8(gray: np.ndarray) -> np.ndarray:
    """Synthetic images are single-channel float64 (fg/bg placeholder
    values, see synthetic.py); render_overlay expects a displayable RGB
    array, same as a loaded micrograph. Pure display conversion, kept here
    rather than in synthetic.py, which has no image-format concerns of its
    own -- its generators are consumed as arrays, not files."""
    lo, hi = float(gray.min()), float(gray.max())
    norm = np.zeros_like(gray) if hi - lo < 1e-9 else (gray - lo) / (hi - lo)
    u8 = (norm * 255).astype(np.uint8)
    return np.stack([u8, u8, u8], axis=-1)


def _run_stage123(gray: np.ndarray, spur_px: float = 3):
    """Stage 1-3 glue, identical to every existing pytest file's
    _run_pipeline/_run helper."""
    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    return skeleton_result, graph_result


def _within(expected: float, measured: float, tol: float) -> bool:
    return abs(expected - measured) < tol


def _within_rel(expected: float, measured: float, rel_tol: float) -> bool:
    return abs(expected - measured) / expected < rel_tol


# -- Curvature / tortuosity cases ----------------------------------------------


def case_curvature_straight_line(out_dir: Path) -> ValidationCaseResult:
    name = "curvature_straight_line"
    gray = generate_t_junction(angle_deg=90.0)
    skel_res, graph_res = _run_stage123(gray)
    curvature_res = compute_edge_curvature(skel_res.skeleton, graph_res)
    out_path = out_dir / f"{name}.png"
    render_overlay(_to_rgb_uint8(gray), skel_res.skeleton, graph_res, out_path)

    rows: list[tuple[str, str, str, bool]] = []
    for edge in curvature_res.edges:
        tort_ok = edge.tortuosity is not None and edge.tortuosity < STRAIGHT_TORTUOSITY_MAX
        rows.append(_row(f"edge {edge.path_index} tortuosity", f"< {STRAIGHT_TORTUOSITY_MAX}", f"{edge.tortuosity:.3f}" if edge.tortuosity is not None else "None", tort_ok))
        if edge.mean_abs_curvature_px_inv is not None:
            curv_ok = edge.mean_abs_curvature_px_inv < STRAIGHT_MEAN_CURVATURE_MAX_PX_INV
            rows.append(_row(f"edge {edge.path_index} mean|κ| (1/px)", f"< {STRAIGHT_MEAN_CURVATURE_MAX_PX_INV}", f"{edge.mean_abs_curvature_px_inv:.4f}", curv_ok))

    return ValidationCaseResult(
        name, "curvature",
        "All 3 arms of a straight T-shaped crack meeting — tortuosity should read near 1.0 and mean curvature near 0 (no drawn curvature).",
        out_path.name, rows, all(r[3] for r in rows),
    )


def case_curvature_arc(out_dir: Path) -> ValidationCaseResult:
    name = "curvature_arc"
    radius = 30.0
    arc_half_angle_deg = 75.0
    gray = generate_curved_t_junction(radius=radius, arc_half_angle_deg=arc_half_angle_deg)
    skel_res, graph_res = _run_stage123(gray)
    curvature_res = compute_edge_curvature(skel_res.skeleton, graph_res)
    out_path = out_dir / f"{name}.png"
    render_overlay(_to_rgb_uint8(gray), skel_res.skeleton, graph_res, out_path)

    true_kappa = 1.0 / radius
    phi = math.radians(arc_half_angle_deg)
    true_tortuosity = phi / (2.0 * math.sin(phi / 2.0))

    curved_edges = [e for e in curvature_res.edges if e.tortuosity is not None and e.tortuosity > 1.02]
    rows: list[tuple[str, str, str, bool]] = [
        _row("n curved (host) edges found", "2", str(len(curved_edges)), len(curved_edges) == 2)
    ]
    for edge in curved_edges:
        if edge.mean_abs_curvature_px_inv is not None:
            kappa_ok = _within_rel(true_kappa, edge.mean_abs_curvature_px_inv, CURVATURE_RECOVERY_REL_TOL)
            rows.append(_row(f"edge {edge.path_index} mean|κ| (1/px)", f"{true_kappa:.4f} (=1/radius)", f"{edge.mean_abs_curvature_px_inv:.4f}", kappa_ok))
        if edge.tortuosity is not None:
            tort_ok = _within_rel(true_tortuosity, edge.tortuosity, TORTUOSITY_RECOVERY_REL_TOL)
            rows.append(_row(f"edge {edge.path_index} tortuosity", f"{true_tortuosity:.4f} (closed-form arc/chord)", f"{edge.tortuosity:.4f}", tort_ok))

    return ValidationCaseResult(
        name, "curvature",
        f"Circular-arc host, radius={radius:.0f}px — closed-form tortuosity and curvature=1/radius recovery.",
        out_path.name, rows, all(r[3] for r in rows),
    )


# -- Anisotropy cases -----------------------------------------------------------


def case_anisotropy_aligned(out_dir: Path) -> ValidationCaseResult:
    name = "anisotropy_aligned"
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=60, rng_seed=1)
    skel_res, graph_res = _run_stage123(gray)
    anisotropy_res = compute_anisotropy(skel_res.skeleton, graph_res)
    out_path = out_dir / f"{name}.png"
    render_orientation_rose(anisotropy_res, out_path)

    rows = [
        _row("anisotropy index A", f"> {ANISOTROPY_HIGH_MIN}", f"{anisotropy_res.anisotropy_index:.3f}", anisotropy_res.anisotropy_index > ANISOTROPY_HIGH_MIN),
        _row(
            "dominant bearing (deg)",
            f"0.0 ± {CIRCULAR_BEARING_TOL_DEG:.0f} (axial)",
            f"{anisotropy_res.dominant_bearing_deg:.1f}",
            _axial_diff_deg(anisotropy_res.dominant_bearing_deg, 0.0) < CIRCULAR_BEARING_TOL_DEG,
        ),
    ]
    return ValidationCaseResult(
        name, "anisotropy",
        "60 independent segments, all at bearing 0° (+jitter) — a fully aligned 'rectilinear' field, known high anisotropy.",
        out_path.name, rows, all(r[3] for r in rows),
    )


def case_anisotropy_isotropic(out_dir: Path) -> ValidationCaseResult:
    name = "anisotropy_isotropic"
    gray = generate_oriented_segment_field(bearings_deg=None, n_segments=60, rng_seed=2)
    skel_res, graph_res = _run_stage123(gray)
    anisotropy_res = compute_anisotropy(skel_res.skeleton, graph_res)
    out_path = out_dir / f"{name}.png"
    render_orientation_rose(anisotropy_res, out_path)

    rows = [
        _row("anisotropy index A", f"< {ANISOTROPY_LOW_TOL}", f"{anisotropy_res.anisotropy_index:.3f}", anisotropy_res.anisotropy_index < ANISOTROPY_LOW_TOL),
    ]
    return ValidationCaseResult(
        name, "anisotropy",
        "60 independent segments at uniformly random bearings — a mudcrack-like isotropic field, known low anisotropy.",
        out_path.name, rows, all(r[3] for r in rows),
    )


def case_anisotropy_orthogonal_blind_spot(out_dir: Path) -> ValidationCaseResult:
    name = "anisotropy_orthogonal_blind_spot"
    gray = generate_oriented_segment_field(bearings_deg=[0.0, 90.0], bearing_weights=[0.5, 0.5], n_segments=80, rng_seed=3)
    skel_res, graph_res = _run_stage123(gray)
    anisotropy_res = compute_anisotropy(skel_res.skeleton, graph_res)
    out_path = out_dir / f"{name}.png"
    render_orientation_rose(anisotropy_res, out_path)

    counts = anisotropy_res.histogram_weighted_counts
    top_two = np.argsort(counts)[-2:]
    total = counts.sum()
    peaks_separated = (
        counts[top_two[0]] > 0.1 * total
        and counts[top_two[1]] > 0.1 * total
        and abs(int(top_two[0]) - int(top_two[1])) >= 5
    )

    rows = [
        _row(
            "anisotropy index A (documented 2nd-order-tensor blind spot)",
            f"≈ 0 (< {ANISOTROPY_LOW_TOL})",
            f"{anisotropy_res.anisotropy_index:.3f}",
            anisotropy_res.anisotropy_index < ANISOTROPY_LOW_TOL,
        ),
        _row("rose histogram shows 2 separated peaks (reveals the blind spot)", "True", str(peaks_separated), peaks_separated),
    ]
    return ValidationCaseResult(
        name, "anisotropy",
        "Equal-weight orthogonal grid (50% at 0°, 50% at 90°) — the scalar index reads isotropic (A≈0, a known limitation of a 2nd-order orientation tensor), but the rose histogram must still show two separated peaks.",
        out_path.name, rows, all(r[3] for r in rows),
    )


ALL_CASES = [
    case_curvature_straight_line,
    case_curvature_arc,
    case_anisotropy_aligned,
    case_anisotropy_isotropic,
    case_anisotropy_orthogonal_blind_spot,
]


def run_all_cases(out_dir: Path) -> list[ValidationCaseResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [case_fn(out_dir) for case_fn in ALL_CASES]
