"""Per-atomic-edge length/width/area metrics.

Naming caution: "width" in this module means physical crack width in px
(sampled from the EDT distance transform) -- CLAUDE.md's third chronometer
("crack width... earlier cracks tend wider due to post-crack drying
shrinkage"). This is a completely different quantity from stage 6's poset
antichain width `w` (the count of mutually-undatable cracks). The two are
never mixed in this module's field names.

Atoms are the same atomic edge (`path_index`, from skan's summary table)
that precedence.py already keys its arcs on -- per CLAUDE.md's "atoms: arcs,
not whole cracks" rule, nothing here collapses collinear edges into a single
"crack".

Four area estimates are computed per edge/image, deliberately kept as
separate, cross-checked numbers rather than collapsed into one "best"
answer (matching CLAUDE.md's existing chronometer-agreement philosophy):

- `area_px2` (exact per-edge partition, seedless watershed): the primary
  method. [interpreted] -- a deterministic partition, but pixels right at a
  junction blob are inherently shared between arms, so which edge "wins"
  them is an artifact of flood order, not a measurement (see
  `area_ambiguous_px2` / `JunctionBlobAmbiguity` below).
- `mask_clean_total_px2` (whole-image/region foreground pixel count): a
  PROVEN upper bound on sum(area_px2) -- watershed with `mask=` never
  assigns a pixel outside the mask, so
  `sum(area_px2) + n_unassigned_px == mask_clean_total_px2` exactly, and
  `n_unassigned_px >= 0` always.
- `area_ribbon_px2` (trapezoidal integral of width along arc length): an
  EXPECTED-but-NOT-PROVEN upper bound on `area_px2` -- it tends to run high
  near junctions (each incident edge separately credits itself the full,
  locally-inflated junction-blob width, double/triple-counting the shared
  region) and carries a small rasterization bias even in isolation. The
  actual sign is measured and reported per run, not assumed.
- `area_core_px2` (junction-disk-excluded): a PROVEN lower bound on
  `area_px2` -- `max(0, area_px2 - area_ambiguous_px2)`, true by
  construction (subtracting a non-negative quantity, clamped at 0).

Bracket, per edge and in aggregate: `0 <= area_core_px2 <= area_px2 <=
mask_clean_total_px2` (all provable), with `area_ribbon_px2` typically (not
provably) landing at or above `area_px2`.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import skan
from skimage.segmentation import watershed

from .graph import GraphResult

WIDTH_TRIM_INNER_PX_PLACEHOLDER = 5.0
# [PLACEHOLDER] Same jitter/junction-blob-avoidance reasoning as
# junctions.py's ANNULUS_INNER_PX_PLACEHOLDER, kept as an independently
# named/tunable constant because it trims for a different purpose (keeping
# a *width sample* off the junction blob and off a tapering tip, not an
# angle-fit band) and may need separate calibration later. Effective value
# at a given endpoint is max(this, medial_radius at that endpoint), reusing
# the same "widen past the blob" pattern junctions.py established. Not
# derived from calibrated um-per-px (none exists yet). Revisit once
# calibration lands.

AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER = 5.0
# [PLACEHOLDER] Same value/reasoning again, defines the disk radius (per
# degree>=3 node, widened to the local medial_radius the same way) used to
# report the area-ambiguity metric -- not to change how the watershed
# itself is seeded.


@dataclass
class EdgeWidthMeasurement:
    path_index: int
    n_samples: int  # [measured]
    trim_inner_src_px: float  # [measured] effective trim used at the src end
    trim_inner_dst_px: float  # [measured] effective trim used at the dst end
    band_span_px: float | None  # [measured] arc-length actually sampled
    mean_px: float | None  # [measured]
    median_px: float | None  # [measured]
    min_px: float | None  # [measured]
    max_px: float | None  # [measured]
    std_px: float | None  # [measured]
    ok: bool
    failure_reason: str | None  # e.g. "edge_too_short_for_trim"


@dataclass
class WatershedAreaResult:
    labels: np.ndarray  # int32, label = path_index + 1, 0 = background/unassigned
    area_px2: dict[int, int]  # path_index -> pixel count  [interpreted]
    n_unassigned_px: int  # [measured] foreground never reached by any seed
    n_seed_fallback_edges: int  # [measured] edges with no interior seed pixel


@dataclass
class JunctionBlobAmbiguity:
    node_id: int
    coord: tuple[float, float]
    radius_px: float  # [measured] max(placeholder, local medial_radius at node)
    total_blob_px2: int  # [measured] mask_clean pixels within radius_px of the node
    claims: dict[int, int]  # path_index -> px of this disk the watershed
    # assigned to that edge's label. [interpreted] -- an artifact of which
    # seed's flood front reached it first, not a measurement of true
    # ownership.


@dataclass
class EdgeMetrics:
    path_index: int
    node_id_src: int
    node_id_dst: int
    length_px: float  # [measured] = skan branch_distance
    width: EdgeWidthMeasurement
    area_px2: int  # [interpreted] watershed partition
    area_ambiguous_px2: int  # [interpreted] see JunctionBlobAmbiguity
    area_ambiguous_frac: float
    area_core_px2: int  # [interpreted] PROVEN lower bound on area_px2
    core_was_clamped: bool  # True if the two endpoint disks' claims exceeded area_px2
    area_ribbon_px2: float  # [interpreted] EXPECTED (not proven) upper bound
    ribbon_minus_watershed_px2: float


@dataclass
class EdgeMetricsResult:
    per_edge: dict[int, EdgeMetrics]
    watershed: WatershedAreaResult
    junction_blob_ambiguity: list[JunctionBlobAmbiguity]
    total_length_px: float  # [measured]
    total_area_px2: int  # [interpreted]
    total_area_core_px2: int  # [interpreted] PROVEN lower bound on total_area_px2
    total_area_ribbon_px2: float  # [interpreted] EXPECTED (not proven) upper bound
    mask_clean_total_px2: int  # [measured] PROVEN upper bound on total_area_px2
    n_unassigned_px: int  # [measured]
    n_zero_core_edges: int  # [interpreted] edges too short to have a defensible core
    n_ribbon_high: int  # [measured] edges where ribbon > watershed, this run
    n_ribbon_low_or_equal: int  # [measured]
    n_width_ok: int
    n_width_failed: int
    length_excluded_from_width_stat_px: float
    length_weighted_mean_width_px: float | None  # [interpreted]
    region_area_px2: int  # analyzed-region pixel area (not foreground area)
    crack_length_density_per_px: float  # [interpreted] px-space only, see module docstring
    width_trim_inner_px: float  # [PLACEHOLDER]
    area_ambiguity_radius_px: float  # [PLACEHOLDER]


def _node_coord_map(graph_result: GraphResult) -> dict[int, tuple[float, float]]:
    return {
        int(node_id): (float(coord[0]), float(coord[1]))
        for node_id, coord in zip(graph_result.node_ids, graph_result.node_coords)
    }


def _effective_trim(coord: tuple[float, float], medial_radius: np.ndarray, inner_px: float) -> float:
    r = int(np.clip(round(coord[0]), 0, medial_radius.shape[0] - 1))
    c = int(np.clip(round(coord[1]), 0, medial_radius.shape[1] - 1))
    return max(inner_px, float(medial_radius[r, c]))


def measure_edge_width(
    skel: skan.Skeleton,
    path_index: int,
    src_coord: tuple[float, float],
    dst_coord: tuple[float, float],
    medial_radius: np.ndarray,
    *,
    trim_inner_px: float = WIDTH_TRIM_INNER_PX_PLACEHOLDER,
) -> EdgeWidthMeasurement:
    """Sample 2*medial_radius along skel.path_coordinates(path_index),
    trimmed by max(trim_inner_px, local endpoint half-width) at BOTH ends --
    the same "skip the junction blob" pattern junctions.py established for
    angle fitting, applied symmetrically here since a degree-1 tip's taper
    is equally unrepresentative of "mid-arm" width as a junction blob is.

    If the trim consumes the whole edge, no width is computed -- ok=False,
    failure_reason="edge_too_short_for_trim" -- never a silently
    contaminated sample.
    """
    coords = skel.path_coordinates(path_index).astype(np.float64)
    trim_src = _effective_trim(src_coord, medial_radius, trim_inner_px)
    trim_dst = _effective_trim(dst_coord, medial_radius, trim_inner_px)

    def _fail(reason: str) -> EdgeWidthMeasurement:
        return EdgeWidthMeasurement(
            path_index=path_index,
            n_samples=0,
            trim_inner_src_px=trim_src,
            trim_inner_dst_px=trim_dst,
            band_span_px=None,
            mean_px=None,
            median_px=None,
            min_px=None,
            max_px=None,
            std_px=None,
            ok=False,
            failure_reason=reason,
        )

    if len(coords) < 2:
        return _fail("edge_too_short_for_trim")

    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(steps)])
    total = float(s[-1])
    band_mask = (s >= trim_src) & (s <= total - trim_dst)
    n = int(band_mask.sum())
    if n == 0:
        return _fail("edge_too_short_for_trim")

    band = coords[band_mask]
    rr = np.clip(np.round(band[:, 0]).astype(int), 0, medial_radius.shape[0] - 1)
    cc = np.clip(np.round(band[:, 1]).astype(int), 0, medial_radius.shape[1] - 1)
    widths = 2.0 * medial_radius[rr, cc]
    s_band = s[band_mask]
    span = float(s_band.max() - s_band.min()) if n > 1 else 0.0

    return EdgeWidthMeasurement(
        path_index=path_index,
        n_samples=n,
        trim_inner_src_px=trim_src,
        trim_inner_dst_px=trim_dst,
        band_span_px=span,
        mean_px=float(widths.mean()),
        median_px=float(np.median(widths)),
        min_px=float(widths.min()),
        max_px=float(widths.max()),
        std_px=float(widths.std()),
        ok=True,
        failure_reason=None,
    )


def partition_area_by_edge(
    skel: skan.Skeleton,
    summary: pd.DataFrame,
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
) -> WatershedAreaResult:
    """Deterministic, seedless watershed: markers = each path's INTERIOR
    polyline pixels (excluding both endpoint node pixels, since those are
    literally shared skeleton pixels between multiple incident paths at a
    junction -- seeding with them would create an arbitrary last-write-wins
    collision instead of letting the flood itself decide ownership of the
    contested region). Elevation = -medial_radius (the skeleton ridge is the
    lowest elevation, so flooding fills outward from it, matching a
    Voronoi-like ownership region). mask=mask_clean restricts flooding to
    foreground. connectivity=8 matches how a 1px-wide skeleton can touch
    mask pixels diagonally.

    Reproducible per CLAUDE.md's determinism requirement: no RNG anywhere.
    """
    markers = np.zeros(mask_clean.shape, dtype=np.int32)
    n_fallback = 0
    for path_index in summary.index:
        coords = skel.path_coordinates(int(path_index))
        rc = np.round(coords).astype(int)
        rc[:, 0] = np.clip(rc[:, 0], 0, mask_clean.shape[0] - 1)
        rc[:, 1] = np.clip(rc[:, 1], 0, mask_clean.shape[1] - 1)
        interior = rc[1:-1]
        if len(interior) == 0:
            # Ultra-short edge (<=2 path pixels): both "ends" are the only
            # pixels available, so seed with them anyway -- reintroduces the
            # last-write-wins collision risk only for this specific edge,
            # counted rather than silently absorbed.
            interior = rc
            n_fallback += 1
        markers[interior[:, 0], interior[:, 1]] = int(path_index) + 1

    labels = watershed(-medial_radius, markers=markers, mask=mask_clean, connectivity=np.ones((3, 3)))

    area_px2 = {
        int(path_index): int(np.sum(labels == int(path_index) + 1)) for path_index in summary.index
    }
    n_unassigned = int(mask_clean.sum()) - int(sum(area_px2.values()))
    return WatershedAreaResult(
        labels=labels,
        area_px2=area_px2,
        n_unassigned_px=n_unassigned,
        n_seed_fallback_edges=n_fallback,
    )


def estimate_edge_area_ribbon(skel: skan.Skeleton, path_index: int, medial_radius: np.ndarray) -> float:
    """Trapezoidal integral of 2*medial_radius(s) ds along the FULL path
    (src to dst, no trimming -- unlike measure_edge_width, this deliberately
    estimates the edge's whole swept area, the same thing the watershed
    method assigns it). [interpreted] -- see module docstring for why this
    is expected to run high near junctions and should not be treated as
    more trustworthy than the watershed value just because it's cheaper.
    """
    coords = skel.path_coordinates(int(path_index)).astype(np.float64)
    if len(coords) < 2:
        return 0.0
    rr = np.clip(np.round(coords[:, 0]).astype(int), 0, medial_radius.shape[0] - 1)
    cc = np.clip(np.round(coords[:, 1]).astype(int), 0, medial_radius.shape[1] - 1)
    widths = 2.0 * medial_radius[rr, cc]
    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    return float(np.sum((widths[:-1] + widths[1:]) / 2.0 * steps))


def _iter_junction_disks(
    graph_result: GraphResult,
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
    radius_px: float,
):
    """Shared geometry for every degree>=3 node (topological -- both
    classified degree-3 T/Y and unclassified degree>=4): crop a local disk
    of radius max(radius_px, medial_radius-at-node). Yields
    (node_id, coord, eff_radius, r_lo, c_lo, disk_bool_mask) where
    disk_bool_mask is sized to the (r_lo:r_hi, c_lo:c_hi) crop, already
    restricted to mask_clean. Used by both compute_junction_blob_ambiguity
    (numeric tally) and compute_ambiguous_pixel_mask (pixel mask) so the two
    can never disagree about which pixels count as "junction-disputed".
    """
    h, w = mask_clean.shape
    for node_id, degree, coord in zip(
        graph_result.node_ids, graph_result.node_degree, graph_result.node_coords
    ):
        if degree < 3:
            continue
        row, col = float(coord[0]), float(coord[1])
        r_idx = int(np.clip(round(row), 0, h - 1))
        c_idx = int(np.clip(round(col), 0, w - 1))
        eff_radius = max(radius_px, float(medial_radius[r_idx, c_idx]))

        r_lo = max(0, int(np.floor(row - eff_radius)))
        r_hi = min(h, int(np.ceil(row + eff_radius)) + 1)
        c_lo = max(0, int(np.floor(col - eff_radius)))
        c_hi = min(w, int(np.ceil(col + eff_radius)) + 1)

        sub_mask = mask_clean[r_lo:r_hi, c_lo:c_hi]
        rr, cc = np.mgrid[r_lo:r_hi, c_lo:c_hi]
        disk = (np.hypot(rr - row, cc - col) <= eff_radius) & sub_mask

        yield int(node_id), (row, col), eff_radius, r_lo, c_lo, disk


def compute_junction_blob_ambiguity(
    graph_result: GraphResult,
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
    labels: np.ndarray,
    *,
    radius_px: float = AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER,
) -> list[JunctionBlobAmbiguity]:
    """For every degree>=3 node, tally within its junction disk (see
    _iter_junction_disks) how many mask_clean pixels each watershed label
    claimed.

    This directly answers "how much of edge X's counted area is actually
    inside a zone geometrically shared by multiple arms" -- surfaced as
    [interpreted], not silently folded into an [measured]-looking area
    total, per CLAUDE.md's evidence-level discipline.
    """
    results: list[JunctionBlobAmbiguity] = []
    for node_id, coord, eff_radius, r_lo, c_lo, disk in _iter_junction_disks(
        graph_result, mask_clean, medial_radius, radius_px
    ):
        r_hi, c_hi = r_lo + disk.shape[0], c_lo + disk.shape[1]
        sub_labels = labels[r_lo:r_hi, c_lo:c_hi]

        total_blob = int(disk.sum())
        claim_labels, claim_counts = np.unique(sub_labels[disk], return_counts=True)
        claims = {
            int(lbl) - 1: int(cnt) for lbl, cnt in zip(claim_labels, claim_counts) if lbl != 0
        }
        results.append(
            JunctionBlobAmbiguity(
                node_id=node_id,
                coord=coord,
                radius_px=eff_radius,
                total_blob_px2=total_blob,
                claims=claims,
            )
        )
    return results


def compute_ambiguous_pixel_mask(
    graph_result: GraphResult,
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
    *,
    radius_px: float = AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER,
) -> np.ndarray:
    """Boolean mask, same shape as mask_clean: True where a pixel falls
    inside ANY degree>=3 node's junction disk (union across nodes, not kept
    per-edge). [interpreted] -- exactly the pixels area_core_px2 excludes.
    Reuses _iter_junction_disks so this visualization/reporting mask can
    never drift out of sync with the numeric core-area computation.
    """
    ambiguous = np.zeros(mask_clean.shape, dtype=bool)
    for _node_id, _coord, _eff_radius, r_lo, c_lo, disk in _iter_junction_disks(
        graph_result, mask_clean, medial_radius, radius_px
    ):
        r_hi, c_hi = r_lo + disk.shape[0], c_lo + disk.shape[1]
        ambiguous[r_lo:r_hi, c_lo:c_hi] |= disk
    return ambiguous


def compute_core_area(area_px2: int, area_ambiguous_px2: int) -> tuple[int, bool]:
    """area_core_px2 = max(0, area_px2 - area_ambiguous_px2) -- the part of
    this edge's watershed-assigned area that sits OUTSIDE every junction's
    disputed disk at either endpoint. Provably <= area_px2 by construction
    (subtracting a non-negative quantity, clamped at 0) -- no empirical
    justification needed, unlike the ribbon-integral bound.

    Returns (area_core_px2, was_clamped). was_clamped=True means this
    edge's two endpoint disks' claims summed to more than its own area_px2
    (expected for very short inter-junction edges, since the two disks
    aren't deduplicated where they overlap) -- reported honestly as "no
    defensible core area for this edge", not silently negative.
    """
    core = area_px2 - area_ambiguous_px2
    return (max(0, core), core < 0)


def compute_edge_metrics(
    skel: skan.Skeleton,
    graph_result: GraphResult,
    mask_clean: np.ndarray,
    medial_radius: np.ndarray,
    *,
    width_trim_inner_px: float = WIDTH_TRIM_INNER_PX_PLACEHOLDER,
    area_ambiguity_radius_px: float = AREA_JUNCTION_BLOB_RADIUS_PLACEHOLDER,
) -> EdgeMetricsResult:
    summary = graph_result.summary
    node_coord = _node_coord_map(graph_result)

    watershed_result = partition_area_by_edge(skel, summary, mask_clean, medial_radius)
    ambiguity = compute_junction_blob_ambiguity(
        graph_result,
        mask_clean,
        medial_radius,
        watershed_result.labels,
        radius_px=area_ambiguity_radius_px,
    )

    ambiguous_by_edge: dict[int, int] = {}
    for jb in ambiguity:
        for path_index, px in jb.claims.items():
            ambiguous_by_edge[path_index] = ambiguous_by_edge.get(path_index, 0) + px

    per_edge: dict[int, EdgeMetrics] = {}
    total_length = 0.0
    n_width_ok = 0
    n_width_failed = 0
    length_excluded = 0.0
    weighted_width_sum = 0.0
    weighted_width_len = 0.0
    n_zero_core = 0
    n_ribbon_high = 0
    n_ribbon_low_eq = 0
    total_ribbon = 0.0

    for path_index, src_id, dst_id, length_px in zip(
        summary.index,
        summary["node_id_src"],
        summary["node_id_dst"],
        summary["branch_distance"],
    ):
        path_index = int(path_index)
        src_id = int(src_id)
        dst_id = int(dst_id)
        length_px = float(length_px)
        total_length += length_px

        width = measure_edge_width(
            skel,
            path_index,
            node_coord[src_id],
            node_coord[dst_id],
            medial_radius,
            trim_inner_px=width_trim_inner_px,
        )
        if width.ok:
            n_width_ok += 1
            weighted_width_sum += width.mean_px * length_px
            weighted_width_len += length_px
        else:
            n_width_failed += 1
            length_excluded += length_px

        area_px2 = watershed_result.area_px2.get(path_index, 0)
        area_ambiguous_px2 = ambiguous_by_edge.get(path_index, 0)
        area_ambiguous_frac = area_ambiguous_px2 / area_px2 if area_px2 > 0 else 0.0
        area_core_px2, was_clamped = compute_core_area(area_px2, area_ambiguous_px2)
        if was_clamped:
            n_zero_core += 1

        area_ribbon_px2 = estimate_edge_area_ribbon(skel, path_index, medial_radius)
        total_ribbon += area_ribbon_px2
        ribbon_diff = area_ribbon_px2 - area_px2
        if ribbon_diff > 0:
            n_ribbon_high += 1
        else:
            n_ribbon_low_eq += 1

        per_edge[path_index] = EdgeMetrics(
            path_index=path_index,
            node_id_src=src_id,
            node_id_dst=dst_id,
            length_px=length_px,
            width=width,
            area_px2=area_px2,
            area_ambiguous_px2=area_ambiguous_px2,
            area_ambiguous_frac=area_ambiguous_frac,
            area_core_px2=area_core_px2,
            core_was_clamped=was_clamped,
            area_ribbon_px2=area_ribbon_px2,
            ribbon_minus_watershed_px2=ribbon_diff,
        )

    mask_clean_total_px2 = int(mask_clean.sum())
    region_area_px2 = int(mask_clean.shape[0] * mask_clean.shape[1])
    length_weighted_mean_width_px = (
        weighted_width_sum / weighted_width_len if weighted_width_len > 0 else None
    )
    total_area_px2 = sum(m.area_px2 for m in per_edge.values())
    total_area_core_px2 = sum(m.area_core_px2 for m in per_edge.values())

    return EdgeMetricsResult(
        per_edge=per_edge,
        watershed=watershed_result,
        junction_blob_ambiguity=ambiguity,
        total_length_px=total_length,
        total_area_px2=total_area_px2,
        total_area_core_px2=total_area_core_px2,
        total_area_ribbon_px2=total_ribbon,
        mask_clean_total_px2=mask_clean_total_px2,
        n_unassigned_px=watershed_result.n_unassigned_px,
        n_zero_core_edges=n_zero_core,
        n_ribbon_high=n_ribbon_high,
        n_ribbon_low_or_equal=n_ribbon_low_eq,
        n_width_ok=n_width_ok,
        n_width_failed=n_width_failed,
        length_excluded_from_width_stat_px=length_excluded,
        length_weighted_mean_width_px=length_weighted_mean_width_px,
        region_area_px2=region_area_px2,
        crack_length_density_per_px=(total_length / region_area_px2 if region_area_px2 > 0 else 0.0),
        width_trim_inner_px=width_trim_inner_px,
        area_ambiguity_radius_px=area_ambiguity_radius_px,
    )


def write_edge_metrics_csv(result: EdgeMetricsResult, out_path: Path) -> None:
    """One row per path_index -- machine-readable bridge to a FUTURE
    multi-image, multi-condition batch comparison (SSC vs LSC, four
    Rakelspalt settings). That batch runner itself is out of scope here;
    this is only the per-image primitive it would consume.
    """
    rows = []
    for path_index, m in sorted(result.per_edge.items()):
        rows.append(
            {
                "path_index": path_index,
                "node_id_src": m.node_id_src,
                "node_id_dst": m.node_id_dst,
                "length_px": m.length_px,
                "width_n_samples": m.width.n_samples,
                "width_mean_px": m.width.mean_px,
                "width_median_px": m.width.median_px,
                "width_min_px": m.width.min_px,
                "width_max_px": m.width.max_px,
                "width_std_px": m.width.std_px,
                "width_ok": m.width.ok,
                "width_failure_reason": m.width.failure_reason,
                "area_px2": m.area_px2,
                "area_ambiguous_px2": m.area_ambiguous_px2,
                "area_ambiguous_frac": m.area_ambiguous_frac,
                "area_core_px2": m.area_core_px2,
                "core_was_clamped": m.core_was_clamped,
                "area_ribbon_px2": m.area_ribbon_px2,
                "ribbon_minus_watershed_px2": m.ribbon_minus_watershed_px2,
            }
        )
    pd.DataFrame(rows).to_csv(out_path, index=False)
