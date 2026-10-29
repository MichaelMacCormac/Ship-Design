"""Headless tests for the Monte Carlo fuel comparison.

Run from the repository root:
    python -m unittest discover tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

import monte_carlo as mc  # noqa: E402
from ship_solver import ShipDesignSolver  # noqa: E402

A, B = "Direct diesel", "Ammonia (Combustion)"


def base_inputs():
    return ShipDesignSolver().input_snapshot()


def solve_fuel(base, fuel, **overrides):
    inp = mc.fuel_setup(base, fuel)
    inp.update(overrides)
    s = ShipDesignSolver().set_inputs(**inp)
    assert s.solve(), s.solver_errors
    return s


class TestDistribution(unittest.TestCase):
    U = (np.arange(20000) + 0.5) / 20000

    def test_fixed(self):
        self.assertTrue(np.all(mc.Distribution("fixed", 7.0).ppf(self.U) == 7.0))

    def test_triangular_bounds_and_mean(self):
        d = mc.Distribution("triangular", 2.0, 3.0, 7.0)
        x = d.ppf(self.U)
        self.assertGreaterEqual(x.min(), 2.0)
        self.assertLessEqual(x.max(), 7.0)
        self.assertAlmostEqual(x.mean(), 4.0, places=2)

    def test_uniform_normal_lognormal_means(self):
        self.assertAlmostEqual(mc.Distribution("uniform", 1.0, 3.0).ppf(self.U).mean(), 2.0, places=3)
        self.assertAlmostEqual(mc.Distribution("normal", 10.0, 2.0).ppf(self.U).mean(), 10.0, places=2)
        x = mc.Distribution("lognormal", 100.0, 30.0).ppf(self.U)
        self.assertAlmostEqual(x.mean(), 100.0, delta=0.5)
        self.assertAlmostEqual(x.std(), 30.0, delta=1.0)

    def test_invalid(self):
        for d in (mc.Distribution("triangular", 3.0, 1.0, 5.0), mc.Distribution("uniform", 5.0, 1.0),
                  mc.Distribution("normal", 0.0, -1.0), mc.Distribution("lognormal", 0.0, 1.0),
                  mc.Distribution("weibull", 1.0)):
            with self.assertRaises(ValueError):
                d.validate()


class TestSampling(unittest.TestCase):
    def test_lhs_one_sample_per_stratum(self):
        n = 50
        s = mc.sample({"carbon_tax": mc.Distribution("uniform", 0.0, 1.0)}, n, seed=3)
        strata = np.floor(s["carbon_tax"] * n).astype(int)
        self.assertEqual(sorted(strata), list(range(n)))

    def test_seed_reproduces(self):
        unc = {"carbon_tax": mc.Distribution("triangular", 0, 50, 200),
               "fuel_price_A": mc.Distribution("uniform", 500, 900)}
        a = mc.sample(unc, 100, seed=11)
        b = mc.sample(unc, 100, seed=11)
        c = mc.sample(unc, 100, seed=12)
        self.assertTrue(all(np.array_equal(a[k], b[k]) for k in unc))
        self.assertFalse(np.array_equal(a["carbon_tax"], c["carbon_tax"]))

    def test_correlation_achieved(self):
        unc = {"fuel_price_A": mc.Distribution("normal", 600, 100),
               "fuel_price_B": mc.Distribution("normal", 700, 100)}
        s = mc.sample(unc, 5000, seed=1, correlations={("fuel_price_A", "fuel_price_B"): 0.6})
        rho = np.corrcoef(s["fuel_price_A"], s["fuel_price_B"])[0, 1]
        self.assertAlmostEqual(rho, 0.6, delta=0.05)

    def test_floor_clips(self):
        s = mc.sample({"carbon_tax": mc.Distribution("normal", 0.0, 100.0)}, 500, seed=1)
        self.assertGreaterEqual(s["carbon_tax"].min(), 0.0)

    def test_unknown_column(self):
        with self.assertRaises(KeyError):
            mc.sample({"warp_drive": mc.Distribution("fixed", 1.0)}, 10)


class TestComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = base_inputs()

    def test_shared_inputs_are_common_to_both_fuels(self):
        # Carbon tax sampled once and applied to both fuels: with every
        # other input fixed, each sample must equal a direct solve of
        # both fuels at that same carbon tax.
        unc = {"carbon_tax": mc.Distribution("uniform", 0.0, 300.0)}
        r = mc.run_comparison(self.base, A, B, unc, n=5, seed=4)
        for i in range(r.n):
            tax = r.samples["carbon_tax"][i]
            sa = solve_fuel(self.base, A, m_CarbonTax=tax, m_CarbonTaxOn=True)
            sb = solve_fuel(self.base, B, m_CarbonTax=tax, m_CarbonTaxOn=True)
            self.assertAlmostEqual(r.rfr_a[i], sa.Rf, places=10)
            self.assertAlmostEqual(r.rfr_b[i], sb.Rf, places=10)

    def test_degenerate_run_matches_plain_solves(self):
        unc = {"interest_rate": mc.Distribution("fixed", self.base["m_Interest"])}
        r = mc.run_comparison(self.base, A, B, unc, n=3, seed=1)
        ra, rb = solve_fuel(self.base, A).Rf, solve_fuel(self.base, B).Rf
        self.assertTrue(np.allclose(r.rfr_a, ra, rtol=0, atol=1e-12))
        self.assertTrue(np.allclose(r.rfr_b, rb, rtol=0, atol=1e-12))
        self.assertEqual(r.p_b_cheaper(), 1.0 if rb < ra else 0.0)
        self.assertEqual(r.base_rfr_a, ra)

    def test_breakeven_carbon_tax_equalises_rfr(self):
        unc = {"fuel_price_B": mc.Distribution("triangular", 500.0, 700.0, 1000.0)}
        spec = mc.BreakEvenSpec("carbon_tax", 0.0, 2000.0)
        r = mc.run_comparison(self.base, A, B, unc, n=4, seed=2, breakeven=spec)
        for i in range(r.n):
            x = r.breakeven[i]
            self.assertTrue(math.isfinite(x))
            self.assertEqual(r.breakeven_status[i], "B_above")
            sa = solve_fuel(self.base, A, m_CarbonTax=x, m_CarbonTaxOn=True)
            sb = solve_fuel(self.base, B, m_CarbonTax=x, m_CarbonTaxOn=True,
                            m_Fuel=r.samples["fuel_price_B"][i])
            self.assertLess(abs(sa.Rf - sb.Rf), 1e-6)

    def test_breakeven_outside_bracket_is_flagged(self):
        spec = mc.BreakEvenSpec("carbon_tax", 0.0, 10.0)
        r = mc.run_comparison(self.base, A, B, {}, n=2, seed=1, breakeven=spec)
        self.assertTrue(np.all(np.isnan(r.breakeven)))
        self.assertTrue(all(st == "A_always" for st in r.breakeven_status))
        self.assertEqual(r.base_breakeven_status, "A_always")

    def test_per_fuel_breakeven_on_fuel_price(self):
        # LNG is close to diesel, so a cheaper-LNG break-even exists.
        lng = "LNG (Dual Fuel)"
        spec = mc.BreakEvenSpec("fuel_price_B", 0.0, 2000.0)
        r = mc.run_comparison(self.base, A, lng, {}, n=1, seed=1, breakeven=spec)
        x = r.breakeven[0]
        self.assertTrue(math.isfinite(x))
        self.assertEqual(r.breakeven_status[0], "B_below")
        sb = solve_fuel(self.base, lng, m_Fuel=x)
        self.assertLess(abs(sb.Rf - r.rfr_a[0]), 1e-6)

    def test_top_driver(self):
        unc = {"fuel_price_B": mc.Distribution("uniform", 400.0, 1200.0),
               "sea_days": mc.Distribution("fixed", 340.0)}
        r = mc.run_comparison(self.base, A, B, unc, n=40, seed=5)
        drv = r.drivers()
        self.assertEqual(drv[0][0], "fuel_price_B")
        self.assertGreater(drv[0][1], 0.99)
        self.assertNotIn("sea_days", [c for c, _ in drv])

    def test_cancel_returns_partial(self):
        calls = []
        r = mc.run_comparison(self.base, A, B, {"carbon_tax": mc.Distribution("uniform", 0, 100)},
                              n=20, seed=1, progress=lambda i, n: calls.append(i),
                              cancelled=lambda: len(calls) >= 5)
        self.assertEqual(r.n, 5)
        self.assertTrue(r.cancelled)
        self.assertEqual(len(r.samples["carbon_tax"]), 5)

    def test_rows_and_summary(self):
        spec = mc.BreakEvenSpec("carbon_tax", 0.0, 2000.0)
        dists, use = mc.default_uncertainty(self.base, A, B)
        unc = {c: d for c, d in dists.items() if use[c]}
        r = mc.run_comparison(self.base, A, B, unc, n=20, seed=1, breakeven=spec,
                              correlations={("fuel_price_A", "fuel_price_B"): 0.5})
        rows = r.to_rows()
        self.assertEqual(len(rows), 21)
        self.assertEqual(len(rows[0]), len(rows[1]))
        text = r.summary()
        self.assertIn("P(B cheaper than A)", text)
        self.assertIn("Break-even on Carbon tax", text)

    def test_same_fuel_rejected(self):
        with self.assertRaises(ValueError):
            mc.run_comparison(self.base, A, A, {}, n=1)

    def test_nuclear_fuel_setup(self):
        inp = mc.fuel_setup(self.base, "Nuclear SMR")
        self.assertTrue(math.isinf(inp["m_Range"]))
        back = mc.fuel_setup(inp, A)
        self.assertFalse(math.isinf(back["m_Range"]))


class TestSolverAdditions(unittest.TestCase):
    def test_machinery_cost_factor_scales_capex(self):
        base = ShipDesignSolver()
        self.assertTrue(base.solve())
        dear = ShipDesignSolver().set_inputs(m_MachineryCostFactor=1.5)
        self.assertTrue(dear.solve())
        self.assertAlmostEqual(dear.cost_machinery_M, 1.5 * base.cost_machinery_M, places=9)
        self.assertAlmostEqual(dear.cost_steel_M, base.cost_steel_M, places=12)
        self.assertGreater(dear.Rf, base.Rf)

    def test_input_snapshot_round_trip(self):
        s = ShipDesignSolver().set_inputs(m_Speed=14.0, ship_name="Bulk carrier")
        snap = s.input_snapshot()
        t = ShipDesignSolver().set_inputs(**snap)
        self.assertEqual((t.m_Speed, t.ship_name), (14.0, "Bulk carrier"))
        self.assertNotIn("solver_errors", snap)


if __name__ == "__main__":
    unittest.main()
