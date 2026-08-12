"""Kink-scan correctness checks against synthetics with known geometry:
a bent line with a known interior corner must yield exactly one flag near
that corner; straight geometry must yield none.
"""

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.kinks import find_kinks
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_kinked_line, generate_t_junction


def _run_kink_scan(gray, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3)
    graph_result = extract_graph(skeleton_result.skeleton)
    return find_kinks(skeleton_result.skeleton, graph_result, **kwargs)


def test_kink_detected_at_known_corner():
    # 60-deg turn at the image center. Skeletonization rounds the apex over
    # ~the line thickness, so the measured turn reads a bit under the drawn
    # 60 deg -- tolerance reflects that, it's not estimator slack.
    gray = generate_kinked_line(turn_deg=60.0)
    result = _run_kink_scan(gray)
    assert len(result.kinks) == 1
    kink = result.kinks[0]
    true_corner = (60.0, 60.0)
    assert abs(kink.coord[0] - true_corner[0]) < 6.0
    assert abs(kink.coord[1] - true_corner[1]) < 6.0
    assert abs(kink.turn_angle_deg - 60.0) < 12.0


def test_straight_line_has_no_kinks():
    gray = generate_kinked_line(turn_deg=0.0)
    result = _run_kink_scan(gray)
    assert len(result.kinks) == 0


def test_t_junction_arms_have_no_kinks():
    # Junctions are graph nodes, not edge-interior corners: a clean T must
    # produce zero kink flags on any of its three straight arms.
    gray = generate_t_junction()
    result = _run_kink_scan(gray)
    assert len(result.kinks) == 0
