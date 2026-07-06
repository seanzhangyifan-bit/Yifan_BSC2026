"""update_master_report must build one HTML page for all coatings: a
second image (same or different coating) adds a section rather than
overwriting, and re-running the same (coating, image_stem) updates its
existing section in place instead of duplicating it."""

from src.crackgraph.html_report import HTML_FILENAME, REGISTRY_FILENAME, update_master_report


def _call(tmp_path, coating, image_stem, runtime_s=1.23, n_sections=16, relpath=None):
    relpath = relpath or f"{coating}/{image_stem}_overview.png"
    return update_master_report(
        tmp_path,
        coating=coating,
        image_stem=image_stem,
        overview_png_relpath=relpath,
        whole_image_runtime_s=runtime_s,
        n_sections=n_sections,
        tiling_desc="4x4 grid",
        timestamp_iso="2026-07-06T00:00:00",
    )


def test_creates_registry_and_html_files(tmp_path):
    html_path = _call(tmp_path, "T5", "image_a")

    assert html_path == tmp_path / HTML_FILENAME
    assert html_path.exists()
    assert (tmp_path / REGISTRY_FILENAME).exists()


def test_html_contains_image_stem_runtime_and_tiling_desc(tmp_path):
    html_path = _call(tmp_path, "T5", "image_a", runtime_s=4.56)

    html = html_path.read_text()
    assert "image_a" in html
    assert "4.56" in html
    assert "4x4 grid" in html
    assert "T5/image_a_overview.png" in html


def test_second_image_same_coating_adds_section_without_losing_first(tmp_path):
    html_path = _call(tmp_path, "T5", "image_a")
    html_path = _call(tmp_path, "T5", "image_b")

    html = html_path.read_text()
    assert "image_a" in html
    assert "image_b" in html
    assert html.count('<section class="coating">') == 1  # same coating -> one section


def test_different_coating_creates_its_own_section(tmp_path):
    html_path = _call(tmp_path, "T5", "image_a")
    html_path = _call(tmp_path, "humidity_loading", "image_b")

    html = html_path.read_text()
    assert "T5" in html
    assert "humidity_loading" in html
    assert html.count('<section class="coating">') == 2


def test_rerunning_same_image_updates_section_instead_of_duplicating(tmp_path):
    _call(tmp_path, "T5", "image_a", runtime_s=1.0)
    html_path = _call(tmp_path, "T5", "image_a", runtime_s=9.99)

    html = html_path.read_text()
    assert html.count('<div class="image-block">') == 1
    assert "9.99" in html
    assert "1.00" not in html
