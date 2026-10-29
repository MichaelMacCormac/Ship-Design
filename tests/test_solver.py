"""Headless tests for ShipDesignSolver and the cash-flow model.

Run from the repository root:
    python -m unittest discover tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from economics import CashFlowInputs, PricePath, build_cash_flow, capital_recovery_factor  # noqa: E402
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
        rows = build_cash_flow(self._inputs(start_year=2030)).to_rows()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(rows[0]), len(rows[1]))
        header = rows[0]
        self.assertEqual(rows[1][header.index("Calendar year")], 2030)
        self.assertEqual(rows[-1][header.index("Calendar year")], 2044)
        self.assertEqual(rows[1][header.index("Fuel price ($/t)")], 600.0)

    def test_levelised_price_of_flat_path_is_the_price(self):
        cf = build_cash_flow(self._inputs())
        self.assertAlmostEqual(cf.levelised_fuel_price, 600.0)
        self.assertTrue(math.isnan(cf.levelised_carbon_price))


class TestPricePath(unittest.TestCase):
    def test_flat(self):
        self.assertTrue(np.array_equal(PricePath().index(2030, 5), np.ones(5)))

    def test_escalation_starts_at_base(self):
        idx = PricePath("escalation", escalation_pct=3.0).index(2030, 10)
        self.assertEqual(idx[0], 1.0)
        self.assertAlmostEqual(idx[-1], 1.03 ** 9)

    def test_keyframes_interpolate_and_hold(self):
        path = PricePath("keyframes", keyframes=((2030, 100.0), (2040, 200.0)))
        idx = path.index(2025, 25)                       # 2025 .. 2049
        self.assertEqual(idx[0], 1.0)                    # before first keyframe: held
        self.assertAlmostEqual(idx[2035 - 2025], 1.5)    # midway
        self.assertEqual(idx[-1], 2.0)                   # after last keyframe: held

    def test_empty_keyframes_is_flat(self):
        path = PricePath("keyframes")
        self.assertTrue(path.is_flat())
        self.assertTrue(np.array_equal(path.index(2030, 3), np.ones(3)))

    def test_invalid_paths_raise(self):
        for path in (PricePath("rocket"),
                     PricePath("keyframes", keyframes=((2040, 100.0), (2030, 120.0))),
                     PricePath("keyframes", keyframes=((2030, -5.0),)),
                     PricePath("escalation", escalation_pct=-100.0)):
            with self.assertRaises(ValueError):
                path.validate()

    def test_describe(self):
        self.assertEqual(PricePath().describe(), "flat")
        self.assertEqual(PricePath("escalation", escalation_pct=2.0).describe(), "+2.0 %/yr")
        self.assertIn("2030:120%", PricePath("keyframes", keyframes=((2030, 120.0),)).describe())


class TestPricePathsInSolver(unittest.TestCase):
    def test_fuel_escalation_raises_rfr_but_not_the_ship(self):
        base, _ = solve(ship_name="Tanker")
        esc, ok = solve(ship_name="Tanker", m_FuelPricePath=PricePath("escalation", escalation_pct=3.0))
        self.assertTrue(ok, esc.solver_errors)
        self.assertGreater(esc.Rf, base.Rf)
        self.assertEqual((esc.L1, esc.P2, esc.S), (base.L1, base.P2, base.S))
        self.assertEqual(esc.Rf_annualised, base.Rf_annualised)

    def test_levelised_fuel_price_matches_pv_weighted_index(self):
        path = PricePath("escalation", escalation_pct=3.0)
        s, ok = solve(ship_name="Tanker", m_FuelPricePath=path)
        self.assertTrue(ok)
        idx = path.index(s.m_DeliveryYear, s.ship_life)
        df = 1.10 ** -np.arange(1, s.ship_life + 1)
        expected = s.F8 * np.sum(idx * df) / np.sum(df)
        self.assertAlmostEqual(s.cash_flow.levelised_fuel_price, expected, places=6)

    def test_carbon_path_ignored_without_carbon_tax(self):
        base, _ = solve(ship_name="Tanker", engine_name="LNG (Dual Fuel)")
        kf, ok = solve(ship_name="Tanker", engine_name="LNG (Dual Fuel)",
                       m_CarbonPricePath=PricePath("keyframes", keyframes=((2030, 300.0),)))
        self.assertTrue(ok)
        self.assertEqual(kf.Rf, base.Rf)

    def test_carbon_keyframes_raise_rfr_with_tax_on(self):
        base, _ = solve(ship_name="Tanker", engine_name="LNG (Dual Fuel)", m_CarbonTaxOn=True)
        kf, ok = solve(ship_name="Tanker", engine_name="LNG (Dual Fuel)", m_CarbonTaxOn=True,
                       m_CarbonPricePath=PricePath("keyframes", keyframes=((2030, 100.0), (2040, 250.0))))
        self.assertTrue(ok)
        self.assertGreater(kf.Rf, base.Rf)
        self.assertEqual(kf.cash_flow.carbon_price[0], 85.0)    # 2027: before first keyframe

    def test_invalid_path_fails_solve(self):
        s, ok = solve(ship_name="Tanker",
                      m_FuelPricePath=PricePath("keyframes", keyframes=((2040, 100.0), (2030, 100.0))))
        self.assertFalse(ok)
        self.assertTrue(any("Fuel price path" in e for e in s.solver_errors))

    def test_results_include_levelised_prices(self):
        s, ok = solve(ship_name="Tanker")
        self.assertTrue(ok)
        self.assertAlmostEqual(s.results()["LevelisedFuelPrice($/t)"], s.F8)


if __name__ == "__main__":
    unittest.main()


class TestTwinScrew(unittest.TestCase):
    TAYLOR, HOLTROP = "Taylor's Series (Legacy)", "Holtrop-Mennen (1984)"

    def _pair(self, **kw):
        out = []
        for n in (1, 2):
            s = ShipDesignSolver().set_inputs(m_NumProps=n, **kw)
            s.ignspd = s.ignpth = True
            self.assertTrue(s.solve(), s.solver_errors)
            out.append(s)
        return out

    def test_single_screw_reports_legacy_factors(self):
        s, ok = solve(ship_name="Tanker")
        self.assertTrue(ok)
        self.assertEqual(s.n_props, 1)
        self.assertEqual(s.prop_eta_r, 1.0)
        w = 1.1 - 3.4 * s.C + 3.1 * s.C ** 1.9
        self.assertAlmostEqual(s.prop_w, w, places=12)
        self.assertAlmostEqual(s.prop_t, 0.6 * w, places=12)

    def test_twin_factors_follow_holtrop_1984(self):
        for method in (self.TAYLOR, self.HOLTROP):
            single, twin = self._pair(ship_name="Tanker", resistance_method=method)
            terms = twin._holtrop_terms()
            cv = terms["one_plus_k1"] * terms["C_F"] + terms["C_A"]
            d_ratio = twin.prop_D / math.sqrt(twin.B * twin.T)
            self.assertAlmostEqual(twin.prop_w, 0.3095 * twin.C + 10 * cv * twin.C - 0.23 * d_ratio, places=9)
            self.assertAlmostEqual(twin.prop_t, 0.325 * twin.C - 0.1885 * d_ratio, places=9)
            eta_r = 0.9737 + 0.111 * (terms["C_P"] - 0.0225 * terms["lcb"]) - 0.06325 * twin.prop_PD
            self.assertAlmostEqual(twin.prop_eta_r, eta_r, places=9)
            self.assertAlmostEqual(twin.Q, twin.prop_eta_o * twin.prop_eta_h * eta_r, places=12)
            self.assertLess(twin.prop_eta_h, single.prop_eta_h, method)
            self.assertGreater(twin.prop_eta_o, single.prop_eta_o, method)

    def test_twin_thrust_split_between_propellers(self):
        single, twin = self._pair(ship_name="Tanker")
        total = 0.7461 * twin.P / (0.515 * twin.V * (1.0 - twin.prop_t))
        self.assertAlmostEqual(twin.prop_thrust_each_kN, total / 2, places=6)

    def test_twin_appendage_drag(self):
        # Holtrop: native appendage component grows; Taylor: an increment is added.
        single, twin = self._pair(ship_name="Tanker", resistance_method=self.HOLTROP)
        self.assertGreater(twin.resistance_components["appendage"], single.resistance_components["appendage"])
        single, twin = self._pair(ship_name="Tanker", resistance_method=self.TAYLOR)
        self.assertEqual(single.twin_app_extra_kN, 0.0)
        self.assertGreater(twin.twin_app_extra_kN, 0.0)

    def test_twin_diesel_machinery_mass_and_cost(self):
        single, twin = self._pair(ship_name="Tanker")
        p2, n1 = twin.P2, twin.N1
        k3 = 0.59
        engines = 2 * (9.38 * ((p2 / 2) / n1) ** 0.84 + k3 * (p2 / 2) ** 0.7)
        shafting = 0.5 * p2 * 0.7457 * twin.m_ShaftMassPerKW / 1000.0
        self.assertAlmostEqual(twin.M_shafting, shafting, places=9)
        self.assertAlmostEqual(twin.M3, engines + shafting, places=6)
        engines_cost = 2 * (twin.m_S5_Machinery1 + twin.m_S6_Machinery2) * (twin.P1 / 2) ** 0.82
        self.assertAlmostEqual(twin.cost_machinery_M * 1e6, engines_cost + twin.cost_shafting, places=2)
        self.assertGreater(twin.Rf, single.Rf)

    def test_twin_nuclear_keeps_one_reactor(self):
        single, twin = self._pair(ship_name="Tanker", engine_name="Nuclear SMR", m_Range=float("inf"))
        reactor = twin.m_Reactor_Cost_per_kW * twin.P2 * 0.7457
        self.assertAlmostEqual(twin.cost_machinery_M * 1e6, reactor + twin.cost_shafting, places=2)
        self.assertGreater(twin.cost_shafting, 0.0)

    def test_invalid_prop_count(self):
        s, ok = solve(ship_name="Tanker", m_NumProps=3)
        self.assertFalse(ok)
        self.assertTrue(any("propellers" in e for e in s.solver_errors))
