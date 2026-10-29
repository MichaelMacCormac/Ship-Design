"""Year-by-year cash flow and Required Freight Rate (RFR).

The legacy RFR annualised everything into one year:

    RFR = (CRF * capex + annual costs - premium income) / annual cargo

build_cash_flow() lays the same cost lines out year by year instead and
defines RFR as the freight rate that makes the present value of revenue equal
the present value of costs:

    RFR = PV(costs - premium income) / PV(cargo carried)

With constant inputs, ship life == loan term and discount rate == loan rate,
the two definitions give the same number (PV of the loan annuity is the
capex, and both PVs share one annuity factor). Each cost line can be a
scalar or a per-year array, so price paths (fuel, carbon) and Monte Carlo
draws can drop in without touching the solver.

PricePath turns a base price into a per-year multiplier: flat, constant
escalation, or calendar-year keyframes (% of base, linearly interpolated).

Pure numpy - no Qt, no solver state.
"""
from dataclasses import dataclass, field

import numpy as np


def capital_recovery_factor(rate, years):
    """Annuity factor: the constant annual payment that repays 1.0 of
    principal over `years` at interest `rate` (a fraction, e.g. 0.10)."""
    if years <= 0:
        raise ValueError("years must be >= 1")
    if rate == 0:
        return 1.0 / years
    g = (1.0 + rate) ** years
    return rate * g / (g - 1.0)


@dataclass
class PricePath:
    """How a price moves relative to its base value over the ship's life.

    mode "flat":        the base price every year.
    mode "escalation":  compounds escalation_pct %/yr from the delivery year
                        (operating year 1 pays the base price).
    mode "keyframes":   ((calendar_year, pct_of_base), ...) linearly
                        interpolated; held flat before the first and after
                        the last keyframe. No keyframes behaves as flat.
    """
    mode: str = "flat"
    escalation_pct: float = 0.0
    keyframes: tuple = ()

    MODES = ("flat", "escalation", "keyframes")

    def validate(self):
        if self.mode not in self.MODES:
            raise ValueError(f"unknown mode {self.mode!r} (expected one of {', '.join(self.MODES)})")
        if self.mode == "escalation" and self.escalation_pct <= -100.0:
            raise ValueError("escalation must be greater than -100 %/yr")
        if self.mode == "keyframes":
            years = [y for y, _ in self.keyframes]
            if any(b <= a for a, b in zip(years, years[1:])):
                raise ValueError("keyframe years must be strictly increasing")
            if any(p < 0 for _, p in self.keyframes):
                raise ValueError("keyframe percentages must not be negative")

    def is_flat(self):
        return (self.mode == "flat"
                or (self.mode == "escalation" and self.escalation_pct == 0.0)
                or (self.mode == "keyframes" and not self.keyframes))

    def index(self, delivery_year, n_years):
        """Multiplier on the base price for operating years 1..n_years."""
        self.validate()
        op_years = np.arange(n_years, dtype=float)          # 0 = delivery year
        if self.mode == "escalation":
            return (1.0 + self.escalation_pct / 100.0) ** op_years
        if self.mode == "keyframes" and self.keyframes:
            years = np.array([y for y, _ in self.keyframes], dtype=float)
            pct = np.array([p for _, p in self.keyframes], dtype=float)
            return np.interp(delivery_year + op_years, years, pct) / 100.0
        return np.ones(n_years)

    def describe(self):
        if self.is_flat():
            return "flat"
        if self.mode == "escalation":
            return f"{self.escalation_pct:+.1f} %/yr"
        return "keyframes " + ", ".join(f"{int(y)}:{p:g}%" for y, p in self.keyframes)


@dataclass
class CashFlowInputs:
    """Inputs to build_cash_flow(). Money in $, quantities per year.

    Every per-year field takes either a scalar (the same value each operating
    year) or a sequence of length ship_life (year 1 first).
    """
    capex: float                  # build cost, $ (financed in full)
    loan_rate: float              # fraction/yr
    loan_term: int                # years of loan repayment
    ship_life: int                # operating years (cargo carried, opex paid)
    discount_rate: float          # fraction/yr
    cargo_per_year: object        # tonnes of cargo carried per year
    fixed_opex: object = 0.0      # crew, port, stores, overhead, other, $
    maintenance: object = 0.0     # hull/outfit + machinery maintenance, $
    fuel_tonnes: object = 0.0     # main-engine fuel, t
    fuel_price: object = 0.0      # $/t
    co2e_tonnes: object = 0.0     # taxable CO2-equivalent, t
    carbon_price: object = 0.0    # $/t CO2e (0 when no carbon tax applies)
    aux_fuel_tonnes: object = 0.0 # auxiliary genset fuel, t
    aux_price: object = 0.0       # $/t
    nuclear: object = 0.0         # annualised core replacement + decommissioning fund, $
    premium_income: object = 0.0  # reefer/cold-chain premium revenue, $
    start_year: int = 1           # calendar year of operating year 1 (labels only)


@dataclass
class CashFlowResult:
    """Yearly cash-flow table plus the PV totals and RFR derived from it.

    Arrays run over years 1..horizon, where horizon = max(ship_life,
    loan_term): loan payments still fall due if the ship is scrapped
    before the loan is repaid, but it earns and spends nothing after.
    """
    years: np.ndarray
    calendar_years: np.ndarray
    capital: np.ndarray
    fixed_opex: np.ndarray
    maintenance: np.ndarray
    fuel: np.ndarray
    carbon: np.ndarray
    aux_fuel: np.ndarray
    nuclear: np.ndarray
    premium_income: np.ndarray
    cargo: np.ndarray
    discount_factor: np.ndarray
    fuel_tonnes: np.ndarray
    fuel_price: np.ndarray
    co2e_tonnes: np.ndarray
    carbon_price: np.ndarray
    net_cost: np.ndarray = field(init=False)
    pv_costs: float = field(init=False)
    pv_cargo: float = field(init=False)
    rfr: float = field(init=False)
    levelised_fuel_price: float = field(init=False)
    levelised_carbon_price: float = field(init=False)

    def __post_init__(self):
        self.net_cost = (self.capital + self.fixed_opex + self.maintenance + self.fuel
                         + self.carbon + self.aux_fuel + self.nuclear - self.premium_income)
        self.pv_costs = float(np.sum(self.net_cost * self.discount_factor))
        self.pv_cargo = float(np.sum(self.cargo * self.discount_factor))
        self.rfr = self.pv_costs / self.pv_cargo if self.pv_cargo != 0 else float("inf")
        # PV-weighted average prices: the single flat price that would give
        # the same PV of fuel (carbon) spend as the path did.
        self.levelised_fuel_price = self._levelised(self.fuel, self.fuel_tonnes)
        self.levelised_carbon_price = self._levelised(self.carbon, self.co2e_tonnes)

    def _levelised(self, cost, qty):
        pv_qty = float(np.sum(qty * self.discount_factor))
        if pv_qty <= 0:
            return float("nan")
        return float(np.sum(cost * self.discount_factor)) / pv_qty

    COLUMNS = ("Year", "Calendar year", "Capital ($)", "Fixed OPEX ($)", "Maintenance ($)",
               "Fuel price ($/t)", "Fuel ($)", "Carbon price ($/t)", "Carbon tax ($)",
               "Aux fuel ($)", "Nuclear core+decom ($)", "Premium income ($)",
               "Net cost ($)", "Cargo (t)", "Discount factor")

    def to_rows(self):
        """Header + one row per year, for CSV export."""
        rows = [list(self.COLUMNS)]
        for i, y in enumerate(self.years):
            rows.append([int(y), int(self.calendar_years[i]), self.capital[i], self.fixed_opex[i],
                         self.maintenance[i], self.fuel_price[i], self.fuel[i],
                         self.carbon_price[i], self.carbon[i], self.aux_fuel[i], self.nuclear[i],
                         self.premium_income[i], self.net_cost[i], self.cargo[i],
                         self.discount_factor[i]])
        return rows


def _per_year(value, ship_life, horizon, name):
    """Expand a scalar or length-ship_life sequence to a horizon-length
    array, zero after the end of ship life."""
    out = np.zeros(horizon)
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        out[:ship_life] = float(arr)
    elif arr.shape == (ship_life,):
        out[:ship_life] = arr
    else:
        raise ValueError(f"{name}: expected a scalar or {ship_life} yearly values, got shape {arr.shape}")
    return out


def build_cash_flow(inp):
    """Lay the cost lines of CashFlowInputs out year by year and derive the RFR."""
    life = int(inp.ship_life)
    term = int(inp.loan_term)
    if life < 1 or term < 1:
        raise ValueError("ship_life and loan_term must both be >= 1 year")
    horizon = max(life, term)

    def py(name):
        return _per_year(getattr(inp, name), life, horizon, name)

    years = np.arange(1, horizon + 1)
    capital = np.zeros(horizon)
    capital[:term] = capital_recovery_factor(inp.loan_rate, term) * inp.capex
    fuel_tonnes, fuel_price = py("fuel_tonnes"), py("fuel_price")
    co2e_tonnes, carbon_price = py("co2e_tonnes"), py("carbon_price")

    return CashFlowResult(
        years=years,
        calendar_years=years + (int(inp.start_year) - 1),
        capital=capital,
        fixed_opex=py("fixed_opex"),
        maintenance=py("maintenance"),
        fuel=fuel_tonnes * fuel_price,
        carbon=co2e_tonnes * carbon_price,
        aux_fuel=py("aux_fuel_tonnes") * py("aux_price"),
        nuclear=py("nuclear"),
        premium_income=py("premium_income"),
        cargo=py("cargo_per_year"),
        discount_factor=(1.0 + inp.discount_rate) ** -years.astype(float),
        fuel_tonnes=fuel_tonnes,
        fuel_price=fuel_price,
        co2e_tonnes=co2e_tonnes,
        carbon_price=carbon_price,
    )
