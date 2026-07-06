"""Sanity checks for the two summary-plot renderers: both produce a
non-empty, sane-sized image file for a real pipeline result and for the
empty/zero-sample edge case, without crashing.
"""

from PIL import Image

from src.crackgraph.anisotropy import compute_anisotropy
from src.crackgraph.binarize import binarize
from src.crackgraph.curvature import compute_edge_curvature
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.summary_plots import render_curvature_histogram, render_orientation_rose
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
