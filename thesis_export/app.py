"""Browser GUI for the crack analysis. Runs locally; nothing is uploaded.

Run: python3 -m streamlit run app.py

The page is laid out the way the analysis works:
    calibration -> regions -> measurements -> figures -> run
Every control sets one field of an AnalysisSettings (src/crackgraph/settings.py),
and the run calls the same analyze_image() as the command line
(src/analyze.py). The settings used are saved in the workbook's
"settings" sheet.
"""

import tempfile
import time
from pathlib import Path

import streamlit as st

from src.crackgraph.analysis import analysis_stages, analyze_image
from src.crackgraph.export import results_tables, write_figures, write_workbook
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


def main() -> None:
    st.set_page_config(page_title="Crack pattern analysis", layout="wide")
    st.title("Crack pattern analysis")
    st.caption("Runs on this machine only. Method: docs/walkthrough/ and METHODOLOGY.md.")

    uploaded = st.file_uploader(
        "Micrographs", type=["jpg", "jpeg", "png", "tif", "tiff", "bmp"], accept_multiple_files=True,
    )
    form = settings_form()
    if form is None or not uploaded:
        return
    settings, figures, map_column = form
    if not st.button("Run analysis"):
        return

    stages = analysis_stages(settings)
    total = len(stages) * len(uploaded)
    done = [0]
    start = time.monotonic()
    bar = st.progress(0.0, text="Starting...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        analyses, errors = [], []
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
            with st.expander(f.name, expanded=len(uploaded) == 1):
                for png in write_figures(analysis, tmp / "figures", figures, map_column):
                    st.image(str(png), caption=png.stem)
        bar.progress(1.0, text="Done.")

        for name, msg in errors:
            st.error(f"{name}: {msg}")
        if not analyses:
            return

        if abs(settings.um_per_px - DEFAULT_UM_PER_PX) < 1e-12:
            st.caption("µm columns use the thesis microscope calibration; change µm per pixel for other images.")
        for name, df in results_tables(analyses).items():
            st.subheader(name.replace("_", " ").capitalize())
            if name == "image_connectivity":
                st.caption("Connectivity is measured on the whole image only, not per region.")
            st.dataframe(df)

        xlsx = tmp / "results.xlsx"
        write_workbook(analyses, settings, xlsx)
        st.download_button(
            "Download results (.xlsx)", data=xlsx.read_bytes(), file_name="crack_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
