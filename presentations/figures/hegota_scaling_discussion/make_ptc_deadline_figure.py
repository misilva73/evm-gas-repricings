"""Generate the PTC-deadline crossover figure for the Hegota scaling deck.

Plots the two feasibility ceilings from the transfer-anchored slot model
(reports/hegota_scaling_exploration.md) as a function of the PTC deadline D:

  - Execution ceiling:   L <= buffer * R * (slot - D)            (falls as D grows)
  - Propagation ceiling: fixed + slope * beta_t * L <= buffer*(D - T1)  (rises as D grows)

The optimum is the crossover (~473M @ D ~= 5.7s); the recommended operating
point (500M @ 5.5s) sits just above it.
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# --- Model parameters (from the report) ---------------------------------------
R = 100.0  # execution anchor, Mgas/s (frozen by the 21k transfer cap)
T1 = 2.0  # earliest payload propagation start, s
SLOT = 12.0  # slot length, s
BUFFER = 0.75  # 25% safety buffer on both windows
SLOPE = 0.443  # propagation slope, ms per KB (p90 MEV-boost fit)
FIXED = 569.0  # propagation fixed overhead, ms
BETA_T = 221.0 / 21000.0  # transfer byte density, B/gas (~0.01052)


def execution_ceiling(d):
    """Feasible gas limit (Mgas) from the execution window."""
    return BUFFER * R * (SLOT - d)


def propagation_ceiling(d):
    """Feasible gas limit (Mgas) from the propagation window."""
    # KB on the wire = beta_t * L_gas / 1000; L_gas = L_Mgas * 1e6
    # fixed + slope * beta_t * 1000 * L_Mgas <= buffer * (d - T1) * 1000
    denom = SLOPE * BETA_T * 1000.0
    return (BUFFER * (d - T1) * 1000.0 - FIXED) / denom


# --- Crossover (symmetric-buffer optimum) -------------------------------------
d_grid = np.linspace(4.5, 7.0, 1001)
diff = execution_ceiling(d_grid) - propagation_ceiling(d_grid)
i = np.argmin(np.abs(diff))
d_star, l_star = d_grid[i], execution_ceiling(d_grid[i])  # ~5.70 s, ~473 Mgas

# Recommended operating point
d_rec, l_rec = 5.5, 500.0

# --- Plot ---------------------------------------------------------------------
EXEC_C = "#e8590c"  # orange
PROP_C = "#1c7ed6"  # blue
HILITE = "#d6336c"  # pink

plt.rcParams.update({"font.size": 13})
fig, ax = plt.subplots(figsize=(10, 5.2))

exec_y = execution_ceiling(d_grid)
prop_y = propagation_ceiling(d_grid)

# Feasible region: below both ceilings (peaks at the crossover)
ax.fill_between(
    d_grid,
    0,
    np.minimum(exec_y, prop_y),
    color="#2f9e44",
    alpha=0.08,
    zorder=0,
)

ax.plot(d_grid, exec_y, color=EXEC_C, lw=3, label="Execution ceiling")
ax.plot(d_grid, prop_y, color=PROP_C, lw=3, label="Propagation ceiling")

# Line annotations (equation + direction)
ax.annotate(
    "Execution ceiling  ↓\n$L \\leq 0.75\\,R\\,(12 - D)$",
    xy=(4.62, execution_ceiling(4.62)),
    xytext=(4.6, 600),
    color=EXEC_C,
    fontsize=13,
    fontweight="bold",
    va="top",
)
ax.annotate(
    "Propagation ceiling  ↑\n$\\mathrm{prop}(L) \\leq 0.75\\,(D - T_1)$",
    xy=(6.7, propagation_ceiling(6.7)),
    xytext=(6.05, 360),
    color=PROP_C,
    fontsize=13,
    fontweight="bold",
    va="top",
)

# Crossover highlight
ax.plot([d_star, d_star], [0, l_star], ls="--", color=HILITE, lw=1.4, zorder=1)
ax.plot([4.5, d_star], [l_star, l_star], ls="--", color=HILITE, lw=1.4, zorder=1)
ax.scatter([d_star], [l_star], s=90, color="#111", zorder=5)
ax.annotate(
    f"Ceilings meet — symmetric optimum\n~{l_star:.0f}M @ D ≈ {d_star:.2f}s  (25% / 25%)",
    xy=(d_star, l_star),
    xytext=(d_star + 0.18, l_star - 70),
    color="#111",
    fontsize=12.5,
    fontweight="bold",
    arrowprops=dict(arrowstyle="-", color="#111", lw=1),
)

# Recommended operating point
ax.scatter(
    [d_rec],
    [l_rec],
    s=130,
    marker="*",
    facecolor="none",
    edgecolor=HILITE,
    linewidths=2.2,
    zorder=6,
)
ax.annotate(
    "★ Recommended\n500M @ 5.5s",
    xy=(d_rec, l_rec),
    xytext=(5.56, 600),
    color=HILITE,
    fontsize=12.5,
    fontweight="bold",
    ha="left",
    arrowprops=dict(arrowstyle="-", color=HILITE, lw=1),
)

ax.set_xlim(4.5, 7.0)
ax.set_ylim(250, 700)
ax.set_xlabel("PTC deadline D (seconds)")
ax.set_ylabel("Gas limit (Mgas)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(True, alpha=0.15)

fig.tight_layout()
out = Path(__file__).parent / "ptc_deadline_crossover.png"
fig.savefig(out, dpi=200, bbox_inches="tight")
print(f"wrote {out}")
