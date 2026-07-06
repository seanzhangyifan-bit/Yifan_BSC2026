"""Renders a battery of ValidationCaseResult (see validation_cases.py) into
one static HTML gallery page, grouped by method (junction/kink/corner/
curvature/anisotropy). Unlike html_report.py's report.html, this is not
registry-backed/incrementally upserted across sessions -- the case battery
is fixed and fully re-run each time scripts/validation_gallery.py is
invoked, so the HTML is simply built fresh from whatever results that run
produced. Same plain-CSS, no-JS visual idiom as html_report.py.
"""

from pathlib import Path

from .validation_cases import ValidationCaseResult

_METHOD_TITLES = {
    "junction": "Junction classification (T / Y / angle recovery)",
    "kink": "Kink detection",
    "corner": "Corner cross-check",
    "curvature": "Curvature / tortuosity",
    "anisotropy": "Anisotropy",
}


def _render_rows(rows: list[tuple[str, str, str, bool]]) -> str:
    row_html = []
    for metric, expected, measured, passed in rows:
        verdict = "PASS" if passed else "FAIL"
        row_html.append(f"""
        <tr class="{"pass" if passed else "fail"}">
          <td>{metric}</td>
          <td>{expected}</td>
          <td>{measured}</td>
          <td class="verdict">{verdict}</td>
        </tr>""")
    return "".join(row_html)


def _render_case(result: ValidationCaseResult) -> str:
    badge = "PASS" if result.passed else "FAIL"
    return f"""
    <div class="case">
      <h3>{result.name} <span class="badge {"pass" if result.passed else "fail"}">{badge}</span></h3>
      <p class="description">{result.description}</p>
      <img src="{result.image_relpath}" alt="{result.name}">
      <table>
        <thead><tr><th>metric</th><th>expected</th><th>measured</th><th>verdict</th></tr></thead>
        <tbody>{_render_rows(result.rows)}</tbody>
      </table>
    </div>"""


def render_validation_report(results: list[ValidationCaseResult], out_path: str | Path) -> Path:
    """Write the full HTML gallery to out_path. Returns out_path."""
    by_method: dict[str, list[ValidationCaseResult]] = {}
    for r in results:
        by_method.setdefault(r.method, []).append(r)

    n_passed = sum(r.passed for r in results)
    n_total = len(results)

    sections_html = []
    for method in _METHOD_TITLES:
        if method not in by_method:
            continue
        cases_html = "".join(_render_case(r) for r in by_method[method])
        sections_html.append(f"""
  <section class="method">
    <h2>{_METHOD_TITLES[method]}</h2>
    {cases_html}
  </section>""")

    body = "".join(sections_html) if sections_html else "<p>No validation cases run yet.</p>"

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Synthetic-pattern validation gallery</title>
<style>
  body {{ font-family: sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
  section.method {{ margin-bottom: 2.5em; }}
  section.method h2 {{ background: #eee; padding: 0.3em 0.6em; }}
  .case {{ margin: 1.5em 0; padding-left: 0.6em; border-left: 3px solid #ccc; }}
  .case h3 {{ margin-bottom: 0.2em; }}
  .description {{ color: #555; font-size: 0.9em; }}
  img {{ max-width: 100%; border: 1px solid #ddd; }}
  table {{ border-collapse: collapse; margin-top: 0.5em; font-size: 0.9em; }}
  th, td {{ border: 1px solid #ddd; padding: 0.3em 0.6em; text-align: left; }}
  tr.fail td {{ background: #fdecea; }}
  .verdict {{ font-weight: bold; }}
  .badge {{ font-size: 0.7em; padding: 0.1em 0.5em; border-radius: 0.3em; }}
  .badge.pass {{ background: #d4edda; color: #155724; }}
  .badge.fail {{ background: #f8d7da; color: #721c24; }}
</style>
</head>
<body>
<h1>Synthetic-pattern validation gallery</h1>
<p>Known-ground-truth synthetic test images (see synthetic.py), run through
the real measurement pipeline and rendered with its own overlay/rose
diagrams, next to expected-vs-measured tables. Every tolerance shown here
mirrors an existing assertion in tests/test_*.py -- this page is a visual
companion to that suite, not a replacement for it. {n_passed}/{n_total} cases pass.</p>
{body}
</body>
</html>
"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path
