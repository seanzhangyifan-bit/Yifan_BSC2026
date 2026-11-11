"""render_validation_report must group cases by method, show a pass/fail
badge per case, and embed the metric/expected/measured table -- checked
against hand-built ValidationCaseResult fixtures, no real image generation
(mirrors test_html_report.py's style)."""

from src.crackgraph.validation_cases import ValidationCaseResult
from src.crackgraph.validation_report import render_validation_report


def _case(name, method, passed, rows=None):
    return ValidationCaseResult(
        name=name,
        method=method,
        description=f"description for {name}",
        image_relpath=f"{name}.png",
        rows=rows or [("angle (deg)", "90.0", "89.4", passed)],
        passed=passed,
    )


def test_creates_html_file(tmp_path):
    html_path = render_validation_report([_case("straight", "curvature", True)], tmp_path / "report.html")
    assert html_path.exists()


def test_groups_cases_by_method(tmp_path):
    results = [
        _case("straight", "curvature", True),
        _case("arc", "curvature", True),
        _case("aligned", "anisotropy", True),
    ]
    html = render_validation_report(results, tmp_path / "report.html").read_text()
    assert html.count('<section class="method">') == 2
    assert "straight" in html and "arc" in html and "aligned" in html


def test_pass_and_fail_badges_rendered(tmp_path):
    results = [_case("good", "curvature", True), _case("bad", "curvature", False)]
    html = render_validation_report(results, tmp_path / "report.html").read_text()
    assert '<span class="badge pass">PASS</span>' in html
    assert '<span class="badge fail">FAIL</span>' in html


def test_image_tag_uses_relpath(tmp_path):
    html = render_validation_report([_case("straight", "curvature", True)], tmp_path / "report.html").read_text()
    assert '<img src="straight.png" alt="straight">' in html


def test_metric_expected_measured_row_rendered(tmp_path):
    rows = [("sector gap (deg)", "90.0", "88.2", True)]
    html = render_validation_report([_case("straight", "curvature", True, rows=rows)], tmp_path / "report.html").read_text()
    assert "<td>sector gap (deg)</td>" in html
    assert "<td>90.0</td>" in html
    assert "<td>88.2</td>" in html
    assert "PASS" in html


def test_summary_counts_passed_cases(tmp_path):
    results = [_case("a", "curvature", True), _case("b", "curvature", False), _case("c", "anisotropy", True)]
    html = render_validation_report(results, tmp_path / "report.html").read_text()
    assert "2/3 cases pass" in html
