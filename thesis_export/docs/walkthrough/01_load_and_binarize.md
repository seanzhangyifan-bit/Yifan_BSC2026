# 1. Loading and binarizing

**Files**: `src/crackgraph/io_utils.py` (17 lines), `src/crackgraph/binarize.py` (40 lines)

These two short files turn a `.jpg` into a black-and-white **mask**: a grid where every pixel
is either crack (`True`) or not crack (`False`). Everything else in the project starts from
that mask.

---

## `io_utils.py`: open the image

### `load_image(path)`, line 9

| Line | Code | What it means |
|---|---|---|
| 9 | `def load_image(path: str \| Path) -> tuple[np.ndarray, np.ndarray]:` | Takes a file path and returns **two** pixel grids. The parts after `:` and `->` are type hints: notes on what goes in and out, not enforced. |
| 14 | `with Image.open(path) as im:` | Opens the file with Pillow (PIL). `with` closes it automatically afterwards. |
| 15 | `rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)` | A **colour** copy: red/green/blue per pixel, whole numbers 0–255. Shape: height × width × 3. |
| 16 | `gray = np.asarray(im.convert("L"), dtype=np.float64)` | A **grayscale** copy: one brightness per pixel, 0 = black, 255 = white, stored as decimals for the maths later. Shape: height × width. |
| 17 | `return gray, rgb` | Returns both. |

- `gray` is what the analysis uses.
- `rgb` is only for drawing results on top of the original photo.
- `"L"` mode weights green most (`0.299·R + 0.587·G + 0.114·B`). Your micrographs are nearly grey
  already, so this barely matters.

---

## `binarize.py`: crack or not crack?

**Why one threshold for the whole image.** The opening comment (lines 1–8) explains that your
images are already high-contrast: bright cracks on a dark background, with no uneven lighting.
So one brightness cutoff for the whole image works. An "adaptive" threshold, a different cutoff
for each small area, would fix a problem these images don't have, and could break thin cracks
apart on JPEG noise. `scripts/validation/segmentation_sensitivity_sweep.py` measures how much the
results change if this threshold moves.

### `BinarizeResult`, line 17: what this step returns

| Field | Meaning |
|---|---|
| `mask` | The black-and-white grid. `True` = crack. |
| `threshold` | The brightness cutoff chosen, 0–255. `[measured]` |
| `foreground_fraction` | Share of the image marked crack. 0.08 = 8%. |
| `sanity_ok` | Is that share inside a plausible range? `[interpreted]` |
| `sanity_band` | The plausible range used, by default 1%–15%. |

### `binarize(gray, *, sanity_band=(0.01, 0.15))`, line 25

| Line | Code | What it means |
|---|---|---|
| 25–29 | function header | Takes the grayscale grid. The `*` means `sanity_band` must be passed by name. |
| 30 | `t = threshold_otsu(gray)` | **The key line.** Otsu's method looks at the histogram of all brightnesses and picks the cutoff that best splits them into two groups (dark background, bright cracks), each as uniform as possible inside itself. Fully automatic. |
| 31 | `mask = gray > t` | Brighter than the cutoff = crack. Runs over all ~55 million pixels at once. |
| 32 | `frac = float(mask.mean())` | The average of True/False values is the share of True. |
| 33 | `ok = sanity_band[0] <= frac <= sanity_band[1]` | Is the share between 1% and 15%? |
| 34–40 | `return BinarizeResult(...)` | Packs everything up. |

**Worth knowing**

- **Cracks must be the bright part.** Line 31 assumes this. Dark-crack images would come out
  inverted.
- **The sanity check only warns.** Nothing stops if it fails. Very crack-dense images often go
  over 15%, which is expected.
- **No cleanup happens here.** Removing specks and filling tiny holes happens at the start of
  `skeleton.py`.

**Tests**: binarize has no dedicated test file. Every pipeline test runs through it, though,
with `sanity_band=(0.0, 1.0)` so synthetic images never trigger the warning.
