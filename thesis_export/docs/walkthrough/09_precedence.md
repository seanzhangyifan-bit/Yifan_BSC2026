# 9. Precedence graph: which crack came first

**File**: `src/crackgraph/precedence.py` (246 lines)

**What it does.** It collects every T-junction's local fact, "the host was there before the
abutter", into one **directed graph**:
- **Nodes** are crack segments (`path_index`).
- **Arrows** run from older to younger.

It then reports:
- **Generations**: how many "was-there-before" steps lead to each segment.
- **Cycles**: groups of segments that each claim to come before another in the group. A cycle is
  impossible in reality. It means a misread junction, or cracks that formed at nearly the same
  time.

**The core principle (`METHODOLOGY.md`).** A single micrograph can't give a full timeline. A T
only says "older than" *at that one meeting point*. The result is a **partial order**: many
pairs of segments stay undated, and that incompleteness is a real result, not a failure. This
file never guesses a missing relation.

**Not done yet, on purpose.** It doesn't remove cycles to force a clean order, and it doesn't
compute the width `w` (the largest set of mutually undatable segments). Both were deferred until
the first-pass graph had been looked at on real data.

---

## Where the arrows come from: two methods, combined with provenance

For each junction, both `junctions.py` (the "tangent fit") and `corners.py` may say "T, with
this abutter":

| Situation | Result |
|---|---|
| Both say T and agree on the abutter | Arrows emitted, tagged "both methods agree" |
| Only one says T | Arrows emitted, tagged with that method |
| Both say T but **disagree on the abutter** | **No arrows.** Counted as a conflict, not decided by coin flip |
| Neither says T | Nothing |

## Setting, line 59

`CORNER_TO_TANGENT_BEARING_TOL_DEG = 45°` 🔴: how closely a corner-method arm must line up with a
tangent-fit arm to be treated as the same segment.

## Result containers, lines 62–79

- **`PrecedenceArc`**: one arrow:
  - the junction it came from
  - abutter and host segments
  - which method(s) support it, and whether both agreed
- **`PrecedenceGraphResult`**:
  - all arrows and the graph itself
  - conflict count and the nodes involved
  - corner claims that couldn't be matched to segments
  - cycles (`nontrivial_sccs`)
  - each segment's generation

## `_corner_claim_to_path_indices(...)`, line 87

The corner method only knows *directions*, not which skeleton segment each direction belongs
to. This function translates:

1. Re-run the T rule on the corner method's three directions to find which one is the abutter.
2. **Lines 113–127**: match each corner direction to the nearest tangent-fit arm direction. Take
   the closest pairs first, use each arm once, and stop beyond 45°.
3. All three matched → return the abutter segment and the two host segments. Otherwise →
   unmapped, with a reason.

This needs all three tangent-fit arms measured. If one was too short, the corner claim is left
unmapped rather than guessed.

## `_compute_generations(graph)`, line 137

1. **Strongly connected components** (`networkx`): groups where every segment can reach every
   other by following arrows. A group of more than one segment is a cycle. So is a single segment
   with an arrow to itself: a loop whose two ends meet at one T, one end abutting the other.
2. **Condensation**: squash each group into a single node. The result never has cycles.
3. **Topological generations**: generation 0 = nothing points to it (oldest); generation 1 =
   only generation-0 nodes point to it; and so on.
4. Segments inside a cycle get generation `None`, meaning undetermined, rather than a forced
   number.

## `build_precedence_graph(...)`, line 161: the main function

| Lines | What happens |
|---|---|
| 177–214 | For each junction, gather both methods' claims and apply the table above. |
| 216–225 | One arrow per host: a T gives two arrows, abutter after each host side. |
| 227–234 | Build the graph with arrows **host → abutter** (older → younger). The comment spells out why it's this direction. |
| 236 | Generations and cycles. |

## Worth knowing

- **Segments untouched by any T** have no generation and appear grey in the precedence picture.
  So do segments stuck in a cycle. The picture doesn't distinguish the two cases yet.
- **The two sides of a straight crack through a junction are separate segments** and can get
  different generations. That's deliberate ("arcs, not whole cracks"). Merging them into one
  crack would need evidence, and it's not implemented.
- **Tests**: `tests/test_precedence.py` (7 tests):
  - a synthetic T gives agreeing arrows and generations; a Y gives none
  - a simple chain gets generations; a 3-segment cycle leaves them undetermined
  - conflicting abutters emit no arrow
  - an unresolved corner check leaves a tangent-only arrow
