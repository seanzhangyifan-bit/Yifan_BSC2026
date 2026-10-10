# Spatial overview & report

**Purpose**: a first *look* at how much crack pattern varies across one whole coating — not a
formal, citable result. Separate from `src/analyze_image.py` (which runs the full stage 1-5
pipeline — junctions, corner cross-check — but only on one small corner-crop region per
invocation); this tier deliberately runs a lighter slice (binarize → skeletonize → graph →
curvature → anisotropy, no junctions/ordering) over a coarse grid of sections plus the whole
image, so you can eyeball spatial variation quickly.

- **`overview_figure.py <image_path> [--n-rows 2] [--n-cols 2] [--out-dir outputs]`**: compiles
  one figure — the raw micrograph in the center, each quadrant's rose diagram + tortuosity
  histogram positioned in the figure corner matching that quadrant's real position in the source
  image, and the whole image's own rose/tortuosity result in a row below. Also updates one master
  HTML report (`outputs/report.html`, covering every coating/image analyzed so far — one page,
  not one per image).
- **`attach_full_analysis.py <image_path>`**: wires an already-generated full-image overlay +
  precedence graph (from `python3 -m src.analyze_image <image> --full-image`) into that image's
  existing block in the master HTML report. Doesn't run the analysis itself — the image must
  already have an entry, created by `overview_figure.py` first.

**Validation status**: none formal, deliberately. This tier exists to spot interesting regions
and sanity-check that a coating "looks reasonable" before committing analysis time elsewhere —
the numbers it produces (rose diagrams, tortuosity histograms) aren't the thesis's headline
claims.
