"""One master HTML report holding every image's overview figure, grouped by
coating (the image's source subfolder under data/raw/, e.g. "T5",
"humidity_loading"). NOT one HTML file per coating and NOT one per image --
a single page so a new session (or the user) can open one file and see
everything analyzed so far.

Design: a small JSON registry (report_data.json, list of entries) is the
source of truth; the HTML itself is always *regenerated in full* from the
registry rather than patched/parsed in place. This avoids the fragility of
hand-rolled HTML find-and-replace (matching markers, nested groups) for
something that gets rebuilt in well under a second even with many entries --
same spirit as xlsx_report.py's "schema is data, rendering is derived"
split, just via JSON+HTML instead of an xlsx workbook.

update_master_report() is the one entry point callers need: it upserts this
image's entry (by (coating, image_stem), so re-running on the same image
replaces its section instead of duplicating it) and rewrites the HTML.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

REGISTRY_FILENAME = "report_data.json"
HTML_FILENAME = "report.html"


@dataclass
class ImageEntry:
    coating: str
    image_stem: str
    overview_png_relpath: str  # relative to the master HTML's own directory
    whole_image_runtime_s: float
    n_sections: int
    tiling_desc: str
    timestamp_iso: str


def _load_registry(json_path: Path) -> list[dict]:
    if not json_path.exists():
        return []
    with open(json_path) as f:
        return json.load(f)


def _save_registry(json_path: Path, entries: list[dict]) -> None:
    with open(json_path, "w") as f:
        json.dump(entries, f, indent=2)


def upsert_entry(json_path: str | Path, entry: ImageEntry) -> None:
    """Replace the entry for this (coating, image_stem) if one already
    exists (re-running the same image updates its section in place),
    otherwise append it."""
    json_path = Path(json_path)
    entries = _load_registry(json_path)
    entry_dict = asdict(entry)
    for i, existing in enumerate(entries):
        if existing["coating"] == entry.coating and existing["image_stem"] == entry.image_stem:
            entries[i] = entry_dict
            break
    else:
        entries.append(entry_dict)
    _save_registry(json_path, entries)


def _render_html(entries: list[dict]) -> str:
    coatings: dict[str, list[dict]] = {}
    for e in entries:
        coatings.setdefault(e["coating"], []).append(e)
    for group in coatings.values():
        group.sort(key=lambda e: e["image_stem"])

    sections_html = []
    for coating in sorted(coatings):
        image_blocks = []
        for e in coatings[coating]:
            image_blocks.append(f"""
    <div class="image-block">
      <h3>{e["image_stem"]}</h3>
      <p class="meta">
        tiling: {e["tiling_desc"]} ({e["n_sections"]} sections) &middot;
        whole-image pipeline runtime: {e["whole_image_runtime_s"]:.2f}s &middot;
        generated: {e["timestamp_iso"]}
      </p>
      <img src="{e["overview_png_relpath"]}" alt="overview figure for {e["image_stem"]}">
    </div>""")
        sections_html.append(f"""
  <section class="coating">
    <h2>{coating}</h2>
    {"".join(image_blocks)}
  </section>""")

    body = "".join(sections_html) if sections_html else "<p>No images analyzed yet.</p>"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Crack analysis overview -- all coatings</title>
<style>
  body {{ font-family: sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
  section.coating {{ margin-bottom: 2.5em; }}
  section.coating h2 {{ background: #eee; padding: 0.3em 0.6em; }}
  .image-block {{ margin: 1.5em 0; padding-left: 0.6em; border-left: 3px solid #ccc; }}
  .image-block h3 {{ margin-bottom: 0.2em; }}
  .meta {{ color: #555; font-size: 0.9em; }}
  img {{ max-width: 100%; border: 1px solid #ddd; }}
</style>
</head>
<body>
<h1>Crack analysis overview -- all coatings</h1>
<p>One section per coating (source subfolder under data/raw/), one image
block per analyzed image. Each image block currently holds its multi
-section overview figure (per-section + whole-image rose diagrams and
curvature/tortuosity histograms) -- see scripts/overview_figure.py.
Overlays and other per-image outputs are not embedded here yet
(deferred, see CLAUDE.md).</p>
{body}
</body>
</html>
"""


def update_master_report(
    master_dir: str | Path,
    *,
    coating: str,
    image_stem: str,
    overview_png_relpath: str,
    whole_image_runtime_s: float,
    n_sections: int,
    tiling_desc: str,
    timestamp_iso: str,
) -> Path:
    """Upsert this image's entry into the registry and rewrite the master
    HTML in full. Returns the path to the (re)written HTML file.
    """
    master_dir = Path(master_dir)
    master_dir.mkdir(parents=True, exist_ok=True)
    json_path = master_dir / REGISTRY_FILENAME
    html_path = master_dir / HTML_FILENAME

    entry = ImageEntry(
        coating=coating,
        image_stem=image_stem,
        overview_png_relpath=overview_png_relpath,
        whole_image_runtime_s=whole_image_runtime_s,
        n_sections=n_sections,
        tiling_desc=tiling_desc,
        timestamp_iso=timestamp_iso,
    )
    upsert_entry(json_path, entry)

    entries = _load_registry(json_path)
    html_path.write_text(_render_html(entries))
    return html_path
