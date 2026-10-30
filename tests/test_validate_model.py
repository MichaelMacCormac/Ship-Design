"""Tests for validate_model.py, fit_basis.py and the Auto-RPM / crash-guard
solver options they rely on.

Run from the repository root:
    python -m unittest discover tests
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import fit_basis  # noqa: E402
import ship_config  # noqa: E402
import ship_database as sdb  # noqa: E402
import validate_model as vm  # noqa: E402
from ship_solver import ShipDesignSolver  # noqa: E402

CLEAN = os.path.join(ROOT, "data", "ships_clean.csv")


def clean_row(**kw):
    base = {"ship_id": "x", "boat_name": "TEST", "tool_type": "Tanker", "split": "validate",
            "delivery_year": "2020", "LOA_m": "", "B_m": "", "D_m": "", "T_m": "", "T_kind": "unknown",
            "DWT": "", "speed_kn": "", "power_kW": "", "rpm": "", "flags": ""}
    base.update({k: str(v) for k, v in kw.items()})
    return base


class TestAutoRPMAndGuard(unittest.TestCase):
    def _solve(self, **kw):
        s = ShipDesignSolver().set_inputs(**kw)
        s.ignspd = s.ignpth = True
        return s, s.solve()

    def test_default_is_original_behaviour(self):
        s, ok = self._solve(ship_name="Tanker")
        self.assertTrue(ok)
        self.assertFalse(s.m_AutoRPM)
        self.assertFalse(s.rpm_adjusted)
        self.assertAlmostEqual(s.L1, 207.34300858940713, places=9)   # unchanged reference

    def test_passing_ship_identical_with_auto_rpm(self):
        a, _ = self._solve(ship_name="Tanker")
        b, _ = self._solve(ship_name="Tanker", m_AutoRPM=True)
        self.assertEqual((a.L1, a.B, a.T, a.P2, a.Rf), (b.L1, b.B, b.T, b.P2, b.Rf))

    def test_pitch_failure_solves_with_auto_rpm(self):
        off, ok_off = self._solve(ship_name="Tanker", m_Weight=100000.0, m_Speed=15.1, m_Econom=False)
        on, ok_on = self._solve(ship_name="Tanker", m_Weight=100000.0, m_Speed=15.1, m_Econom=False,
                                m_AutoRPM=True)
        self.assertFalse(ok_off)
        self.assertEqual(off.Kpwrerr % off.PITCH_HIGH, 0)
        self.assertTrue(ok_on)
        self.assertTrue(on.rpm_adjusted)
        self.assertLess(on.rpm_final, on.rpm_initial)
        self.assertTrue(0.5 <= on.prop_PD <= 1.4)

    def test_auto_rpm_restores_ignpth(self):
        s = ShipDesignSolver().set_inputs(ship_name="Tanker", m_AutoRPM=True)
        s.ignpth = False
        s.solve()
        self.assertFalse(s.ignpth)

    def test_complex_result_is_reported_not_raised(self):
        s = ShipDesignSolver()

        def boom():
            raise TypeError("'>=' not supported between instances of 'float' and 'complex'")
        s._solve_once = boom
        self.assertFalse(s.solve())
        self.assertTrue(any("Numerical failure" in e for e in s.solver_errors))

    def test_other_type_errors_still_raise(self):
        s = ShipDesignSolver()

        def boom():
            raise TypeError("something else")
        s._solve_once = boom
        with self.assertRaises(TypeError):
            s.solve()


class TestValidationHelpers(unittest.TestCase):
    def test_metrics(self):
        m = vm.metrics([110, 90, 100], [100, 100, 100])
        self.assertEqual(m["n"], 3)
        self.assertAlmostEqual(m["bias_pct"], 0.0)
        self.assertAlmostEqual(m["mape_pct"], 20 / 3)
        self.assertAlmostEqual(m["rmse"], math.sqrt(200 / 3))
        m = vm.metrics([1, 2, 3], [1, 2, 3])
        self.assertEqual((m["r2"], m["mape_pct"]), (1.0, 0.0))
        self.assertTrue(math.isnan(vm.metrics([], [])["bias_pct"]))

    def test_flagged_field_excluded(self):
        r = clean_row(B_m="32.2", T_m="12", D_m="11", flags="T>=D")
        self.assertEqual(sdb.field_value(r, "B_m"), 32.2)
        self.assertIsNone(sdb.field_value(r, "T_m"))
        self.assertIsNone(sdb.field_value(r, "D_m"))

    def test_lbp_ratio_by_type(self):
        self.assertAlmostEqual(sdb.lbp(clean_row(LOA_m="200", tool_type="Tanker")), 194.0)
        self.assertAlmostEqual(sdb.lbp(clean_row(LOA_m="200", tool_type="Container Ship")), 190.0)
        self.assertAlmostEqual(sdb.lbp(clean_row(LOA_m="200", tool_type="Tanker"), +0.01), 200 * 0.97 * 1.01)
        self.assertEqual(sdb.lbp(clean_row(LOA_m="200", flags="length_is_lbp")), 200.0)

    def test_dwt_matching_converges(self):
        r = clean_row(DWT="80000", speed_kn="14.5", tool_type="Bulk carrier")
        res = vm.solve_ship(r, vm.TAYLOR, vm.LEGACY, True)
        self.assertTrue(res["ok"], res["reason"])
        self.assertLessEqual(abs(res["W5"] - 80000) / 80000, vm.DWT_TOL)
        self.assertGreater(res["W5"], res["cargo_DW"])

    def test_failure_reason_reported(self):
        r = clean_row(DWT="100000", speed_kn="15.1", tool_type="Tanker")
        res = vm.solve_ship(r, vm.TAYLOR, vm.LEGACY, False)
        self.assertFalse(res["ok"])
        self.assertIn("pitch", res["reason"])

    def test_summarise_counts(self):
        rows = [clean_row(DWT="80000", speed_kn="14.5", tool_type="Bulk carrier", LOA_m="229", B_m="32.26"),
                clean_row(DWT="100000", speed_kn="15.1", tool_type="Tanker", LOA_m="250", B_m="44")]
        results = vm.run_validation(rows, [(vm.TAYLOR, vm.LEGACY, False), (vm.TAYLOR, vm.LEGACY, True)])
        table = vm.summarise(results)
        allrow = [m for m in table if m["tool_type"] == "All" and m["comparison"] == "Lbp"]
        self.assertEqual([m["attempted"] for m in allrow], [2, 2])
        off, on = [m["solved"] for m in allrow]
        self.assertEqual(on, 2)          # both solve with Auto-RPM
        self.assertLessEqual(off, on)    # the original behaviour solves no more


class TestFitBasis(unittest.TestCase):
    def test_linfit_recovers_coefficients(self):
        x = np.linspace(10, 50, 60)
        a, b, r2, n = fit_basis.linfit(x, 3.0 + 2.5 * x)
        self.assertAlmostEqual(a, 3.0, places=9)
        self.assertAlmostEqual(b, 2.5, places=9)
        self.assertAlmostEqual(r2, 1.0)
        self.assertEqual(n, 60)

    def test_gates(self):
        self.assertEqual(fit_basis.gated(1.0, 2.0, 0.9, 40), (1.0, 2.0))
        self.assertEqual(fit_basis.gated(1.0, 2.0, 0.4, 40), (None, None))   # R2 gate
        self.assertEqual(fit_basis.gated(1.0, 2.0, 0.9, 20), (None, None))   # n gate

    def test_fit_type_on_synthetic_ships(self):
        rng = np.random.default_rng(0)
        rows = []
        for dwt in rng.uniform(20000, 300000, 50):
            lbp = 20.0 + 4.5 * dwt ** (1 / 3)
            loa = lbp / 0.97
            b = 0.18 * lbp - 1.0
            d = 0.09 * lbp + 2.0
            t = 0.75 * d - 1.5
            rows.append(clean_row(split="fit", LOA_m=loa, B_m=b, D_m=d, T_m=t, DWT=dwt))
        coefs, stats = fit_basis.fit_type(rows)
        self.assertAlmostEqual(coefs["L_a"], 20.0, places=4)
        self.assertAlmostEqual(coefs["L_b"], 4.5, places=6)
        self.assertAlmostEqual(coefs["LB_m"], 0.18, places=6)
        self.assertAlmostEqual(coefs["DT_c"], -1.5, places=4)
        self.assertEqual(coefs["L_c"], 1.0)

    def test_basis_loader(self):
        before = dict(ship_config.EmpiricalBasisConfig.DATA)
        legacy = json.dumps(before["Legacy (Watson/Gilfillan 1977)"], sort_keys=True)
        old_japan = json.dumps(before["Japan Dataset (2020s)"], sort_keys=True)
        self.assertIsNone(ship_config.load_fitted_basis(os.path.join(tempfile.mkdtemp(), "missing.json")))
        path = os.path.join(tempfile.mkdtemp(), "b.json")
        with open(path, "w") as f:
            json.dump({"basis_name": "Test basis", "types": {"Tanker": {"L_a": 1.0, "L_b": 5.0, "L_c": 1.0}}}, f)
        try:
            self.assertEqual(ship_config.load_fitted_basis(path), "Test basis")
            self.assertEqual(ship_config.EmpiricalBasisConfig.get("Test basis", "Tanker")["L_b"], 5.0)
            self.assertIsNone(ship_config.EmpiricalBasisConfig.get("Test basis", "Tanker")["LB_m"])
        finally:
            ship_config.EmpiricalBasisConfig.DATA.pop("Test basis", None)
        after = ship_config.EmpiricalBasisConfig.DATA
        self.assertEqual(json.dumps(after["Legacy (Watson/Gilfillan 1977)"], sort_keys=True), legacy)
        self.assertEqual(json.dumps(after["Japan Dataset (2020s)"], sort_keys=True), old_japan)
        self.assertEqual(ShipDesignSolver().empirical_basis, "Legacy (Watson/Gilfillan 1977)")


class TestAllModulesCompile(unittest.TestCase):
    def test_every_module_compiles(self):
        """Catches syntax errors in modules the unit tests don't import
        (e.g. the Qt GUI), without importing Qt here."""
        import py_compile
        for name in sorted(os.listdir(ROOT)):
            if name.endswith(".py"):
                py_compile.compile(os.path.join(ROOT, name), doraise=True)


@unittest.skipUnless(os.path.exists(CLEAN), "clean dataset not present")
class TestCLI(unittest.TestCase):
    def test_quick_run_end_to_end(self):
        out = tempfile.mkdtemp()
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "validate_model.py"), "--quick", "12",
                               "--out", out, "--data", CLEAN], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        for name in ("metrics.csv", "validation_report.md", "errors_by_type.png"):
            self.assertTrue(os.path.exists(os.path.join(out, name)), name)
        self.assertTrue(any(n.startswith("results_") for n in os.listdir(out)))


if __name__ == "__main__":
    unittest.main()
