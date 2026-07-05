"""Synthetic test image generation: a minimal, known-topology T-junction.

Used to validate the stage 1-3 chain end-to-end against a case with a known
right answer (1 junction of degree 3, 3 endpoints, 3 edges), rather than
just "runs without crashing" on real data.
"""

import numpy as np


def generate_t_junction(
    size: int = 120,
    thickness: int = 5,
    margin: int = 10,
    fg_value: float = 230.0,
    bg_value: float = 10.0,
) -> np.ndarray:
    """Grayscale image with exactly one T-junction.

    A horizontal "host" line spans the image width (inset by `margin` on
    each side); a vertical "abutter" line meets it from above at the
    host's midpoint and stops there (does not cross through) -- forming
    exactly one 3-way junction, with three endpoints (both host ends and
    the abutter's free end).
    """
    img = np.full((size, size), bg_value, dtype=np.float64)
    mid = size // 2
    half_t = thickness // 2

    # host: horizontal line
    img[mid - half_t : mid + half_t + 1, margin : size - margin] = fg_value

    # abutter: vertical line from the top margin down to the host line
    col_mid = size // 2
    img[margin : mid + half_t + 1, col_mid - half_t : col_mid + half_t + 1] = fg_value

    return img
