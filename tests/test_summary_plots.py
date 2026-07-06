"""Sanity checks for the two summary-plot renderers: both produce a
non-empty, sane-sized image file for a real pipeline result and for the
empty/zero-sample edge case, without crashing.
"""

import numpy as np
import pytest
from PIL import Image

from src.crackgraph.anisotropy import compute_anisotropy
from src.crackgraph.binarize import binarize
from src.crackgraph.curvature import compute_edge_curvature
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.summary_plots import (
    render_curvature_histogram,
    render_orientation_rose,
    render_overview_figure,
)
from src.crackgraph.synthetic import generate_curved_t_junction, generate_oriented_segment_field

MIN_PLOT_DIM_PX = 50


def _run_curvature_and_anisotropy(gray, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    graph_result = extract_graph(skeleton_result.skeleton)
    curvature_result = compute_edge_curvature(skeleton_result.skeleton, graph_result)
    anisotropy_result = compute_anisotropy(skeleton_result.skeleton, graph_result)
    return curvature_result, anisotropy_result


def test_orientation_rose_renders_for_real_pipeline_result(tmp_path):
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=40, rng_seed=1)
    _, anisotropy_result = _run_curvature_and_anisotropy(gray)
    out_path = tmp_path / "rose.png"

    render_orientation_rose(anisotropy_result, out_path)

    assert out_path.exists()
    img = Image.open(out_path)
    assert img.size[0] > MIN_PLOT_DIM_PX
    assert img.size[1] > MIN_PLOT_DIM_PX


def test_curvature_histogram_renders_for_real_pipeline_result(tmp_path):
    gray = generate_curved_t_junction()
    curvature_result, _ = _run_curvature_and_anisotropy(gray)
    out_path = tmp_path / "hist.png"

    render_curvature_histogram(curvature_result, out_path)

    assert out_path.exists()
    img = Image.open(out_path)
    assert img.size[0] > MIN_PLOT_DIM_PX
    assert img.size[1] > MIN_PLOT_DIM_PX


def test_orientation_rose_handles_zero_samples(tmp_path):
    # compute_anisotropy's own empty-graph branch: n_samples=0, all-zero
    # histogram counts. Must render an (empty) rose, not crash.
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=40, rng_seed=1)
    _, anisotropy_result = _run_curvature_and_anisotropy(gray)
    anisotropy_result.histogram_weighted_counts = anisotropy_result.histogram_weighted_counts * 0.0
    anisotropy_result.n_samples = 0

    out_path = tmp_path / "empty_rose.png"
    render_orientation_rose(anisotropy_result, out_path)

    assert out_path.exists()


def test_curvature_histogram_handles_no_edges(tmp_path):
    gray = generate_curved_t_junction()
    curvature_result, _ = _run_curvature_and_anisotropy(gray)
    curvature_result.edges = []

    out_path = tmp_path / "empty_hist.png"
    render_curvature_histogram(curvature_result, out_path)

    assert out_path.exists()


def _synthetic_rgb(gray):
    return np.stack([gray, gray, gray], axis=-1).astype("uint8")


def test_overview_figure_renders_four_quadrants_plus_whole_image(tmp_path):
    gray_a = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=40, rng_seed=1)
    gray_b = generate_curved_t_junction()
    curv_a, aniso_a = _run_curvature_and_anisotropy(gray_a)
    curv_b, aniso_b = _run_curvature_and_anisotropy(gray_b)

    sections = [
        ("section r0c0", aniso_a, curv_a),
        ("section r0c1", aniso_b, curv_b),
        ("section r1c0", aniso_a, curv_a),
        ("section r1c1", aniso_b, curv_b),
    ]
    whole_image_result = ("whole image", aniso_a, curv_a)
    out_path = tmp_path / "overview.png"

    render_overview_figure(sections, _synthetic_rgb(gray_a), whole_image_result, out_path)

    assert out_path.exists()
    img = Image.open(out_path)
    assert img.size[0] > MIN_PLOT_DIM_PX
    assert img.size[1] > MIN_PLOT_DIM_PX


def test_overview_figure_handles_quadrant_with_no_data(tmp_path):
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=40, rng_seed=1)
    curv, aniso = _run_curvature_and_anisotropy(gray)

    empty_curv, empty_aniso = _run_curvature_and_anisotropy(gray)
    empty_curv.edges = []
    empty_aniso.histogram_weighted_counts = empty_aniso.histogram_weighted_counts * 0.0
    empty_aniso.n_samples = 0

    sections = [
        ("section r0c0", empty_aniso, empty_curv),
        ("section r0c1", aniso, curv),
        ("section r1c0", aniso, curv),
        ("section r1c1", aniso, curv),
    ]
    whole_image_result = ("whole image", aniso, curv)
    out_path = tmp_path / "overview_partial_no_data.png"

    render_overview_figure(sections, _synthetic_rgb(gray), whole_image_result, out_path)

    assert out_path.exists()


def test_overview_figure_requires_exactly_four_sections(tmp_path):
    gray = generate_oriented_segment_field(bearings_deg=[0.0], n_segments=40, rng_seed=1)
    curv, aniso = _run_curvature_and_anisotropy(gray)
    whole_image_result = ("whole image", aniso, curv)

    with pytest.raises(AssertionError):
        render_overview_figure(
            [("section r0c0", aniso, curv)], _synthetic_rgb(gray), whole_image_result, tmp_path / "bad.png"
        )
