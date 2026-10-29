"""Monte Carlo comparison of two fuels under economic uncertainty.

Samples uncertain economic inputs (fuel prices and escalation, carbon tax and
escalation, interest rate, sea days, machinery capex, reactor cost), solves
the same ship with fuel A and fuel B for every sample, and reports how often
B is cheaper, what drives the RFR gap, and - per sample - the value of a
chosen input at which the two fuels break even.

Shared inputs (carbon, finance, utilisation) use the same draw for A and B
(common random numbers), so the comparison is paired: differences come from
the fuels, not from sampling noise. Per-fuel inputs (fuel price, fuel
escalation, machinery cost) are drawn separately for A and B, optionally
correlated through a Gaussian copula.

Qt-free: numpy, the stdlib NormalDist and the headless ShipDesignSolver.

    from monte_carlo import run_comparison, default_uncertainty, BreakEvenSpec
    base = ShipDesignSolver().input_snapshot()
    unc = default_uncertainty(base, "Direct diesel", "Ammonia (Combustion)")
    res = run_comparison(base, "Direct diesel", "Ammonia (Combustion)", unc, n=2000,
                         seed=1, breakeven=BreakEvenSpec("carbon_tax", 0, 1000))
    print(res.summary())
"""
import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Callable, ClassVar, Optional

import numpy as np

from economics import PricePath
from ship_config import DEFAULT_FUEL_PRICE, FuelConfig
from ship_solver import ShipDesignSolver

_STD_NORMAL = NormalDist()
_norm_ppf = np.vectorize(_STD_NORMAL.inv_cdf, otypes=[float])
_erf = np.vectorize(math.erf, otypes=[float])


def _norm_cdf(z):
    return 0.5 * (1.0 + _erf(np.asarray(z, dtype=float) / math.sqrt(2.0)))


# ----------------------------------------------------------------------
# Distributions
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Distribution:
    """A 1-D input distribution, sampled through its inverse CDF.

    fixed(a) | uniform(a=low, b=high) | triangular(a=low, b=mode, c=high)
    | normal(a=mean, b=sd) | lognormal(a=mean, b=sd)   (mean/sd of the value
    itself, not of its log)
    """
    kind: str = "fixed"
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0

    KINDS: ClassVar[tuple] = ("fixed", "uniform", "triangular", "normal", "lognormal")
    PARAM_NAMES: ClassVar[dict] = {
        "fixed": ("Value", "", ""),
        "uniform": ("Low", "High", ""),
        "triangular": ("Low", "Mode", "High"),
        "normal": ("Mean", "SD", ""),
        "lognormal": ("Mean", "SD", ""),
    }

    def validate(self):
        k, a, b, c = self.kind, self.a, self.b, self.c
        if k not in self.KINDS:
            raise ValueError(f"unknown distribution {k!r}")
        if k == "uniform" and not a <= b:
            raise ValueError("uniform needs low <= high")
        if k == "triangular" and not a <= b <= c:
            raise ValueError("triangular needs low <= mode <= high")
        if k in ("normal", "lognormal") and b < 0:
            raise ValueError(f"{k} needs sd >= 0")
        if k == "lognormal" and a <= 0:
            raise ValueError("lognormal needs mean > 0")

    def ppf(self, u):
        """Inverse CDF at probabilities u (array in (0, 1))."""
        self.validate()
        u = np.clip(np.asarray(u, dtype=float), 1e-12, 1.0 - 1e-12)
        k, a, b, c = self.kind, self.a, self.b, self.c
        if k == "fixed":
            return np.full(u.shape, float(a))
        if k == "uniform":
            return a + (b - a) * u
        if k == "triangular":
            if c == a:
                return np.full(u.shape, float(a))
            fc = (b - a) / (c - a)
            left = a + np.sqrt(u * (c - a) * (b - a))
            right = c - np.sqrt((1.0 - u) * (c - a) * (c - b))
            return np.where(u < fc, left, right)
        z = _norm_ppf(u)
        if k == "normal":
            return a + b * z
        sigma2 = math.log(1.0 + (b / a) ** 2)
        return np.exp(math.log(a) - 0.5 * sigma2 + math.sqrt(sigma2) * z)

    def mean(self):
        k, a, b, c = self.kind, self.a, self.b, self.c
        return {"fixed": a, "uniform": (a + b) / 2, "triangular": (a + b + c) / 3,
                "normal": a, "lognormal": a}[k]

    def describe(self):
        names = [n for n in self.PARAM_NAMES[self.kind] if n]
        vals = (self.a, self.b, self.c)[:len(names)]
        return f"{self.kind}(" + ", ".join(f"{v:g}" for v in vals) + ")"


# ----------------------------------------------------------------------
# Uncertain variables
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Variable:
    key: str
    label: str
    unit: str
    per_fuel: bool
    apply: Callable          # apply(inputs_dict, value)
    floor: Optional[float] = None
    ceil: Optional[float] = None

    def clip(self, v):
        if self.floor is not None:
            v = max(v, self.floor)
        if self.ceil is not None:
            v = min(v, self.ceil)
        return v


VALUE = object()   # placeholder for "the sampled value" in _set()


def _set(**pairs):
    """apply() that writes fixed attribute values, with VALUE as placeholder."""
    def apply(inputs, value):
        for k, v in pairs.items():
            inputs[k] = value if v is VALUE else v
    return apply

VARIABLES = {v.key: v for v in (
    Variable("fuel_price", "Fuel price", "$/t", True, _set(m_Fuel=VALUE), floor=0.01),  # solver needs > 0
    Variable("fuel_escalation", "Fuel escalation", "%/yr", True,
             lambda inp, v: inp.__setitem__("m_FuelPricePath", PricePath("escalation", escalation_pct=v)),
             floor=-99.0),
    Variable("carbon_tax", "Carbon tax", "$/tCO2e", False, _set(m_CarbonTax=VALUE, m_CarbonTaxOn=True),
             floor=0.0),
    Variable("carbon_escalation", "Carbon escalation", "%/yr", False,
             lambda inp, v: inp.__setitem__("m_CarbonPricePath", PricePath("escalation", escalation_pct=v)),
             floor=-99.0),
    Variable("interest_rate", "Interest rate", "%", False, _set(m_Interest=VALUE), floor=0.0),
    Variable("sea_days", "Sea days", "days/yr", False, _set(m_Seadays=VALUE), floor=1.0, ceil=365.0),
    Variable("machinery_cost", "Machinery capex", "x estimate", True, _set(m_MachineryCostFactor=VALUE),
             floor=0.0),
    Variable("reactor_cost", "Reactor cost", "$/kW", False, _set(m_Reactor_Cost_per_kW=VALUE), floor=1.0),
)}


def columns():
    """All sample columns: shared keys, per-fuel keys with _A / _B."""
    cols = []
    for v in VARIABLES.values():
        cols.extend([v.key + "_A", v.key + "_B"] if v.per_fuel else [v.key])
    return cols


def column_info(col):
    """(Variable, side) for a column; side is None for shared, else 'A'/'B'."""
    if col in VARIABLES and not VARIABLES[col].per_fuel:
        return VARIABLES[col], None
    key, _, side = col.rpartition("_")
    if key in VARIABLES and VARIABLES[key].per_fuel and side in ("A", "B"):
        return VARIABLES[key], side
    raise KeyError(f"unknown Monte Carlo input {col!r}")


def column_label(col, fuel_a="A", fuel_b="B"):
    var, side = column_info(col)
    who = "" if side is None else f" ({fuel_a if side == 'A' else fuel_b})"
    return f"{var.label}{who} [{var.unit}]"


# ----------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------
def sample(uncertain, n, seed=None, method="lhs", correlations=None):
    """Draw n samples of every column in `uncertain` ({column: Distribution}).

    method "lhs" stratifies each column into n equal-probability bins (one
    draw per bin); "random" is plain Monte Carlo. `correlations` maps
    (col1, col2) -> rank-ish correlation applied through a Gaussian copula.
    """
    cols = list(uncertain)
    d = len(cols)
    if n < 1:
        raise ValueError("n must be >= 1")
    rng = np.random.default_rng(seed)
    if d == 0:
        return {}
    if method == "lhs":
        strata = rng.permuted(np.tile(np.arange(n), (d, 1)), axis=1).T
        u = (strata + rng.random((n, d))) / n
    elif method == "random":
        u = rng.random((n, d))
    else:
        raise ValueError(f"unknown sampling method {method!r}")

    pairs = {k: r for k, r in (correlations or {}).items()
             if k[0] in uncertain and k[1] in uncertain and r != 0}
    if pairs:
        corr = np.eye(d)
        for (c1, c2), r in pairs.items():
            i, j = cols.index(c1), cols.index(c2)
            corr[i, j] = corr[j, i] = r
        try:
            chol = np.linalg.cholesky(corr)
        except np.linalg.LinAlgError:
            raise ValueError("correlation matrix is not positive definite")
        u = _norm_cdf(_norm_ppf(u) @ chol.T)

    out = {}
    for i, col in enumerate(cols):
        var, _ = column_info(col)
        vals = uncertain[col].ppf(u[:, i])
        if var.floor is not None or var.ceil is not None:
            vals = np.clip(vals, var.floor if var.floor is not None else -np.inf,
                           var.ceil if var.ceil is not None else np.inf)
        out[col] = vals
    return out


# ----------------------------------------------------------------------
# Defaults (illustrative - edit for a real study)
# ----------------------------------------------------------------------
def base_fuel_price(base_inputs, engine):
    """The form's price for the form's engine, else DEFAULT_FUEL_PRICE."""
    if engine == base_inputs.get("engine_name"):
        return float(base_inputs.get("m_Fuel", 0.0))
    return float(DEFAULT_FUEL_PRICE.get(engine, base_inputs.get("m_Fuel", 600.0)))


def default_uncertainty(base_inputs, fuel_a, fuel_b):
    """({column: Distribution}, {column: enabled}) starting values.

    Placeholder spreads around the current inputs, meant to be edited.
    """
    def tri(lo, mode, hi):
        return Distribution("triangular", lo, mode, hi)

    interest = float(base_inputs.get("m_Interest", 10.0))
    seadays = float(base_inputs.get("m_Seadays", 340.0))
    reactor = float(base_inputs.get("m_Reactor_Cost_per_kW", 9000.0))
    any_nuclear = any(FuelConfig.get(f)["IsNuclear"] for f in (fuel_a, fuel_b))
    dists, use = {}, {}
    for side, fuel in (("A", fuel_a), ("B", fuel_b)):
        p = base_fuel_price(base_inputs, fuel)
        dists[f"fuel_price_{side}"] = tri(0.7 * p, p, 1.5 * p)
        dists[f"fuel_escalation_{side}"] = tri(-1.0, 1.0, 4.0)
        dists[f"machinery_cost_{side}"] = tri(0.9, 1.0, 1.3)
        nuclear = FuelConfig.get(fuel)["IsNuclear"]
        use[f"fuel_price_{side}"] = not nuclear
        use[f"fuel_escalation_{side}"] = not nuclear
        use[f"machinery_cost_{side}"] = True
    dists["carbon_tax"] = tri(30.0, 100.0, 250.0)
    dists["carbon_escalation"] = tri(0.0, 3.0, 7.0)
    dists["interest_rate"] = tri(0.6 * interest, interest, 1.2 * interest)
    dists["sea_days"] = tri(0.88 * seadays, seadays, min(1.03 * seadays, 365.0))
    dists["reactor_cost"] = tri(0.7 * reactor, reactor, 1.6 * reactor)
    use.update(carbon_tax=True, carbon_escalation=True, interest_rate=True, sea_days=True,
               reactor_cost=any_nuclear)
    return {c: dists[c] for c in columns()}, {c: use[c] for c in columns()}


def default_breakeven_bracket(col, base_inputs, fuel_a, fuel_b):
    var, side = column_info(col)
    if var.key == "fuel_price":
        p = base_fuel_price(base_inputs, fuel_a if side == "A" else fuel_b)
        return 0.0, max(5.0 * p, 1000.0)
    return {"fuel_escalation": (-10.0, 20.0), "carbon_tax": (0.0, 1000.0),
            "carbon_escalation": (-10.0, 20.0), "interest_rate": (0.1, 30.0),
            "sea_days": (50.0, 365.0), "machinery_cost": (0.1, 5.0),
            "reactor_cost": (500.0, 30000.0)}[var.key]


# ----------------------------------------------------------------------
# Running
# ----------------------------------------------------------------------
PROP_NAMES = {1: "single", 2: "twin"}


def option_names(fuel_a, props_a, fuel_b, props_b):
    """Display names for the two options; ", single" / ", twin" is added
    only when the two sides differ in propeller count."""
    if props_a == props_b:
        return fuel_a, fuel_b
    return f"{fuel_a}, {PROP_NAMES[props_a]}", f"{fuel_b}, {PROP_NAMES[props_b]}"


def fuel_setup(base_inputs, engine, n_props=None):
    """Copy of base_inputs prepared to solve with `engine` (and, if given,
    `n_props` propellers)."""
    if engine not in FuelConfig.DATA:
        raise KeyError(f"unknown fuel {engine!r}")
    inp = dict(base_inputs)
    fd = FuelConfig.DATA[engine]
    if engine != base_inputs.get("engine_name"):
        inp["m_LHV"] = fd["LHV"] if fd["LHV"] > 0 else 42.7
    inp["m_Fuel"] = base_fuel_price(base_inputs, engine)
    inp["engine_name"] = engine
    if n_props is not None:
        if n_props not in PROP_NAMES:
            raise ValueError(f"number of propellers must be 1 or 2, got {n_props}")
        inp["m_NumProps"] = n_props
    if fd["IsNuclear"]:
        inp["m_Range"] = float("inf")
    elif math.isinf(inp.get("m_Range", 0.0)):
        inp["m_Range"] = inp.get("m_conventional_Range", 12000.0)
    # Batch runs: tolerate transient speed/pitch range errors (the solver
    # auto-corrects RPM), never stop for debug prompts.
    inp["ignspd"] = inp["ignpth"] = True
    inp["dbgmd"] = False
    inp["m_Econom"] = True
    return inp


def _inputs_for(base_side, side, values, override=None):
    inp = dict(base_side)
    items = list(values.items()) + ([override] if override else [])
    for col, v in items:
        var, s = column_info(col)
        if s is None or s == side:
            var.apply(inp, var.clip(float(v)))
    return inp


def _solve(inputs):
    s = ShipDesignSolver().set_inputs(**inputs)
    return s, s.solve()


def _rfr(inputs):
    s, ok = _solve(inputs)
    return s.Rf if ok else float("nan")


def _stability_summary(solver, ok):
    """(GM_min, stability_ok, first failure) of a base-case solve."""
    if not ok:
        return None
    fails = list(getattr(solver, "stability_failures", []))
    if getattr(solver, "deck_fit_warning", ""):
        fails.append(solver.deck_fit_warning)
    return (getattr(solver, "GM_min", float("nan")), bool(getattr(solver, "stability_ok", False)),
            fails[0] if fails else "")


@dataclass
class BreakEvenSpec:
    """Find, per sample, the value of `column` in [lo, hi] where RFR_A == RFR_B."""
    column: str
    lo: float
    hi: float
    max_iter: int = 30
    rel_tol: float = 1e-9


def _breakeven(base, values, spec, rfr_a, rfr_b):
    """(x*, status). status: 'B_above' / 'B_below' (B is cheaper above /
    below x*), 'A_always' / 'B_always' (no crossing in the bracket), or
    'failed'."""
    var, side = column_info(spec.column)
    tol = spec.rel_tol * max(1.0, abs(rfr_a) + abs(rfr_b))

    def gap(x):
        ov = (spec.column, x)
        ra = _rfr(_inputs_for(base["A"], "A", values, ov)) if side in (None, "A") else rfr_a
        rb = _rfr(_inputs_for(base["B"], "B", values, ov)) if side in (None, "B") else rfr_b
        return rb - ra

    lo, hi = var.clip(spec.lo), var.clip(spec.hi)
    a, fa, b, fb = lo, gap(lo), hi, gap(hi)
    if not (math.isfinite(fa) and math.isfinite(fb)):
        return float("nan"), "failed"
    if fa * fb > 0:
        return float("nan"), "B_always" if fa < 0 else "A_always"
    status = "B_above" if fb < fa else "B_below"
    if fa == 0:
        return a, status
    if fb == 0:
        return b, status
    for _ in range(spec.max_iter):            # regula falsi, Illinois variant
        c = (a * fb - b * fa) / (fb - fa)
        fc = gap(c)
        if not math.isfinite(fc):
            return float("nan"), "failed"
        if abs(fc) <= tol:
            return c, status
        if fc * fb < 0:
            a, fa = b, fb
        else:
            fa *= 0.5
        b, fb = c, fc
    return b, status


@dataclass
class ComparisonResult:
    fuel_a: str
    fuel_b: str
    samples: dict
    rfr_a: np.ndarray
    rfr_b: np.ndarray
    base_rfr_a: float
    base_rfr_b: float
    breakeven_spec: Optional[BreakEvenSpec] = None
    breakeven: Optional[np.ndarray] = None
    breakeven_status: Optional[np.ndarray] = None
    base_breakeven: float = float("nan")
    base_breakeven_status: str = ""
    n_requested: int = 0
    cancelled: bool = False
    name_a: str = ""          # display names (fuel, plus propeller count when
    name_b: str = ""          # the two sides differ in it); default: the fuel
    stability_a: Optional[tuple] = None   # base case (GM_min, ok, first failure);
    stability_b: Optional[tuple] = None   # the hull does not vary with the samples
    gap: np.ndarray = field(init=False)
    ok: np.ndarray = field(init=False)

    def __post_init__(self):
        self.name_a = self.name_a or self.fuel_a
        self.name_b = self.name_b or self.fuel_b
        self.gap = self.rfr_b - self.rfr_a
        self.ok = np.isfinite(self.rfr_a) & np.isfinite(self.rfr_b)

    @property
    def n(self):
        return len(self.rfr_a)

    def p_b_cheaper(self):
        return float(np.mean(self.gap[self.ok] < 0)) if self.ok.any() else float("nan")

    @staticmethod
    def percentiles(arr, qs=(10, 50, 90)):
        arr = np.asarray(arr, dtype=float)
        arr = arr[np.isfinite(arr)]
        return tuple(float(np.percentile(arr, q)) for q in qs) if arr.size else tuple(float("nan") for _ in qs)

    def drivers(self):
        """[(column, Spearman rho with the gap)], largest |rho| first.
        Columns that did not vary are left out."""
        out = []
        g = self.gap[self.ok]
        if g.size < 3 or np.ptp(g) == 0:
            return out
        rg = np.argsort(np.argsort(g))
        for col, vals in self.samples.items():
            x = np.asarray(vals)[self.ok]
            if np.ptp(x) == 0:
                continue
            rho = float(np.corrcoef(np.argsort(np.argsort(x)), rg)[0, 1])
            out.append((col, rho))
        return sorted(out, key=lambda t: -abs(t[1]))

    def breakeven_counts(self):
        if self.breakeven_status is None:
            return {}
        st = self.breakeven_status[self.ok]
        return {k: int(np.sum(st == k)) for k in ("B_above", "B_below", "A_always", "B_always", "failed")}

    def summary(self):
        a, b = self.name_a, self.name_b
        n_ok = int(self.ok.sum())
        lines = [f"Monte Carlo: {a} (A) vs {b} (B)",
                 f"Samples: {n_ok} solved of {self.n}"
                 + (f" (run cancelled after {self.n} of {self.n_requested})" if self.cancelled else "")]
        if self.n - n_ok:
            lines.append(f"  {self.n - n_ok} sample(s) failed to solve and are excluded.")
        lines.append(f"Base case RFR:  A = {self.base_rfr_a:.2f}   B = {self.base_rfr_b:.2f}  ($/t)")
        stab = []
        for side, st in (("A", self.stability_a), ("B", self.stability_b)):
            if st is not None:
                gm, ok, why = st
                stab.append(f"{side} GM min {gm:.2f} m {'OK' if ok else 'FAIL'}" + ("" if ok or not why else f" ({why})"))
        if stab:
            lines.append("Stability (base case):  " + "   ".join(stab))
        if n_ok:
            lines.append(f"P(B cheaper than A) = {100 * self.p_b_cheaper():.1f} %")
            for name, arr in (("RFR A", self.rfr_a[self.ok]), ("RFR B", self.rfr_b[self.ok]),
                              ("Gap B-A", self.gap[self.ok])):
                p10, p50, p90 = self.percentiles(arr)
                lines.append(f"{name:8s} P10 {p10:9.2f}   P50 {p50:9.2f}   P90 {p90:9.2f}  ($/t)")
        if self.breakeven_spec is not None and n_ok:
            spec = self.breakeven_spec
            var, _ = column_info(spec.column)
            label = column_label(spec.column, a, b)
            lines.append("")
            lines.append(f"Break-even on {label}, searched {spec.lo:g} to {spec.hi:g}:")
            counts = self.breakeven_counts()
            crossing = self.breakeven[self.ok & np.isfinite(self.breakeven)]
            if crossing.size:
                p10, p50, p90 = self.percentiles(crossing)
                lines.append(f"  P10 {p10:,.2f}   P50 {p50:,.2f}   P90 {p90:,.2f}  {var.unit}")
            tot = max(n_ok, 1)
            lines.append(f"  B cheaper above break-even: {counts['B_above']} | below: {counts['B_below']}"
                         f" | no crossing, A always cheaper: {counts['A_always']}"
                         f" | B always cheaper: {counts['B_always']}"
                         + (f" | failed: {counts['failed']}" if counts['failed'] else "")
                         + f"  (of {tot})")
            if math.isfinite(self.base_breakeven):
                side = "above" if self.base_breakeven_status == "B_above" else "below"
                lines.append(f"  Base case: B cheaper {side} {self.base_breakeven:,.2f} {var.unit}")
            elif self.base_breakeven_status:
                lines.append(f"  Base case: no crossing ({self.base_breakeven_status.replace('_', ' ')})")
        drv = self.drivers()
        if drv:
            lines.append("")
            lines.append("Drivers of the gap (Spearman rho; + means raises B's RFR relative to A):")
            for col, rho in drv[:8]:
                lines.append(f"  {column_label(col, a, b):45s} {rho:+.2f}")
        return "\n".join(lines)

    def to_rows(self):
        cols = list(self.samples)
        header = ["Sample"] + cols + [f"RFR A {self.name_a} ($/t)", f"RFR B {self.name_b} ($/t)", "Gap B-A ($/t)"]
        if self.breakeven is not None:
            header += [f"Break-even {self.breakeven_spec.column}", "Break-even status"]
        rows = [header]
        for i in range(self.n):
            row = [i + 1] + [float(self.samples[c][i]) for c in cols]
            row += [float(self.rfr_a[i]), float(self.rfr_b[i]), float(self.gap[i])]
            if self.breakeven is not None:
                row += [float(self.breakeven[i]), str(self.breakeven_status[i])]
            rows.append(row)
        return rows


def run_comparison(base_inputs, fuel_a, fuel_b, uncertain, n=1000, seed=None, method="lhs",
                   correlations=None, breakeven=None, progress=None, cancelled=None,
                   props_a=None, props_b=None):
    """Sample `uncertain` ({column: Distribution}) n times and solve the ship
    with fuel A and fuel B for each sample.

    props_a / props_b: 1 or 2 propellers per side (None keeps the base
    input), so the two options may be the same fuel with single vs twin
    screw. base_inputs: a ShipDesignSolver.input_snapshot(). progress(i, n) is
    called after each sample; if cancelled() returns True the run stops and
    returns the samples completed so far.
    """
    base_props = base_inputs.get("m_NumProps", 1)
    pa = props_a if props_a is not None else base_props
    pb = props_b if props_b is not None else base_props
    if (fuel_a, pa) == (fuel_b, pb):
        raise ValueError("choose two different options (fuel or number of propellers)")
    for col in uncertain:
        column_info(col)
    if breakeven is not None:
        column_info(breakeven.column)
        if not breakeven.lo < breakeven.hi:
            raise ValueError("break-even bracket needs lo < hi")

    samples = sample(uncertain, n, seed=seed, method=method, correlations=correlations)
    base = {"A": fuel_setup(base_inputs, fuel_a, pa), "B": fuel_setup(base_inputs, fuel_b, pb)}
    name_a, name_b = option_names(fuel_a, pa, fuel_b, pb)

    solver_a, ok_a = _solve(base["A"])
    solver_b, ok_b = _solve(base["B"])
    base_a = solver_a.Rf if ok_a else float("nan")
    base_b = solver_b.Rf if ok_b else float("nan")
    base_be, base_status = float("nan"), ""
    if breakeven is not None and math.isfinite(base_a) and math.isfinite(base_b):
        base_be, base_status = _breakeven(base, {}, breakeven, base_a, base_b)

    rfr_a, rfr_b = np.full(n, np.nan), np.full(n, np.nan)
    be = np.full(n, np.nan) if breakeven is not None else None
    be_status = np.full(n, "", dtype=object) if breakeven is not None else None
    done = n
    for i in range(n):
        if cancelled is not None and cancelled():
            done = i
            break
        values = {col: samples[col][i] for col in samples}
        rfr_a[i] = _rfr(_inputs_for(base["A"], "A", values))
        rfr_b[i] = _rfr(_inputs_for(base["B"], "B", values))
        if breakeven is not None and math.isfinite(rfr_a[i]) and math.isfinite(rfr_b[i]):
            be[i], be_status[i] = _breakeven(base, values, breakeven, rfr_a[i], rfr_b[i])
        if progress is not None:
            progress(i + 1, n)

    trim = slice(0, done)
    return ComparisonResult(
        fuel_a=fuel_a, fuel_b=fuel_b, name_a=name_a, name_b=name_b,
        stability_a=_stability_summary(solver_a, ok_a), stability_b=_stability_summary(solver_b, ok_b),
        samples={c: v[trim] for c, v in samples.items()},
        rfr_a=rfr_a[trim], rfr_b=rfr_b[trim],
        base_rfr_a=base_a, base_rfr_b=base_b,
        breakeven_spec=breakeven,
        breakeven=be[trim] if be is not None else None,
        breakeven_status=be_status[trim] if be_status is not None else None,
        base_breakeven=base_be, base_breakeven_status=base_status,
        n_requested=n, cancelled=done < n,
    )
