"""Analyse crack micrographs: one row of numbers per image and region.

    image --> engine (once) --> regions --> measurements --> results.xlsx + figures

Examples:
    # Crack stats for every image in a folder, whole image (the thesis table)
    python3 -m src.analyze ../data/raw/T5 --out-dir outputs/t5

    # 3x3 grid, only the left column, with tortuosity and anisotropy
    python3 -m src.analyze image.jpg --regions grid --grid 3x3 --cells 1,4,7 \\
        --measure crack_stats tortuosity anisotropy

    # Centre half of the image, a different microscope calibration
    python3 -m src.analyze image.jpg --regions centre --centre-frac 0.5 --um-per-px 0.5

Outputs, under --out-dir: results.xlsx (sheets: regions, image_connectivity,
segments, settings) and <source folder>/<image>_*.png figures.
"""

import argparse
from pathlib import Path

from src.crackgraph.analysis import SCALE_BAR_CHECKED, SCALE_BAR_NOT_CHECKED, analyze_image
from src.crackgraph.export import FIGURES, write_figures, write_workbook
from src.crackgraph.regions import REGION_MODES, RegionSpec
from src.crackgraph.settings import CRACK_STATS_GROUPS, DEFAULT_UM_PER_PX, MEASUREMENTS, AnalysisSettings

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def find_images(paths: list[str]) -> list[Path]:
    """Image files named directly, plus every image file under named folders."""
    found = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES)
        elif p.is_file():
            found.append(p)
        else:
            raise SystemExit(f"Not found: {p}")
    if not found:
        raise SystemExit("No image files found in the given paths.")
    return found


def _grid(text: str) -> tuple[int, int]:
    try:
        rows, cols = (int(x) for x in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"grid must look like 3x3, got {text!r}")
    return rows, cols


def _int_list(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.split(",") if x.strip())


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("images", nargs="+", help="Image files and/or folders (searched recursively).")
    p.add_argument("--out-dir", default="outputs/analysis")

    g = p.add_argument_group("calibration")
    g.add_argument("--um-per-px", type=float, default=DEFAULT_UM_PER_PX,
                   help=f"Microscope calibration (default {DEFAULT_UM_PER_PX:.4f}, the thesis images).")

    g = p.add_argument_group("regions")
    g.add_argument("--regions", choices=REGION_MODES, default="whole")
    g.add_argument("--centre-frac", type=float, default=0.5,
                   help="For --regions centre: share of width and height (0.5 = middle half).")
    g.add_argument("--grid", type=_grid, default=(2, 2), help="For --regions grid: ROWSxCOLS, e.g. 3x3.")
    g.add_argument("--cells", type=_int_list, default=None,
                   help="For --regions grid: cells to report, numbered row by row from 1 (default: all).")

    g = p.add_argument_group("what to measure")
    g.add_argument("--measure", nargs="+", choices=MEASUREMENTS, default=["crack_stats"])
    g.add_argument("--groups", type=lambda s: tuple(s.split(",")), default=CRACK_STATS_GROUPS,
                   help=f"Crack-stats column groups, comma-separated (default all: {','.join(CRACK_STATS_GROUPS)}).")
    g.add_argument("--runtime", action="store_true", help="Add runtime columns.")
    g.add_argument("--scale-bars-checked", action="store_true",
                   help="Record scale_bar_check as visually confirmed. Only if you checked every image.")

    g = p.add_argument_group("figures")
    g.add_argument("--figures", nargs="*", choices=FIGURES, default=["overlay"])
    g.add_argument("--map-column", default="crack_area_pct", help="Column drawn by the 'map' figure.")
    return p.parse_args(argv)


def settings_from_args(args) -> AnalysisSettings:
    n_rows, n_cols = args.grid
    return AnalysisSettings(
        um_per_px=args.um_per_px,
        regions=RegionSpec(mode=args.regions, centre_frac=args.centre_frac,
                           n_rows=n_rows, n_cols=n_cols, cells=args.cells),
        measurements=tuple(args.measure),
        crack_stats_groups=tuple(args.groups),
        include_runtime=args.runtime,
    )


def main(argv=None):
    args = parse_args(argv)
    settings = settings_from_args(args)
    images = find_images(args.images)
    out_dir = Path(args.out_dir)
    scale_bar_check = SCALE_BAR_CHECKED if args.scale_bars_checked else SCALE_BAR_NOT_CHECKED

    print(f"Regions: {settings.regions.describe()}; measuring: {', '.join(settings.measurements)}")
    print(f"Calibration: {settings.um_per_px:.4f} µm/px -> spur cut-off {settings.spur_px:g} px, "
          f"dark-speck limit {settings.dark_speck_area_px} px")
    analyses = []
    for i, image in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {image}")
        analysis = analyze_image(image, settings, scale_bar_check=scale_bar_check)
        for path in write_figures(analysis, out_dir, tuple(args.figures), args.map_column):
            print(f"    figure: {path}")
        analyses.append(analysis)

    xlsx = out_dir / "results.xlsx"
    write_workbook(analyses, settings, xlsx)
    print(f"\nWrote {sum(len(a.rows) for a in analyses)} rows to {xlsx}")


if __name__ == "__main__":
    main()
