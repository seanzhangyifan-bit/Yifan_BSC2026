"""Stage 1-3 correctness check against a synthetic image with a known
topology: one T-junction, meaning exactly 1 junction node (degree 3),
3 endpoint nodes, and 3 edges.
"""

from src.crackgraph.binarize import binarize
from src.crackgraph.graph import extract_graph
from src.crackgraph.skeleton import skeletonize_and_prune
from src.crackgraph.synthetic import generate_t_junction


def test_t_junction_topology():
    gray = generate_t_junction()

    binarize_result = binarize(gray, sanity_band=(0.0, 1.0))
    assert binarize_result.mask.any()

    skeleton_result = skeletonize_and_prune(
        binarize_result.mask,
        source_image=gray,
        spur_px=3,  # small: the synthetic arms are long relative to real spurs
    )
    graph_result = extract_graph(skeleton_result.skeleton)

    assert graph_result.n_endpoints == 3
    assert graph_result.n_junctions_deg3 == 1
    assert graph_result.n_junctions_deg_ge4 == 0
    assert graph_result.n_edges == 3
    assert len(graph_result.node_ids) == 4
