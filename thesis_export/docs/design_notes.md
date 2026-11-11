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

KNOWN LIMITATION -- spurious skeleton loops, not fixed by spur_px: Zhang's
thinning is pixel-local (each pixel is erased or kept based only on its
immediate neighborhood, never on the shape's overall width or center), so
on a locally wide or slightly irregular crack band it can trace both edges
of the band for a short stretch before merging back into one line, leaving
a small closed loop instead of a single centerline. This is a well-known
general sensitivity of skeleton/medial-axis methods to boundary noise, not
specific to this codebase.

The pruning loop above is structurally blind to this: it only ever removes
branch_type 0 (isolated fragment) and branch_type 1 (spur, one endpoint
degree-1) branches, never branch_type 2 (junction-to-junction) or 3
(cycle) -- and a loop's two strands are anchored to the graph at both
ends, so they are always type 2 or 3, regardless of how spur_px is tuned.

Measured, not assumed: `scripts/validation/skeleton_loop_sweep.py` audits every image
in the real dataset for junction-to-junction edges shorter than that
image's own average crack width (the fingerprint of this artifact). Result
across the 39-image dataset: 0% to 55.2% of all edges per image, only
weakly correlated with average crack width (r ~ 0.31 against
avg_width_px) and NOT cleanly explained by substrate -- Membran and PTFE
samples have essentially the same mean (~9.7% vs ~9.3%), and the single
worst offender in the dataset is a Membran sample. This inflates n_edges
and deflates avg_edge_length_px for affected images (see
docs/batch_stats/crack_stats_schema.md S4); it has a much larger effect on the planned
junction-census/T-vs-Y work, since many of the extra "junctions" this
creates aren't real crack meetings. No fix is implemented yet -- documented
as a known, measured limitation, not silently worked around.

Corner-tracing artifacts (in addition to plain short spurs): the medial
axis transform mathematically *must* trace a skeleton branch into every
concave corner of the mask boundary -- this is not thinning noise, it is a
correct property of the medial axis, and it is blind to length. A branch
tracing into a real notch (e.g. the ragged edge of a flaked-off region, or
a background inlet between two crack walls) can be far longer than
SPUR_PX_PLACEHOLDER and survive flat-length pruning untouched. Confirmed on
a real case this session (T2-A_membran_v2): a branch with a near-perfectly
linear 2.0px -> 121.7px width ramp over 45px, visually confirmed tracing
into a real black wedge with no crack present.

Two other criteria were tried and rejected before settling on the one
below: a windowed tip-width comparison (too conservative, missed
medium/long artifacts entirely) and a "fraction of the branch above its own
tip-median width" test (mathematically flawed -- for a genuinely real,
noisy-but-stable-width crack, the tip-region median is a random draw from
the same distribution as the rest of the branch, so ~50% of pixels exceed
it by symmetric noise alone; the >50% threshold sat right at a coin flip
for exactly the branches that should survive).

What is used instead: the Pearson correlation between pixel position
(0 = the free tip, where one exists) and local width (2 * medial_radius)
along the branch. A genuine crack's width is noisy but flat around a
steady value -> correlation near 0. A corner-tracing artifact's width
ramps monotonically toward the notch it's chasing -> correlation near +1.
This sidesteps the coin-flip problem because it tests for a trend, not a
fraction above a reference drawn from the same noisy population.

This targets the same general problem as several standard skeleton-pruning
methods from the literature -- Discrete Curve Evolution pruning (Bai, Liu &
Latecki, IEEE TPAMI 2007), the lambda-medial-axis (Chazal & Lieutier,
Graphical Models 2005), and the scale-axis transform (Giesen et al., SoCG
2009) -- but the correlation test here is a much simpler, single-parameter
stand-in, not a reimplementation of any of them.

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
candidates only above MIN_CANDIDATE_AREA_PX2 -- width is the single
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
own evidence-level discipline rules out. Instead, edges that end up
touching the exclusion boundary are meant to be flagged and dropped from
downstream length/width statistics (see cut_adjacent_path_indices) rather
than having their geometry cosmetically smoothed.

Every constant below is 🔴 assumed (chosen by inspection this session, no
independent sweep) except where noted -- see CALIBRATION.md's convention.
