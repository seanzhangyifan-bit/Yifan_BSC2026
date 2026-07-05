"""Image loading for the crack-graph pipeline."""

from pathlib import Path

import numpy as np
from PIL import Image


def load_image(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Load an image and return (grayscale float64, RGB uint8) arrays.

    Grayscale conversion uses PIL's standard luma weighting ('L' mode).
    """
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
        gray = np.asarray(im.convert("L"), dtype=np.float64)
    return gray, rgb
