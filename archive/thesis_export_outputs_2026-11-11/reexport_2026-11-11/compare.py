"""Compare thesis_stats before vs after the host-stub + dark-speck change (same code otherwise)."""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
b = pd.read_excel(D / "before" / "thesis_stats.xlsx").set_index("image_filename")
a = pd.read_excel(D / "after" / "thesis_stats.xlsx").set_index("image_filename").loc[b.index]
COLS = ["crack", "flaking", "wcrack", "N", "fgc", "ledge", "ledge_gc", "dgc"]
cond = b.index.str.replace(r"_v\d+.*", "", regex=True)

print("## Per image: % change after vs before")
pct = (100 * (a[COLS] - b[COLS]) / b[COLS].replace(0, np.nan)).round(1)
pct.index = [i.replace("_mm000001.jpg", "") for i in pct.index]
print(pct.to_string())
print("\nmax |change| per column:", pct.abs().max().round(1).to_dict())

print("\n## Per condition: ledge (µm), mean of replicates, and replicate spread (max-min)/mean")
rows = []
for c in dict.fromkeys(cond):
    m = cond == c
    lb, la = b.loc[m, "ledge"], a.loc[m, "ledge"]
    rows.append({"condition": c, "n": int(m.sum()), "ledge before": round(lb.mean(), 1), "ledge after": round(la.mean(), 1),
                 "change %": round(100 * (la.mean() - lb.mean()) / lb.mean(), 1),
                 "rep spread before %": round(100 * (lb.max() - lb.min()) / lb.mean(), 1) if m.sum() > 1 else None,
                 "rep spread after %": round(100 * (la.max() - la.min()) / la.mean(), 1) if m.sum() > 1 else None})
cdf = pd.DataFrame(rows).set_index("condition")
print(cdf.to_string())

GROUPS = {"solvent ratio (membrane)": ["T2-A_membran", "T3-M", "T4-M"],
          "humidity (NR212)": ["0RH_NR212", "23RH_NR212", "75RH_NR212"],
          "gap height (T5 PTFE)": ["T5-PTFE_H50", "T5-PTFE_H95", "T5-PTFE_H145", "T5-PTFE_H190"]}
print("\n## Within each comparison group: ledge ranking and pairwise ratios")
for g, cs in GROUPS.items():
    rb = sorted(cs, key=lambda c: cdf.at[c, "ledge before"])
    ra = sorted(cs, key=lambda c: cdf.at[c, "ledge after"])
    print(f"\n{g}: ranking before {rb}\n{' ' * len(g)}  ranking after  {ra}  -> {'SAME' if rb == ra else 'CHANGED'}")
    for c1, c2 in itertools.combinations(cs, 2):
        r_b = cdf.at[c1, "ledge before"] / cdf.at[c2, "ledge before"]
        r_a = cdf.at[c1, "ledge after"] / cdf.at[c2, "ledge after"]
        print(f"   {c1} / {c2}: {r_b:.2f} -> {r_a:.2f}")
