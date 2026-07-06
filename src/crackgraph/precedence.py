"""Stage 5 (first pass): assemble a precedence graph from stage 4's T-junction
readings, and characterize (but do not resolve) any cycles.

Scope, decided with the user: this pass builds the graph, unions both stage-4
classifiers (tangent-fit + corner cross-check) into precedence constraints
with provenance, and reports cycles as a data-quality metric per CLAUDE.md's
"report minimum-feedback-arc-set size... rather than silently deleting."
It deliberately does NOT try to resolve cycles into a forced acyclic poset,
and does NOT compute width `w` (stage 6) -- both are explicitly deferred
until this pass has been reviewed against real data ("let's just see how the
connections look like first").

Atoms are unchanged from stage 3: each `path_index` (a row of
GraphResult.summary, i.e. one skan-extracted skeleton branch) is already the
atomic unit. No further arc-splitting and no collapsing is done here --
CLAUDE.md's "atoms: arcs, not whole cracks" principle means two collinear
segments straddling an uncollapsed junction are colored/ordered independently
unless a future evidence-backed collapse pass says otherwise.

Constraint source -- union with provenance (decided with the user, not
consensus-only and not either method alone): for every node where the
tangent-fit and/or the corner cross-check resolves to "T", collect each
method's claim as (abutter_path_index, host_path_indices). If both resolve
and agree on the abutter, the resulting arcs are tagged as agreeing; if only
one resolves, the arcs are tagged with that one method; if both resolve but
DISAGREE on which arm is the abutter, no arc is emitted from that node at
all and it is counted as a conflict -- an honest gap, not a coin flip.

The corner cross-check's CornerCrossCheck does not itself store which
`path_index` its resolved abutter corresponds to (it only knows bearings,
not skeleton edge identity) -- classify_from_gaps' abutter/host indices are
recomputed here from the already-public arm_bearings_deg (deterministic,
same rule as junctions.py/corners.py use), then matched to the tangent-fit's
own per-arm bearings at that node (JunctionClassification.edge_directions)
by nearest angular distance, to recover path_index identity. This requires
all 3 tangent-fit arm bearings to be available at that node; if the tangent
fit could not measure all 3 (e.g. a too-short arm), the corner claim is left
unmapped for now rather than guessed at -- a documented simplification for
this first pass, worth revisiting once real data shows how often it bites.

Cycle characterization uses networkx's condensation (each strongly-connected
component collapsed to one supernode, which is always a DAG) rather than a
hand-rolled minimum-feedback-arc-set solver (networkx has none, and
CLAUDE.md's own steps separate "DAG/cycle check" from a later, more careful
poset-repair step). Any path_index inside a nontrivial SCC (size > 1) gets
generation=None -- undetermined, reported rather than forced -- while
everything else gets its topological generation for free from the
condensation's DAG structure.
"""

from dataclasses import dataclass

import networkx as nx

from .corners import CornerCrossCheck
from .junctions import JunctionAnalysisResult, classify_from_gaps, sector_gaps_deg_from_bearings

CORNER_TO_TANGENT_BEARING_TOL_DEG = 45.0
# [PLACEHOLDER] how far apart the corner method's and the tangent-fit's
# independent bearing estimates for the same arm may be and still be treated
# as "the same arm" when recovering path_index identity for a corner-only
# claim. Deliberately generous (these are two geometrically distinct
# measurements, not two readings of the same fit) but not yet measured via a
# sweep the way ANNULUS_OUTER_PX_PLACEHOLDER/CORNER_WINDOW_PX were -- revisit
# once real disagreement-rate data exists (see corner cross-check report).


@dataclass
class PrecedenceArc:
    node_id: int
    abutter_path_index: int
    host_path_index: int
    supporting_methods: tuple[str, ...]  # subset of ("tangent_fit", "corner_cross_check")
    methods_agree: bool  # True only when both methods resolved this node to T with the same abutter


@dataclass
class PrecedenceGraphResult:
    arcs: list[PrecedenceArc]
    graph: nx.DiGraph  # nodes = path_index touched by >=1 arc, edges = precedence
    n_conflicting_abutter: int  # both methods resolved T but disagreed on the abutter -- no arc emitted
    conflicting_node_ids: list[int]
    n_corner_unmapped: int  # corner resolved T but couldn't be tied to path indices (see module docstring)
    nontrivial_sccs: list[frozenset[int]]  # cyclic clusters (size > 1) -- the cycle report, not resolved
    generation: dict[int, int | None]  # path_index -> topological generation; None if undetermined


def _angle_diff(a: float, b: float) -> float:
    """Smallest signed difference a-b, wrapped to (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def _corner_claim_to_path_indices(
    cc: CornerCrossCheck,
    path_bearings: dict[int, float],
    y_angle_tol_deg: float,
    t_straight_tol_deg: float,
    t_right_tol_deg: float,
    match_tol_deg: float,
) -> tuple[int | None, tuple[int, int] | None, str | None]:
    """Recover (abutter_path_index, host_path_indices) for a corner-resolved
    T-junction, or (None, None, reason) if it can't be tied to path indices.
    """
    if cc.label != "T" or cc.arm_bearings_deg is None:
        return None, None, "corner_not_T"
    if len(path_bearings) < 3:
        return None, None, "tangent_fit_bearings_incomplete_cannot_map_corner_claim"

    gap_tuples = sector_gaps_deg_from_bearings(cc.arm_bearings_deg)
    label, abutter_local, host_local = classify_from_gaps(
        gap_tuples, y_angle_tol_deg, t_straight_tol_deg, t_right_tol_deg
    )
    if label != "T":
        # Recomputed from the same public rule cc.label was derived from --
        # a mismatch would mean the caller passed different tolerances than
        # cross_check_junctions used. Surface it rather than trust cc.label.
        return None, None, "corner_label_recompute_mismatch"

    path_items = list(path_bearings.items())  # [(path_index, bearing_deg), ...]
    pairs = [
        (abs(_angle_diff(cc.arm_bearings_deg[local_idx], pb)), local_idx, path_idx)
        for local_idx in range(3)
        for path_idx, pb in path_items
    ]
    pairs.sort(key=lambda t: t[0])

    assignment: dict[int, int] = {}
    used_paths: set[int] = set()
    for diff, local_idx, path_idx in pairs:
        if local_idx in assignment or path_idx in used_paths or diff > match_tol_deg:
            continue
        assignment[local_idx] = path_idx
        used_paths.add(path_idx)

    if len(assignment) != 3:
        return None, None, "corner_to_pathindex_bearing_mismatch"

    abutter_path = assignment[abutter_local]
    host_paths = (assignment[host_local[0]], assignment[host_local[1]])
    return abutter_path, host_paths, None


def _compute_generations(graph: nx.DiGraph) -> tuple[dict[int, int | None], list[frozenset[int]]]:
    if graph.number_of_nodes() == 0:
        return {}, []

    sccs = list(nx.strongly_connected_components(graph))
    nontrivial_sccs = [frozenset(s) for s in sccs if len(s) > 1]
    nontrivial_nodes: set[int] = set().union(*nontrivial_sccs) if nontrivial_sccs else set()

    condensed = nx.condensation(graph, scc=sccs)
    generation: dict[int, int | None] = {}
    for gen_idx, supernodes in enumerate(nx.topological_generations(condensed)):
        for supernode in supernodes:
            for node in condensed.nodes[supernode]["members"]:
                generation[node] = None if node in nontrivial_nodes else gen_idx
    return generation, nontrivial_sccs


def build_precedence_graph(
    junction_result: JunctionAnalysisResult,
    corner_cross_check: list[CornerCrossCheck],
    *,
    y_angle_tol_deg: float,
    t_straight_tol_deg: float,
    t_right_tol_deg: float,
    corner_to_tangent_bearing_tol_deg: float = CORNER_TO_TANGENT_BEARING_TOL_DEG,
) -> PrecedenceGraphResult:
    corner_by_node = {cc.node_id: cc for cc in corner_cross_check}

    arcs: list[PrecedenceArc] = []
    n_conflicting = 0
    conflicting_node_ids: list[int] = []
    n_corner_unmapped = 0

    for jc in junction_result.classifications:
        tangent_claim = (jc.abutter_path_index, jc.host_path_indices) if jc.label == "T" else None

        corner_claim = None
        cc = corner_by_node.get(jc.node_id)
        if cc is not None and cc.label == "T":
            path_bearings = {ed.path_index: ed.bearing_deg for ed in jc.edge_directions if ed.ok}
            abutter_p, host_p, reason = _corner_claim_to_path_indices(
                cc,
                path_bearings,
                y_angle_tol_deg,
                t_straight_tol_deg,
                t_right_tol_deg,
                corner_to_tangent_bearing_tol_deg,
            )
            if abutter_p is not None:
                corner_claim = (abutter_p, host_p)
            else:
                n_corner_unmapped += 1

        if tangent_claim is not None and corner_claim is not None:
            if tangent_claim[0] != corner_claim[0]:
                n_conflicting += 1
                conflicting_node_ids.append(jc.node_id)
                continue
            abutter, hosts = tangent_claim
            supporting: tuple[str, ...] = ("tangent_fit", "corner_cross_check")
            agree = True
        elif tangent_claim is not None:
            abutter, hosts = tangent_claim
            supporting = ("tangent_fit",)
            agree = False
        elif corner_claim is not None:
            abutter, hosts = corner_claim
            supporting = ("corner_cross_check",)
            agree = False
        else:
            continue

        for host in hosts:
            arcs.append(
                PrecedenceArc(
                    node_id=jc.node_id,
                    abutter_path_index=abutter,
                    host_path_index=host,
                    supporting_methods=supporting,
                    methods_agree=agree,
                )
            )

    graph = nx.DiGraph()
    for arc in arcs:
        # host -> abutter, NOT abutter -> host: per CLAUDE.md, "the crack
        # that abuts arrived after the crack it hit" -- the host was
        # already there (an existing discontinuity the abutter's tip
        # couldn't cross), so the host is the *earlier* node and the
        # abutter is *later*. Generation(host) < generation(abutter).
        graph.add_edge(arc.host_path_index, arc.abutter_path_index)

    generation, nontrivial_sccs = _compute_generations(graph)

    return PrecedenceGraphResult(
        arcs=arcs,
        graph=graph,
        n_conflicting_abutter=n_conflicting,
        conflicting_node_ids=conflicting_node_ids,
        n_corner_unmapped=n_corner_unmapped,
        nontrivial_sccs=nontrivial_sccs,
        generation=generation,
    )
