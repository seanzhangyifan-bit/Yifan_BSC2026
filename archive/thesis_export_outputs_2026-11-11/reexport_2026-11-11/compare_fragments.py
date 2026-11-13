"""Fragment removal on (current pipeline, after/) vs off (fragments_kept/), 19 thesis images."""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
UM = 100 / 164


def load(name):
    c = pd.read_excel(D / name / "crack_stats.xlsx").set_index("image_filename")
    t = pd.read_excel(D / name / "thesis_stats.xlsx").set_index("image_filename")
    # total length of edges used for length stats = crack area / average width (as defined in the export)
    t["length_mm"] = (c.crack_area_pct / 100 * c.image_width_px * c.image_height_px / c.avg_width_px) * UM / 1000
    return t


on, off = load("after"), load("fragments_kept")
off = off.loc[on.index]
COLS = ["N", "length_mm", "ledge", "ledge_gc", "fgc", "dgc", "wcrack", "crack"]
cond = on.index.str.replace(r"_v\d+.*", "", regex=True)
short = [i.replace("_mm000001.jpg", "") for i in on.index]

print("## Per image: removed (current) -> kept")
tab = pd.DataFrame({
    "N": [f"{int(a)} -> {int(b)}" for a, b in zip(on.N, off.N)],
    "N change %": (100 * (off.N - on.N) / on.N).round(0).values,
    "length mm": [f"{a:.1f} -> {b:.1f}" for a, b in zip(on.length_mm, off.length_mm)],
    "length %": (100 * (off.length_mm - on.length_mm) / on.length_mm).round(1).values,
    "ledge %": (100 * (off.ledge - on.ledge) / on.ledge).round(1).values,
    "fgc": [f"{a:.3f} -> {b:.3f}" for a, b in zip(on.fgc, off.fgc)],
    "wcrack %": (100 * (off.wcrack - on.wcrack) / on.wcrack).round(1).values,
    "crack %": (100 * (off.crack - on.crack) / on.crack).round(2).values,
}, index=short)
print(tab.to_string())

print("\n## Per condition: mean over replicates, replicate spread (max-min)/mean")
rows = []
for c in dict.fromkeys(cond):
    m = cond == c
    r = {"condition": c, "n": int(m.sum())}
    for col in ("N", "ledge"):
        a, b = on.loc[m, col], off.loc[m, col]
        r[f"{col} removed"] = round(a.mean(), 1)
        r[f"{col} kept"] = round(b.mean(), 1)
        r[f"{col} spread removed %"] = round(100 * (a.max() - a.min()) / a.mean(), 0) if m.sum() > 1 else None
        r[f"{col} spread kept %"] = round(100 * (b.max() - b.min()) / b.mean(), 0) if m.sum() > 1 else None
    rows.append(r)
cdf = pd.DataFrame(rows).set_index("condition")
print(cdf.to_string())

GROUPS = {"solvent ratio (membrane)": ["T2-A_membran", "T3-M", "T4-M"],
          "humidity (NR212)": ["0RH_NR212", "23RH_NR212", "75RH_NR212"],
          "gap height (T5 PTFE)": ["T5-PTFE_H50", "T5-PTFE_H95", "T5-PTFE_H145", "T5-PTFE_H190"]}
print("\n## Rankings within each comparison group (low -> high)")
for g, cs in GROUPS.items():
    for col in ("N", "ledge"):
        ra = sorted(cs, key=lambda c: cdf.at[c, f"{col} removed"])
        rb = sorted(cs, key=lambda c: cdf.at[c, f"{col} kept"])
        print(f"{g}, {col}: removed {ra}\n{' ' * (len(g) + len(col) + 2)}  kept    {rb}  -> {'SAME' if ra == rb else 'CHANGED'}")
    for c1, c2 in itertools.combinations(cs, 2):
        print(f"   N ratio {c1}/{c2}: {cdf.at[c1, 'N removed'] / cdf.at[c2, 'N removed']:.2f} -> "
              f"{cdf.at[c1, 'N kept'] / cdf.at[c2, 'N kept']:.2f}")
