import matplotlib as mpl, matplotlib.pyplot as plt
import numpy as np, pandas as pd

SURF   = "#fcfcfb"
INK    = "#0b0b0b"
INK2   = "#52514e"
MUTED  = "#8a8983"
GRID   = "#e3e2dd"
S1="#2a78d6"; S2="#eb6834"; S3="#1baf7a"; S4="#eda100"; S5="#e87ba4"; S6="#008300"; S7="#4a3aa7"; S8="#e34948"
SEQ = mpl.colors.LinearSegmentedColormap.from_list("seq", ["#d7e5f7","#2a78d6","#12305c"])
DIV = mpl.colors.LinearSegmentedColormap.from_list("div", ["#e34948","#efeee9","#2a78d6"])

def setup():
    mpl.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.edgecolor": GRID, "axes.linewidth": 1.0,
        "axes.labelcolor": INK2, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.labelsize": 10, "axes.titlesize": 11.5, "axes.titleweight": "600",
        "axes.titlelocation": "left", "axes.titlepad": 9,
        "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.grid": True, "axes.grid.axis": "y",
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 9,
        "font.family": "DejaVu Sans", "font.size": 10,
        "figure.dpi": 110, "savefig.dpi": 110, "savefig.bbox": "tight",
    })

def binned_median(x, y, nbins=14, minn=15):
    """Equal-count bins -> (centre, median, q25, q75, n)."""
    s = pd.DataFrame({"x": x, "y": y}).dropna().sort_values("x")
    if len(s) < minn * 3: return None
    qs = np.linspace(0, 1, nbins + 1)
    edges = np.unique(s.x.quantile(qs).values)
    if len(edges) < 4: return None
    g = s.groupby(pd.cut(s.x, edges, include_lowest=True), observed=True)
    out = g.agg(x=("x","median"), y=("y","median"),
                q1=("y", lambda v: v.quantile(.25)), q3=("y", lambda v: v.quantile(.75)),
                n=("y","size")).dropna()
    return out[out.n >= minn]

def driver_panel(ax, x, y, c, label, unit="", nbins=14, logx=False):
    """Scatter coloured by date (sequential) + binned-median spine."""
    m = np.isfinite(x) & np.isfinite(y)
    x, y, c = np.asarray(x)[m], np.asarray(y)[m], np.asarray(c)[m]
    ax.scatter(x, y, c=c, cmap=SEQ, s=5, alpha=.38, linewidths=0, rasterized=True)
    b = binned_median(x, y, nbins)
    if b is not None:
        ax.fill_between(b.x, b.q1, b.q3, color=S2, alpha=.14, linewidth=0)
        ax.plot(b.x, b.y, color=S2, lw=2.0, solid_capstyle="round", zorder=5)
    if logx: ax.set_xscale("log")
    ax.set_xlabel(f"{label} {unit}".strip())
    return b
