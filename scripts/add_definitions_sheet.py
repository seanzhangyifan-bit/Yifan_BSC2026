"""One-off: add a `definitions` sheet to a crack_stats_v3 workbook.

Short, one-line definitions for the substantive stats columns (crack area,
width, edge length, connectivity, flaking, pruning-count), condensed from
`docs/crack_stats_schema.md`'s existing per-column reference (`crack_stats.xlsx`'s
schema doc) -- reusing that already-vetted text rather than re-deriving
definitions from scratch. Deliberately skips pure identifier/provenance
columns (`image_filename`, `source_folder`, `image_width_px`/`image_height_px`,
`scale_bar_check`, `batch`) and the `runtime_*` timing columns -- this sheet
is about what the crack-pattern measurements *mean*, not about row
identity or how long a row took to compute.

Two columns' definitions are written fresh here rather than copied verbatim
from the schema doc, because crack_stats_v3's semantics genuinely differ
from the crack_stats.xlsx/v2 lineage that doc describes: `flaking_n_edges_omitted`
(v3 omits touching edges from the connectivity graph G entirely, whereas v1's
`flaking_n_edges_excluded_near_cut` keeps them in G and only drops them from
length/width stats) and `n_components`/`giant_component_fraction` (v3's version
of "the full graph" already has flaking-touching edges removed, so these counts
are computed on a stricter graph than v1's).

Usage:
    python3 -m scripts.add_definitions_sheet [--xlsx outputs/crack_stats_v3_batch_bcd.xlsx]
"""

import argparse
from copy import copy
from pathlib import Path

from openpyxl import load_workbook

# (column, definition, unit, evidence tag) -- tag legend matches this
# project's own convention (measured / interpreted / calibrated), see
# docs/crack_stats_schema.md Sec. 5.
DEFINITIONS = [
    ("crack_area_pct",
     "Share of image pixels classified as crack by Otsu thresholding, after flaking exclusion and despeckling.",
     "% of image area", "measured"),
    ("crack_area_pct_excl_flakes",
     "Same crack-pixel count as crack_area_pct, but the denominator excludes the flaking-exclusion area instead of the whole image (that area is missing material, not confirmed non-crack).",
     "% of non-excluded image area", "measured"),
    ("crack_area_mm2",
     "crack_area_pct's pixel count converted to physical area via the 0.6098 um/px mosaic calibration factor.",
     "mm^2", "calibrated"),
    ("avg_width_px",
     "Crude width estimate: total crack area divided by total skeleton length. An area/length ratio, not a direct per-pixel measurement -- see median_width_px for that.",
     "px", "interpreted"),
    ("avg_width_um",
     "avg_width_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("median_width_px",
     "Median of (2 x local medial radius) sampled at every pixel of every non-omitted skeleton edge -- a direct per-pixel distance-transform width measurement.",
     "px", "interpreted"),
    ("median_width_um",
     "median_width_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("avg_edge_length_px",
     "Mean length of one graph edge (distance between one junction/endpoint and the next) among non-omitted edges. Not the mean length of a whole physical crack -- a crack passing through several junctions counts as several edges.",
     "px", "measured"),
    ("avg_edge_length_um",
     "avg_edge_length_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("median_edge_length_px",
     "Median (rather than mean) graph edge length among non-omitted edges -- less sensitive to a few very long or very short edges than avg_edge_length_px.",
     "px", "interpreted"),
    ("median_edge_length_um",
     "median_edge_length_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("median_edge_length_gc_px",
     "Same as median_edge_length_px, restricted to edges whose both endpoints lie in the giant (largest, by total length) connected component.",
     "px", "interpreted"),
    ("median_edge_length_gc_um",
     "median_edge_length_gc_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("n_components",
     "Number of disconnected pieces in the crack-network graph, after crack_stats_v3's omit-by-membership flaking exclusion has already been applied to the graph itself (stricter than crack_stats v1, which keeps flaking-touching edges in the graph and only drops them from length/width stats).",
     "count", "measured"),
    ("giant_component_fraction",
     "Share of total crack length belonging to the single largest connected component. 1.0 means one fully connected network; well below 1 means the crack pattern is still fragmented into separate islands.",
     "fraction, 0-1", "measured"),
    ("giant_component_span_px",
     "Straight-line distance between the two farthest-apart points on the giant component's own skeleton pixel path (every pixel, not just junction/endpoint node coordinates) -- physical spatial reach of the largest connected network.",
     "px", "interpreted"),
    ("giant_component_span_um",
     "giant_component_span_px converted to microns via the 0.6098 um/px calibration factor.",
     "um", "calibrated"),
    ("flaking_excluded_area_pct",
     "Share of image area identified as flaking/delamination (catalyst layer physically missing, not fractured) and excluded before skeletonization even runs.",
     "% of image area", "measured"),
    ("flaking_n_candidates",
     "Number of flaking/delamination regions identified (local width far exceeding the image's own typical crack width, grown back out to their true boundary). Read as 'candidates passing the width test', not a confirmed count -- see docs/crack_stats_schema.md Sec. 4b for a known false-positive gap.",
     "count", "interpreted"),
    ("flaking_n_edges_omitted",
     "Number of graph edges with any pixel inside a flaking-exclusion region, omitted entirely -- from both the stats columns above AND the connectivity graph itself (n_components/giant_component_fraction). This is crack_stats_v3's key methodology difference from v1, which keeps these edges in the graph and only drops them from length/width stats.",
     "count", "measured"),
    ("n_corner_artifacts_pruned",
     "Number of skeleton branches removed during pruning because their local width trends monotonically along their length (a medial-axis branch tracing into a concave mask-boundary corner), rather than because they were short.",
     "count", "interpreted"),
]

HEADER = ["Column", "Definition", "Unit", "Evidence tag"]


def add_definitions_sheet(xlsx_path: Path, sheet_name: str = "definitions") -> None:
    wb = load_workbook(xlsx_path)
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    ws.append(HEADER)
    for row in DEFINITIONS:
        ws.append(list(row))
    widths = [28, 100, 22, 14]
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width
    for cell in ws[1]:
        bold_font = copy(cell.font)
        bold_font.bold = True
        cell.font = bold_font
    wb.save(xlsx_path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=str, default="outputs/crack_stats_v3_batch_bcd.xlsx")
    args = p.parse_args()
    xlsx_path = Path(args.xlsx)
    add_definitions_sheet(xlsx_path)
    print(f"Added/replaced 'definitions' sheet ({len(DEFINITIONS)} rows) in {xlsx_path}")


if __name__ == "__main__":
    main()
