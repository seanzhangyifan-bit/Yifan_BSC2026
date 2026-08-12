# Glossary

One line per term, no elaboration — definitions drawn from existing prose in
[`CLAUDE.md`](CLAUDE.md) and [`README.md`](README.md), not invented here. For the
reasoning behind *why* the analysis targets these concepts rather than a full
chronology, read CLAUDE.md.

- **Partial order / poset** — an ordering where some pairs of elements have a known
  before/after relation and others simply don't; the analysis reconstructs this, not a
  full chronology, because a single micrograph gives no external timestamps.
- **Antichain** — a set of elements with no ordering relation between any pair of them:
  mutually undatable relative to each other.
- **Width `w`** — the size of the largest antichain in the precedence poset: the count of
  cracks that can't be dated relative to each other, and an index of how concurrent vs.
  hierarchical the cracking was.
- **T-junction** — one crack meeting another at ~90°; certifies exactly one local fact —
  the crack that abuts arrived after the crack it hit, at that point.
- **Y-junction** — a degree-3 junction with three ~120° sector gaps between arms;
  indicates concurrent growth and carries no ordering signal.
- **Abutter** — at a T-junction, the arc whose tip stopped upon meeting another crack; it
  arrived *after* the host.
- **Host arc** — at a T-junction, the arc that was already there when the abutter's tip
  reached it; the *earlier* of the two.
- **Annulus** — the donut-shaped region around a junction vertex (inner radius a few px,
  outer radius ~h/2) used to measure each arm's local approach direction, avoiding both
  vertex-pixel jitter and far-field curvature.
- **Generation** — a junction/edge's position in the topological order of the precedence
  graph (earlier ⇒ smaller number); undetermined (`None`) for anything caught inside an
  unresolved cycle.
- **Growth-arc** — an oriented crack segment, the atomic unit of the partial order
  (preferred over whole cracks, since a through-line may actually be two arrested cracks
  meeting head-on).
