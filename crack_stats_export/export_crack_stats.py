"""Export a small, standalone crack-statistics table for external consumption.

Deliberately stripped to stage 1-3 only (binarize -> skeletonize -> graph
extraction) -- no junction classification, corner cross-check, anisotropy,
or curvature. Those stages exist for the parent project's own crack-growth-
ordering work (reconstructing a partial order of which crack arrived after
which, from junction geometry); this export only wants area, width, edge
length, and network-connectivity summary stats, and doesn't need any of
that machinery. See docs/crack_stats_schema.md for the full column
reference this script's output is documented against -- keep the two in
sync if either changes.

STANDALONE EXPORT NOTE: this file is a frozen, minimally-adjusted copy of
`scripts/export_crack_stats.py` from the parent repository, packaged here
with its complete (and only) dependency set -- see README.md for the two
specific adjustments made (import paths, and how `repo_root` is located)
to make it runnable outside that repository. The logic, comments, and
calibration/exclusion constants below are otherwise untouched.

Usage:
    python3 export_crack_stats.py [--out crack_stats.xlsx]
        [--input-dir data/raw] [--pattern "**/*_mm000001.jpg"]
        [--um-per-px 0.609756]

    By default, expects a `data/raw/` folder next to this script, laid out
    exactly like the parent project's own raw-image catalogue (see
    README.md) -- this export does not bundle that private raw dataset, so
    running it as-is against an empty/missing data/raw/ will correctly exit
    with "no images matched" rather than silently doing nothing.

    Point it at a different folder/naming convention/calibration with
    --input-dir/--pattern/--um-per-px -- see README.md for a worked example.
    Defaults reproduce this project's own original behavior exactly.
"""

import argparse
from pathlib import Path

import networkx as nx
import pandas as pd

from crackgraph.binarize import binarize
from crackgraph.graph import extract_graph
from crackgraph.io_utils import load_image
from crackgraph.skeleton import skeletonize_and_prune

# Source: an external calibration tool (figlib/calibration.py,
# calibration.json) that is NOT part of this repository -- this is a
# hand-carried snapshot of that tool's output, not derived here and not
# re-derived by eye. Valid for the "mm" (full-resolution stitched mosaic)
# tag ONLY -- do not apply to 100x/200x/300x/500x/800x single-tile frames,
# which have their own, different factors. If this repo ever imports that
# tool directly, figlib.calibration.um_per_px("mm") should replace this
# constant as the live source of truth.
#
# This is this PROJECT's calibration, tied to its specific microscope/
# capture setup -- not a universal constant. Override with --um-per-px for
# a different dataset; there is no way to auto-detect the right value, so
# an unchanged default on someone else's images will silently produce
# wrong physical-unit columns rather than erroring. Caller's responsibility.
UM_PER_PX_MM_TAG = 100 / 164  # 0.609756... um/px

# The four constants below (KNOWN_BAD_FRAME_SUBSTRINGS, CONFIRMED_SCALE_BAR_
# IMAGES, ADDITIONAL_IMAGES, and the default --pattern) are curated facts
# about THIS project's specific raw-image catalogue, not general-purpose
# parameters -- if you point this script at your own --input-dir with
# different filenames, these three lists will simply match nothing and be
# harmless no-ops, not errors. Edit them (or ignore them) for your own data.

# Filenames confirmed to be mistagged as "mm" but are not the standard
# mosaic capture (would read ~2x too small if calibrated with the factor
# above). This pattern can't actually match the default --pattern below
# (wrong suffix, 000000 not 000001) but is kept here, checked explicitly,
# as a second, independent guard rather than relying on the glob alone.
KNOWN_BAD_FRAME_SUBSTRINGS = ["_D_mm000000"]

# The "*_mm000001.jpg" naming convention is NOT a reliable guarantee of "no
# blue scale-bar overlay" -- it's just usually true. Every candidate file
# was directly viewed (bottom-right corner crop) rather than trusted on the
# naming pattern alone, and it broke in more than one way over the life of
# this export -- see docs/crack_stats_schema.md SS2/2b/2d for the full
# verification history. Filenames confirmed to carry a scale bar despite
# matching the naming pattern are excluded entirely here, not just
# calibration-nulled, because they violate the actual selection criterion
# (no scale bar). If more images are ever added to data/raw/, re-verify by
# eye -- don't trust the 000001 suffix alone.
CONFIRMED_SCALE_BAR_IMAGES = ["T5-M_H190_v2_mm000001.jpg"]

# Sample where the default *_mm000001.jpg index is the wrong (undersized) capture --
# this sample's actual mm000000/mm000001 pair is 4429x3322, not the standard ~7300x7600
# every other row has. mm000002/mm000003 are the standard-sized pair; mm000002 carries
# the blue scale bar, mm000003 doesn't. See docs/crack_stats_schema.md S7b.
# Path is relative to --input-dir (not to the repo root) so it still resolves
# correctly if --input-dir is overridden.
ADDITIONAL_IMAGES = ["humidity_loading_ptfe/23RH_PTFE_v1_mm000003.jpg"]

DEFAULT_INPUT_DIR = "data/raw"
DEFAULT_PATTERN = "**/*_mm000001.jpg"


def compute_row(image_path: Path, um_per_px: float = UM_PER_PX_MM_TAG) -> dict:
    """Run one micrograph through binarize -> skeletonize -> graph-extract
    and derive one row's worth of summary statistics from the result.

    Every quantity here is either read directly off the pixels/graph
    (`measured`), a stated formula applied on top of a measured quantity
    (`interpreted`), or dependent on the `um_per_px` calibration factor
    (`calibrated`) -- see docs/crack_stats_schema.md SS4-5 for the
    authoritative column-by-column evidence-level tagging; this docstring
    is a pointer to that, not a duplicate of it. `um_per_px` defaults to
    this project's own `UM_PER_PX_MM_TAG` (see --um-per-px to override).
    """
    gray, _rgb = load_image(image_path)
    full_h, full_w = gray.shape

    binarize_result = binarize(gray)
    skeleton_result = skeletonize_and_prune(binarize_result.mask, source_image=gray)
    graph_result = extract_graph(skeleton_result.skeleton)

    crack_area_px2 = binarize_result.foreground_fraction * full_w * full_h
    total_length_px = float(graph_result.summary["branch_distance"].sum())

    avg_width_px = crack_area_px2 / total_length_px if total_length_px > 0 else float("nan")
    avg_edge_length_px = (
        total_length_px / graph_result.n_edges if graph_result.n_edges > 0 else float("nan")
    )

    # Percolation view of the same graph: how many disconnected crack
    # fragments survived stage 2's pruning (fragments/spurs shorter than
    # spur_px_threshold are already gone before this ever runs -- these
    # counts are "components at least that long," not literally every
    # mark in the raw mask), and what share of total crack length belongs
    # to the single largest one.
    G = nx.from_pandas_edgelist(
        graph_result.summary, source="node_id_src", target="node_id_dst",
        edge_attr="branch_distance",
    )
    n_components = nx.number_connected_components(G)
    if n_components > 0:
        component_lengths = [
            sum(d["branch_distance"] for _, _, d in G.subgraph(c).edges(data=True))
            for c in nx.connected_components(G)
        ]
        giant_component_fraction = max(component_lengths) / total_length_px
    else:
        giant_component_fraction = float("nan")

    is_bad_frame = any(s in image_path.name for s in KNOWN_BAD_FRAME_SUBSTRINGS)
    if is_bad_frame:
        crack_area_mm2 = avg_width_um = avg_edge_length_um = None
    else:
        crack_area_mm2 = crack_area_px2 * (um_per_px ** 2) / 1e6
        avg_width_um = avg_width_px * um_per_px
        avg_edge_length_um = avg_edge_length_px * um_per_px

    return {
        "image_filename": image_path.name,
        "source_folder": image_path.parent.name,
        "image_width_px": full_w,
        "image_height_px": full_h,
        "scale_bar_check": "no blue bar (visually confirmed)",
        "crack_area_pct": binarize_result.foreground_fraction * 100,
        "crack_area_mm2": crack_area_mm2,
        "avg_width_px": avg_width_px,
        "avg_width_um": avg_width_um,
        "avg_edge_length_px": avg_edge_length_px,
        "avg_edge_length_um": avg_edge_length_um,
        "n_components": n_components,
        "giant_component_fraction": giant_component_fraction,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=str, default="crack_stats.xlsx")
    p.add_argument(
        "--input-dir", type=str, default=DEFAULT_INPUT_DIR,
        help=f"Folder to search for images, relative to this script (default: {DEFAULT_INPUT_DIR!r}).",
    )
    p.add_argument(
        "--pattern", type=str, default=DEFAULT_PATTERN,
        help=f"Glob pattern to match within --input-dir (default: {DEFAULT_PATTERN!r}).",
    )
    p.add_argument(
        "--um-per-px", type=float, default=UM_PER_PX_MM_TAG,
        help=f"Physical calibration factor for the calibrated columns "
             f"(default: {UM_PER_PX_MM_TAG!r}, this project's own mm-tag "
             "value -- see docs/crack_stats_schema.md SS6). Not auto-detected; "
             "supply the right value for your own capture setup.",
    )
    args = p.parse_args()

    # STANDALONE ADJUSTMENT: in the parent repo this script lives two
    # levels under the repo root (scripts/export_crack_stats.py), so
    # repo_root was `Path(__file__).resolve().parent.parent`. Here the
    # script sits directly at this export folder's root (one level
    # shallower), so repo_root is just its own parent directory.
    repo_root = Path(__file__).resolve().parent
    input_dir = repo_root / args.input_dir

    # ADDITIONAL_IMAGES is a fixed list of filenames specific to the
    # original dataset (see its own comment above) -- existence-checked
    # here, not just globbed, so pointing --input-dir at a different
    # dataset makes it a harmless no-op rather than a crash on a file that
    # was never going to be there.
    extra_paths = []
    for rel in ADDITIONAL_IMAGES:
        candidate = input_dir / rel
        if candidate.exists():
            extra_paths.append(candidate)
        else:
            print(f"[note] ADDITIONAL_IMAGES entry not found under {input_dir}, skipped: {rel} "
                  "(specific to the original dataset -- expected if you're using --input-dir "
                  "for your own data)")

    all_image_paths = sorted(input_dir.glob(args.pattern)) + extra_paths
    if not all_image_paths:
        raise SystemExit(
            f"No images matched {args.pattern!r} under {input_dir}. This export "
            "does not bundle the private raw micrograph dataset -- see "
            "README.md, or pass --input-dir/--pattern to point at your own images."
        )

    image_paths = [p for p in all_image_paths if p.name not in CONFIRMED_SCALE_BAR_IMAGES]
    skipped = [p for p in all_image_paths if p.name in CONFIRMED_SCALE_BAR_IMAGES]
    for p in skipped:
        print(f"[skip] {p.relative_to(repo_root)} -- confirmed blue scale-bar overlay, excluded")

    rows = []
    for i, image_path in enumerate(image_paths, 1):
        print(f"[{i}/{len(image_paths)}] {image_path.relative_to(repo_root)}")
        rows.append(compute_row(image_path, um_per_px=args.um_per_px))

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, sheet_name="crack_stats")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
