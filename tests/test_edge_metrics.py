"""Stage 3.5 correctness check: given synthetic geometries with KNOWN
ground truth (length, width, and -- via mask pixel counts -- area), does
edge_metrics.py recover them, and do the proven bound relationships
between its four area methods (core <= exact <= mask total, ribbon
typically >= exact) actually hold?
"""

from src.crackgraph.binarize import binarize
from src.crackgraph.edge_metrics import compute_edge_metrics, partition_area_by_edge
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import (
    generate_double_t_junction,
    generate_straight_line,
    generate_t_junction,
    generate_y_junction,
)

# Empirically observed rasterization bias (EDT/discretization), not a bug --
# see edge_metrics.py's module docstring and the plan's design notes.
WIDTH_RECOVERY_TOL_PX = 2.0


def _run(gray, spur_px=3.0, **kwargs):
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=spur_px)
    graph_result = extract_graph(skeleton_result.skeleton)
    result = compute_edge_metrics(
        skeleton_result.skeleton,
        graph_result,
        skeleton_result.mask_clean,
        skeleton_result.medial_radius,
        **kwargs,
    )
    return result, skeleton_result, graph_result


def test_straight_edge_length_area_exact():
    gray = generate_straight_line(thickness=7, length=70.0)
    result, skeleton_result, graph_result = _run(gray)
    assert graph_result.n_edges == 1
    m = next(iter(result.per_edge.values()))
    # Only one seed in the whole image -- nothing to compete with, so the
    # watershed partition must claim every mask pixel exactly.
    assert m.area_px2 == result.mask_clean_total_px2
    assert result.n_unassigned_px == 0
    # Skeleton endpoints sit inset from the exact rectangle corners by a
    # few px (thinning doesn't reach all the way into a flat cut end) --
    # a known rasterization effect, not a bug; measured margin ~3.6px here.
    assert abs(m.length_px - 70.0) < 5.0


def test_t_junction_area_conservation():
    gray = generate_t_junction(angle_deg=90.0)
    result, _, graph_result = _run(gray)
    assert len(result.per_edge) == 3
    total = sum(m.area_px2 for m in result.per_edge.values())
    assert total + result.n_unassigned_px == result.mask_clean_total_px2
    for m in result.per_edge.values():
        assert m.area_px2 > 0

    assert len(result.junction_blob_ambiguity) == 1
    jb = result.junction_blob_ambiguity[0]
    assert sum(jb.claims.values()) == jb.total_blob_px2
    assert len(jb.claims) == 3


def test_width_matches_known_thickness():
    gray = generate_straight_line(thickness=7, length=70.0)
    result, _, _ = _run(gray)
    m = next(iter(result.per_edge.values()))
    assert m.width.ok
    assert abs(m.width.mean_px - 7.0) <= WIDTH_RECOVERY_TOL_PX


def test_width_trim_flags_too_short_edge():
    # Abutter too short (4px) to survive trimming max(5px placeholder,
    # local junction-blob half-width) off both ends.
    gray = generate_t_junction(angle_deg=90.0, arm_length=4.0)
    result, _, graph_result = _run(gray, spur_px=0.5)
    short_edges = [
        m for m in result.per_edge.values() if m.length_px < 10.0
    ]
    assert short_edges
    for m in short_edges:
        assert not m.width.ok
        assert m.width.failure_reason == "edge_too_short_for_trim"


def test_area_conservation_with_pruned_fragment():
    gray = generate_t_junction(angle_deg=90.0).copy()
    # Isolated 2x9 fragment, far from the T, sized to survive
    # remove_small_objects (min_object_px=4) but skeletonize to a short
    # isolated (branch_type 0) path fully removed by fragment pruning.
    fg_value = 230.0
    gray[10:12, 10:19] = fg_value
    fragment_mask_px = int((gray[10:12, 10:19] == fg_value).sum())

    result, skeleton_result, _ = _run(gray, spur_px=10.0)
    assert skeleton_result.n_fragments_pruned >= 1
    total = sum(m.area_px2 for m in result.per_edge.values())
    assert total + result.n_unassigned_px == result.mask_clean_total_px2
    assert result.n_unassigned_px > 0
    # Loose, same-order-of-magnitude check (fragment length != fragment
    # mask area exactly), not an exact match.
    assert result.n_unassigned_px <= fragment_mask_px * 2


def test_watershed_determinism():
    gray = generate_t_junction(angle_deg=90.0)
    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray, spur_px=3.0)
    graph_result = extract_graph(skeleton_result.skeleton)
    r1 = partition_area_by_edge(
        skeleton_result.skeleton, graph_result.summary, skeleton_result.mask_clean, skeleton_result.medial_radius
    )
    r2 = partition_area_by_edge(
        skeleton_result.skeleton, graph_result.summary, skeleton_result.mask_clean, skeleton_result.medial_radius
    )
    assert (r1.labels == r2.labels).all()


def test_mask_total_is_hard_upper_bound():
    for gray in (
        generate_straight_line(thickness=7, length=70.0),
        generate_t_junction(angle_deg=90.0),
        generate_y_junction(),
    ):
        result, _, _ = _run(gray)
        assert result.total_area_px2 <= result.mask_clean_total_px2


def test_ribbon_matches_watershed_on_isolated_edge():
    gray = generate_straight_line(thickness=7, length=70.0)
    result, _, _ = _run(gray)
    m = next(iter(result.per_edge.values()))
    # Nothing to double-count -- the two methods should closely agree.
    assert abs(m.area_ribbon_px2 - m.area_px2) / m.area_px2 < 0.1


def test_ribbon_overshoots_at_junction():
    gray = generate_t_junction(angle_deg=90.0)
    result, _, _ = _run(gray)
    # Expected-but-not-proven overshoot from double-counting the shared
    # junction blob across incident edges -- see module docstring.
    assert result.total_area_ribbon_px2 > result.total_area_px2


def test_core_area_is_hard_lower_bound():
    for gray in (
        generate_straight_line(thickness=7, length=70.0),
        generate_t_junction(angle_deg=90.0),
        generate_y_junction(),
    ):
        result, _, _ = _run(gray)
        for m in result.per_edge.values():
            assert m.area_core_px2 <= m.area_px2
            assert m.area_core_px2 >= 0


def test_core_area_clamps_on_short_inter_junction_edge():
    gray = generate_double_t_junction(gap_px=6.0)
    result, _, graph_result = _run(gray, spur_px=2.0)
    assert graph_result.n_junctions_deg3 >= 2
    for m in result.per_edge.values():
        assert m.area_core_px2 <= m.area_px2
    assert result.n_zero_core_edges >= 1
    assert any(m.core_was_clamped for m in result.per_edge.values())
