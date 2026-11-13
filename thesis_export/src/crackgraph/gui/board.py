"""Drag-and-drop grouping board for the Streamlit GUI (app.py).

The frontend is one self-contained file, grouping_board/index.html: no build
step, no network access. Streamlit is imported here only, so the rest of the
library doesn't need it.

Python owns the assignment {image_filename: [row, col] or None}. Each time
Python changes it itself (pre-sort, clear, a new board layout) it bumps
`rev`; the board then adopts it. Moves made on the board come back tagged
with that `rev`, so a stale value from before a Python-side change is ignored.
"""

import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image
from streamlit.components.v1 import declare_component

_board = declare_component("grouping_board", path=str(Path(__file__).parent / "grouping_board"))

THUMB_PX = 160


def thumbnail_data_uri(rgb: np.ndarray, size: int = THUMB_PX) -> str:
    """A small JPEG of the image as a data: URI, for the board."""
    img = Image.fromarray(np.asarray(rgb)).convert("RGB")
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def grouping_board(
    images: list[dict], rows: list[str], cols: list[str], row_label: str, col_label: str,
    assignment: dict, rev: int, key: str,
) -> dict | None:
    """Draw the board. Returns the board's last {rev, seq, assignment}, or None
    before the user has moved anything."""
    return _board(
        images=images, rows=rows, cols=cols, row_label=row_label, col_label=col_label,
        assignment={k: (list(v) if v else None) for k, v in assignment.items()},
        rev=rev, key=key, default=None,
    )
