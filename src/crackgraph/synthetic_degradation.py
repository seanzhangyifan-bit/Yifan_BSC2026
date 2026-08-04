"""Composable image-degradation passes for the synthetic-benchmark matrix.

Kept separate from synthetic.py on purpose: these operate on an already-
rasterized grayscale array (post-processing) and have nothing to do with
geometry construction -- mirrors this project's one-file-per-concern
pattern (flaking.py vs skeleton.py).

None of these have a closed-form ground truth for their degraded pixel
values -- two are lossy (JPEG re-encoding) or randomized (debris), and none
have documented real-world evidence in this project's own dataset (see
synthetic-benchmark plan and binarize.py's own docstring, which states real
images have no illumination gradient to compensate for). Callers should
report a clean-vs-degraded delta, or (for apply_debris at small speck size)
a pipeline invariant that should hold regardless -- never a fabricated
"expected" value for the degraded output itself.
"""

import io

import numpy as np
from PIL import Image
from skimage.draw import disk


def apply_illumination_gradient(
    gray: np.ndarray,
    direction_deg: float = 0.0,
    amplitude: float = 60.0,
) -> np.ndarray:
    """Add a smooth linear intensity ramp (peak-to-peak `amplitude`,
    oriented along `direction_deg`, 0=left-to-right/+col) to `gray`,
    clipped to [0, 255]. `[speculated]`: binarize.py's own docstring
    states these images have no illumination gradient to compensate for --
    this exists as a worst-case/precautionary check, not a fix for an
    observed problem.
    """
    theta = np.radians(direction_deg)
    rr, cc = np.mgrid[0 : gray.shape[0], 0 : gray.shape[1]]
    row_c, col_c = gray.shape[0] / 2.0, gray.shape[1] / 2.0
    # projection of each pixel's offset from center onto the gradient
    # direction, normalized to [-0.5, 0.5] across the image's own extent.
    proj = (cc - col_c) * np.cos(theta) + (rr - row_c) * np.sin(theta)
    span = float(np.abs(proj).max()) or 1.0
    ramp = (proj / span) * (amplitude / 2.0)
    return np.clip(gray + ramp, 0.0, 255.0)


def apply_jpeg_blocking(gray: np.ndarray, quality: int = 15) -> np.ndarray:
    """A REAL JPEG encode/decode round-trip (via Pillow), not a hand-
    simulated blockiness filter -- this is the only way to genuinely
    reproduce DCT block-boundary artifacts, closing the gap named in
    scripts/skeleton_loop_sweep.py:25 ("no synthetic case reproduces
    JPEG-compression boundary noise"). Lossy and libjpeg-version-
    dependent by construction -- no closed-form ground truth for the
    output pixel values, only a clean-vs-degraded comparison downstream.
    """
    u8 = np.clip(gray, 0.0, 255.0).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(u8, mode="L").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    decoded = np.array(Image.open(buf).convert("L"), dtype=np.float64)
    return decoded


def apply_debris(
    gray: np.ndarray,
    n_specks: int = 40,
    speck_radius_range_px: tuple[float, float] = (1.0, 4.0),
    fg_value: float = 230.0,
    rng_seed: int = 0,
) -> np.ndarray:
    """Stamp `n_specks` small bright filled disks (radius drawn uniformly
    from `speck_radius_range_px`) at random positions -- a stand-in for
    surface debris/charging artifacts. `[speculated]`: no evidence of this
    in the real dataset either (see synthetic-benchmark plan). Kept small
    by default (diameter well under skeleton.py's SPUR_PX_PLACEHOLDER=15)
    so a downstream pipeline-integration test can check whether pruning
    actually removes these specks, rather than asserting it here where no
    pipeline runs.
    """
    out = gray.copy()
    rng = np.random.default_rng(rng_seed)
    for _ in range(n_specks):
        row = float(rng.uniform(0, gray.shape[0]))
        col = float(rng.uniform(0, gray.shape[1]))
        radius = float(rng.uniform(*speck_radius_range_px))
        rr, cc = disk((row, col), radius, shape=gray.shape)
        out[rr, cc] = fg_value
    return out
