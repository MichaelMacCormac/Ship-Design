"""Refit the Japan empirical basis from the clean dataset's fit split.

The original "Japan Dataset (2020s)" coefficients were fitted from the
hand-cleaned V10 file, which contains extraction errors, and from every ship
(so validating against the same ships would be circular). This refits the
same functional forms on the clean dataset's *fit* split only (ships
delivered before the split cutoff), leaving the *validate* split unseen:

    Lbp = L_a + L_b * DWT^(1/3)          (L_c fixed at 1)
    B   = LB_m * Lbp + LB_c
    D   = LD_m * Lbp + LD_c
    T   = DT_m * D   + DT_c

A coefficient pair is kept only if its fit has R^2 >= 0.5 on n >= 30 ships;
otherwise it is None and the solver falls back to the legacy formula for
that dimension (as EmpiricalBasisConfig already documents).

Output: data/japan_basis_clean.json, which ship_config.py loads as the extra
basis "Japan clean (fit split)". The existing bases are untouched.

Run:  python fit_basis.py [--data data/ships_clean.csv] [--out data/japan_basis_clean.json]
"""
import argparse
import json
import os

import numpy as np

import ship_database as sdb

BASIS_NAME = "Japan clean (fit split)"
MIN_R2 = 0.5
MIN_N = 30
TYPES = ("Tanker", "Bulk carrier", "Container Ship", "Cargo vessel", "Cruise Ship")


def linfit(x, y):
    """Least-squares y = a + b*x. Returns (a, b, r2, n)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    if n < 3 or np.ptp(x) == 0:
        return None, None, float("nan"), n
    b, a = np.polyfit(x, y, 1)
    resid = y - (a + b * x)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid ** 2)) / ss_tot if ss_tot > 0 else float("nan")
    return float(a), float(b), r2, n


def gated(a, b, r2, n):
    ok = a is not None and n >= MIN_N and r2 >= MIN_R2
    return (a, b) if ok else (None, None)


def fit_type(rows):
    """Fit the four relations for one ship type's fit-split rows."""
    def pairs(fx, fy):
        xs, ys = [], []
        for r in rows:
            x, y = fx(r), fy(r)
            if x is not None and y is not None:
                xs.append(x)
                ys.append(y)
        return xs, ys

    cbrt_dwt = lambda r: (sdb.field_value(r, "DWT") ** (1 / 3)) if sdb.field_value(r, "DWT") else None
    out, stats = {"L_c": 1.0}, {}
    for (ka, kb), fx, fy in (
            (("L_a", "L_b"), cbrt_dwt, sdb.lbp),
            (("LB_c", "LB_m"), sdb.lbp, lambda r: sdb.field_value(r, "B_m")),
            (("LD_c", "LD_m"), sdb.lbp, lambda r: sdb.field_value(r, "D_m")),
            (("DT_c", "DT_m"), lambda r: sdb.field_value(r, "D_m"), lambda r: sdb.field_value(r, "T_m"))):
        a, b, r2, n = linfit(*pairs(fx, fy))
        out[ka], out[kb] = gated(a, b, r2, n)
        stats[ka[:2] if ka != "L_a" else "L"] = {"r2": None if np.isnan(r2) else round(r2, 4), "n": n,
                                                 "kept": out[ka] is not None,
                                                 "raw": [a, b]}
    return out, stats


def fit(rows):
    fit_rows = [r for r in rows if r.get("split") == "fit"]
    types, stats = {}, {}
    for t in TYPES:
        coefs, st = fit_type([r for r in fit_rows if r.get("tool_type") == t])
        stats[t] = st
        if any(coefs[k] is not None for k in ("L_a", "LB_m", "LD_m", "DT_m")):
            types[t] = coefs
    return types, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join("data", "ships_clean.csv"))
    ap.add_argument("--out", default=os.path.join("data", "japan_basis_clean.json"))
    a = ap.parse_args()
    rows = sdb.load_clean(a.data)
    years = [int(r["delivery_year"]) for r in rows if r.get("split") == "validate" and r.get("delivery_year")]
    types, stats = fit(rows)
    doc = {
        "basis_name": BASIS_NAME,
        "source": a.data,
        "fitted_on": "fit split only (delivered before the validation cutoff)",
        "validation_cutoff_year": min(years) if years else None,
        "lbp_over_loa": sdb.LBP_OVER_LOA,
        "gates": {"min_r2": MIN_R2, "min_n": MIN_N},
        "types": types,
        "stats": stats,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    print(f"Wrote {a.out}")
    for t, st in stats.items():
        line = "  ".join(f"{k}: n={v['n']} R2={v['r2']} {'kept' if v['kept'] else 'dropped'}" for k, v in st.items())
        print(f"  {t:15s} {line}")


if __name__ == "__main__":
    main()
