# Methodology

Part of a BSc thesis (Zhang 2026, KIT Thin Film Technology group) on PEMFC catalyst-layer ink
formulation and coating, comparing short-side-chain (SSC) and long-side-chain (LSC) PFSA
ionomers.

**Purpose**: turn catalyst-layer crack micrographs into numbers that let crack patterns be compared
across conditions (ionomer, Rakelspalt, substrate, humidity).

## Results

- **Main output**: whole-image crack stats: crack area, flaked area, width, segment count and
  length, connectivity (`docs/batch_stats/crack_stats_schema.md`).
- **Optional**: the same per region (centre, grid cells), tortuosity/curvature, a rose plot of
  crack directions, a per-segment table.
- **Judging an error**: by its effect on these numbers, compared with (a) the spread between
  `v1`/`v2` replicates and (b) the gap between conditions. Errors that grow with crack width or
  density matter most: they can tilt a comparison.

## Pipeline

Stages 1–3 are the **engine**, run once per image (`engine.py`).

1. **Binarize**: global Otsu threshold (`binarize.py`).
2. **Skeletonize**: homotopy-preserving thinning; prune dead ends shorter than about the largest
   agglomerate size (`skeleton.py`).
   - **Flaking exclusion** (`flaking.py`): patches where the catalyst layer flaked off (seen on
     membrane T2/T3/T4) are bright like cracks but are missing material. Pixels far wider than the
     image's typical crack width are grown out to the patch boundary. Every segment touching a
     patch is left out of every measurement and of the connectivity graph.
3. **Graph**: nodes, segments, and each segment's pixel path (`graph.py`).
4. **Regions** (`regions.py`): whole image, centre, or grid cells. A region selects part of the
   engine result, so all regions share one threshold and one flaking reference.
5. **Measure** each region (`measures/`). Pixel quantities: pixels inside the region. Segment
   quantities: whole segments, placed by their middle pixel. Connectivity: whole image only,
   because cutting at a border splits the network.

## Settings

All in `settings.py`, set from the GUI (`app.py`) or the command line (`src/analyze.py`).

- **User-set**: µm per pixel, regions, measurements, crack-stats column groups, figures. Which
  engine settings to expose is still open.
- **Physical thresholds**: the spur cut-off and dark-speck limit are justified by agglomerate
  size, so they're stored in µm (9.15 µm, 48.3 µm²) and converted with µm per pixel. At
  0.6098 µm/px: exactly 15 px and 130 px, as in the thesis numbers.
- **Reproducibility**: every workbook has a `settings` sheet. Default whole-image crack stats
  equal the earlier exporter's exactly (checked on two real images; locked in by a test).
- **One engine pass, not one per region**: re-running per crop would give each region its own
  threshold and flaking reference, so regions wouldn't be comparable or add up.

## Libraries

- `scikit-image`: threshold, skeleton, distance transform.
- `skan`: skeleton → branch graph.
- `networkx`: connectivity (components, giant component).

## Using the crack stats

- **Downstream**: the sibling `image_visualization` project ("figlib") reads the crack-stats
  workbook via `figlib/crack_data.py` and never edits it; fix things here. Keep the schema doc
  consistent with what figlib assumes (`_sample_id()`, `crack_levels_table`).
- **Replicates**: `v1`/`v2` are separate captures of one condition. Include every replicate. For
  per-condition statistics, group by `image_filename` without the `_mm######.jpg` suffix and
  average only where there are ≥ 2 replicates.
- **Scale bars**: `mm000000`/`mm000001` names don't reliably tell which file has a burned-in
  scale bar. Check each image by eye (bottom-right corner). The tool doesn't look at names.

## Validation gallery

- `scripts/validation/validation_gallery.py`: 5 synthetic cases (curvature, anisotropy) through
  the real pipeline, with overlay or rose images and expected-vs-measured tables
  (`outputs/validation/report.html`).
- Tolerances are copied, with a cross-reference, from the matching `tests/test_*.py`.
- `anisotropy_orthogonal_grid` shows why the rose plot is reported instead of a single index: an
  equal-weight orthogonal grid would read as random directions.
- Each case re-derives its expected values from its generator arguments.

## References

- **Thin-film fracture**: Beuth 1992 (channelling cracks); Xia & Hutchinson 2000 (shear-lag
  model, crack curvature); Goehring 2012 (crack-network evolution); Bohn, Pauchard & Couder 2005
  (hierarchical crack patterns).
- **Directions**: axial circular statistics — Mardia & Jupp, *Directional Statistics*, 2000;
  Fisher, *Statistical Analysis of Circular Data*, 1993.
- **Curvature**: chord/turning-angle estimation — Rosenfeld & Johnston, "Angle Detection on
  Digital Curves", *IEEE Trans. Computers* C-22(9), 1973. Chosen to share `_chord_scan.py` with
  the direction scan, not for accuracy over the 3-point circle fit.
- **Tortuosity** (arc ÷ chord): a generic ratio, as in Bouchaud, "Scaling properties of cracks",
  *J. Phys.: Condens. Matter* 9, 4319, 1997.

## Other docs

- `README.md`: setup and running.
- `GLOSSARY.md`: term definitions.
- `CALIBRATION.md`: justification status of each tunable constant.
- `docs/walkthrough/`: code walkthrough, including each constant's rationale.
- `docs/batch_stats/crack_stats_schema.md`: every crack-stats column.
