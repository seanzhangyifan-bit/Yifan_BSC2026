"""Browser GUI for the crack analysis. Runs locally; nothing is uploaded.

Run: python3 -m streamlit run app.py

The page is laid out the way the analysis works:
    calibration -> regions -> measurements -> figures -> run
Every control sets one field of an AnalysisSettings (src/crackgraph/settings.py),
and the run calls the same analyze_image() as the command line
(src/analyze.py). The settings used are saved in the workbook's
"settings" sheet.

After a run, "Compare images" lets you sort the analysed images onto a
drag-and-drop board (src/crackgraph/gui/board.py): columns and rows are the
two things you varied, images in one cell are replicates. The labels go into
the workbook's "labels" sheet. Results are kept in st.session_state so they
survive the reruns that every board move triggers.
"""

import tempfile
import time
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.crackgraph.analysis import analysis_stages, analyze_image
from src.crackgraph.export import results_tables, write_figures, write_workbook
from src.crackgraph.grouping import labels_table, plot_replicates, presort_by_name
from src.crackgraph.gui.board import grouping_board, thumbnail_data_uri
from src.crackgraph.regions import RegionSpec
from src.crackgraph.settings import CRACK_STATS_GROUPS, DEFAULT_UM_PER_PX, AnalysisSettings

GROUP_LABELS = {
    "area": "Crack area",
    "width": "Crack width",
    "segment_length": "Segment length",
    "connectivity": "Connectivity (whole image only)",
    "flaking": "Flaking exclusion",
    "pruning": "Pruning counts",
}


def settings_form() -> tuple[AnalysisSettings, tuple[str, ...], str] | None:
    """Draw the settings controls; return (settings, figures, map column),
    or None if the choices don't make a valid run."""
    st.subheader("1. Calibration")
    um_per_px = st.number_input(
        "µm per pixel", min_value=0.0001, value=DEFAULT_UM_PER_PX, format="%.4f",
        help="Default: the thesis microscope calibration. The spur cut-off (9.1 µm) and the "
             "dark-speck limit (48 µm²) are converted to pixels with this value.",
    )

    st.subheader("2. Which part of the image")
    mode = st.radio(
        "Regions", ["whole", "centre", "grid"], horizontal=True,
        format_func={"whole": "Whole image", "centre": "Centre", "grid": "Grid"}.get,
    )
    centre_frac, n_rows, n_cols, cells = 0.5, 2, 2, None
    if mode == "centre":
        centre_frac = st.slider("Share of width and height", 0.1, 1.0, 0.5, 0.05)
    elif mode == "grid":
        c1, c2 = st.columns(2)
        n_rows = c1.number_input("Rows", 1, 20, 3)
        n_cols = c2.number_input("Columns", 1, 20, 3)
        all_cells = list(range(1, n_rows * n_cols + 1))
        chosen = st.multiselect(
            "Cells to analyse (numbered row by row from the top left)", all_cells, default=all_cells,
        )
        if not chosen:
            st.info("Pick at least one cell.")
            return None
        cells = None if len(chosen) == len(all_cells) else tuple(sorted(chosen))

    st.subheader("3. What to measure")
    measurements = []
    if st.checkbox("Crack stats", value=True):
        measurements.append("crack_stats")
        groups = st.multiselect(
            "Column groups", CRACK_STATS_GROUPS, default=list(CRACK_STATS_GROUPS),
            format_func=GROUP_LABELS.get,
        )
    else:
        groups = list(CRACK_STATS_GROUPS)
    if st.checkbox("Tortuosity & curvature"):
        measurements.append("tortuosity")
    if st.checkbox("Anisotropy (rose plot of crack directions)"):
        measurements.append("anisotropy")
    if st.checkbox("Per-segment table", help="One row per crack segment: length, width, area."):
        measurements.append("segments")
    include_runtime = st.checkbox("Runtime columns")
    if not measurements:
        st.info("Select at least one measurement.")
        return None

    st.subheader("4. Figures")
    figures = st.multiselect(
        "Figures", ["overlay", "panels", "map"], default=["overlay"],
        format_func={
            "overlay": "Skeleton overlay with regions",
            "panels": "Rose + tortuosity per region",
            "map": "Colour map of one column (grid/centre only)",
        }.get,
    )
    map_column = "crack_area_pct"
    if "map" in figures:
        map_column = st.text_input("Column for the colour map", "crack_area_pct")

    settings = AnalysisSettings(
        um_per_px=um_per_px,
        regions=RegionSpec(mode=mode, centre_frac=centre_frac, n_rows=n_rows, n_cols=n_cols, cells=cells),
        measurements=tuple(measurements),
        crack_stats_groups=tuple(groups),
        include_runtime=include_runtime,
    )
    return settings, tuple(figures), map_column


def run_analysis(uploaded, settings: AnalysisSettings, figures, map_column) -> dict:
    """Analyse every upload; return what the page shows afterwards. Figures are
    kept as PNG bytes because the temporary folder is gone by then."""
    stages = analysis_stages(settings)
    total = len(stages) * len(uploaded)
    done = [0]
    start = time.monotonic()
    bar = st.progress(0.0, text="Starting...")
    analyses, errors, pngs = [], [], {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, f in enumerate(uploaded):
            path = tmp / "upload" / f.name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(f.getvalue())
            label = f"{f.name} ({i + 1}/{len(uploaded)})"

            def on_stage(stage, label=label):
                done[0] += 1
                elapsed = time.monotonic() - start
                bar.progress(min(done[0] / total, 1.0), text=f"{label}: {stage} · {elapsed:.0f} s")

            try:
                analysis = analyze_image(path, settings, on_stage=on_stage)
            except Exception as exc:  # noqa: BLE001 -- report and carry on with the other images
                errors.append((f.name, str(exc)))
                continue
            analyses.append(analysis)
            written = write_figures(analysis, tmp / "figures", figures, map_column)
            pngs[f.name] = [(p.stem, p.read_bytes()) for p in written]
    bar.progress(1.0, text="Done.")
    return {
        "analyses": analyses, "errors": errors, "pngs": pngs, "settings": settings,
        "thumbs": [{"name": a.image_path.name, "thumb": thumbnail_data_uri(a.rgb)} for a in analyses],
        "run_id": time.time_ns(),
    }


def show_results(run: dict) -> None:
    for name, msg in run["errors"]:
        st.error(f"{name}: {msg}")
    for name, figs in run["pngs"].items():
        with st.expander(name, expanded=len(run["pngs"]) == 1):
            for stem, data in figs:
                st.image(data, caption=stem)
    if not run["analyses"]:
        return
    if abs(run["settings"].um_per_px - DEFAULT_UM_PER_PX) < 1e-12:
        st.caption("µm columns use the thesis microscope calibration; change µm per pixel for other images.")
    for name, df in results_tables(run["analyses"]).items():
        st.subheader(name.replace("_", " ").capitalize())
        if name == "image_connectivity":
            st.caption("Connectivity is measured on the whole image only, not per region.")
        st.dataframe(df)


def _values(text: str) -> list[str]:
    """Comma-separated values, stripped; empty and repeated ones dropped."""
    out = []
    for v in text.split(","):
        v = v.strip()
        if v and v not in out:
            out.append(v)
    return out


def compare_section(run: dict) -> pd.DataFrame | None:
    """Grouping board, labels table and replicates plot. Returns the labels
    table for the workbook, or None when nothing is on the board."""
    st.header("Compare images")
    names = [t["name"] for t in run["thumbs"]]
    if len(names) < 2:
        st.info("Analyse at least two images to compare them.")
        return None
    st.caption(
        "Name what you varied, then sort the images onto the board: drag them, or click several and "
        "then click a cell. Images in one cell are replicates. Images left in Unsorted are left out."
    )
    c1, c2 = st.columns(2)
    col_label = c1.text_input("Columns: what you varied", "condition", key="cmp_col_label").strip()
    cols = _values(c1.text_input("Column values, comma-separated", "A, B", key="cmp_cols"))
    row_label = c2.text_input("Rows: a second thing you varied (optional)", "", key="cmp_row_label").strip()
    rows = _values(c2.text_input("Row values, comma-separated", "", key="cmp_rows")) if row_label else []

    regions = results_tables(run["analyses"])["regions"]
    reserved = set(regions.columns) | {"replicate", "_row"}
    problems = []
    if not col_label or not cols:
        problems.append("Give the columns a name and at least one value.")
    if row_label and not rows:
        problems.append("Give the rows at least one value, or clear the row name.")
    if row_label and row_label == col_label:
        problems.append("Rows and columns need different names.")
    problems += [f'"{label}" is already a results column; pick another name.'
                 for label in (col_label, row_label) if label in reserved]
    if problems:
        for p in problems:
            st.warning(p)
        return None
    single_row = not rows
    row_key = row_label or "_row"
    rows = rows or ["all"]

    # A new run, or changed rows/columns, resets or trims the board: a Python-side change, so bump rev.
    ss = st.session_state
    layout = (run["run_id"], tuple(rows), tuple(cols))
    if ss.get("cmp_layout") != layout:
        same_run = ss.get("cmp_layout", (None,))[0] == run["run_id"]
        old = ss.get("cmp_assign", {}) if same_run else {}
        ss.cmp_assign = {n: old.get(n) if old.get(n) and old[n][0] in rows and old[n][1] in cols else None
                         for n in names}
        ss.cmp_rev = ss.get("cmp_rev", 0) + 1
        ss.cmp_layout = layout
        ss.cmp_msg = ""

    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("Pre-sort by file name", help="Places an image when exactly one column value (and one row "
                 "value, if rows are used) appears as a whole part of its file name. Everything else "
                 "stays in Unsorted."):
        ss.cmp_assign = presort_by_name(names, rows, cols, match_rows=not single_row)
        ss.cmp_rev += 1
        missed = [n for n, c in ss.cmp_assign.items() if c is None]
        ss.cmp_msg = f"Placed {len(names) - len(missed)} of {len(names)} images." + (
            f" Could not read: {', '.join(missed)}. Place those by hand, or leave them out." if missed else "")
    if b2.button("Clear board"):
        ss.cmp_assign = {n: None for n in names}
        ss.cmp_rev += 1
        ss.cmp_msg = ""
    if ss.get("cmp_msg"):
        st.caption(ss.cmp_msg)

    value = grouping_board(run["thumbs"], rows, cols, row_label, col_label, ss.cmp_assign, ss.cmp_rev,
                           key="cmp_board")
    if value and value.get("rev") == ss.cmp_rev and (value["rev"], value["seq"]) != ss.get("cmp_seen"):
        ss.cmp_assign = {n: tuple(c) if c else None for n, c in value["assignment"].items()}
        ss.cmp_seen = (value["rev"], value["seq"])

    labels = labels_table(ss.cmp_assign, row_key, col_label, rows, cols, order=names)
    if labels.empty:
        st.info("Nothing on the board yet.")
        return None
    shown = labels.drop(columns=["_row"]) if single_row else labels

    left, right = st.columns([3, 2])
    with right:
        st.subheader("Labels")
        st.caption('Saved in the workbook\'s "labels" sheet.')
        st.dataframe(shown, hide_index=True)
    with left:
        st.subheader("Replicates per group")
        numeric = [c for c in regions.columns if pd.api.types.is_numeric_dtype(regions[c])]
        if not numeric:
            st.info("No numeric results to plot.")
            return shown
        default = numeric.index("crack_area_pct") if "crack_area_pct" in numeric else 0
        metric = st.selectbox("Result to plot", numeric, index=default, key="cmp_metric")
        region_names = list(dict.fromkeys(regions["region"]))
        region = region_names[0]
        if len(region_names) > 1:
            region = st.selectbox("Region", region_names, key="cmp_region")
        data = regions[regions["region"] == region].merge(labels, on="image_filename")
        fig, ax = plt.subplots(figsize=(6, 3.6))
        plot_replicates(ax, data, metric, col_label, row_key, cols, rows)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.caption("Each dot is one image. Bars are group means, drawn only where a group has 2 or more "
                   "images. n = 1 is shown in red: there is no replicate spread to compare against.")
    return shown


def download_section(run: dict, labels: pd.DataFrame | None) -> None:
    if not run["analyses"]:
        return
    with tempfile.TemporaryDirectory() as tmp:
        xlsx = Path(tmp) / "results.xlsx"
        write_workbook(run["analyses"], run["settings"], xlsx, labels=labels)
        data = xlsx.read_bytes()
    st.download_button(
        "Download results (.xlsx)", data=data, file_name="crack_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Includes a labels sheet when images are on the board.",
    )


def main() -> None:
    st.set_page_config(page_title="Crack pattern analysis", layout="wide")
    st.title("Crack pattern analysis")
    st.caption("Runs on this machine only. Method: docs/walkthrough/ and METHODOLOGY.md.")

    uploaded = st.file_uploader(
        "Micrographs", type=["jpg", "jpeg", "png", "tif", "tiff", "bmp"], accept_multiple_files=True,
    )
    form = settings_form()
    if form is not None and uploaded and st.button("Run analysis"):
        settings, figures, map_column = form
        st.session_state.run = run_analysis(uploaded, settings, figures, map_column)

    run = st.session_state.get("run")
    if run is None:
        return
    st.divider()
    st.caption("Results of the last run. Changed settings take effect when you run again.")
    show_results(run)
    labels = compare_section(run) if run["analyses"] else None
    download_section(run, labels)


if __name__ == "__main__":
    main()
