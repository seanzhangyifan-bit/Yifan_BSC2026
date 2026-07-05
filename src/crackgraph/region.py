"""Default region-of-interest selection.

Full-image runs are deferred (see README) while stage 1-3 is being validated.
The working default is a fixed top-left corner crop, sized and inset as a
fraction of image *width* only (so the recipe is reproducible across images
of slightly different dimensions without hand-picking pixel coordinates).
"""

from dataclasses import dataclass


@dataclass
class Region:
    row_slice: slice
    col_slice: slice
    corner_frac: float
    edge_margin_frac: float


def default_corner_crop(
    height: int,
    width: int,
    *,
    corner_frac: float = 0.125,
    edge_margin_frac: float = 0.02,
) -> Region:
    """Top-left corner crop, inset from the true image edges.

    margin_px and crop_px are both derived from `width` only, per the
    project's current working convention, and applied uniformly to rows
    and columns.
    """
    margin_px = round(edge_margin_frac * width)
    crop_px = round(corner_frac * width)
    row_end = min(margin_px + crop_px, height)
    col_end = min(margin_px + crop_px, width)
    row_slice = slice(min(margin_px, row_end), row_end)
    col_slice = slice(min(margin_px, col_end), col_end)
    return Region(
        row_slice=row_slice,
        col_slice=col_slice,
        corner_frac=corner_frac,
        edge_margin_frac=edge_margin_frac,
    )
