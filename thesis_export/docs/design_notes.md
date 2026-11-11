# Design notes

Full design rationale for the core pipeline modules, relocated verbatim from what used to
be each module's opening docstring. The source files keep a short summary that points
here. Only two stale file paths were updated to the current folder layout.

## skeleton.py

`src/crackgraph/skeleton.py`

Stage 2: skeletonize + prune short spurs.

Homotopy-preserving thinning (skimage's Zhang's algorithm), followed by
iterative spur pruning via skan.Skeleton.prune_paths. Pruning is iterative,
not a single pass: removing a spur can expose a new short branch at a
junction that was previously higher-valence, so a single pass under-prunes.

KNOWN LIMITATION -- small loops and short junction-to-junction edges
(corrected 2026-11-11; the earlier explanation is kept at the end of this
block).

Where small loops come from. skimage's skeletonize() preserves topology: it
never creates or removes a hole. So every closed loop in the skeleton
surrounds a hole in the cleaned mask -- a real crack cell, or a dark speck
inside a wide crack that is larger than DARK_SPECK_AREA_PX and so
wasn't removed. Thinning does not "trace both walls" of a crack and leave a
loop where the mask has no hole. Checked on 2048 px centre crops of all 41
*_mm000001 micrographs: the number of mask holes equals the number of
independent graph cycles on 33 of 41. On the other 8 there are 1-5 extra
cycles, most likely where the skeleton is locally 2 px thick, so skan's
8-connected pixel graph has two paths between the same junctions with no
background pixel between them (multi-edges were found on those images).

What skeleton_loop_sweep.py actually measures. Its fingerprint is
junction-to-junction edges shorter than the image's average crack width.
On the same 41 crops that is 370 edges; only 30 (8%) lie within one crack
width of a small hole (a dark speck). The other 92% are short segments
between junctions that sit close together. On dense images most are
longer than 5 px, so they are not pixel clusters. Most likely they are
split crossings (an X read as two 3-way junctions joined by a short edge,
as in the synthetic hexagon test) or two cracks meeting a wide host at
nearby points; the second is real geometry, not an artifact. This split
has not been checked by eye. So the sweep's 0-55.2% of edges per image is
a count of short junction-to-junction edges, not of fake loops.

Why pruning doesn't touch either. The pruning loop only removes
branch_type 0 (isolated fragment) and 1 (dead end). Loop strands and
edges between two junctions are type 2 or 3, whatever spur_px is.

Effect: these edges inflate n_edges and deflate edge-length statistics on
affected images (see docs/batch_stats/crack_stats_schema.md S4) and add
junctions to the census. Speck loops are reduced by dark-speck removal,
raised from 50 to 130 px (the area of a d90 ~ 7.8 um agglomerate) on
2026-11-11; that removes about 10 loops on the densest crops. Short edges
between close junctions would need a junction-merging step; none is
implemented.

Earlier explanation (superseded): "Zhang's thinning is pixel-local ... on a
locally wide or slightly irregular crack band it can trace both edges of
the band for a short stretch before merging back into one line, leaving a
small closed loop instead of a single centerline." This doesn't hold for a
topology-preserving thinning: a loop needs a hole in the mask.

Host stubs (in addition to plain short spurs). Thinning sends a branch from
a crack's centre line into every bump, notch or corner on its wall, whatever
the branch's length (a correct property of the medial axis, not noise). On
wide cracks these stubs are often longer than SPUR_PX_PLACEHOLDER, so the
length rule misses them. Confirmed case (T2-A_membran_v2): a 45 px branch
whose width ramps 2.0 -> 121.7 px, tracing into a black wedge with no crack.

Current rule (since 2026-11-11): a dead end is removed if less than
SPUR_PX_PLACEHOLDER (9.1 um) of its length lies outside the crack it branches
from. The host is the other branches at its junction; host half-width
r_host = median medial radius along them, 1-3 junction-blob radii out (the
blob where cracks meet is wider than either crack). A dead-end pixel is
outside if it is farther than r_host from the host centre line. A stub runs
from the centre line to the wall and stops, so almost none of it is outside;
a real side crack leaves the host. It uses the same physical scale as the
spur rule, which is its special case (r_host = 0), and adds no constant.

Variants tested and rejected (outputs/corner_rule_test/, 2048 px centre
crops of 6 micrographs, summary.html):
- reach = length - r_host: counts the in-host part of branches that leave
  at a shallow angle. Results within threshold noise of the chosen rule
  (12 branches differ, all scoring 13-15 px either way).
- reach = farthest distance from the host centre line - r_host: removes
  hooks (real cracks that curl round and run alongside the host just past
  its wall; 23 on these crops), because they never get far from the host.
- junction-pixel radius as r_host: inflated by the junction blob; removed
  real short side cracks on thin-crack images.

Previous rule (until 2026-11-11), kept for history: a dead end or fragment
was removed if its width rose steadily from tip to junction (Pearson
correlation of position vs width > 0.99). On the same crops it missed about
67 interior stubs at correlation 0.94-0.99 and removed 7 real cracks cut off
by the crop edge. Replacing it raises ledge by up to ~22% on dense wide-crack
images together with the dark-speck change (see CHANGELOG.md). Earlier still,
a windowed tip-width comparison (missed medium/long artifacts) and a
"fraction above the tip median" test (a coin flip on noisy real cracks) were
rejected before correlation was chosen.

Known limits of the current rule: r_host assumes the host is locally uniform
in width; real side cracks reaching less than 9.1 um past their host are
removed (by design, same scale argument as spur_px); dead ends at the image
border are judged like any other.

This targets the same general problem as standard skeleton-pruning methods
-- Discrete Curve Evolution pruning (Bai, Liu & Latecki, IEEE TPAMI 2007),
the lambda-medial-axis (Chazal & Lieutier, Graphical Models 2005), the
scale-axis transform (Giesen et al., SoCG 2009) -- but is a much simpler
rule, not a reimplementation of any of them.

## flaking.py

`src/crackgraph/flaking.py`

Identify and exclude large flaked/delaminated catalyst-layer regions from
the crack mask before they contaminate crack-area, width, length, and
connectivity statistics.

Why this exists: a flaked-off patch (catalyst layer physically absent,
exposing substrate) reads as bright/foreground under the same Otsu threshold
as a real crack, but it is not a crack -- it is a 2D area of missing
material, not a 1D fracture. Left uncorrected, it (a) inflates
crack_area_pct, (b) corrupts avg_width_px/avg_edge_length_px because
skeletonizing its filled interior produces a genuinely multi-branched,
non-representative medial axis (not the "double-line loop" artifact
documented in skeleton.py -- a different mechanism: the medial axis of a
blob-shaped region is *inherently* branchy, this isn't thinning noise), and
(c) silently discards the fact that we have zero evidence about what crack
pattern, if any, existed under the now-missing material.

Identification (this module's own contribution, not reused from elsewhere):
a pixel is a candidate-blob pixel if its local width (2 * medial_radius,
the same EDT half-width skeleton.py already computes) exceeds
WIDTH_FLAG_MULTIPLIER_K times this image's own reference crack width --
sampled at skeleton centerline pixels only (the one place medial_radius
reads a genuine half-width rather than "however close this pixel happens to
be to an edge"), median rather than mean so a blob's own messy interior
skeleton (a small fraction of total skeleton mileage) can't drag the
reference value up. Connected components of the flagged region are kept as
candidates only above MIN_CANDIDATE_AREA_PX -- width is the single
identification criterion, deliberately: an earlier version also required
high solidity (area / convex-hull area) to separate compact blobs from
merely-locally-wide, elongated crack bands, but that second criterion was
dropped after a real elongated candidate on T2-A_membran_v2 (solidity
0.674, well below the 0.75 cutoff) was confirmed by inspection to be real
delamination, not a wide crack -- solidity was excluding genuine cases and
was harder to justify than width alone. One criterion, explainable, beats
two where the second one is doing more harm than good.

Treatment: WIDTH_FLAG_MULTIPLIER_K=4 means a flagged seed pixel is, by
construction, more than (K/2) * reference_width_px from the nearest
background pixel -- the seed starts already eroded inward from the true
boundary by that amount. Growing the seed back out has to at least undo
that erosion before it can reach the true edge; GROWTH_MULTIPLIER=2.2
follows directly (2.0 = K/2 exactly undoes the erosion, +10% margin to
reliably clear it -- verified by visual inspection against real candidates,
not derived from first principles). Growth is mask-constrained dilation
(can never cross a real black boundary), cropped to each candidate's padded
bounding box (growth is inherently local, so this is a safe, not a lossy,
optimization). Nothing here converges to a fully "moated" stop in the
mathematical sense -- almost every candidate touches at least one thin
crack corridor, and dilation will keep creeping a little further down it on
every step, forever, in a fully connected network. GROWTH_MULTIPLIER is
therefore a disclosed stopping budget, not a discovered boundary.

Deliberately not built here: any attempt to reshape the exclusion boundary
to look more like a natural crack tip (a "meniscus", considered and
rejected in favour of the approach below) -- that would be shaping the
output to look right rather than measuring anything, which this project's
own evidence-level discipline rules out. Instead, the mask is skeletonized
once and every edge touching the excluded region is omitted from the stats
and the connectivity graph (flake_touching_path_indices), rather than having
its geometry cosmetically smoothed.

Every constant below is 🔴 assumed (chosen by inspection this session, no
independent sweep) except where noted -- see CALIBRATION.md's convention.
