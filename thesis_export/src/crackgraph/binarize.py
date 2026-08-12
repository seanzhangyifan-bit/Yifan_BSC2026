"""Stage 1: binarize a (near-binary) crack micrograph.

Global Otsu thresholding only -- no adaptive/local thresholding. These
images have no illumination gradient to compensate for (they read as
already-segmented bright crack lines on a black background, not raw SEM
grayscale texture), so adaptive thresholding would solve a problem that
isn't present and risks fragmenting thin lines on JPEG noise.
"""

from dataclasses import dataclass

import numpy as np
from skimage.filters import threshold_otsu


@dataclass
class BinarizeResult:
    mask: np.ndarray  # bool
    threshold: float  # [measured] Otsu threshold, 0-255 grayscale
    foreground_fraction: float  # [measured]
    sanity_ok: bool  # [interpreted]
    sanity_band: tuple[float, float]


def binarize(
    gray: np.ndarray,
    *,
    sanity_band: tuple[float, float] = (0.01, 0.15),
) -> BinarizeResult:
    t = threshold_otsu(gray)
    mask = gray > t
    frac = float(mask.mean())
    ok = sanity_band[0] <= frac <= sanity_band[1]
    return BinarizeResult(
        mask=mask,
        threshold=float(t),
        foreground_fraction=frac,
        sanity_ok=ok,
        sanity_band=sanity_band,
    )
