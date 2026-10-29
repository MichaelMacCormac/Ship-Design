"""Headless tests for ShipDesignSolver and the cash-flow model.

Run from the repository root:
    python -m unittest discover tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from economics import CashFlowInputs, build_cash_flow, capital_recovery_factor  # noqa: E402
from ship_solver import ShipDesignSolver  # noqa: E402


def solve(**inputs):
    s = ShipDesignSolver().set_inputs(**inputs)
    ok = s.solve()
    return s, ok


class TestHeadlessSolver(unittest.TestCase):
    def test_solver_does_not_import_qt(self):
        self.assertNotIn("PySide6", sys.modules)

    # Reference values captured from the GUI (ShipDesViewWidget.on_calculate)
    # before the solver was split out of it.
    def test_diesel_tanker_matches_gui_reference(self):
        s, ok = solve(ship_name="Tanker", engine_name="Direct diesel")
        self.assertTrue(ok, s.solver_errors)
        self.assertAlmostEqual(s.L1, 207.34300858940713, places=9)
        self.assertAlmostEqual(s.B, 31.89892439837033, places=9)
        self.assertAlmostEqual(s.C, 0.818524807853084, places=12)
        self.assertAlmostEqual(s.P2, 19482.9162724039, places=6)
        self.assertAlmostEqual(s.S, 277.8606938202307, places=9)
        self.assertAlmostEqual(s.Rf, 74.70836870675606, places=9)

    def test_hydrogen_container_holtrop_matches_gui_reference(self):
        s, ok = solve(ship_name="Container Ship", engine_name="Hydrogen (Fuel Cell)",
                      resistance_method="Holtrop-Mennen (1984)", m_Fuel=4000.0, m_LHV=120.0)
        self.assertTrue(ok, s.solver_errors)
        self.assertAlmostEqual(s.L1, 217.71296033733475, places=9)
        self.assertAlmostEqual(s.P2, 18679.507262263454, places=6)
        self.assertAlmostEqual(s.Rf, 108.88783997046323, places=9)

    def test_nuclear_tanker_matches_gui_reference(self):
        s, ok = solve(ship_name="Tanker", engine_name="Nuclear SMR", m_Range=float("inf"))
        self.assertTrue(ok, s.solver_errors)
        self.assertAlmostEqual(s.S, 340.97765002151556, places=9)
        self.assertAlmostEqual(s.Rf, 96.25935396047979, places=9)

    def test_failure_is_reported_not_raised(self):
        s, ok = solve(ship_name="Tanker", m_Weight=-1.0)
        self.assertFalse(ok)
        self.assertTrue(any("Cargo Weight" in e for e in s.solver_errors))

    def test_unknown_input_name_raises(self):
        with self.assertRaises(AttributeError):
            ShipDesignSolver().set_inputs(m_Speeed=14.0)

    def test_unknown_ship_type_is_rejected(self):
        s, ok = solve(ship_name="Submarine")
        self.assertFalse(ok)

    def test_results_dict(self):
        s, ok = solve(ship_name="Tanker")
        self.assertTrue(ok)
        r = s.results()
        self.assertEqual(r["Lbp(m)"], s.L1)
        self.assertEqual(r["RFR($/tonne or $/TEU)"], s.Rf)

    def test_repeat_solves_on_one_instance_are_stable(self):
        s = ShipDesignSolver()
        self.assertTrue(s.solve())
        first = s.Rf
        self.assertTrue(s.solve())
        self.assertEqual(s.Rf, first)


class TestCashFlowInSolver(unittest.TestCase):
    def test_cash_flow_rfr_equals_annualised_when_life_equals_loan(self):
        for engine, extra in (("Direct diesel", {}),
                              ("LNG (Dual Fuel)", {"m_CarbonTaxOn": True, "m_MethaneSlip": 2.0}),
                              ("Nuclear SMR", {"m_Range": float("inf")})):
            s, ok = solve(ship_name="Tanker", engine_name=engine, **extra)
            self.assertTrue(ok, (engine, s.solver_errors))
            self.assertTrue(math.isclose(s.Rf, s.Rf_annualised, rel_tol=1e-12), engine)

    def test_longer_ship_life_lowers_rfr(self):
        base, _ = solve(ship_name="Tanker")
        longer, ok = solve(ship_name="Tanker", m_ShipLife=25.0)
        self.assertTrue(ok)
        self.assertLess(longer.Rf, base.Rf)
        self.assertEqual(len(longer.cash_flow.years), 25)
        self.assertEqual(longer.cash_flow.capital[20], 0.0)  # loan repaid after year 15

    def test_shorter_ship_life_still_pays_off_loan(self):
        s, ok = solve(ship_name="Tanker", m_ShipLife=10.0)
        self.assertTrue(ok)
        cf = s.cash_flow
        self.assertEqual(len(cf.years), 15)
        self.assertGreater(cf.capital[14], 0.0)
        self.assertEqual(cf.cargo[12], 0.0)
        self.assertGreater(s.Rf, s.Rf_annualised)

    def test_zero_ship_life_is_rejected(self):
        s, ok = solve(ship_name="Tanker", m_ShipLife=0.0)
        self.assertFalse(ok)
        self.assertTrue(any("Ship life" in e for e in s.solver_errors))


class TestCashFlowModel(unittest.TestCase):
    def _inputs(self, **kw):
        base = dict(capex=100e6, loan_rate=0.08, loan_term=15, ship_life=15,
                    discount_rate=0.08, cargo_per_year=1e6, fixed_opex=5e6,
                    maintenance=1e6, fuel_tonnes=20000.0, fuel_price=600.0)
        base.update(kw)
        return CashFlowInputs(**base)

    def test_pv_of_loan_payments_equals_capex(self):
        cf = build_cash_flow(self._inputs(fixed_opex=0.0, maintenance=0.0, fuel_tonnes=0.0))
        self.assertAlmostEqual(cf.pv_costs, 100e6, delta=1e-3)

    def test_constant_inputs_match_annualised_formula(self):
        cf = build_cash_flow(self._inputs())
        annual = capital_recovery_factor(0.08, 15) * 100e6 + 5e6 + 1e6 + 20000.0 * 600.0
        self.assertTrue(math.isclose(cf.rfr, annual / 1e6, rel_tol=1e-12))

    def test_zero_interest_spreads_capex_evenly(self):
        self.assertAlmostEqual(capital_recovery_factor(0.0, 20), 0.05)

    def test_fuel_price_path_is_used_year_by_year(self):
        flat = build_cash_flow(self._inputs())
        prices = [600.0] * 10 + [1200.0] * 5
        rising = build_cash_flow(self._inputs(fuel_price=prices))
        self.assertEqual(rising.fuel[0], 20000.0 * 600.0)
        self.assertEqual(rising.fuel[-1], 20000.0 * 1200.0)
        self.assertGreater(rising.rfr, flat.rfr)

    def test_wrong_length_path_raises(self):
        with self.assertRaises(ValueError):
            build_cash_flow(self._inputs(fuel_price=[600.0] * 3))

    def test_premium_income_reduces_net_cost(self):
        cf = build_cash_flow(self._inputs(premium_income=2e6))
        plain = build_cash_flow(self._inputs())
        self.assertAlmostEqual(plain.net_cost[0] - cf.net_cost[0], 2e6)

    def test_to_rows_shape(self):
        rows = build_cash_flow(self._inputs()).to_rows()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(rows[0]), len(rows[1]))


if __name__ == "__main__":
    unittest.main()
