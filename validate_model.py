"""Validate the ship design solver against the clean ship database.

For every tool-typed ship in the chosen split (default: the validation
split, delivered on or after the cutoff year), the solver designs a ship of
the same type, speed and total deadweight, and its main dimensions and
power are compared with the real ship's.

Configurations: resistance method (Taylor, Holtrop) x empirical basis
(Legacy, and the refitted "Japan clean (fit split)" if present) x Auto-RPM
(off = the tool's original behaviour, on = pitch-driven RPM correction).

Matching deadweight: the solver's target is cargo deadweight, the database
gives total deadweight, so each ship is solved with a secant iteration on
the cargo target until total DW (W5) matches the database DWT within 0.1 %.

Stated assumptions (written into the report):
  * Lbp = LOA x a per-type ratio (ship_database.LBP_OVER_LOA); length errors
    are also given at +/-1 % on the ratio.
  * Direct-drive diesel; propeller RPM = the database rpm when known, else
    the solver default (120 rpm); range = solver default; economics off.
  * Database power is engine MCR: compared with installed P2 (which includes
    the solver's 30 % margin) and service P1 is compared with 0.85 x MCR.
  * Draughts marked as scantling are not compared.

Run:  python validate_model.py [--split validate|fit|all] [--quick N]
                               [--data data/ships_clean.csv] [--out data/validation]
"""
import argparse
import csv
import math
import os
import random
from collections import OrderedDict

import numpy as np

import ship_database as sdb
from ship_config import EmpiricalBasisConfig
from ship_solver import ShipDesignSolver

TAYLOR = "Taylor's Series (Legacy)"
HOLTROP = "Holtrop-Mennen (1984)"
LEGACY = "Legacy (Watson/Gilfillan 1977)"
CLEAN = "Japan clean (fit split)"
DEFAULT_RPM = 120.0
NCR_OVER_MCR = 0.85
DWT_TOL = 0.001

# (label, predicted key, actual function)
COMPARISONS = [
    ("Lbp", "Lbp", lambda r: sdb.lbp(r)),
    ("Lbp (ratio +1%)", "Lbp", lambda r: sdb.lbp(r, +0.01)),
    ("Lbp (ratio -1%)", "Lbp", lambda r: sdb.lbp(r, -0.01)),
    ("B", "B", lambda r: sdb.field_value(r, "B_m")),
    ("D", "D", lambda r: sdb.field_value(r, "D_m")),
    ("T", "T", lambda r: None if r.get("T_kind") == "scantling" else sdb.field_value(r, "T_m")),
    ("P installed vs MCR", "P2_kW", lambda r: sdb.field_value(r, "power_kW")),
    ("P service vs 0.85 MCR", "P1_kW",
     lambda r: (sdb.field_value(r, "power_kW") or 0) * NCR_OVER_MCR or None),
]
HEADLINE = ("Lbp", "B", "T", "P installed vs MCR", "P service vs 0.85 MCR")


def configs(include_clean=True):
    bases = [LEGACY] + ([CLEAN] if include_clean and CLEAN in EmpiricalBasisConfig.DATA else [])
    return [(m, b, a) for m in (TAYLOR, HOLTROP) for b in bases for a in (False, True)]


def config_label(method, basis, auto):
    return (f"{'Taylor' if method == TAYLOR else 'Holtrop'} / "
            f"{'Legacy' if basis == LEGACY else 'Japan clean'} / Auto-RPM {'on' if auto else 'off'}")


def config_slug(method, basis, auto):
    return (f"{'taylor' if method == TAYLOR else 'holtrop'}_{'legacy' if basis == LEGACY else 'japanclean'}_"
            f"{'autorpm' if auto else 'original'}")


def failure_reason(s):
    if s.solver_errors:
        msg = s.solver_errors[0]
        if "Numerical failure" in msg:
            return "numerical (complex result)"
    k = getattr(s, "Kpwrerr", 1)
    parts = [name for name, code in (("pitch > 1.4", s.PITCH_LOW), ("pitch < 0.5", s.PITCH_HIGH),
                                      ("speed too low", s.SPEED_LOW), ("speed too high", s.SPEED_HIGH),
                                      ("no convergence", s.NOT_CONVERGE),
                                      ("Fn/CB out of method range", s.RESISTANCE_OUT_OF_RANGE))
             if k and k != 1 and k % code == 0]
    if parts:
        return ", ".join(parts)
    return (s.solver_errors[0].splitlines()[0][:60] if s.solver_errors else "failed")


def solve_ship(row, method, basis, auto, max_iter=10):
    """Design the ship to match the row's type, speed and total DWT.
    Returns a dict of predictions (ok=True) or a failure reason (ok=False)."""
    dwt = sdb.field_value(row, "DWT")
    speed = sdb.field_value(row, "speed_kn")
    rpm = float(row["rpm"]) if row.get("rpm") else DEFAULT_RPM

    def run(cargo):
        s = ShipDesignSolver().set_inputs(
            ship_name=row["tool_type"], engine_name="Direct diesel", m_Weight=cargo, m_Speed=speed,
            m_Erpm=rpm, m_Prpm=rpm, m_Econom=False, resistance_method=method, empirical_basis=basis,
            m_AutoRPM=auto)
        s.ignspd = s.ignpth = True
        return s, s.solve()

    w_prev, f_prev = None, None
    w = 0.93 * dwt
    s, ok = None, False
    for it in range(1, max_iter + 1):
        s, ok = run(w)
        if not ok:
            return {"ok": False, "reason": failure_reason(s), "iterations": it}
        f = s.W5 - dwt
        if abs(f) <= DWT_TOL * dwt:
            break
        if f_prev is None or f == f_prev:
            w_next = w * dwt / s.W5
        else:
            w_next = w - f * (w - w_prev) / (f - f_prev)
        w_prev, f_prev, w = w, f, max(w_next, 0.05 * dwt)
    else:
        return {"ok": False, "reason": "deadweight not matched", "iterations": max_iter}
    return {"ok": True, "reason": "", "iterations": it, "Lbp": s.L1, "B": s.B, "D": s.D, "T": s.T,
            "CB": s.C, "P1_kW": s.P1 * 0.7457, "P2_kW": s.P2 * 0.7457, "W5": s.W5, "cargo_DW": s.W1,
            "rpm_used": s.rpm_final, "rpm_adjusted": bool(s.rpm_adjusted)}


def metrics(pred, actual):
    """n, mean bias %, MAPE %, RMSE (units of the quantity), R^2."""
    p, a = np.asarray(pred, float), np.asarray(actual, float)
    n = len(a)
    if n == 0:
        return {"n": 0, "bias_pct": float("nan"), "mape_pct": float("nan"),
                "rmse": float("nan"), "r2": float("nan")}
    rel = (p - a) / a
    ss_tot = float(np.sum((a - a.mean()) ** 2))
    return {"n": n, "bias_pct": 100 * float(rel.mean()), "mape_pct": 100 * float(np.abs(rel).mean()),
            "rmse": float(np.sqrt(np.mean((p - a) ** 2))),
            "r2": 1.0 - float(np.sum((p - a) ** 2)) / ss_tot if ss_tot > 0 else float("nan")}


def select_ships(rows, split):
    keep = [r for r in rows if r.get("tool_type") and sdb.field_value(r, "DWT")
            and sdb.field_value(r, "speed_kn")]
    if split != "all":
        keep = [r for r in keep if r.get("split") == split]
    return keep


def run_validation(rows, cfgs, progress=None):
    """{config: [(row, result), ...]}"""
    out = OrderedDict()
    for ci, cfg in enumerate(cfgs):
        res = []
        for i, r in enumerate(rows):
            res.append((r, solve_ship(r, *cfg)))
            if progress:
                progress(ci, i)
        out[cfg] = res
    return out


def summarise(results):
    """Metric rows: one per (config, ship type incl. 'All', comparison)."""
    table = []
    for cfg, res in results.items():
        types = sorted({r["tool_type"] for r, _ in res})
        for t in types + ["All"]:
            sub = [(r, x) for r, x in res if t == "All" or r["tool_type"] == t]
            solved = [(r, x) for r, x in sub if x["ok"]]
            base = {"config": config_label(*cfg), "tool_type": t, "attempted": len(sub),
                    "solved": len(solved),
                    "rpm_adjusted": sum(1 for _, x in solved if x.get("rpm_adjusted"))}
            for label, key, actual in COMPARISONS:
                pa = [(x[key], actual(r)) for r, x in solved if actual(r)]
                m = metrics([p for p, _ in pa], [a for _, a in pa])
                table.append(dict(base, comparison=label, **m))
    return table


def write_results(results, out_dir):
    for cfg, res in results.items():
        path = os.path.join(out_dir, f"results_{config_slug(*cfg)}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            head = ["ship_id", "boat_name", "tool_type", "split", "delivery_year", "DWT", "speed_kn", "rpm_db",
                    "ok", "reason", "iterations", "rpm_used", "rpm_adjusted"]
            for label, key, _ in COMPARISONS:
                head += [f"{label} pred", f"{label} actual", f"{label} err %"]
            w.writerow(head)
            for r, x in res:
                line = [r["ship_id"], r["boat_name"], r["tool_type"], r["split"], r["delivery_year"], r["DWT"],
                        r["speed_kn"], r["rpm"], x["ok"], x["reason"], x["iterations"],
                        _f(x.get("rpm_used")), x.get("rpm_adjusted", "")]
                for label, key, actual in COMPARISONS:
                    a = actual(r)
                    p = x.get(key) if x["ok"] else None
                    line += [_f(p), _f(a), _f(100 * (p - a) / a) if (p is not None and a) else ""]
                w.writerow(line)


def _f(v, nd=4):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.{nd}g}" if abs(v) < 1e5 else f"{v:.0f}"


def write_metrics(table, out_dir):
    path = os.path.join(out_dir, "metrics.csv")
    cols = ["config", "tool_type", "comparison", "attempted", "solved", "rpm_adjusted", "n",
            "bias_pct", "mape_pct", "rmse", "r2"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for m in table:
            w.writerow([m[c] if not isinstance(m[c], float) else _f(m[c]) for c in cols])
    return path


# ----------------------------------------------------------------------
# Figures and report
# ----------------------------------------------------------------------
TYPE_COLORS = OrderedDict([("Bulk carrier", "#2a78d6"), ("Tanker", "#eb6834"), ("Container Ship", "#1baf7a")])
OTHER_COLOR = "#8a8984"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e2e1dc"


def _style(ax):
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def figures(results, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths = []
    panels = [("Lbp", "Lbp (m)"), ("B", "Beam B (m)"), ("T", "Draught T (m)"),
              ("P installed vs MCR", "Installed power vs MCR (kW)")]
    for cfg, res in results.items():
        if not cfg[2]:
            continue                                   # figures for Auto-RPM on
        fig, axes = plt.subplots(2, 2, figsize=(10, 9), layout="constrained")
        for ax, (label, title) in zip(axes.flat, panels):
            key, actual = next((k, a) for l, k, a in COMPARISONS if l == label)
            pts = {}
            for r, x in res:
                a = actual(r)
                if x["ok"] and a:
                    t = r["tool_type"] if r["tool_type"] in TYPE_COLORS else "Other"
                    pts.setdefault(t, []).append((a, x[key]))
            allv = [v for p in pts.values() for xy in p for v in xy]
            if allv:
                lo, hi = min(allv) * 0.9, max(allv) * 1.1
                ax.plot([lo, hi], [lo, hi], color=INK, linewidth=1)
                ax.fill_between([lo, hi], [lo * 0.9, hi * 0.9], [lo * 1.1, hi * 1.1], color=GRID, alpha=0.6,
                                linewidth=0, label="±10 %")
                for t, color in list(TYPE_COLORS.items()) + [("Other", OTHER_COLOR)]:
                    if t in pts:
                        xs, ys = zip(*pts[t])
                        ax.scatter(xs, ys, s=16, color=color, alpha=0.75, linewidths=0, label=f"{t} ({len(xs)})")
                ax.set_xlim(lo, hi)
                ax.set_ylim(lo, hi)
            ax.set_xlabel(f"Actual {title}")
            ax.set_ylabel(f"Predicted {title}")
            _style(ax)
            ax.legend(frameon=False, fontsize=8, loc="upper left")
        fig.suptitle(f"Predicted vs actual - {config_label(*cfg)}", fontsize=11)
        path = os.path.join(out_dir, f"pred_vs_actual_{config_slug(*cfg)}.png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)

    # Error distributions by type (Holtrop / Legacy / Auto-RPM on, the headline config)
    head = next((c for c in results if c == (HOLTROP, LEGACY, True)), None)
    if head:
        res = results[head]
        fig, axes = plt.subplots(1, 4, figsize=(13, 4), layout="constrained", sharey=False)
        for ax, (label, title) in zip(axes, panels):
            key, actual = next((k, a) for l, k, a in COMPARISONS if l == label)
            data, names, colors = [], [], []
            for t, color in TYPE_COLORS.items():
                errs = [100 * (x[key] - actual(r)) / actual(r) for r, x in res
                        if r["tool_type"] == t and x["ok"] and actual(r)]
                if errs:
                    data.append(errs)
                    names.append(f"{t}\n(n={len(errs)})")
                    colors.append(color)
            if data:
                bp = ax.boxplot(data, patch_artist=True, widths=0.55, showfliers=True,
                                medianprops={"color": INK}, flierprops={"markersize": 3, "markeredgecolor": MUTED})
                for patch, c in zip(bp["boxes"], colors):
                    patch.set_facecolor(c)
                    patch.set_alpha(0.75)
                ax.set_xticks(range(1, len(names) + 1))
                ax.set_xticklabels(names, fontsize=8)
            ax.axhline(0, color=INK, linewidth=1)
            ax.set_title(title, fontsize=10)
            ax.set_ylabel("Error (%)")
            _style(ax)
        fig.suptitle(f"Prediction error by ship type - {config_label(*head)}", fontsize=11)
        path = os.path.join(out_dir, "errors_by_type.png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)

    # Basis comparison: MAPE, Legacy vs Japan clean (Auto-RPM on), both methods
    table = summarise(results)
    comp = [c for c in results if c[2]]
    if len({c[1] for c in comp}) > 1:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained", sharey=True)
        for ax, method in zip(axes, (TAYLOR, HOLTROP)):
            labels = ["Lbp", "B", "T", "P installed vs MCR"]
            x = np.arange(len(labels))
            for k, (basis, color) in enumerate(((LEGACY, "#2a78d6"), (CLEAN, "#eb6834"))):
                lab = config_label(method, basis, True)
                vals = [next((m["mape_pct"] for m in table if m["config"] == lab and m["tool_type"] == "All"
                              and m["comparison"] == c), float("nan")) for c in labels]
                bars = ax.bar(x + (k - 0.5) * 0.38, vals, width=0.36, color=color,
                              label="Legacy basis" if basis == LEGACY else "Japan clean basis")
                for b_, v in zip(bars, vals):
                    if not math.isnan(v):
                        ax.text(b_.get_x() + b_.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom",
                                fontsize=8, color=MUTED)
            ax.set_xticks(x)
            ax.set_xticklabels(["Lbp", "B", "T", "Installed P"])
            ax.set_title("Taylor" if method == TAYLOR else "Holtrop", fontsize=10)
            ax.set_ylabel("Mean absolute % error")
            _style(ax)
            ax.legend(frameon=False, fontsize=8)
        fig.suptitle("Empirical basis comparison (validation split, Auto-RPM on)", fontsize=11)
        path = os.path.join(out_dir, "basis_comparison.png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        paths.append(path)
    return paths


def write_report(results, table, figs, out_dir, split, data_path):
    lines = ["# Validation against the clean ship database", ""]
    first = next(iter(results.values()))
    n = len(first)
    lines += [f"Data: `{data_path}`, split **{split}** - {n} ship(s) of the tool's types with DWT and speed.", ""]
    lines += ["## Assumptions", "",
              "- Each real ship is redesigned at its own type, speed and total deadweight "
              "(secant on the cargo target until total DW matches within 0.1 %).",
              "- Lbp = LOA x " + ", ".join(f"{t} {v}" for t, v in sdb.LBP_OVER_LOA.items())
              + "; length errors also shown at +/-1 % on the ratio.",
              f"- Direct-drive diesel; RPM = database rpm where known, else {DEFAULT_RPM:g} rpm; "
              "range = solver default; economics off.",
              f"- Database power = MCR: compared with installed P2 (includes the solver's 30 % margin); "
              f"service P1 compared with {NCR_OVER_MCR} x MCR.",
              "- Fields flagged implausible by the cleaning pipeline, and scantling draughts, are excluded "
              "from that field's comparison only.", ""]
    lines += ["## Solve rate", "", "| Configuration | Attempted | Solved | RPM adjusted |", "|---|---|---|---|"]
    for m in table:
        if m["tool_type"] == "All" and m["comparison"] == "Lbp":
            lines.append(f"| {m['config']} | {m['attempted']} | {m['solved']} | {m['rpm_adjusted']} |")
    lines += ["", "## Accuracy (all types)", "",
              "| Configuration | Quantity | n | Bias % | MAPE % | R² |", "|---|---|---|---|---|---|"]
    for m in table:
        if m["tool_type"] == "All" and m["comparison"] in HEADLINE + ("Lbp (ratio +1%)", "Lbp (ratio -1%)", "D"):
            lines.append(f"| {m['config']} | {m['comparison']} | {m['n']} | {m['bias_pct']:+.1f} | "
                         f"{m['mape_pct']:.1f} | {m['r2']:.3f} |")
    lines += ["", "## Accuracy by ship type", "",
              "| Configuration | Type | Quantity | n | Bias % | MAPE % | R² |", "|---|---|---|---|---|---|---|"]
    for m in table:
        if m["tool_type"] != "All" and m["comparison"] in HEADLINE and m["n"]:
            lines.append(f"| {m['config']} | {m['tool_type']} | {m['comparison']} | {m['n']} | "
                         f"{m['bias_pct']:+.1f} | {m['mape_pct']:.1f} | {m['r2']:.3f} |")
    lines += ["", "## Failure reasons", ""]
    for cfg, res in results.items():
        reasons = {}
        for _, x in res:
            if not x["ok"]:
                reasons[x["reason"]] = reasons.get(x["reason"], 0) + 1
        if reasons:
            lines.append(f"- {config_label(*cfg)}: " + "; ".join(f"{k} x{v}" for k, v in
                                                                 sorted(reasons.items(), key=lambda kv: -kv[1])))
    lines += ["", "## Figures", ""] + [f"- `{os.path.basename(p)}`" for p in figs]
    path = os.path.join(out_dir, "validation_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join("data", "ships_clean.csv"))
    ap.add_argument("--out", default=os.path.join("data", "validation"))
    ap.add_argument("--split", default="validate", choices=("validate", "fit", "all"))
    ap.add_argument("--quick", type=int, default=0, help="random subset of N ships (0 = all)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    rows = select_ships(sdb.load_clean(a.data), a.split)
    if a.quick:
        rows = random.Random(a.seed).sample(rows, min(a.quick, len(rows)))
    os.makedirs(a.out, exist_ok=True)
    cfgs = configs()
    print(f"Validating {len(rows)} ships x {len(cfgs)} configurations ...")
    results = run_validation(rows, cfgs)
    table = summarise(results)
    write_results(results, a.out)
    write_metrics(table, a.out)
    figs = [] if a.no_figures else figures(results, a.out)
    report = write_report(results, table, figs, a.out, a.split, a.data)
    print(f"Wrote {report}")
    for m in table:
        if m["tool_type"] == "All" and m["comparison"] in HEADLINE:
            print(f"  {m['config']:44s} {m['comparison']:24s} solved {m['solved']:3d}/{m['attempted']:3d}  "
                  f"n={m['n']:3d}  bias {m['bias_pct']:+6.1f}%  MAPE {m['mape_pct']:5.1f}%  R2 {m['r2']:.3f}")


if __name__ == "__main__":
    main()
