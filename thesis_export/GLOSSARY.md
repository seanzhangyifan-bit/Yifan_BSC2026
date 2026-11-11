# Glossary

One line per term, no elaboration. For the reasoning behind the analysis, read
[`METHODOLOGY.md`](METHODOLOGY.md).

- **Skeleton** — the crack mask thinned to 1-pixel-wide centre lines, keeping its
  connectivity (homotopy-preserving thinning).
- **Node** — a junction or a loose end of the skeleton.
- **Degree** — how many segments meet at a node: 1 = loose end, 3 = three-way junction,
  4+ = crossing.
- **Segment / edge / path** — one stretch of skeleton between two nodes, numbered by skan's
  `path_index`.
- **Junction blob** — the patch of crack pixels where several segments meet; it doesn't
  clearly belong to any one segment, so per-segment area there is bracketed, not exact.
- **Flaking** — patches where the catalyst layer has come off, exposing substrate; bright like
  a crack but not a fracture, so segments touching them are left out of the stats.
- **Giant component** — the connected piece of the crack network with the most total crack
  length.
- **Tortuosity** — a segment's path length divided by the straight-line distance between its
  ends; 1 = perfectly straight.
- **Anisotropy** — how strongly the crack segments point in one dominant direction, from the
  length-weighted 2nd-order orientation tensor (0 = no preferred direction).
