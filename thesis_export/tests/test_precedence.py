"""Stage 5 (first pass) correctness: does build_precedence_graph correctly
union the two stage-4 classifiers into provenance-tagged arcs, and does it
correctly characterize (not resolve) cycles via condensation?

Most tests here hand-construct JunctionClassification/CornerCrossCheck
fixtures directly rather than running the full image pipeline (the pattern
used in test_junction_angle.py/test_corners.py) -- the merge/conflict/cycle
logic tested here is pure graph-and-provenance logic, independent of image
geometry, and a genuine abutter-identity *conflict* between two methods
cannot be produced by jittering a single real synthetic junction (a T's
bearings admit exactly one valid host-pair assignment; disagreement
requires the two methods to measure genuinely different bearings). A couple
of integration tests at the top confirm the real pipeline wiring works.
"""

import networkx as nx

from src.crackgraph.binarize import binarize
from src.crackgraph.corners import CornerCrossCheck, cross_check_junctions, find_background_contours
from src.crackgraph.graph import extract_graph
from src.crackgraph.junctions import EdgeDirection, JunctionAnalysisResult, JunctionClassification, classify_junctions
from src.crackgraph.precedence import _compute_generations, build_precedence_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_t_junction, generate_y_junction

TOL = dict(y_angle_tol_deg=15.0, t_straight_tol_deg=20.0, t_right_tol_deg=20.0)


def _run_real_pipeline(gray, spur_px=3):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    junction_result = classify_junctions(skeleton_result.skeleton, graph_result)
    contours = find_background_contours(skeleton_result.mask_clean)
    cross_check = cross_check_junctions(junction_result, contours, **TOL)
    return junction_result, cross_check


def test_real_t_junction_produces_agreeing_arcs_and_generations():
    gray = generate_t_junction(angle_deg=90.0)
    junction_result, cross_check = _run_real_pipeline(gray)
    result = build_precedence_graph(junction_result, cross_check, **TOL)

    assert len(result.arcs) == 2
    assert all(a.methods_agree for a in result.arcs)
    assert all(a.supporting_methods == ("tangent_fit", "corner_cross_check") for a in result.arcs)

    jc = junction_result.classifications[0]
    assert {a.host_path_index for a in result.arcs} == set(jc.host_path_indices)
    assert {a.abutter_path_index for a in result.arcs} == {jc.abutter_path_index}

    assert result.nontrivial_sccs == []
    # host precedes abutter (the host was already there; the abutter
    # arrived later and stopped against it -- see precedence.py docstring).
    assert result.generation[jc.abutter_path_index] == 1
    for host in jc.host_path_indices:
        assert result.generation[host] == 0


def test_real_y_junction_produces_no_arcs():
    gray = generate_y_junction(bearings_deg=(90.0, 210.0, 330.0))
    junction_result, cross_check = _run_real_pipeline(gray)
    result = build_precedence_graph(junction_result, cross_check, **TOL)

    assert result.arcs == []
    assert result.n_conflicting_abutter == 0
    assert result.graph.number_of_nodes() == 0
    assert result.generation == {}


def test_compute_generations_simple_chain_no_cycle():
    # 0 -> 1 -> 2: a plain chain, no contradictions.
    graph = nx.DiGraph()
    graph.add_edge(0, 1)
    graph.add_edge(1, 2)
    generation, nontrivial_sccs = _compute_generations(graph)
    assert nontrivial_sccs == []
    assert generation == {0: 0, 1: 1, 2: 2}


def test_compute_generations_three_cycle_leaves_generation_undetermined():
    # 0 -> 1 -> 2 -> 0: a contradictory precedence loop (exactly the
    # "genuinely near-simultaneous or misread junction" case CLAUDE.md
    # anticipates) -- must be reported, not silently broken or resolved.
    graph = nx.DiGraph()
    graph.add_edge(0, 1)
    graph.add_edge(1, 2)
    graph.add_edge(2, 0)
    generation, nontrivial_sccs = _compute_generations(graph)
    assert nontrivial_sccs == [frozenset({0, 1, 2})]
    assert generation == {0: None, 1: None, 2: None}


def _edge_dir(path_index: int, bearing_deg: float) -> EdgeDirection:
    return EdgeDirection(
        path_index=path_index,
        direction=None,
        bearing_deg=bearing_deg,
        curvature_per_px=None,
        fit_degree=1,
        fit_rms_px=None,
        fit_coef_row=None,
        fit_coef_col=None,
        band_s_range=None,
        n_points_in_band=2,
        annulus_clipped=False,
        effective_inner_radius_px=5.0,
        ok=True,
        failure_reason=None,
    )


def _junction_classification(node_id, abutter, hosts, edge_dirs) -> JunctionClassification:
    return JunctionClassification(
        node_id=node_id,
        coord=(0.0, 0.0),
        vertex_halfwidth_px=None,
        edge_directions=edge_dirs,
        sector_gaps_deg=[90.0, 90.0, 180.0],
        label="T",
        abutter_path_index=abutter,
        host_path_indices=hosts,
        failure_reason=None,
    )


def _junction_result(classifications) -> JunctionAnalysisResult:
    return JunctionAnalysisResult(
        classifications=classifications,
        n_deg3_total=len(classifications),
        n_t=sum(c.label == "T" for c in classifications),
        n_y=0,
        n_ambiguous=sum(c.label == "ambiguous" for c in classifications),
        n_insufficient_data=0,
        n_deg_ge4_unclassified=0,
        inner_radius_px=5.0,
        outer_radius_px=60.0,
        y_angle_tol_deg=15.0,
        t_straight_tol_deg=20.0,
        t_right_tol_deg=20.0,
    )


def test_conflicting_abutter_produces_no_arc_and_is_counted():
    # Tangent-fit claims path 10 is the abutter (hosts 11, 12). The corner
    # method independently measures bearings {320, 130, 220} at the SAME
    # node -- worked out by hand so that, after matching each corner
    # bearing to its nearest tangent-fit arm bearing (within the 45 deg
    # tolerance), classify_from_gaps identifies path 12 as ITS abutter
    # instead. Two independent methods, two different abutters: an honest
    # conflict, not something to silently pick a side on.
    jc = _junction_classification(
        node_id=1,
        abutter=10,
        hosts=(11, 12),
        edge_dirs=[_edge_dir(10, 0.0), _edge_dir(11, 90.0), _edge_dir(12, 180.0)],
    )
    junction_result = _junction_result([jc])
    cc = CornerCrossCheck(
        node_id=1,
        corners=[],
        arm_bearings_deg=[320.0, 130.0, 220.0],
        sector_gaps_deg=[90.0, 100.0, 170.0],
        label="T",
        unresolved_reason=None,
        agrees_with_tangent_fit=None,
        max_gap_disagreement_deg=None,
    )

    result = build_precedence_graph(junction_result, [cc], **TOL)

    assert result.arcs == []
    assert result.n_conflicting_abutter == 1
    assert result.conflicting_node_ids == [1]


def test_corner_unresolved_leaves_tangent_only_arc():
    jc = _junction_classification(
        node_id=2,
        abutter=20,
        hosts=(21, 22),
        edge_dirs=[_edge_dir(20, 0.0), _edge_dir(21, 90.0), _edge_dir(22, 270.0)],
    )
    junction_result = _junction_result([jc])
    cc = CornerCrossCheck(
        node_id=2,
        corners=[],
        arm_bearings_deg=None,
        sector_gaps_deg=None,
        label=None,
        unresolved_reason="unsupported_corner_count_1",
        agrees_with_tangent_fit=None,
        max_gap_disagreement_deg=None,
    )

    result = build_precedence_graph(junction_result, [cc], **TOL)

    assert len(result.arcs) == 2
    assert all(a.supporting_methods == ("tangent_fit",) for a in result.arcs)
    assert all(not a.methods_agree for a in result.arcs)
    assert result.n_conflicting_abutter == 0
