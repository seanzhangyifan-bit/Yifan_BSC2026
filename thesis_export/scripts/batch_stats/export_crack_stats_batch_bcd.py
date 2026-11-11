"""One-off crack-stats run over three specific thesis batches (B/C/D),
not the full default dataset scripts/batch_stats/export_crack_stats.py's own main()
covers.

Batch B -- T5 gap-height variation, PTFE (8 files, characterization2_ptfe/):
    T5-PTFE_H50/H95/H145/H190, each v1/v2.
Batch C -- T5 dew-point/humidity variation, membrane (5 files,
    humidity_loading/): 0RH_NR212, 23RH_NR212 (v1/v2 each), 75RH_NR212_v1
    only -- 75RH_NR212_v2 is excluded at the author's request (flagged as anomalous
    during data review).
Batch D -- T2/T3/T4, membrane, low-gap-height variant (6 files): T2-M_H90_v1/v2,
    T3-M_H95_v1/v2, T4-M_H95_v1/v2. T2-M_H90 comes from "Pt Kat Characterization 2"
    (same OneDrive source project as T3/T4's _H95 files) -- not
    data/raw/aquivion_t2_membran/, which traces back to a different OneDrive
    project ("Pt Kat Aquivion T2") entirely and is not a gap-height variant of
    the same T2 series.

Usage:
    python3 -m scripts.batch_stats.export_crack_stats_batch_bcd [--data-dir data/raw]
        [--out outputs/crack_stats_batch_bcd.xlsx] [--scale-bars-checked]

File paths below are relative to --data-dir. See export_crack_stats.py's
docstring for --data-dir and --scale-bars-checked.
"""

import argparse
from pathlib import Path

import pandas as pd

from scripts.batch_stats.export_crack_stats import SCALE_BAR_CHECKED, SCALE_BAR_NOT_CHECKED, add_batch_args, compute_row

BATCH_B_T5_GAP_HEIGHT_PTFE = [
    "characterization2_ptfe/T5-PTFE_H50_v1_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H50_v2_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H95_v1_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H95_v2_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H145_v1_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H145_v2_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H190_v1_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H190_v2_mm000001.jpg",
]

BATCH_C_T5_DEWPOINT_MEMBRANE = [
    "humidity_loading/0RH_NR212_v1_mm000001.jpg",
    "humidity_loading/0RH_NR212_v2_mm000001.jpg",
    "humidity_loading/23RH_NR212_v1_mm000001.jpg",
    "humidity_loading/23RH_NR212_v2_mm000001.jpg",
    "humidity_loading/75RH_NR212_v1_mm000001.jpg",
    # 75RH_NR212_v2_mm000001.jpg deliberately omitted -- see module docstring.
]

BATCH_D_T2_T3_T4_MEMBRANE_H95 = [
    "characterization2_membran/T2-M_H90_v1_mm000001.jpg",
    "characterization2_membran/T2-M_H90_v2_mm000001.jpg",
    "characterization2_membran/T3-M_H95_v1_mm000001.jpg",
    "characterization2_membran/T3-M_H95_v2_mm000001.jpg",
    "characterization2_membran/T4-M_H95_v1_mm000001.jpg",
    "characterization2_membran/T4-M_H95_v2_mm000001.jpg",
]

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=str, default="outputs/crack_stats_batch_bcd.xlsx")
    p.add_argument("--cache-dir", type=str, default=None)
    add_batch_args(p)
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = (repo_root / args.data_dir).resolve()
    scale_bar_check = SCALE_BAR_CHECKED if args.scale_bars_checked else SCALE_BAR_NOT_CHECKED
    cache_dir = repo_root / args.cache_dir if args.cache_dir else None

    groups = [
        ("B", BATCH_B_T5_GAP_HEIGHT_PTFE),
        ("C", BATCH_C_T5_DEWPOINT_MEMBRANE),
        ("D", BATCH_D_T2_T3_T4_MEMBRANE_H95),
    ]
    all_paths = [(label, data_dir / rel) for label, paths in groups for rel in paths]
    missing = [path for _, path in all_paths if not path.exists()]
    if missing:
        listed = "\n  ".join(str(path.relative_to(data_dir)) for path in missing)
        raise SystemExit(
            f"{len(missing)} of {len(all_paths)} batch images not found under {data_dir}:\n  {listed}\n"
            "Pass --data-dir to point at your micrograph folder."
        )

    rows = []
    for i, (label, image_path) in enumerate(all_paths, 1):
        print(f"[{i}/{len(all_paths)}] batch {label}: {image_path.relative_to(data_dir)}")
        row = compute_row(image_path, cache_dir=cache_dir, scale_bar_check=scale_bar_check)
        row["batch"] = label
        rows.append(row)

    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, sheet_name="crack_stats_bcd")
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
