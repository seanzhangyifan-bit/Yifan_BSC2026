"""Debug figure: what the engine changed or left out, drawn on the micrograph.

Meant for judging how the algorithm performs on an image, not for reporting.
Left: the whole image. Right: four full-resolution crops (A-D), picked where
the engine made the most corrections (pruning, specks, flaking), plus the
image centre as a neutral reference. Crop outlines are drawn on the overview.

Layers:
- kept skeleton (lime), edges omitted because they touch flaking (magenta)
- flaking-excluded region (red tint)
- pruned branches: spurs (orange), fragments (yellow), host stubs (sky blue)
- dark specks removed from cracks (blue), bright spots filled (white circles)
- the binarized crack boundary (grey line, crops only)

Specks are a few pixels across, so the overview marks them with dots; the
crops show their real shape. Display only: nothing here changes a measurement.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image
from scipy import ndimage

from .analysis import ImageAnalysis

CROP_PX = 512  # side of each zoom crop, in image pixels
OVERVIEW_PX = 1500  # longest side of the overview, in display pixels
DPI = 150

KEPT = "lime"
OMITTED = "magenta"
FLAKING_RGBA = (1.0, 0.0, 0.0, 0.3)
PRUNED = {"spur": "orange", "fragment": "yellow", "host_stub": "deepskyblue"}
PRUNED_LABEL = {"spur": "spur", "fragment": "fragment", "host_stub": "host stub"}
DARK_SPECK = "blue"
BRIGHT_SPOT = "white"
BOUNDARY = "silver"


def _layers(analysis: ImageAnalysis) -> dict:
    """Pixel masks and paths for every layer, in full-image coordinates."""
    eng = analysis.engine
    mask = eng.binarize.mask
    clean = eng.skeleton.mask_clean
    kept, omitted = [], []
    for k in eng.graph.summary.index:
        coords = eng.skeleton.skeleton.path_coordinates(int(k))
        (omitted if int(k) in eng.omitted else kept).append(coords)
    pruned = {reason: [] for reason in PRUNED}
    for rec in eng.skeleton.pruned_branches:
        pruned[rec.reason].append(rec.coords)
    dark = clean & ~mask  # remove_small_holes turned these into crack
    bright = mask & ~clean  # remove_small_objects turned these into background
    return {
        "dark_specks": dark,
        "bright_spots": bright,
        "dark_centres": _centroids(dark),
        "bright_centres": _centroids(bright),
        "flaking": eng.flaking.excluded_mask,
        "kept": kept,
        "omitted": omitted,
        "pruned": pruned,
    }


def _centroids(mask: np.ndarray) -> np.ndarray:
    """(row, col) centre of each connected blob's bounding box. Bounding-box
    centres, not centres of mass: specks are a few pixels wide, so the two
    agree to within a pixel, and this is much faster on a large image."""
    labels, n = ndimage.label(mask)
    if n == 0:
        return np.zeros((0, 2))
    return np.array([((r.start + r.stop - 1) / 2, (c.start + c.stop - 1) / 2) for r, c in ndimage.find_objects(labels)])


def _pick_crops(analysis: ImageAnalysis, layers: dict) -> list[tuple[str, int, int]]:
    """Top-left corners of up to four CROP_PX windows: where the most
    branches were pruned, where the most specks were removed or filled,
    the biggest flaked patch, and the image centre. Duplicates are replaced
    by the next busiest window, so the four crops differ."""
    h, w = analysis.engine.shape
    c = min(CROP_PX, h, w)
    nr, nc = max(1, h // c), max(1, w // c)

    def block_counts(points: np.ndarray) -> np.ndarray:
        counts = np.zeros((nr, nc))
        if len(points):
            r = np.clip((points[:, 0] // c).astype(int), 0, nr - 1)
            col = np.clip((points[:, 1] // c).astype(int), 0, nc - 1)
            np.add.at(counts, (r, col), 1)
        return counts

    pruned_mid = np.array([co[len(co) // 2] for paths in layers["pruned"].values() for co in paths]).reshape(-1, 2)
    speck_pts = np.vstack([layers["dark_centres"], layers["bright_centres"]])
    flake = layers["flaking"]
    flake_counts = np.zeros((nr, nc))
    if flake.any():
        flake_counts = flake[: nr * c, : nc * c].reshape(nr, c, nc, c).sum(axis=(1, 3)).astype(float)
    omitted_mid = np.array([co[len(co) // 2] for co in layers["omitted"]]).reshape(-1, 2)

    candidates = [
        ("most pruning", block_counts(pruned_mid)),
        ("most specks", block_counts(speck_pts)),
        ("flaking", flake_counts + block_counts(omitted_mid)),
    ]
    busy = sum(cnt / max(cnt.max(), 1) for _, cnt in candidates)
    chosen, out = set(), []
    for why, counts in candidates:
        if counts.max() <= 0:
            continue
        for idx in np.argsort(counts, axis=None)[::-1]:
            rc = tuple(int(x) for x in np.unravel_index(idx, counts.shape))
            if rc not in chosen:
                chosen.add(rc)
                out.append((why, rc[0] * c, rc[1] * c))
                break
    centre = (max(0, h // 2 - c // 2), max(0, w // 2 - c // 2))
    out.append(("image centre", *centre))
    for idx in np.argsort(busy, axis=None)[::-1]:  # fill up to four
        if len(out) >= 4:
            break
        rc = tuple(int(x) for x in np.unravel_index(idx, busy.shape))
        if rc not in chosen:
            chosen.add(rc)
            out.append(("busy area", rc[0] * c, rc[1] * c))
    return out[:4]


def _tint(ax, mask: np.ndarray, rgba, extent=None) -> None:
    if mask.any():
        img = np.zeros((*mask.shape, 4))
        img[mask] = rgba
        ax.imshow(img, extent=extent, interpolation="nearest", zorder=1)


def _draw_paths(ax, paths, color, width, offset=(0, 0), scale=1.0, window=None) -> None:
    segs = []
    for co in paths:
        if window is not None:
            r0, r1, c0, c1 = window
            if co[:, 0].max() < r0 or co[:, 0].min() >= r1 or co[:, 1].max() < c0 or co[:, 1].min() >= c1:
                continue
        segs.append(((co - offset) * scale)[:, ::-1])
    if segs:
        ax.add_collection(LineCollection(segs, colors=color, linewidths=width, zorder=3))


def _draw_overview(ax, analysis, layers, crops, c) -> None:
    h, w = analysis.engine.shape
    scale = min(1.0, OVERVIEW_PX / max(h, w))
    size = (round(w * scale), round(h * scale))
    ax.imshow(np.asarray(Image.fromarray(analysis.rgb).resize(size, Image.LANCZOS)))
    flake_small = np.asarray(Image.fromarray(layers["flaking"]).resize(size, Image.NEAREST))
    _tint(ax, flake_small, FLAKING_RGBA)
    _draw_paths(ax, layers["kept"], KEPT, 0.3, scale=scale)
    _draw_paths(ax, layers["omitted"], OMITTED, 0.8, scale=scale)
    for reason, color in PRUNED.items():
        _draw_paths(ax, layers["pruned"][reason], color, 1.8, scale=scale)
    for key, kw in (("dark_centres", dict(c=DARK_SPECK, s=2)),
                    ("bright_centres", dict(facecolors="none", edgecolors=BRIGHT_SPOT, s=4, linewidths=0.4))):
        pts = layers[key] * scale
        if len(pts):
            ax.scatter(pts[:, 1], pts[:, 0], zorder=4, **kw)
    for letter, (_, r0, c0) in zip("ABCD", crops):
        ax.add_patch(plt.Rectangle((c0 * scale, r0 * scale), c * scale, c * scale,
                                   fill=False, edgecolor="white", linewidth=1.0, zorder=5))
        ax.text(c0 * scale + 4, r0 * scale + 4, letter, color="black", fontsize=8, va="top", zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_xlim(0, size[0])
    ax.set_ylim(size[1], 0)
    ax.axis("off")
    ax.set_title("Whole image (specks shown as dots)", fontsize=9)


def _draw_crop(ax, analysis, layers, letter, why, r0, c0, c) -> None:
    r1, c1 = r0 + c, c0 + c
    sl = (slice(r0, r1), slice(c0, c1))
    ax.imshow(analysis.rgb[sl], interpolation="nearest")
    ax.contour(analysis.engine.binarize.mask[sl], levels=[0.5], colors=BOUNDARY, linewidths=0.4, zorder=2)
    _tint(ax, layers["flaking"][sl], FLAKING_RGBA)
    _tint(ax, layers["dark_specks"][sl], matplotlib.colors.to_rgba(DARK_SPECK, 0.7))
    window = (r0, r1, c0, c1)
    _draw_paths(ax, layers["kept"], KEPT, 0.8, offset=(r0, c0), window=window)
    _draw_paths(ax, layers["omitted"], OMITTED, 1.2, offset=(r0, c0), window=window)
    for reason, color in PRUNED.items():
        _draw_paths(ax, layers["pruned"][reason], color, 1.4, offset=(r0, c0), window=window)
    pts = _centroids(layers["bright_spots"][sl])
    if len(pts):
        ax.scatter(pts[:, 1], pts[:, 0], facecolors="none", edgecolors=BRIGHT_SPOT, s=30, linewidths=0.8, zorder=4)
    ax.set_xlim(-0.5, c - 0.5)
    ax.set_ylim(c - 0.5, -0.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"{letter}: {why}  (rows {r0}-{r1}, cols {c0}-{c1})", fontsize=8)


def render_debug_figure(analysis: ImageAnalysis, out_path: Path) -> None:
    eng = analysis.engine
    layers = _layers(analysis)
    c = min(CROP_PX, *eng.shape)
    crops = _pick_crops(analysis, layers)

    fig = plt.figure(figsize=(20, 11), dpi=DPI, layout="constrained")
    left, right = fig.subfigures(1, 2, width_ratios=[1, 1])
    _draw_overview(left.subplots(), analysis, layers, crops, c)
    axes = right.subplots(2, 2).ravel()
    for ax, letter, (why, r0, c0) in zip(axes, "ABCD", crops):
        _draw_crop(ax, analysis, layers, letter, why, r0, c0, c)
    for ax in axes[len(crops):]:
        ax.axis("off")

    sk, fl = eng.skeleton, eng.flaking
    n_dark, n_bright = len(layers["dark_centres"]), len(layers["bright_centres"])
    handles = [
        Line2D([], [], color=KEPT, lw=2, label=f"kept skeleton ({len(layers['kept'])} segments)"),
        Line2D([], [], color=OMITTED, lw=2, label=f"touches flaking, left out ({len(layers['omitted'])})"),
        Patch(color=FLAKING_RGBA, label=f"flaking excluded ({fl.excluded_area_pct:.2f} % of image)"),
        Line2D([], [], color=PRUNED["spur"], lw=2, label=f"pruned spur ({sk.n_spurs_pruned})"),
        Line2D([], [], color=PRUNED["fragment"], lw=2, label=f"pruned fragment ({sk.n_fragments_pruned})"),
        Line2D([], [], color=PRUNED["host_stub"], lw=2, label=f"pruned host stub ({sk.n_host_stubs_pruned})"),
        Patch(color=DARK_SPECK, label=f"dark speck removed ({n_dark})"),
        Line2D([], [], ls="", marker="o", mfc="none", mec="black", label=f"bright spot filled ({n_bright})"),
        Line2D([], [], color=BOUNDARY, lw=1, label="binarized crack boundary (crops)"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=5, fontsize=8, frameon=False)
    settings = analysis.settings
    fig.suptitle(
        f"{analysis.image_path.name}: debug view  |  Otsu threshold {eng.binarize.threshold:.0f}, "
        f"crack pixels {100 * eng.binarize.foreground_fraction:.1f} %  |  spur cut-off {settings.spur_px:g} px, "
        f"dark-speck limit {settings.dark_speck_area_px} px  |  median crack width {fl.reference_width_px:.1f} px",
        fontsize=10,
    )
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
