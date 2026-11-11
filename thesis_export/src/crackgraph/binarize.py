"""Stage 1: binarize a (near-binary) crack micrograph.

These images are assumed to have no illumination gradient to compensate for.
"""

from dataclasses import dataclass

import numpy as np
from skimage.filters import threshold_otsu


@dataclass
class BinarizeResult:
    mask: np.ndarray  # bool
    threshold: float  # [measured] Otsu threshold, 0-255 grayscale
    foreground_fraction: float  # [measured]


def binarize(gray: np.ndarray) -> BinarizeResult:
    t = threshold_otsu(gray)
    mask = gray > t
    return BinarizeResult(
        mask=mask,
        threshold=float(t),
        foreground_fraction=float(mask.mean()),
    )
