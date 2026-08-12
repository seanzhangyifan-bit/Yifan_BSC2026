"""Local, browser-based GUI for the core pipeline and the batch crack-stats export.

Run: streamlit run app.py

Runs entirely on this machine -- Streamlit serves locally at http://localhost:8501, nothing is
uploaded anywhere. This is a thin front-end onto two existing entry points (src/analyze_image.py
and scripts/batch_stats/export_crack_stats.py), not a new analysis method -- see METHODOLOGY.md
for the scientific reasoning and README.md's "five deliverables" table for validation status.

The two functions below (run_single_image_analysis, run_batch_analysis) contain all the actual
logic and take no Streamlit objects as arguments -- they're callable and testable on their own,
independent of the browser UI. Everything below main() is thin Streamlit glue.
"""

import io
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from scripts.batch_stats.export_crack_stats import compute_row

REPO_ROOT = Path(__file__).resolve().parent


def run_single_image_analysis(
    image_path: Path, out_dir: Path, *, full_image: bool = False, show_fit_detail: bool = False
) -> dict:
    """Runs src.analyze_image as a subprocess -- deliberately not imported directly, since
    analyze_image.py is a monolithic CLI script with no function separable from its own argument
    parsing and printing today. Shelling out keeps this GUI at zero risk to that well-tested
    pipeline code. Returns the console report text plus paths to whichever overlay/precedence
    PNGs analyze_image.py actually wrote (filename convention confirmed directly against its
    source, not guessed: {stem}_{corner|full}_overlay[.png|_detail.png],
    {stem}_{corner|full}_precedence.png, under out_dir/<image's own parent folder name>/)."""
    cmd = [sys.executable, "-m", "src.analyze_image", str(image_path), "--out-dir", str(out_dir)]
    if full_image:
        cmd.append("--full-image")
    if show_fit_detail:
        cmd.append("--show-fit-detail")
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    stem = image_path.stem
    tag = "full" if full_image else "corner"
    subfolder = out_dir / image_path.parent.name
    overlay_png = subfolder / f"{stem}_{tag}_overlay.png"
    precedence_png = subfolder / f"{stem}_{tag}_precedence.png"
    detail_png = subfolder / f"{stem}_{tag}_overlay_detail.png"

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "overlay_png": overlay_png if overlay_png.exists() else None,
        "precedence_png": precedence_png if precedence_png.exists() else None,
        "detail_png": detail_png if (show_fit_detail and detail_png.exists()) else None,
    }


def run_batch_analysis(image_paths: list[Path]) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Calls compute_row() directly, per image -- already a clean, general-purpose function with
    no hardcoded filename-pattern dependency (unlike export_crack_stats.py's own main(), which
    globs a fixed naming convention this GUI's arbitrary uploads won't match). Returns the results
    table plus a list of (filename, error message) for any image that failed, rather than letting
    one bad image abort the whole batch."""
    rows = []
    errors = []
    for path in image_paths:
        try:
            rows.append(compute_row(path))
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not swallowed
            errors.append((path.name, str(exc)))
    return pd.DataFrame(rows), errors


def _single_image_tab() -> None:
    st.header("Single image")
    st.caption(
        "Full stage 1-5 pipeline: binarize, skeletonize, classify every junction (T/Y), "
        "cross-check against an independent corner method, assemble a precedence graph."
    )
    uploaded = st.file_uploader(
        "Upload a micrograph", type=["jpg", "jpeg", "png", "tif", "tiff"], key="single_upload"
    )
    col1, col2 = st.columns(2)
    full_image = col1.checkbox("Analyze full image (default: top-left corner crop)")
    show_fit_detail = col2.checkbox("Show fit-detail overlay")

    if uploaded is None:
        return
    if not st.button("Run analysis", key="run_single"):
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_path = tmp_path / uploaded.name
        image_path.write_bytes(uploaded.getvalue())
        out_dir = tmp_path / "outputs"

        with st.spinner("Running the pipeline..."):
            try:
                result = run_single_image_analysis(
                    image_path, out_dir, full_image=full_image, show_fit_detail=show_fit_detail
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Analysis failed to run: {exc}")
                return

        if result["returncode"] != 0:
            st.error("Analysis failed:")
            st.code(result["stderr"] or result["stdout"] or "(no output captured)")
            return

        st.success("Done.")
        if result["overlay_png"] is not None:
            st.image(str(result["overlay_png"]), caption="Junction classification overlay")
        if result["detail_png"] is not None:
            st.image(str(result["detail_png"]), caption="Fit-detail overlay")
        if result["precedence_png"] is not None:
            st.image(str(result["precedence_png"]), caption="Precedence graph")
        st.subheader("Console report")
        st.code(result["stdout"] or "(no output captured)")


def _batch_tab() -> None:
    st.header("Batch folder")
    st.caption(
        "Stage 1-3 only (binarize -> skeletonize -> graph extraction) -- crack density, width, "
        "and connectivity stats per image, no junction classification or ordering. Same "
        "computation as scripts/batch_stats/export_crack_stats.py."
    )
    uploaded_files = st.file_uploader(
        "Upload multiple micrographs",
        type=["jpg", "jpeg", "png", "tif", "tiff"],
        accept_multiple_files=True,
        key="batch_upload",
    )
    if not uploaded_files:
        return
    if not st.button("Run batch analysis", key="run_batch"):
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_paths = []
        for uploaded in uploaded_files:
            p = tmp_path / uploaded.name
            p.write_bytes(uploaded.getvalue())
            image_paths.append(p)

        progress = st.progress(0.0, text="Starting...")
        results = []
        errors = []
        for i, path in enumerate(image_paths):
            progress.progress(i / len(image_paths), text=f"Processing {path.name} ({i + 1}/{len(image_paths)})")
            try:
                results.append(compute_row(path))
            except Exception as exc:  # noqa: BLE001
                errors.append((path.name, str(exc)))
        progress.progress(1.0, text="Done.")

        if errors:
            st.warning(f"{len(errors)} of {len(image_paths)} image(s) failed:")
            for name, msg in errors:
                st.text(f"  {name}: {msg}")

        if not results:
            return

        df = pd.DataFrame(results)
        st.warning(
            "The µm/mm² columns (avg_width_um, crack_area_mm2, median_width_um, etc.) assume "
            "this project's own microscope calibration (100/164 µm/px) and are almost "
            "certainly wrong for a different image source. The _px columns are unaffected by "
            "calibration and are always meaningful."
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


def main() -> None:
    st.set_page_config(page_title="Crack pattern analysis", layout="wide")
    st.title("Crack pattern analysis")
    st.caption(
        "Local tool -- runs entirely on this machine, nothing is uploaded anywhere. "
        "See METHODOLOGY.md for the scientific reasoning behind the analysis."
    )
    tab1, tab2 = st.tabs(["Single image", "Batch folder"])
    with tab1:
        _single_image_tab()
    with tab2:
        _batch_tab()


if __name__ == "__main__":
    main()
