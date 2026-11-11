# 10. The GUI

**File**: `app.py` (407 lines)

```
python3 -m streamlit run app.py
```

It opens a page in your browser at `http://localhost:8501`. Everything runs on your own
computer; nothing is uploaded.

**What it is.** A thin front end over three commands you've already met:
- the per-image analysis (page 8)
- the crack-stats export (page 5)
- the spatial overview (page 9)

It adds no new analysis. The validation tools and the experimental code are deliberately left
out.

---

## How the code is organised

**Pipeline side (lines 75–183).** These functions take no Streamlit objects, so they work on
their own.

| Function | Line | What it does |
|---|---|---|
| `_format_duration` | 75 | "75" → "1m 15s", rounded down. It's a rough estimate, so no false precision. |
| `_run_streaming` | 85 | Runs a command and passes each line of its output on **as it arrives**, instead of waiting for the end. |
| `run_single_image_analysis` | 102 | Runs `src.analyze_image` as a **separate process**, with `--skip-*` flags for unchecked boxes, then finds the pictures it wrote. It's a separate process because `analyze_image` is one big command-line script (review R1). That way the GUI can't break it. |
| `run_spatial_overview` | 138 | The same for the overview figure. |
| `_make_stage_progress_callback` | 165 | Watches the output for known section headers (`STAGE_MARKERS`, line 46) and moves the progress bar one step per header. |

The crack stats are computed **in the same process**, by calling `compute_row` directly. Its
`on_stage` callback drives the progress bar.

**Streamlit side: `main()`, line 186.**
1. A file uploader for one or more images.
2. Checkboxes for what to run: crack stats, curvature, anisotropy, spatial overview.
3. "Advanced options": analyse the full image instead of the corner crop.
4. On **Run analysis**:
   - save the uploads to a temporary folder
   - work out the total number of steps for the progress bar
   - run each selected analysis on each image
5. For each image, a collapsible section with the overlay, full text report
   and a download button.
6. A crack-stats table with an **.xlsx download**, plus a warning that the µm/mm² columns assume
   this project's own microscope calibration.

The time-remaining estimate is a straight-line extrapolation, hidden for the first two steps
because early steps aren't representative.

## Worth knowing

- **Crack stats always use the full image**, while the per-image analysis defaults to the
  corner crop (about 1.5% of the image). Each result now says which region it covers, and a
  note appears when both are shown (review finding 10).
- **Uploads are always recorded as `scale_bar_check = "not checked"`**, because nobody has
  looked at them.
- **The temporary folder is deleted when the run finishes.** Download anything you want to keep.
- **Tests**: `tests/test_entry_points.py` checks that the GUI starts without errors (Streamlit's
  `AppTest`). It doesn't click through an upload.
