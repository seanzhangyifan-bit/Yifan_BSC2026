# Calibration notes

Full rationale for every constant listed in [`CALIBRATION.md`](../CALIBRATION.md), relocated
verbatim from what used to be each constant's inline comment. Nothing here is reworded or
summarized — if a constant's justification changes, update it here (and re-run the
referenced sweep script), not just the one-line pointer left in the source file.

## SPUR_PX_PLACEHOLDER

`src/crackgraph/skeleton.py:24` — value `15`

**Physical justification (added 2026-11-11, after the fact).** The value was chosen before
any of this was known; it was then checked against measured length scales and found to
match them. It was not re-derived or changed.

- **Scale.** 15 px × 0.6098 µm/px = **9.1 µm** (calibration for `mm` mosaic images only; see
  `docs/batch_stats/crack_stats_schema.md` §6).
- **Agglomerate size** `[measured]`. Laser diffraction of the wet inks
  (`../image_visualization/data/Auswertung_PGV_v1.xlsx`, read via figlib's `psd_data.py`):
  d90 = 7.7–7.9 µm and d99 ≈ 7–10 µm for inks T2–T4; T1 d90 = 4.2 µm; T5 d90 = 1.3 µm with a
  ~2 vol% tail above 10 µm.
- **Film thickness** `[measured]` (`../image_visualization/data/Schichten_Charakterisierung.xlsx`):
  mostly 8–16 µm; the thin T5 height-variation series is 3–6 µm.
- **Argument** `[interpreted]`. Agglomerates of this size make the crack walls rough on the
  same scale, and thinning turns wall bumps into short dead ends. A dead end shorter than
  about one large agglomerate (or one film thickness) can't be told apart from wall
  roughness, so it isn't counted as a crack.

**Caveats.**
- The PSD is of diluted wet ink; agglomerates may re-form during drying. It is the best
  available proxy for agglomerate size in the dried layer, not a direct measurement of it.
- One cut-off is used for every image on purpose. The physical scales differ between inks
  and coatings, and a per-condition cut-off would make conditions measured differently.
- The argument covers spurs (wall bumps), not fragments: removed fragments on thin-crack
  images are mostly pieces of real faint cracks broken up by thresholding.
- `ledge` depends strongly on this cut-off (on six 2048 px crops, `ledge` rises 50% on
  T3-PTFE_v1 between no cut-off and 15 px), so it must be reported together with `ledge`.

Original note, kept for history:

> Not derived from real film-thickness h or a calibrated um-per-pixel value -- neither
> exists yet (calibration is supplied manually, later). Chosen only as "somewhat larger
> than the skeleton's vertex-jitter scale (a few px)", so as to not eat real short
> branches. Must be revisited once calibration lands.

No sweep script targets this constant. Most synthetic tests invoke the pipeline with
`spur_px=3` (an override, not the default), i.e. the test harnesses deliberately bypass this
constant's default value rather than validating it.

## DARK_SPECK_AREA_PX

`src/crackgraph/skeleton.py:30` — value `130` (was `HOLE_AREA_THRESHOLD_PX2` = `50` until 2026-11-11)

Dark specks inside a crack (pieces of catalyst layer or dust sitting in the gap) smaller than this
many px are removed right after bright spots are filled (`remove_small_objects`) and before
`skeletonize()`. A speck left in makes the skeleton loop around it, adding two junctions and
short edges.

**Physical justification.** 130 px × (0.6098 µm/px)² = **48 µm²**, the area of a circle of
diameter ≈ 7.8 µm: the d90 agglomerate size of inks T2–T4 `[measured]` (same PSD source as
`SPUR_PX_PLACEHOLDER` above). A dark speck no bigger than one agglomerate inside a crack is
read as material sitting in the gap, not a separate crack cell `[interpreted]`. Same caveats
as above: wet-ink PSD, one value for every image, `mm` images only.

**Measured effect of 50 → 130 px** (2048 px centre crops of 6 micrographs,
`outputs/hole_fill_test/`): 14 real specks inside cracks newly removed (plus 5 dark background
slivers cut off at the crop edge), removing their loops; `ledge` +0.9 to +6.9% on the four crops with specks,
`wcrack`, crack area and `N` unchanged.

The old 50 px value was carried over from an informal prototype script and never derived.

## Removed: CORR_THRESHOLD and MIN_LEN_FOR_CORR_PX

Removed 2026-11-11 with the correlation-based corner test they belonged to (0.99, 🟡, a 4-point
hand sweep on one image; and 4 px, 🔴). The host-stub rule that replaced the test uses
`SPUR_PX_PLACEHOLDER` and adds no constant of its own. Why the test was replaced:
`docs/design_notes.md`, skeleton.py section.
