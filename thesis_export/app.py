"""Local, browser-based GUI covering three of this project's five deliverables (see
README.md's "five deliverables" table): the per-image pipeline, the batch crack-stats
export, and the spatial overview figure. Deliverables #4 (validation gallery) and #5
(experimental) are intentionally command-line only -- #4 is evidence *about* the pipeline,
not something you'd run against your own image, and #5 is explicitly unvalidated.

Run: python3 -m streamlit run app.py
(if the bare `streamlit run app.py` command says "command not found", see README.md's
Setup section -- it's a PATH issue, not a broken install)

Runs entirely on this machine -- Streamlit serves locally at http://localhost:8501, nothing is
uploaded anywhere. This is a thin front-end onto existing entry points (src/analyze_image.py,
scripts/batch_stats/export_crack_stats.py, scripts/spatial_overview/overview_figure.py), not a
new analysis method -- see METHODOLOGY.md for the scientific reasoning and README.md's "five
deliverables" table for validation status.

run_single_image_analysis and run_spatial_overview contain the pipeline-side logic and take no
Streamlit objects as arguments -- they're callable and testable on their own, independent of the
browser UI (their `on_line` callback, if passed, is a plain callable, not a Streamlit object).
The crack-stats side calls compute_row() directly (see
scripts/batch_stats/export_crack_stats.py), which has the same property. Everything below main()
is thin Streamlit glue.
"""

import io
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from scripts.batch_stats.export_crack_stats import COMPUTE_ROW_STAGES, compute_row

REPO_ROOT = Path(__file__).resolve().parent

# Ordered, fixed set of section-header lines src/analyze_image.py always prints, one per
# stage, whether or not that stage was requested -- a skipped stage still prints its own
# header, immediately followed by a one-line "(skipped, ...)" instead of full stats (see
# analyze_image.py). Keeping this list independent of which measurements were checked lets
# the progress bar advance deterministically for any checkbox combination, without having
# to predict which headers a given run will produce.
STAGE_MARKERS: list[tuple[str, str]] = [
    ("-- Stage 1: Binarize --", "Binarizing"),
    ("-- Flaking/delamination exclusion", "Checking for flaking"),
    ("-- Stage 2: Skeletonize + prune --", "Skeletonizing"),
    ("-- Stage 3: Graph extraction (skan) --", "Extracting graph"),
    ("-- Edge curvature & tortuosity", "Curvature & tortuosity"),
    ("-- Network anisotropy", "Anisotropy"),
    ("-- Edge geometry: length/width/area", "Edge geometry"),
    ("-- Stage 4: Junction classification", "Junction classification"),
    ("-- Corner cross-check", "Corner cross-check"),
    ("-- Stage 5: Precedence graph", "Precedence graph"),
    ("-- Output --", "Writing output"),
]

# Same idea as STAGE_MARKERS, but for scripts/spatial_overview/overview_figure.py, which only
# prints two runtime lines (see its main()) rather than one header per stage. The second
# marker isn't a line prefix (it starts with a tile count that varies), so matching uses
# substring containment rather than startswith -- see _make_stage_progress_callback.
OVERVIEW_STAGE_MARKERS: list[tuple[str, str]] = [
    ("Whole-image pipeline runtime:", "Whole-image pass"),
    (" sections (", "Per-quadrant sections"),
]


def _format_duration(seconds: float) -> str:
    """Rounds down to whole seconds/minutes -- this is a rough progress estimate, not a
    measurement, so sub-second precision would only be false confidence."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s"


def _run_streaming(cmd: list[str], on_line: Callable[[str], None] | None) -> subprocess.CompletedProcess:
    """Runs cmd, calling on_line(line) as each line of output arrives, instead of blocking
    silently until the whole process exits (what subprocess.run(capture_output=True) does).
    stdout and stderr are merged -- the caller only needs one thing to read failures out of."""
    proc = subprocess.Popen(
        cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line)
        if on_line is not None:
            on_line(line)
    proc.wait()
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout="".join(lines), stderr="")


def run_single_image_analysis(
    image_path: Path,
    out_dir: Path,
    *,
    full_image: bool = False,
    show_fit_detail: bool = False,
    skip_curvature: bool = False,
    skip_anisotropy: bool = False,
    skip_junctions: bool = False,
    skip_corner_cross_check: bool = False,
    skip_precedence: bool = False,
    on_line: Callable[[str], None] | None = None,
) -> dict:
    """Runs src.analyze_image as a subprocess -- deliberately not imported directly, since
    analyze_image.py is a monolithic CLI script with no function separable from its own argument
    parsing and printing today. Shelling out keeps this GUI at zero risk to that well-tested
    pipeline code. Returns the console report text plus paths to whichever overlay/precedence
    PNGs analyze_image.py actually wrote (filename convention confirmed directly against its
    source, not guessed: {stem}_{corner|full}_overlay[.png|_detail.png],
    {stem}_{corner|full}_precedence.png, under out_dir/<image's own parent folder name>/ --
    the precedence PNG simply won't exist if skip_junctions/skip_precedence left it unbuilt)."""
    cmd = [sys.executable, "-m", "src.analyze_image", str(image_path), "--out-dir", str(out_dir)]
    if full_image:
        cmd.append("--full-image")
    if show_fit_detail:
        cmd.append("--show-fit-detail")
    if skip_curvature:
        cmd.append("--skip-curvature")
    if skip_anisotropy:
        cmd.append("--skip-anisotropy")
    if skip_junctions:
        cmd.append("--skip-junctions")
    if skip_corner_cross_check:
        cmd.append("--skip-corner-cross-check")
    if skip_precedence:
        cmd.append("--skip-precedence")
    result = _run_streaming(cmd, on_line)

    stem = image_path.stem
    tag = "full" if full_image else "corner"
    subfolder = out_dir / image_path.parent.name
    overlay_png = subfolder / f"{stem}_{tag}_overlay.png"
    precedence_png = subfolder / f"{stem}_{tag}_precedence.png"
    detail_png = subfolder / f"{stem}_{tag}_overlay_detail.png"

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "overlay_png": overlay_png if overlay_png.exists() else None,
        "precedence_png": precedence_png if precedence_png.exists() else None,
        "detail_png": detail_png if (show_fit_detail and detail_png.exists()) else None,
    }


def run_spatial_overview(
    image_path: Path, out_dir: Path, *, on_line: Callable[[str], None] | None = None
) -> dict:
    """Runs scripts.spatial_overview.overview_figure as a subprocess, same reasoning as
    run_single_image_analysis (shell out, zero risk to the script itself). Always uses the
    script's own 2x2 default grid -- METHODOLOGY.md notes render_overview_figure asserts
    exactly 4 sections, so this deliberately doesn't expose --n-rows/--n-cols. The script also
    updates outputs/report.html/report_data.json under out_dir as a side effect -- meaningless
    here since out_dir is a per-run temp directory the GUI throws away, so this doesn't surface
    that path to the caller."""
    cmd = [
        sys.executable,
        "-m",
        "scripts.spatial_overview.overview_figure",
        str(image_path),
        "--out-dir",
        str(out_dir),
    ]
    result = _run_streaming(cmd, on_line)
    overview_png = out_dir / image_path.parent.name / f"{image_path.stem}_overview.png"
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "overview_png": overview_png if overview_png.exists() else None,
    }


def _make_stage_progress_callback(
    markers: list[tuple[str, str]], bump: Callable[[str], None], image_label: str
) -> Callable[[str], None]:
    """Watches a subprocess's output lines for the given (marker, label) pairs, in order, and
    calls bump() once per stage reached -- gives real, per-stage progress instead of one
    spinner for the whole run. Substring containment, not startswith, since not every marker
    (e.g. OVERVIEW_STAGE_MARKERS' section-count line) is a fixed line prefix."""
    seen = 0

    def on_line(line: str) -> None:
        nonlocal seen
        if seen >= len(markers):
            return
        marker, label = markers[seen]
        if marker in line:
            seen += 1
            bump(f"{image_label} — {label}")

    return on_line


def main() -> None:
    st.set_page_config(page_title="Crack pattern analysis", layout="wide")
    st.title("Crack pattern analysis")
    st.caption(
        "Local tool -- runs entirely on this machine, nothing is uploaded anywhere. "
        "See METHODOLOGY.md for the scientific reasoning behind the analysis."
    )

    uploaded_files = st.file_uploader(
        "Upload one or more micrographs",
        type=["jpg", "jpeg", "png", "tif", "tiff"],
        accept_multiple_files=True,
        key="upload",
    )

    st.subheader("What to run")
    col1, col2 = st.columns(2)
    with col1:
        run_crack_stats = st.checkbox(
            "Crack stats (density, width, connectivity)",
            value=True,
            key="cb_crack_stats",
            help="Density, width, and connectivity numbers for each image, exported to a spreadsheet.",
        )
        run_curvature = st.checkbox(
            "Curvature & tortuosity",
            value=True,
            key="cb_curvature",
            help=(
                "How much each crack segment bends, and how much longer its actual path is "
                "than a straight line between its ends."
            ),
        )
        run_anisotropy = st.checkbox(
            "Anisotropy",
            value=True,
            key="cb_anisotropy",
            help="Whether cracks in this image tend to point in one dominant direction, or are randomly oriented.",
        )
    with col2:
        run_junctions = st.checkbox(
            "Junction classification (T/Y)",
            value=True,
            key="cb_junctions",
            help="Labels each 3-way crack meeting as a T (one crack stopped at another) or a Y (three cracks met at once).",
        )
        run_corner_check = st.checkbox(
            "Corner cross-check",
            value=True,
            key="cb_corner_check",
            disabled=not run_junctions,
            help="Requires junction classification. Double-checks each T/Y label with a second, independent method, to catch disagreements.",
        )
        run_precedence = st.checkbox(
            "Precedence graph",
            value=True,
            key="cb_precedence",
            disabled=not run_junctions,
            help=(
                "Requires junction classification. Uses T-junctions to work out which crack "
                "came first at each meeting point, and builds a partial timeline from that."
            ),
        )
        run_overview = st.checkbox(
            "Spatial overview (quadrant comparison)",
            value=False,
            key="cb_overview",
            help=(
                "Compares crack patterns across the image's four quadrants in one figure -- "
                "a quick first look at spatial variation, not a validated result."
            ),
        )
    # Effective values for building CLI flags -- force these off if junction classification
    # is off, regardless of a disabled checkbox's last displayed state.
    eff_corner_check = run_corner_check and run_junctions
    eff_precedence = run_precedence and run_junctions
    run_pipeline = run_curvature or run_anisotropy or run_junctions

    with st.expander("Advanced options"):
        full_image = st.checkbox("Analyze full image (default: top-left corner crop)")
        show_fit_detail = st.checkbox("Show fit-detail overlay")

    nothing_selected = not (run_crack_stats or run_pipeline or run_overview)
    if nothing_selected:
        st.info("Select at least one analysis to run.")
    if not uploaded_files:
        return

    if not st.button("Run analysis", key="run", disabled=nothing_selected):
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_paths = []
        for uploaded in uploaded_files:
            p = tmp_path / uploaded.name
            p.write_bytes(uploaded.getvalue())
            image_paths.append(p)
        out_dir = tmp_path / "outputs"
        n_images = len(image_paths)

        total_steps = (
            (len(STAGE_MARKERS) if run_pipeline else 0)
            + (len(COMPUTE_ROW_STAGES) if run_crack_stats else 0)
            + (len(OVERVIEW_STAGE_MARKERS) if run_overview else 0)
        ) * n_images
        steps_done = [0]
        start_time = time.monotonic()
        bar = st.progress(0.0, text="Starting...")

        def bump(text: str) -> None:
            steps_done[0] += 1
            frac = steps_done[0] / total_steps
            elapsed = time.monotonic() - start_time
            # Straight-line extrapolation from progress so far -- a rough estimate, not a
            # measurement, and a noisy one until a few steps have actually completed (early
            # stages like binarizing aren't representative of slower ones like junction
            # classification), so it's withheld for the first couple of steps rather than
            # shown with false confidence.
            eta_note = ""
            if steps_done[0] >= 3:
                eta = elapsed / frac - elapsed
                eta_note = f" · {_format_duration(elapsed)} elapsed, ~{_format_duration(eta)} left (rough estimate)"
            bar.progress(min(frac, 1.0), text=f"{text}{eta_note}")

        crack_stats_rows = []
        crack_stats_errors = []
        pipeline_errors = []
        overview_errors = []

        for i, image_path in enumerate(image_paths):
            image_label = f"{image_path.name} ({i + 1}/{n_images})"

            if run_pipeline:
                on_line = _make_stage_progress_callback(STAGE_MARKERS, bump, image_label)
                try:
                    result = run_single_image_analysis(
                        image_path,
                        out_dir,
                        full_image=full_image,
                        show_fit_detail=show_fit_detail,
                        skip_curvature=not run_curvature,
                        skip_anisotropy=not run_anisotropy,
                        skip_junctions=not run_junctions,
                        skip_corner_cross_check=not eff_corner_check,
                        skip_precedence=not eff_precedence,
                        on_line=on_line,
                    )
                except Exception as exc:  # noqa: BLE001
                    pipeline_errors.append((image_path.name, str(exc)))
                    result = None

                if result is not None:
                    with st.expander(f"Pipeline: {image_path.name}", expanded=n_images == 1):
                        if result["returncode"] != 0:
                            st.error("Analysis failed:")
                            st.code(result["stdout"] or "(no output captured)")
                        else:
                            if result["overlay_png"] is not None:
                                st.image(str(result["overlay_png"]), caption="Junction classification overlay")
                            if result["detail_png"] is not None:
                                st.image(str(result["detail_png"]), caption="Fit-detail overlay")
                            if result["precedence_png"] is not None:
                                st.image(str(result["precedence_png"]), caption="Precedence graph")
                            report_text = result["stdout"] or "(no output captured)"
                            with st.expander("Console report (full text)", expanded=False):
                                st.code(report_text)
                            st.download_button(
                                "Download console report (.txt)",
                                data=report_text,
                                file_name=f"{image_path.stem}_report.txt",
                                mime="text/plain",
                                key=f"dl_report_{i}",
                            )

            if run_overview:
                on_line = _make_stage_progress_callback(OVERVIEW_STAGE_MARKERS, bump, image_label)
                try:
                    overview_result = run_spatial_overview(image_path, out_dir, on_line=on_line)
                except Exception as exc:  # noqa: BLE001
                    overview_errors.append((image_path.name, str(exc)))
                    overview_result = None

                if overview_result is not None:
                    with st.expander(f"Spatial overview: {image_path.name}", expanded=n_images == 1):
                        if overview_result["returncode"] != 0:
                            st.error("Spatial overview failed:")
                            st.code(overview_result["stdout"] or "(no output captured)")
                        elif overview_result["overview_png"] is not None:
                            st.image(
                                str(overview_result["overview_png"]),
                                caption="Spatial overview (whole image + per-quadrant rose/tortuosity)",
                            )

            if run_crack_stats:
                try:
                    crack_stats_rows.append(
                        compute_row(
                            image_path,
                            on_stage=lambda stage, label=image_label: bump(f"{label} — {stage}"),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    crack_stats_errors.append((image_path.name, str(exc)))

        bar.progress(1.0, text="Done.")

        if pipeline_errors:
            st.warning(f"Pipeline failed to run for {len(pipeline_errors)} image(s):")
            for name, msg in pipeline_errors:
                st.text(f"  {name}: {msg}")

        if overview_errors:
            st.warning(f"Spatial overview failed to run for {len(overview_errors)} image(s):")
            for name, msg in overview_errors:
                st.text(f"  {name}: {msg}")

        if run_crack_stats:
            if crack_stats_errors:
                st.warning(f"Crack stats failed for {len(crack_stats_errors)} of {n_images} image(s):")
                for name, msg in crack_stats_errors:
                    st.text(f"  {name}: {msg}")
            if crack_stats_rows:
                st.subheader("Crack stats")
                df = pd.DataFrame(crack_stats_rows)
                st.warning(
                    "The µm/mm² columns (avg_width_um, crack_area_mm2, median_width_um, etc.) "
                    "assume this project's own microscope calibration (100/164 µm/px) and are "
                    "almost certainly wrong for a different image source. The _px columns are "
                    "unaffected by calibration and are always meaningful."
                )
                st.dataframe(df)
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine="openpyxl")
                st.download_button(
                    "Download as .xlsx",
                    data=buf.getvalue(),
                    file_name="batch_crack_stats.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


if __name__ == "__main__":
    main()
