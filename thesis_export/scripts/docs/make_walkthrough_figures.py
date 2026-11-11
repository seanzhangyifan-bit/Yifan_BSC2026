"""Draw the explainer figures embedded in docs/walkthrough/ (01, 02).

Each figure runs the real library call the pipeline uses (threshold_otsu,
skeletonize, distance_transform_edt, skan) on a small hand-drawn shape, so the
picture shows what the library actually does, not a cartoon of it. The one
exception is the thinning animation: skeletonize() exposes no intermediate
steps, so it is animated with skimage's thin(), a close relative; the last
frames show thin()'s and skeletonize()'s finished results side by side in time.

real_pruned_branches.png is the one figure from real data: it runs the actual
pipeline on centre crops of three micrographs and shows branches the cleanup
loop removed, plus their numbers. It is skipped if data/raw isn't found.

Run: python3 -m scripts.docs.make_walkthrough_figures
Writes to docs/walkthrough/img/.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import skan
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import ListedColormap
from scipy.ndimage import convolve, distance_transform_edt, gaussian_filter
from skimage.draw import disk, line, polygon
from skimage.filters import threshold_otsu
from skimage.morphology import skeletonize, thin

OUT = Path(__file__).resolve().parents[2] / "docs" / "walkthrough" / "img"
BG, CRACK, REMOVED, SKEL = "#1b1b1b", "#d9d9d9", "#e8743b", "#2ca02c"


def _thick_line(img, r0, c0, r1, c1, w):
    rr, cc = line(r0, c0, r1, c1)
    for r, c in zip(rr, cc):
        dr, dc = disk((r, c), w / 2, shape=img.shape)
        img[dr, dc] = True


def _crack_image(size=160, seed=1):
    """Blurry, noisy grayscale crack network: what Otsu has to split."""
    m = np.zeros((size, size), bool)
    _thick_line(m, 10, 30, 150, 50, 6)
    _thick_line(m, 80, 40, 70, 150, 4)
    _thick_line(m, 30, 34, 20, 140, 3)
    _thick_line(m, 120, 46, 150, 120, 3)
    g = gaussian_filter(m.astype(float), 1.2) * 190 + 25
    g += gaussian_filter(np.random.default_rng(seed).normal(0, 30, m.shape), 0.6)
    return np.clip(g, 0, 255)


def otsu_sweep():
    gray = _crack_image()
    hist, edges = np.histogram(gray, bins=64, range=(0, 255))
    centers = (edges[:-1] + edges[1:]) / 2
    # Between-class variance for every candidate cutoff: Otsu picks its peak.
    ts = np.arange(5, 250, 4)
    p = hist / hist.sum()
    sigma_b = []
    for t in ts:
        lo = centers <= t
        w0, w1 = p[lo].sum(), p[~lo].sum()
        if w0 == 0 or w1 == 0:
            sigma_b.append(0.0)
            continue
        mu0 = (p[lo] * centers[lo]).sum() / w0
        mu1 = (p[~lo] * centers[~lo]).sum() / w1
        sigma_b.append(w0 * w1 * (mu0 - mu1) ** 2)
    sigma_b = np.array(sigma_b)
    t_otsu = threshold_otsu(gray)

    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6), dpi=72)
    ax[0].imshow(gray, cmap="gray", vmin=0, vmax=255)
    ax[0].set_title("input (grayscale)")
    mask_im = ax[1].imshow(gray > ts[0], cmap="gray")
    ax[1].set_title("mask = gray > cutoff")
    for a in ax[:2]:
        a.axis("off")
    bars = ax[2].bar(centers, hist, width=edges[1] - edges[0], color="#888")
    ax[2].set_yscale("log")
    ax[2].set_xlabel("brightness")
    ax[2].set_ylabel("pixel count (log)")
    vline = ax[2].axvline(ts[0], color="k", lw=1.5)
    ax2 = ax[2].twinx()
    ax2.plot(ts, sigma_b, color="#d62728", lw=1.5)
    ax2.set_yticks([])
    dot, = ax2.plot([ts[0]], [sigma_b[0]], "o", color="#d62728")
    ax2.text(0.98, 0.95, "red: how well the cutoff\nseparates the two groups",
             transform=ax2.transAxes, ha="right", va="top", fontsize=8, color="#d62728")
    title = ax[2].set_title("")
    fig.tight_layout()

    # Sweep, then hold on Otsu's choice.
    i_otsu = int(np.argmin(np.abs(ts - t_otsu)))
    frames = list(range(len(ts))) + [i_otsu] * 25

    def draw(k):
        t = ts[k]
        final = k == i_otsu and frames.count(k) > 1 and draw.n >= len(ts)
        draw.n += 1
        mask_im.set_data(gray > (t_otsu if final else t))
        for b, c in zip(bars, centers):
            b.set_color("#4a90d9" if c > t else "#888")
        vline.set_xdata([t, t])
        dot.set_data([t], [sigma_b[k]])
        title.set_text(f"Otsu's pick: {t_otsu:.0f}" if final else f"cutoff = {t}")
        title.set_color("#d62728" if final else "k")
        return []

    draw.n = 0
    FuncAnimation(fig, draw, frames=frames, interval=80).save(OUT / "otsu_sweep.gif", writer=PillowWriter(fps=12))
    plt.close(fig)


def _blob():
    """Small crack-like blob with uneven width: a T plus a bulge."""
    m = np.zeros((44, 56), bool)
    _thick_line(m, 10, 4, 10, 51, 7)
    _thick_line(m, 12, 30, 39, 26, 5)
    rr, cc = polygon([5, 18, 18, 5], [8, 8, 16, 16], m.shape)
    m[rr, cc] = True
    return m


def thinning_animation():
    m = _blob()
    steps = [m]
    k = 1
    while True:
        s = thin(m, max_num_iter=k)
        if np.array_equal(s, steps[-1]):
            break
        steps.append(s)
        k += 1
    final_skel = skeletonize(m)

    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    cmap = ListedColormap([BG, REMOVED, CRACK, SKEL])
    im = ax.imshow(np.zeros(m.shape), cmap=cmap, vmin=0, vmax=3)
    ax.set_xticks(np.arange(-0.5, m.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, m.shape[0], 1), minor=True)
    ax.grid(which="minor", color="#333", lw=0.3)
    ax.tick_params(which="both", length=0, labelbottom=False, labelleft=False)
    title = ax.set_title("")
    fig.tight_layout()

    # Circle the stubs skeletonize() leaves in the square bulge (thin() leaves none there).
    from matplotlib.patches import Circle
    ring = Circle((11.5, 10.5), 4.5, fill=False, ec="#ffd400", lw=2, visible=False)
    ax.add_patch(ring)

    frames = [i for i in range(len(steps)) for _ in range(4)] + ["thin"] * 16 + ["skel"] * 20

    def draw(i):
        ring.set_visible(i == "skel")
        if i == "thin":
            img = np.where(steps[-1], 3, np.where(m, 1, 0))
            title.set_text("thin() finished: 1 px wide, no side branches")
        elif i == "skel":
            img = np.where(final_skel, 3, np.where(m, 1, 0))
            title.set_text("skeletonize() (pipeline): 2 stubs in the bulge")
        else:
            prev = steps[max(i - 1, 0)]
            img = np.where(steps[i], 2, np.where(prev & ~steps[i], 1, 0))
            title.set_text(f"thin(), pass {i}: peel off removable edge pixels (orange)")
        im.set_data(img)
        return []

    FuncAnimation(fig, draw, frames=frames, interval=120).save(OUT / "thinning.gif", writer=PillowWriter(fps=8))
    plt.close(fig)


def distance_transform_figure():
    m = _blob()
    dist = distance_transform_edt(m)
    skel = skeletonize(m)

    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    ax[0].imshow(np.where(m, 1, 0), cmap=ListedColormap([BG, CRACK]))
    ax[0].set_title("mask")
    hm = ax[1].imshow(np.ma.masked_where(~m, dist), cmap="viridis")
    ax[1].set_facecolor(BG)
    rr, cc = np.nonzero(skel)
    for r, c in zip(rr[::3], cc[::3]):
        ax[1].text(c, r, f"{dist[r, c]:.0f}", ha="center", va="center", fontsize=6, color="w",
                   bbox=dict(boxstyle="square,pad=0.1", fc="k", ec="none", alpha=0.6))
    ax[1].set_title("distance_transform_edt: px to nearest background\n(numbers = value on the skeleton)")
    fig.colorbar(hm, ax=ax[1], fraction=0.04)
    for a in ax:
        a.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "distance_transform.png", dpi=110)
    plt.close(fig)


def skan_branch_types_figure():
    m = np.zeros((70, 90), bool)
    _thick_line(m, 20, 5, 20, 84, 1)       # main line
    _thick_line(m, 20, 45, 60, 45, 1)      # stem -> T junction
    _thick_line(m, 20, 25, 13, 25, 1)      # short spur
    _thick_line(m, 40, 45, 40, 70, 1)      # box with the stem: closed cell
    _thick_line(m, 40, 70, 20, 70, 1)
    _thick_line(m, 55, 70, 55, 84, 1)      # isolated piece
    _thick_line(m, 63, 5, 63, 7, 1)        # tiny isolated speck
    rr, cc = disk((48, 14), 7, shape=m.shape)  # lone ring: closed loop
    ring = np.zeros_like(m)
    ring[rr, cc] = True
    ring[disk((48, 14), 6, shape=m.shape)] = False
    m |= ring
    skel = skeletonize(m)

    def plot(a, sk, title):
        s = skan.Skeleton(sk)
        summ = skan.summarize(s, separator="_")
        colors = {0: "#9467bd", 1: "#e8743b", 2: "#4a90d9", 3: "#2ca02c"}
        a.imshow(np.zeros(sk.shape), cmap=ListedColormap([BG]))
        for i, t in enumerate(summ["branch_type"]):
            p = s.path_coordinates(i)
            a.plot(p[:, 1], p[:, 0], color=colors[int(t)], lw=2.5)
        deg = convolve(sk.astype(int), np.ones((3, 3), int), mode="constant") - 1
        rr, cc = np.nonzero(sk)
        for r, c in zip(rr, cc):
            if deg[r, c] == 1:
                a.plot(c, r, "o", ms=5, mfc="w", mec="k")
            elif deg[r, c] >= 3:
                a.plot(c, r, "s", ms=6, color="#ffd400")
        a.set_title(title)
        a.axis("off")
        return s, summ

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    s, summ = plot(ax[0], skel, "skan.summarize(): branch_type per branch")
    short = summ.index[(summ["branch_type"].isin([0, 1])) & (summ["branch_distance"] < 10)]
    pruned = s.prune_paths(list(short)).skeleton_image.astype(bool)
    plot(ax[1], pruned, "after prune_paths() on short type-0/1 branches")
    handles = [plt.Line2D([], [], color=c, lw=3, label=l) for c, l in [
        ("#9467bd", "0 isolated piece"), ("#e8743b", "1 dead end"),
        ("#4a90d9", "2 junction to junction"), ("#2ca02c", "3 closed loop")]]
    handles += [plt.Line2D([], [], ls="", marker="o", mfc="w", mec="k", label="endpoint (1 neighbour)"),
                plt.Line2D([], [], ls="", marker="s", color="#ffd400", label="junction (3+ neighbours)")]
    fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "skan_branch_types.png", dpi=110)
    plt.close(fig)


# -- real-data figure: what the cleanup loop actually removes --

REAL_IMAGES = [
    "characterization2_ptfe/T3-PTFE_v1_mm000001.jpg",
    "characterization2_membran/T4-M_H95_v1_mm000001.jpg",
    "characterization2_ptfe/T5-PTFE_H95_v1_mm000001.jpg",
]
REAL_CROP_PX = 2048  # centre crop, to keep the run short
REASON_LABEL = {"spur": "spur", "fragment": "fragment", "corner_artifact": "corner branch"}
REASON_COLOR = {"spur": "#e8743b", "fragment": "#9467bd", "corner_artifact": "#d62728"}


def _find_data_dir() -> Path | None:
    here = Path(__file__).resolve().parents[2]
    for cand in (here / "data" / "raw", here.parent / "data" / "raw"):
        if all((cand / p).exists() for p in REAL_IMAGES):
            return cand
    return None


def _branch_numbers(coords, medial_radius, kept_skel):
    """Width at each end and the |correlation| between position and width,
    oriented tip-first (the end farther from the kept skeleton)."""
    c = np.round(coords).astype(int)
    dist_to_kept = distance_transform_edt(~kept_skel)
    if dist_to_kept[c[0, 0], c[0, 1]] < dist_to_kept[c[-1, 0], c[-1, 1]]:
        c = c[::-1]
    widths = 2.0 * medial_radius[c[:, 0], c[:, 1]]
    corr = float(np.corrcoef(np.arange(len(widths)), widths)[0, 1]) if widths.std() > 0 else 0.0
    return widths[0], widths[-1], corr


def real_pruned_branches_figure(data_dir: Path):
    from src.crackgraph.binarize import binarize
    from src.crackgraph.io_utils import load_image
    from src.crackgraph.skeleton import SPUR_PX_PLACEHOLDER, skeletonize_and_prune

    records, rows = [], []
    for rel in REAL_IMAGES:
        gray, _ = load_image(data_dir / rel)
        h, w = gray.shape
        r0, c0 = (h - REAL_CROP_PX) // 2, (w - REAL_CROP_PX) // 2
        gray = gray[r0:r0 + REAL_CROP_PX, c0:c0 + REAL_CROP_PX]
        sr = skeletonize_and_prune(binarize(gray).mask, source_image=gray)
        kept = sr.skeleton.skeleton_image.astype(bool)
        name = Path(rel).stem.replace("_mm000001", "")
        for pb in sr.pruned_branches:
            w_tip, w_end, corr = _branch_numbers(pb.coords, sr.medial_radius, kept)
            records.append(dict(img=name, gray=gray, kept=kept, coords=pb.coords, reason=pb.reason,
                                length=pb.branch_distance, w_tip=w_tip, w_end=w_end, corr=corr))
        removed_len = sum(pb.branch_distance for pb in sr.pruned_branches)
        rows.append((name, sr.n_spurs_pruned, sr.n_fragments_pruned, sr.n_corner_artifacts_pruned,
                     100 * removed_len / (removed_len + kept.sum())))

    # Three examples per reason, picked by length percentile (deterministic).
    # Skip branches near the crop edge: there the crop, not the crack, shapes them.
    def away_from_edge(r, margin=40):
        co = r["coords"]
        return co.min() >= margin and co.max() <= REAL_CROP_PX - 1 - margin

    picks = []
    for reason in ("spur", "fragment", "corner_artifact"):
        pool = sorted((r for r in records if r["reason"] == reason and away_from_edge(r)),
                      key=lambda r: r["length"])
        picks += [pool[int(q * (len(pool) - 1))] for q in (0.25, 0.5, 0.95)]

    fig, axs = plt.subplots(3, 3, figsize=(10, 10.6))
    for ax, r in zip(axs.flat, picks):
        co = r["coords"]
        pad = int(max(30, 1.5 * max(r["w_tip"], r["w_end"])))
        H, W = r["gray"].shape
        r0, r1 = max(int(co[:, 0].min()) - pad, 0), min(int(co[:, 0].max()) + pad, H)
        c0, c1 = max(int(co[:, 1].min()) - pad, 0), min(int(co[:, 1].max()) + pad, W)
        ax.imshow(r["gray"][r0:r1, c0:c1], cmap="gray", vmin=0, vmax=255, interpolation="nearest")
        ys, xs = np.nonzero(r["kept"][r0:r1, c0:c1])
        ax.scatter(xs, ys, s=0.6, c=SKEL)
        ax.plot(co[:, 1] - c0, co[:, 0] - r0, color=REASON_COLOR[r["reason"]], lw=2.2)
        ax.set_title(f"{REASON_LABEL[r['reason']]} · {r['img']}\n{r['length']:.0f} px long · width "
                     f"{r['w_tip']:.0f} → {r['w_end']:.0f} px · corr {r['corr']:.2f}", fontsize=8)
        ax.axis("off")
    fig.suptitle("Branches removed by the cleanup loop (coloured) and the skeleton that stays (green)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "real_pruned_branches.png", dpi=90)
    plt.close(fig)

    # Numbers for the walkthrough text.
    print("| Image | Spurs | Fragments | Corner branches | Skeleton length removed |")
    print("|---|---|---|---|---|")
    for name, n_s, n_f, n_c, pct in rows:
        print(f"| {name} | {n_s} | {n_f} | {n_c} | {pct:.1f}% |")
    print(f"\nspur_px = {SPUR_PX_PLACEHOLDER}")
    for reason in ("spur", "fragment", "corner_artifact"):
        rs = [r for r in records if r["reason"] == reason]
        L = np.array([r["length"] for r in rs])
        print(f"{reason}: n={len(rs)} length median {np.median(L):.0f} px, range {L.min():.0f}-{L.max():.0f} px")
        if reason == "corner_artifact":
            ratio = np.array([r["w_end"] / max(r["w_tip"], 1) for r in rs])
            print(f"  width end/tip median {np.median(ratio):.1f}x, corr median "
                  f"{np.median([r['corr'] for r in rs]):.3f}")
    for r in picks:
        print(f"pick: {r['reason']:15s} {r['img']:15s} L={r['length']:.0f} w {r['w_tip']:.0f}->{r['w_end']:.0f} corr {r['corr']:.2f}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    OUT.mkdir(parents=True, exist_ok=True)
    otsu_sweep()
    thinning_animation()
    distance_transform_figure()
    skan_branch_types_figure()
    data_dir = _find_data_dir()
    if data_dir is None:
        print("real micrographs not found under data/raw; skipped real_pruned_branches.png")
    else:
        real_pruned_branches_figure(data_dir)
    print(f"wrote figures to {OUT}")
