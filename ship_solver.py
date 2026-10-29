"""GUI-free ship design solver.

ShipDesignSolver holds every input, intermediate and result of a design run
and the physics/economics routines that act on them.  It imports nothing
from Qt, so it can run headless (batch sweeps, Monte Carlo, tests):

    from ship_solver import ShipDesignSolver
    s = ShipDesignSolver()
    s.set_inputs(ship_name="Tanker", engine_name="Direct diesel", m_Weight=50000.0)
    if s.solve():
        print(s.results()["RFR"])

ShipDesViewWidget inherits from this class, copies its widget values onto
these attributes (_update_ui_to_data) and overrides the reporting hooks
(_show_error, _log, _warn, _debug_*, _focus_field) with Qt dialogs.
"""
import math

import numpy as np

from economics import CashFlowInputs, build_cash_flow
from ship_config import FuelConfig, ShipConfig, ResistanceMethodConfig, EmpiricalBasisConfig


class ShipDesignSolver:
    def __init__(self):

        self.NOT_CONVERGE = 2
        self.SPEED_LOW = 3 #
        self.SPEED_HIGH = 5 #
        self.PITCH_LOW = 7 #
        self.PITCH_HIGH = 11 #
        self.RESISTANCE_OUT_OF_RANGE = 13 # Selected resistance method outside its valid Fn/CB range

        self.m_Econom = True #
        self.m_VolumeLimit = True
        self.m_CustomDensity = -1.0
        self.m_Block = 0.818525 #
        self.m_Breadth = 31.898924 #
        self.m_Depth = 15.358741 #
        self.m_Draught = 11.725275 #
        self.m_Erpm = 120.0 #
        self.m_Fuel = 625.0 #
        self.m_LHV = 42.7
        self.m_Interest = 10.0 #
        self.m_Length = 207.34301 #
        self.m_Prpm = 120.0 #
        self.m_Range = 12000.0 #
        self.m_Repay = 15.0 #
        self.m_ShipLife = 15.0 # Operating years for the cash flow (may differ from loan term)        
        self.m_Results = "Press the Calculate button\r\nto find ship dimensions ..." #
        self.m_Seadays = 340.0 #
        self.m_Speed = 15.0 #
        self.m_Voyages = 17.0 #
        self.m_Weight = 50000.0 #
        self.m_Cargo = 0  # 0=Cargo, 1=Ship, 2=TEU
        self.m_Error = 0.001 #
        self.m_Lbratio = False #
        self.m_Btratio = False #
        self.m_Cbvalue = False #
        self.m_BtratioV = 1.0e-6 * int(1.0e6 * self.m_Breadth / (self.m_Draught if self.m_Draught != 0 else 1e-9) + 0.5) #
        self.m_CbvalueV = self.m_Block #
        self.m_LbratioV = 1.0e-6 * int(1.0e6 * self.m_Length / (self.m_Breadth if self.m_Breadth != 0 else 1e-9) + 0.5) #
        self.m_Bvalue = False #
        self.m_BvalueV = self.m_Breadth #
        self.m_PdtratioV = 0.6 #
        self.m_Pdtratio = True #
        self.m_Append = False #
        self.m_TEU = 3000.0
        self.m_TEU_Avg_Weight = 14.0
        self.m_Reactor_Cost_per_kW = 9000.0 # ($/kW)
        self.m_Core_Life = 20.0             # (Years)
        self.m_Decom_Cost = 200.0           # (M$)
        self.m_CarbonTax = 85.0 # Current EU ETS approx price ($/tonne CO2)
        self.m_CarbonIntensity = 3.114 # Tonnes CO2 per Tonne Diesel fuel
        self.m_Power_Factor = 1.0 # Defaults to 100% (Flat profile)
        self.m_conventional_Range = self.m_Range # Store the default

        # ----------------------------------------------------------------
        # Sensitivity / retrofit knobs (added for chapter 5 analysis).
        # All default to "no effect"; UI exposes them via the
        # "Sensitivity & Retrofit" panel.
        # ----------------------------------------------------------------
        self.m_MethaneSlip = 0.0       # % of LNG fuel mass slipped as CH4
        self.m_GWP_methane = 30.0      # IPCC AR6 GWP100 for CH4 vs CO2
        self.m_ResUncertPct = 0.0      # Global Pe multiplier (Holtrop sensitivity)
        self.m_RetrofitMode = False    # If True, machinery cost is discounted
        self.m_RetrofitFactor = 0.40   # Default machinery cost discount

        # Per-run override of fuel_data["Carbon"] (tCO2 / t fuel).  None
        # means "use the FuelConfig value".  Set by the Battle Mode dialog
        # so each engine can be evaluated against a user-tweaked carbon
        # factor (e.g. green H2 = 0, grey methanol = 1.375, etc.) without
        # mutating the shared FuelConfig.DATA table.
        self.m_CarbonOverride = None

        # Outputs filled by _solve_volume_limit / _get_volume_status — exposed
        # to the CSV writer and the result dropdowns.
        self.vol_expansion_iters = 0
        self.last_vol_breakdown = None  # (cargo, fuel, mach, stores, ratio)
        self.attained_cii = 0.0

        self.Kcases = 0 #
        self.Ketype = 1 #
        self.Kstype = 1 #
        self.Kpwrerr = 1 #
        self.CalculatedOk = False #
        self.Ksaved = True #
        self.design_mode = 0 # 0=Cargo, 1=Ship, 2=TEU
        self.target_teu = 0
        self.Lb01=4.0; self.Lb02=0.025; self.Lb03=30.0; self.Lb04=6.5; self.Lb05=130.0
        self.Cb11=0.93; self.Cb12=0.110; self.Cb13=1.23; self.Cb14=0.395; self.Cb15=1.0 #
        self.Cb21=0.93; self.Cb22=0.110; self.Cb23=1.23; self.Cb24=0.395; self.Cb25=1.0 #
        self.Cb31=1.23; self.Cb32=0.395; self.Cb33=1.23; self.Cb34=0.395; self.Cb35=1.0 #
        self.L111=0.0; self.L112=5.0; self.L113=0.8; self.L121=0.0; self.L122=5.0; self.L123=0.8 #
        self.L131=0.0; self.L132=5.0; self.L133=0.7 #
        self.ignspd = False #
        self.ignpth = False #
        self.dbgmd = False #
        self.maxit = 1000 #

        # ------------------------------------------------------------------
        # Resistance-method state
        # ------------------------------------------------------------------
        # The currently-active resistance method's display name. Mirrors the
        # combo_resistance_method dropdown but cached here so that headless
        # callers (range/battle modes) can read it without touching the UI.
        self.resistance_method = "Taylor's Series (Legacy)"

        # ------------------------------------------------------------------
        # Empirical basis state
        # ------------------------------------------------------------------
        # Selects between the legacy Watson/Gilfillan dimensional regressions
        # and the regressions fitted to the Japanese newsletter dataset.
        # Defaults to legacy so existing behaviour is preserved.  Mirrors the
        # combo_basis dropdown but cached here so range/battle modes can
        # read it without touching the UI.
        self.empirical_basis = "Legacy (Watson/Gilfillan 1977)"

        # Component breakdown filled by whichever _calc_pe_<method>() runs.
        # Keys: 'friction', 'wave', 'appendage', 'air', 'bulb', 'transom',
        # 'correlation', 'total'. Values are kN, or None if the active method
        # did not natively compute that component (Taylor case - the back-fit
        # in _apply_resistance_breakdown handles those).
        self.resistance_components = {}

        # Holtrop hull-form parameters. None = "auto-derive in _calc_pe_holtrop".
        # Filling any of these via the UI overrides the auto-derivation for
        # that single parameter only.
        self.lcb_pct = None       # LCB as percent of L from midships, +fwd
        self.iE_deg = None        # Half-angle of entrance, degrees
        self.cm = None            # Midship section coefficient
        self.cwp = None           # Waterplane coefficient
        self.has_bulb = False
        self.abt = 0.0            # Bulb cross-section area at FP, m^2
        self.hb = 0.0             # Bulb centroid height above keel, m
        self.has_transom = False
        self.at = 0.0             # Immersed transom area, m^2
        self.cstern = 0           # Afterbody form: -25, 0, +10
        self.s_app_override = None  # Appendage wetted area, m^2 (None = 4% of S)


        self.L1 = 0.0; self.B = 0.0; self.D = 0.0; self.T = 0.0; self.C = 0.0
        self.R = 0.0; self.V = 0.0; self.N1 = 0.0; self.N2 = 0.0; self.V7 = 0.0
        self.D1 = 0.0; self.F8 = 0.0; self.I = 0.0; self.N = 0; self.ship_life = 0
        self.Pdt = 0.0; self.W = 0.0; self.E = 0.0
        self.W1 = 0.0; self.M = 0.0; self.M1 = 0.0; self.M2 = 0.0; self.M3 = 0.0
        self.W5 = 0.0; self.P = 0.0; self.P1 = 0.0; self.P2 = 0.0
        self.Q = 0.0; self.Q1 = 0.0; self.Q2 = 0.0; self.Rf = 0.0
        self.S = 0.0; self.F0 = 0.0; self.F5 = 0.0; self.F9 = 0.0
        self.G6 = 0.0; self.H1 = 0.0; self.H7 = 0.0; self.Kcount = 0

        self._V1 = (0.0, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8)
        self._A6 = (0.0, 0.2461132, -0.4579327, -0.1716513, 0.4350189,
                    3.681142e-02, -5.782276e-02, -3.677581e-02, 8.540912e-02)
        self._B6 = (0.0, 0.5545783, -4.203888e-02, -0.7284746, 0.0,
                    0.1089609, -5.997375e-02, -0.1277425)
        self._C6 = (0.0, 8.077402e-02, 0.6003515, 0.0, 0.0, 0.0884936, 6.762783e-02)
        self._D6 = (0.0, -0.2862038, 0.0, 0.0, 0.0, -2.004734e-02)
        self._X1 = (
            0.0, # Index 0 (not used)
            -0.7750, 0.2107, 0.0872, 0.0900, 0.0116, 0.0883, 0.0081, 0.0631, # 1-8
            0.0429, -0.0249, -0.0124, 0.0236, -0.0301, 0.0877, -0.1243, -0.0269, # 9-16
            -0.7612, 0.2223, 0.0911, 0.0768, 0.0354, 0.0842, 0.0151, 0.0644, # 17-24
            0.0650, -0.0187, 0.0292, -0.0245, -0.0442, 0.1124, -0.1341, -0.0006, # 25-32
            -0.7336, 0.2339, 0.0964, 0.0701, 0.0210, 0.0939, 0.0177, 0.0656, # 33-40
            0.1062, -0.0270, 0.0647, -0.0776, -0.0537, 0.1151, -0.0775, 0.1145, # 41-48
            -0.6836, 0.2765, 0.0995, 0.0856, 0.0496, 0.1270, 0.0175, 0.0957, # 49-56
            0.1463, -0.0502, 0.1629, -0.1313, -0.0863, 0.1133, 0.0355, 0.2255, # 57-64
            -0.5760, 0.3161, 0.1108, 0.1563, 0.2020, 0.1790, 0.0170, 0.1193, # 65-72
            0.1706, -0.0699, 0.3574, -0.3034, -0.0944, 0.0839, 0.1715, 0.2006, # 73-80
            -0.3290, 0.3562, 0.1134, 0.4449, 0.3557, 0.1272, 0.0066, 0.1415, # 81-88
            0.1238, -0.0051, 0.2882, -0.2508, -0.0115, -0.0156, 0.2569, 0.0138, # 89-96
            -0.0384, 0.4550, 0.0661, 1.0124, 0.2985, 0.0930, 0.0118, 0.5080, # 97-104
            0.2203, -0.0514, 0.2110, 0.0486, 0.0046, -0.1433, 0.2680, 0.2283 # 105-112
        )
        
        self._E5=0.2; self._Y1=0.5; self._Y2=0.0
        self._L2 = (30, 40, 60, 80, 100, 120, 140, 160, 180, 200,
                    220, 240, 260, 280, 300, 320, 340, 360)
        self._F1 = (250, 334, 573, 841, 1135, 1459, 1803, 2126, 2393, 2612,
                    2792, 2946, 3072, 3176, 3262, 3331, 3382, 3425)
        self._F2 = (250, 334, 573, 887, 1271, 1690, 2109, 2520, 2915, 3264,
                    3586, 3880, 4152, 4397, 4630, 4844, 5055, 5260)

        self.m_S1_Steel1 = 22000.0   # Steel cost param 1
        self.m_S2_Steel2 = 3800.0    # Steel cost param 2
        self.m_S3_Outfit1 = 240000.0 # Outfit cost param 1
        self.m_S4_Outfit2 = 50000.0  # Outfit cost param 2
        self.m_S5_Machinery1 = 9500.0  # Machinery cost param 1 (conventional)
        self.m_S6_Machinery2 = 21000.0 # Machinery cost param 2 (conventional)
        self.m_H2_Crew = 3000000.0    # Annual crew cost
        # Maintenance percentage applied to HULL + OUTFIT only (S8 + S9).
        # Machinery maintenance is now fuel-specific and lives in
        # FuelConfig["MaintenancePct"] (applied to S0 in _cost). This split
        # fixes the prior bug where a flat 4% on total build cost made
        # nuclear OPEX an order of magnitude too high — reactor capex
        # dominates S0 but real nuclear plant O&M is ~1-2% of capex/yr,
        # not 4%, and core replacement is already amortised into H7.
        self.m_H3_Maint_Percent = 0.04
        self.m_H4_Port = 1500000.0   # Annual port/admin
        self.m_H5_Stores = 650000.0  # Annual stores
        self.m_H6_Overhead = 1500000.0 # Annual overhead
        self.m_H8_Other = 0.0       # Annual other

        # ----------------------------------------------------------------
        # Selections that used to be read straight off widgets inside the
        # physics. The GUI copies them across in _update_ui_to_data;
        # headless callers set them directly (or via set_inputs).
        # ----------------------------------------------------------------
        self.ship_name = "Tanker"            # key into ShipConfig.DATA
        self.engine_name = "Direct diesel"   # key into FuelConfig.DATA
        self.m_CarbonTaxOn = False           # apply m_CarbonTax to fuel CO2e

        # Auxiliary / cargo-cooling load. Values are passed to float() at
        # use, exactly as the widget text used to be, so bad input fails
        # the same way it always did.
        self.m_AuxEnabled = False
        self.m_AuxMode = "None"              # "None" / "Reefer Plugs (Container)" / "Insulated Hold (Bulk)"
        self.m_AuxBase = 250.0               # hotel load, kW
        self.m_AuxP1 = 10.0                  # % of TEU or volume cooled
        self.m_AuxP2 = 3.0                   # kW/TEU or kW per 1000 m3
        self.m_AuxPrem = 0.0                 # reefer freight premium per unit

        # Energy-saving devices
        self.m_ALS = False                   # air lubrication
        self.m_ALSEff = 5.0                  # % friction reduction on flat bottom
        self.m_Wind = False                  # wind assist
        self.m_WindSav = 10.0                # % of effective power

        # Reporting sinks used by the headless hook defaults below.
        self.solver_errors = []
        self.solver_warnings = []
        self.solver_log = []

    # ------------------------------------------------------------------
    # Reporting hooks. Headless defaults just record; ShipDesViewWidget
    # overrides them with message boxes and the results text box.
    # ------------------------------------------------------------------
    def _show_error(self, message, title="Input error"):
        self.solver_errors.append(f"{title}: {message}")

    def _warn(self, message):
        self.solver_warnings.append(message)

    def _log(self, message):
        self.solver_log.append(message)

    def _focus_field(self, widget_name):
        """Point the user at the offending input (no-op headless)."""

    def _debug_info(self, message, title):
        """Debug-mode information popup (no-op headless)."""

    def _show_debug_msg(self, message, title="Info. from OnButtonCal in debug mode"):
        """Debug-mode continue prompt; True = keep iterating in debug mode."""
        return True

    def _debug_stop(self, message):
        """Debug run is hopeless - leave debug mode."""
        self.dbgmd = False

    # ------------------------------------------------------------------
    # Headless helpers
    # ------------------------------------------------------------------
    def set_inputs(self, **inputs):
        """Set input attributes by name. Unknown names raise, so a typo in a
        batch script fails loudly instead of being silently ignored."""
        for name, value in inputs.items():
            if not hasattr(self, name):
                raise AttributeError(f"Unknown solver input: {name!r}")
            setattr(self, name, value)
        return self

    def _sync_type_ids(self):
        """Derive Kstype/Ketype (1-based) from ship_name/engine_name, using the
        same DATA ordering the GUI combo boxes are populated from. Unknown
        names give 0, which _check_data rejects."""
        ships = list(ShipConfig.DATA)
        engines = list(FuelConfig.DATA)
        self.Kstype = ships.index(self.ship_name) + 1 if self.ship_name in ships else 0
        self.Ketype = engines.index(self.engine_name) + 1 if self.engine_name in engines else 0

    def results(self):
        """Key outputs of the last solve(), keyed like the GUI result dropdowns.
        Economic entries are NaN when economics are off; everything is NaN
        when the last solve() failed."""
        keys = ["RFR($/tonne or $/TEU)", "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB",
                "Displacement(t)", "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)",
                "InstalledPower(kW)", "BuildCost(M$)", "AnnualFuelCost(M$)",
                "AnnualCarbonTax(M$)", "AnnualisedCAPEX(M$)", "AnnualOPEX(M$)",
                "EEDI(gCO2/t.nm)", "AttainedCII", "FuelVol%Hull", "VolCargo(m3)",
                "VolFuel(m3)", "VolMachinery(m3)", "VolStores(m3)", "VolUtilisation%"]
        if not self.CalculatedOk:
            return {k: np.nan for k in keys}
        econ = bool(self.m_Econom)
        is_teu = (self.design_mode == 2)

        def _econ(v):
            return v if econ else np.nan

        try:
            fd = FuelConfig.get(self.engine_name)
            lhv = self.m_LHV if self.m_LHV > 0 else 42.7
            sfc_g_kwh = 3600.0 / (lhv * fd["Efficiency"])
            cap = self.W1 if self.W1 > 1.0 else 1.0
            cf = fd["Carbon"]
            if self.engine_name == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
            eedi = (0.75 * self.P2 * 0.7457 * cf * sfc_g_kwh) / (cap * self.V) if self.V > 0 else np.nan
        except Exception:
            eedi = np.nan

        return {
            "RFR($/tonne or $/TEU)": _econ(self.Rf * self.m_TEU_Avg_Weight if is_teu else self.Rf),
            "Lbp(m)": self.L1, "B(m)": self.B, "D(m)": self.D, "T(m)": self.T, "CB": self.C,
            "Displacement(t)": self.M, "CargoDW(t)": self.W1, "TotalDW(t)": self.W5,
            "ServicePower(kW)": 0.7457 * self.P1, "InstalledPower(kW)": 0.7457 * self.P2,
            "BuildCost(M$)": _econ(self.S),
            "AnnualFuelCost(M$)": _econ(self.H7 / 1e6),
            "AnnualCarbonTax(M$)": _econ(getattr(self, 'annual_carbon_tax', 0.0) / 1e6),
            "AnnualisedCAPEX(M$)": _econ(getattr(self, 'H1', 0.0) / 1e6),
            "AnnualOPEX(M$)": _econ(getattr(self, 'annual_opex', 0.0) / 1e6),
            "EEDI(gCO2/t.nm)": eedi,
            "AttainedCII": getattr(self, 'attained_cii', np.nan),
            "FuelVol%Hull": getattr(self, 'fuel_vol_pct_hull', np.nan),
            "VolCargo(m3)": getattr(self, 'vol_cargo', np.nan),
            "VolFuel(m3)": getattr(self, 'vol_fuel', np.nan),
            "VolMachinery(m3)": getattr(self, 'vol_mach', np.nan),
            "VolStores(m3)": getattr(self, 'vol_stores', np.nan),
            "VolUtilisation%": getattr(self, 'vol_utilisation_pct', np.nan),
        }

    def solve(self):
        """Run one design calculation from the current m_* inputs.

        The calculation core of the old OnButtonCal: resolve the design
        mode, iterate L1 until the cargo deadweight converges, run the
        volume limiter, re-balance the propeller, then cost the ship.
        Returns True and sets CalculatedOk on success; on failure returns
        False after reporting through _show_error / _log.
        """

        keys_to_reset = ['M_aux_mach', 'M_aux_outfit', 'W_aux_fuel',
                         'aux_cost_annual', 'calculated_fuel_mass', 'raw_fuel_mass',
                         '_esd_applied']
        for k in keys_to_reset:
            if hasattr(self, k):
                delattr(self, k)

        self._sync_type_ids()
        self.design_mode = self.m_Cargo # 0=Cargo, 1=Ship, 2=TEU
        self.target_teu = 0

        if self.design_mode == 2:
            self.W = self.m_TEU * self.m_TEU_Avg_Weight
            self.target_teu = self.m_TEU

            self.E = 0.01 * self.W * self.m_Error

            self.m_Cargo = 0

        elif self.design_mode == 0:
            self.W = self.m_Weight
            self.E = 0.01 * self.W * self.m_Error

        if self.Ketype == 1:
            self.m_Prpm = self.m_Erpm

        self._initdata(0)
        self.CalculatedOk = False

        if not self._check_data():
            self.m_Cargo = self.design_mode
            return False

        if self.m_Cargo == 0:
            W1 = self.W + 2.0 * self.E + 10.0
            Z = 0; Y = 1; J = 10.0; L3 = 0.0; W2 = 0.0
            self.Kcount = 0

            # ---- Active empirical basis dispatch -----------------------
            # Resolve the basis + ship-type once per OnButtonCal call.  The
            # helpers below close over (_basis_active, _coefs) and are
            # consumed both by the initial-guess block immediately following
            # and by the per-ship-type branches inside the convergence loop.
            #
            # Each helper returns None when the basis is Legacy OR when the
            # specific coefficient pair is None (low-R^2 fit, or ship type
            # not present in the chosen basis).  Callers treat None as
            # "use the existing legacy formula for this dimension".
            _kstype_to_name = {v["ID"]: k for k, v in ShipConfig.DATA.items()}
            _ship_name   = _kstype_to_name.get(self.Kstype, "Tanker")
            _basis       = getattr(self, "empirical_basis",
                                   "Legacy (Watson/Gilfillan 1977)")
            _coefs       = EmpiricalBasisConfig.get(_basis, _ship_name)
            _basis_active = _basis != "Legacy (Watson/Gilfillan 1977)"

            def _basis_L_initial(W_val):
                if (_basis_active and _coefs.get("L_a") is not None
                        and _coefs.get("L_b") is not None):
                    return (_coefs["L_a"]
                            + _coefs["L_b"] * ((W_val / _coefs["L_c"]) ** (1/3)))
                return None

            def _basis_B(L_val):
                if (_basis_active and _coefs.get("LB_m") is not None
                        and _coefs.get("LB_c") is not None):
                    return _coefs["LB_m"] * L_val + _coefs["LB_c"]
                return None

            def _basis_D(L_val):
                if (_basis_active and _coefs.get("LD_m") is not None
                        and _coefs.get("LD_c") is not None):
                    return _coefs["LD_m"] * L_val + _coefs["LD_c"]
                return None

            def _basis_T(D_val):
                if (_basis_active and _coefs.get("DT_m") is not None
                        and _coefs.get("DT_c") is not None):
                    return _coefs["DT_m"] * D_val + _coefs["DT_c"]
                return None

            # ---- Initial L1 guess --------------------------------------
            # Use basis when active+available, else fall back to the
            # user-tweakable legacy self.L1xx parameters (Watson/Gilfillan).
            _L_basis = _basis_L_initial(self.W)
            if _L_basis is not None:
                self.L1 = _L_basis
            elif self.Kstype == 1:
                self.L1 = self.L111 + self.L112 * ((self.W / self.L113) ** (1/3))
            elif self.Kstype == 2:
                self.L1 = self.L121 + self.L122 * ((self.W / self.L123) ** (1/3))
            else:
                self.L1 = self.L131 + self.L132 * ((self.W / self.L133) ** (1/3))

            if self.dbgmd:
                msg = f"Initial ship length: L1={self.L1:7.2f}\r\n"
                msg += f"and the target DW = {self.W:8.2f}\r\n"
                self._debug_info(msg, "Info. from OnButtonCal in debug mode")

            while self.Kcount < 500 and abs(self.W - W1) > self.E:
                self.Kcount += 1

                if self.Kcount > 1:
                    if Y != Z + 1:
                        self.L1 -= 0.5 * J; Y += 1
                    elif self.W >= W1:
                        L3 = self.L1; W2 = W1; self.L1 += J
                    else:
                        if (W1 - W2) == 0: W1 = W2 + 1e-9 # Avoid division by zero
                        L = L3 + (self.W - W2) * (self.L1 - L3) / (W1 - W2)
                        self.L1 = L; J = 0.25 * J; Y += 1; Z += 2

                if self.L1 <= 0: self.L1 = 1e-9 # Prevent negative length leading to complex numbers
                vosl = self.V / (math.sqrt(self.L1) if self.L1 > 0 else 1e-9)

                if self.Kstype == 1: # Tanker
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    elif self.m_Bvalue: self.B = self.m_BvalueV
                    else:
                        _B = _basis_B(self.L1)
                        if _B is not None:
                            self.B = _B
                        elif self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03))
                        else: self.B = self.L1 / self.Lb04
                    if self.m_Cbvalue: self.C = self.m_CbvalueV
                    else:
                        if vosl < self.Cb15: self.C = self.Cb11 - self.Cb12 * vosl
                        else: self.C = self.Cb13 - self.Cb14 * vosl
                    if self.m_Btratio:
                        self.T = self.B / self.m_BtratioV
                        self.D = self.T / 0.78
                        if not self._freeboard(): return False
                    else:
                        _D = _basis_D(self.L1)
                        self.D = _D if _D is not None else self.L1 / 13.5
                        _T = _basis_T(self.D)
                        self.T = _T if _T is not None else 0.78 * self.D
                        if not self._freeboard(): return False
                        self.T = self.D - self.F5
                elif self.Kstype == 2: # Bulk carrier
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    elif self.m_Bvalue: self.B = self.m_BvalueV
                    else:
                        _B = _basis_B(self.L1)
                        if _B is not None:
                            self.B = _B
                        elif self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03))
                        else: self.B = self.L1 / self.Lb04
                    if self.m_Cbvalue: self.C = self.m_CbvalueV
                    else:
                        if vosl < self.Cb25: self.C = self.Cb21 - self.Cb22 * vosl
                        else: self.C = self.Cb23 - self.Cb24 * vosl
                    if self.m_Btratio:
                        self.T = self.B / self.m_BtratioV
                        self.D = self.T / 0.70
                        if not self._freeboard(): return False
                    else:
                        _D = _basis_D(self.L1)
                        self.D = _D if _D is not None else self.L1 / 11.75
                        _T = _basis_T(self.D)
                        self.T = _T if _T is not None else 0.7 * self.D
                        if not self._freeboard(): return False
                        self.T = self.D - self.F5
                elif self.Kstype == 4:  # Container Ship
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    elif self.m_Bvalue: self.B = self.m_BvalueV
                    else:
                        _B = _basis_B(self.L1)
                        if _B is not None:
                            self.B = _B
                        elif self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03))
                        else: self.B = self.L1 / self.Lb04

                    # --- ADDED: Container ships need a block coefficient ---
                    if self.m_Cbvalue: self.C = self.m_CbvalueV
                    else:
                        if vosl < self.Cb35: self.C = self.Cb31 - self.Cb32 * vosl
                        else: self.C = self.Cb33 - self.Cb34 * vosl

                    # Container ships: D/L ~ 1/13.5, T/D ~ 0.72 (legacy
                    # fallbacks; the Japan-basis T(D) regression failed
                    # the R^2 reliability gate so DT is always None for
                    # container ships and the legacy 0.72 ratio applies).
                    _D = _basis_D(self.L1)
                    self.D = _D if _D is not None else self.L1 / 13.5
                    _T = _basis_T(self.D)
                    self.T = _T if _T is not None else 0.72 * self.D
                    if not self._freeboard(): return False
                    self.T = self.D - self.F5
                else: # Cargo vessel
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    elif self.m_Bvalue: self.B = self.m_BvalueV
                    else:
                        if self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03))
                        else: self.B = self.L1 / self.Lb04
                    if self.m_Cbvalue: self.C = self.m_CbvalueV
                    else:
                        if vosl < self.Cb35: self.C = self.Cb31 - self.Cb32 * vosl
                        else: self.C = self.Cb33 - self.Cb34 * vosl
                    if self.m_Btratio:
                        self.T = self.B / self.m_BtratioV; self.D = self.T / 0.7
                        if not self._freeboard(): return False
                    else:
                        self.D = (self.B - 2.74) / 1.4; self.T = 0.7 * self.D
                        if not self._freeboard(): return False

                self.M = 1.025 * self.L1 * self.B * self.T * self.C
                if not self._stability(): return False

                if not self._power():
                     return False

                if not self._mass(): return False

                W1 = self.W1

                if self.dbgmd:
                    msg = f"This is at the end of iteration {self.Kcount:3d}\r\n"
                    msg += f" The current L1={self.L1:7.2f}, B={self.B:6.2f}\r\n"
                    msg += f" T={self.T:6.2f}, CB={self.C:6.3f} and D={self.D:6.2f}.\r\n"
                    msg += f" Error code: Kpwrerr={self.Kpwrerr:3d}\r\n"
                    msg += f" The present value: DW={W1:8.2f}.\r\n"
                    msg += f" (The target DW={self.W:8.2f}).\r\n\r\n"
                    if self.Kpwrerr == 1: msg += " This iteration is all right.\r\n"
                    else: msg += " An error was detected in this iteration.\r\n"
                    if W1 <= 0.0: msg += "\r\n (This is hopeless now, please\r\n   get out of the debug mode!)\r\n"
                    if self.Kcount < 5: msg += "\r\n Continue in the debug mode?\r\n"
                    elif self.Kcount < 10: msg += "\r\n Still stay in the debug mode?\r\n"
                    else:
                        if W1 <= 0.0: msg += "\r\n  ***** Stop debugging now! *****\r\n"
                        else: msg += "\r\n Keep running in the debug mode?\r\n"
                    if W1 <= 0.0 and self.Kcount >= 10:
                        self._debug_stop(msg)
                    else:
                        if not self._show_debug_msg(msg): break


            if self.Kpwrerr != 1:
                msg = "The program tried its best but\r\n"
                msg += "calculation has failed because\r\n"
                if self.Kpwrerr % self.SPEED_LOW == 0: msg += " -- ship speed is too low!\r\n"
                if self.Kpwrerr % self.SPEED_HIGH == 0: msg += " -- ship speed is too high!\r\n"
                if self.Kpwrerr % self.PITCH_LOW == 0: msg += " -- prop. pitch out of range (|->)!\r\n"
                if self.Kpwrerr % self.PITCH_HIGH == 0: msg += " -- prop. pitch out of range (<-|)!\r\n"
                if self.Kpwrerr % self.RESISTANCE_OUT_OF_RANGE == 0:
                    msg += " -- Fn/CB outside valid range for selected resistance method!\r\n"
                self._show_error(msg, "Fatal error (Input data wrong?)")
                # Restore original mode
                self.m_Cargo = self.design_mode
                return False

            if self.Kcount >= 500:
                self._warn("Warning: Allowable error too small!")

        elif self.m_Cargo == 1:
            if not self._freeboard(): return False
            self.M = 1.025 * self.L1 * self.B * self.T * self.C
            if not self._stability(): return False
            if not self._power(): return False
            if not self._mass(): return False

        self._apply_resistance_breakdown()

        self._auxiliary()

        if not self._mass(): return False

        self.m_Cargo = self.design_mode

        self._solve_volume_limit()

        retries = 0
        while not self._power() and retries < 15:

            if self.Kpwrerr % self.PITCH_LOW == 0:
                self._log(f"[Auto-Correcting: Pitch > 1.4. Increasing RPM from {self.N2:.1f} to {self.N2*1.05:.1f}]")
                self.N2 *= 1.05
                self.N1 *= 1.05

            elif self.Kpwrerr % self.PITCH_HIGH == 0:
                self._log(f"[Auto-Correcting: Pitch < 0.5. Decreasing RPM from {self.N2:.1f} to {self.N2*0.95:.1f}]")
                self.N2 *= 0.95
                self.N1 *= 0.95

            else:
                break

            retries += 1

        if self.Kpwrerr != 1:
            self._log("\nERROR: Propeller design fundamentally failed!")
            self._log("The physics engine cannot balance the thrust required for this weight/speed.")
            self._log("Try: 1) Reducing Speed, 2) Reducing Range, or 3) Unchecking 'Prop.dia. to T ratio'.")
            return False
        self._apply_resistance_breakdown()

        if not self._mass(): return False

        self._power()

        if not self._power(): return False

        self._apply_resistance_breakdown()

        self._auxiliary()

        if not self._mass(): return False

        if self.W1 <= 0:
             self.m_Results += "\n!!! CRITICAL WARNING !!!\n"
             self.m_Results += "Auxiliary weight > Cargo Capacity.\n"
             self.m_Results += "Increase Ship Dimensions or decrease Aux Load.\n"

        if self.m_Econom:
            if not self._cost(): return False

        self.CalculatedOk = True
        self.Ksaved = False

        if self.W1 <= 0:
            warning = (
                "\r\n\r\n"
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
                "!!! DESIGN ERROR: SHIP TOO HEAVY !!!\r\n"
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
                "The weight of Fuel/Machinery exceeds the\r\n"
                "entire displacement of the ship.\r\n"
                f"Cargo Deadweight: {self.W1:.1f} tonnes\r\n"
                "\r\n"
                "This usually happens with Batteries or Hydrogen\r\n"
                "on long ranges. Reduce Range or Speed.\r\n"
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
            )
            self.m_Results = warning + self.m_Results

        if self.design_mode == 2:
            estimated_capacity = self._estimate_teu_capacity(self.L1, self.B, self.D)
            if estimated_capacity < self.target_teu:
                warning = (
                    "\r\n\r\n"
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
                    "!!! DESIGN WARNING: VOLUME-LIMITED !!!\r\n"
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
                    f"Target TEU:         {int(self.target_teu)}\r\n"
                    f"Est. Capacity:    {int(estimated_capacity)} TEU\r\n"
                    "\r\n"
                    "The calculated ship can carry the *weight*,\r\n"
                    "but does not have enough *volume* (space).\r\n"
                    "The design is not feasible as-is.\r\n"
                    "\r\n"
                    "Try one of the following:\r\n"
                    " - Increase L/B or B/T constraints.\r\n"
                    " - Manually specify a 'fuller' ship.\r\n"
                    " - Reduce avg. weight/TEU if possible.\r\n"
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\r\n"
                )
                if self.m_Append and self.Kcases > 0:
                    self.m_Results += warning
                else:
                    self.m_Results = warning + self.m_Results


        # Capture CII and volume-budget snapshots so batch callers can read
        # them via get_result_value without depending on _outvdu running first
        # or on output checkboxes being ticked.
        self._compute_cii()
        self._capture_volume_budget()
        return True

    def _check_data(self):
        """Port of Sub_checkdata"""
        num_types = len(ShipConfig.DATA)
        
        if self.Kstype < 1 or self.Kstype > num_types:
            self._show_error(f"Fatal error: Ship type {self.Kstype} unknown!", "Input error")
            return False
        num_engines = len(FuelConfig.DATA) 
        if self.Ketype < 1 or self.Ketype > num_engines:
            self._show_error(f"Fatal error: Engine type {self.Ketype} unknown!", "Input error")
            return False

        if self.m_Cargo == 0: # Cargo mode
            if self.W <= 0.0 or self.E <= 0.0:
                self._show_error("Fatal error: Cargo Weight/Error must be positive!", "Input error")
                self._focus_field("edit_weight")
                return False
        elif self.m_Cargo == 2: # TEU mode
             if self.m_TEU <= 0.0 or self.m_TEU_Avg_Weight <= 0.0:
                self._show_error("Fatal error: TEU and Avg. Weight must be positive!", "Input error")
                self._focus_field("edit_teu")
                return False
        elif self.m_Cargo == 1: # Ship dimensions mode
            if self.L1 <= 0.0 or self.B <= 0.0 or self.D <= 0.0 or self.T <= 0.0 or self.C <= 0.0:
                self._show_error("Fatal error: Ship dimensions must be positive!", "Input error")
                self._focus_field("edit_length")
                return False
            if self.C > 1.0:
                self._show_error("Fatal error: CB should be less than 1.0!", "Input error")
                self._focus_field("edit_block")
                return False
        
        if self.m_Cargo != 1: # Cargo or TEU mode
            if self.m_Lbratio and self.m_LbratioV <= 0:
                self._show_error("Fatal error: L/B ratio must be positive!", "Input error")
                self._focus_field("edit_lbratio")
                return False
            if self.m_Bvalue and self.m_BvalueV <= 0:
                self._show_error("Fatal error: B value must be positive!", "Input error")
                self._focus_field("edit_bvalue")
                return False
            if self.m_Btratio and self.m_BtratioV <= 0:
                self._show_error("Fatal error: B/T ratio must be positive!", "Input error")
                self._focus_field("edit_btratio")
                return False
            if self.m_Cbvalue and (self.m_CbvalueV <= 0 or self.m_CbvalueV > 1.0):
                self._show_error("Fatal error: CB must be positive and < 1.0!", "Input error")
                self._focus_field("edit_cbvalue")
                return False
        
        if self.m_Pdtratio and self.m_PdtratioV <= 0.0:
            self._show_error("Fatal error: Prop.dia ratio must be positive!", "Input error")
            self._focus_field("edit_pdtratio")
            return False
        
        if self.V <= 0.0 or self.R <= 0.0 or self.N1 <= 0.0 or self.N2 <= 0.0:
            self._show_error("Fatal error: Speed, Range, and RPMs must be positive!", "Input error")
            self._focus_field("edit_speed")
            return False
            
        if self.m_Econom:
            if self.V7 <= 0.0 or self.D1 <= 0.0 or self.I < 0.0 or self.N < 1:
                self._show_error("Fatal error: Economic values must be positive (Interest >= 0)!", "Input error")
                self._focus_field("edit_voyages")
                return False

            if self.ship_life < 1:
                self._show_error("Fatal error: Ship life must be at least 1 year!", "Input error")
                self._focus_field("edit_ship_life")
                return False
            
            if self.Ketype == 4: # Nuclear
                if self.m_Reactor_Cost_per_kW <= 0 or self.m_Core_Life <= 0 or self.m_Decom_Cost < 0:
                    self._show_error("Fatal error: Nuclear costs must be positive!", "Input error")
                    self._focus_field("edit_reactor_cost")
                    return False
            else: # Fossil
                if self.F8 <= 0.0:
                    self._show_error("Fatal error: Fuel cost must be positive!", "Input error")
                    self._focus_field("edit_fuel")
                    return False

        # ----------------------------------------------------------------
        # Resistance method-specific validation
        # ----------------------------------------------------------------
        method_cfg = ResistanceMethodConfig.get(
            getattr(self, 'resistance_method', "Taylor's Series (Legacy)")
        )
        if method_cfg["requires_advanced_params"]:
            # Holtrop currently — only method that needs hull-form params today.
            # When Hollenbach or another method is added, give it its own
            # branch here keyed off its own config flag.
            if self.lcb_pct is not None and (self.lcb_pct < -5.0 or self.lcb_pct > 5.0):
                self._show_error(
                    "Holtrop validation: LCB outside regression range "
                    "(approximately -5% to +5% of L from midships).",
                    "Input error",
                )
                self._focus_field("edit_lcb_pct")
                return False
            for name, val in (
                ("CM",  self.cm),
                ("CWP", self.cwp),
            ):
                if val is not None and (val <= 0.0 or val > 1.0):
                    self._show_error(
                        f"Holtrop validation: {name} must be in (0, 1].",
                        "Input error",
                    )
                    return False
            # CP is derived from CB/CM inside _calc_pe_holtrop, but if CM is
            # set such that CP > 1 the regression breaks. Catch it here.
            if self.cm is not None and self.cm > 0:
                cp_check = self.C / self.cm
                if cp_check > 1.0:
                    self._show_error(
                        f"Holtrop validation: CP = CB/CM = {cp_check:.3f} > 1.0. "
                        "Increase CM or reduce CB.",
                        "Input error",
                    )
                    return False
            if self.has_bulb:
                if self.abt <= 0.0:
                    self._show_error(
                        "Holtrop validation: bulb is enabled but ABT is not positive.",
                        "Input error",
                    )
                    self._focus_field("edit_abt")
                    return False
                if self.hb >= self.T:
                    self._show_error(
                        f"Holtrop validation: bulb height hB ({self.hb}) must be "
                        f"less than draught T ({self.T}). The bulb must be submerged.",
                        "Input error",
                    )
                    self._focus_field("edit_hb")
                    return False
            if self.has_transom and self.at <= 0.0:
                self._show_error(
                    "Holtrop validation: transom is enabled but AT is not positive.",
                    "Input error",
                )
                self._focus_field("edit_at")
                return False
            if self.cstern not in (-25, 0, 10):
                self._show_error(
                    f"Holtrop validation: CSTERN must be one of -25, 0, +10 "
                    f"(got {self.cstern}).",
                    "Input error",
                )
                return False

        return True

    # --- NEW: TEU Capacity Placeholder ---
    def _estimate_teu_capacity(self, L, B, D):
        """
        Estimates the TEU capacity based on main dimensions.
        MODIFIED: Using research paper (Abramowski, et al., 2018).
        Based on inverted formula (38): LBD = f(TEU).
        """
        try:
            LBD_product = L * B * D
            
            if LBD_product <= 0:
                return 0
                
            
            teu_est = ( (LBD_product + 20143.62) / 104.422 ) ** (1.0 / 0.9)
            
            return teu_est
            
        except (ValueError, OverflowError):
            return 0

    def _get_volume_status(self):
        """
        Calculates Required vs Available Volume.
        """
        ship_data = ShipConfig.get(self.ship_name)
        fuel_data = FuelConfig.get(self.engine_name)
        
        vol_hull = self.L1 * self.B * self.D * self.C
        vol_avail = vol_hull * ship_data.get("Profile_Factor", 1.0)
        
        vol_cargo = 0.0
        
        if self.design_mode == 2: # TEU Mode
            vol_cargo = self.m_TEU * 33.0 
        elif ship_data.get("Design_Type") == "Volume": 
            if ship_data["ID"] == 5: # Cruise
                vol_cargo = self.W * 50.0 
            else:
                vol_cargo = self.W / 0.5
        else:
            if self.m_CustomDensity > 0:
                density = self.m_CustomDensity
            else:
                density = ship_data.get("Cargo_Density", 1.0)
            
            vol_cargo = self.W / density
            vol_cargo *= 1.10 # Stowage Factor

        vol_fuel = 0.0
        # Volume must be based on RAW fuel mass, not tank-inclusive mass.
        # TankFactor handles tank STEEL MASS; VolFactor handles tank+insulation VOLUME.
        # Using calculated_fuel_mass here would treat the tank's mass as if it were
        # additional liquid fuel, inflating volume by ~8x for hydrogen.
        raw_mass = getattr(self, 'raw_fuel_mass', None)
        if raw_mass is None:  # backward-compat fallback if _mass() hasn't run yet
            tf = fuel_data.get("TankFactor", 1.0) or 1.0
            raw_mass = getattr(self, 'calculated_fuel_mass', 0.0) / tf
        if raw_mass > 0 and fuel_data["Density"] > 0:
            vol_fuel = (raw_mass * 1000.0) / fuel_data["Density"] * fuel_data["VolFactor"]
        
        vol_mach = (self.P2 * 0.7457) * 0.4 
        # Stores volume should scale with Lightship Mass (M1+M2+M3), not Cargo DWT (W1)
        lightship = getattr(self, 'M1', 0) + getattr(self, 'M2', 0) + getattr(self, 'M3', 0)
        vol_stores = lightship * 0.05
        
        vol_req = vol_cargo + vol_fuel + vol_mach + vol_stores
        
        ratio = vol_req / (vol_avail if vol_avail > 0 else 1.0)
        return vol_req, vol_avail, ratio

    def _solve_volume_limit(self):
        """
        Phase 3 Expansion Loop (ROBUST):
        Expands dimensions if volume is insufficient.
        Handles power calculation failures gracefully.
        """
        # Reset the expansion-iteration counter every call so batch runs see
        # fresh values per row.
        self.vol_expansion_iters = 0

        if not self.m_VolumeLimit:
            return True 

        req, avail, ratio = self._get_volume_status()
        
        if ratio <= 1.0:
            return True 

        self._log(f"\n--- VOLUME LIMIT DETECTED ---")
        self._log(f"Required: {int(req)} m3 | Available: {int(avail)} m3")
        self._log(f"Expanding ship dimensions...")

        target_payload = self.W 
        L_orig, B_orig, D_orig = self.L1, self.B, self.D
        
        # Suppress speed/pitch popups during expansion — we expect transient out-of-range
        # conditions while iterating toward a valid hull. Restore on exit.
        prev_ignspd, prev_ignpth = self.ignspd, self.ignpth
        self.ignspd = True
        self.ignpth = True
        try:
            for i in range(50):
                self.vol_expansion_iters = i + 1  # 1-indexed for human reading
                # Use a slightly more aggressive expansion for volume-heavy fuels (H2, NH3)
                fuel_data_local = FuelConfig.get(self.engine_name)
                expansion_factor = 1.03 if fuel_data_local.get("VolFactor", 1.0) >= 1.5 else 1.02
                
                self.L1 *= expansion_factor
                
                if self.L1 > 0:
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    else: self.B *= expansion_factor
                    self.D *= expansion_factor

                C_safe = self.C if self.C > 0 else 0.8
                if self.Kstype == 1:
                    self.T = self.D * 0.78
                else:
                    self.T = self.D * 0.70

                power_ok = self._power()
                
                if not power_ok:
                    # Power solver failed at this size — bump installed power as a guess
                    # and let _mass() recompute fuel from it.
                    self.P1 *= (expansion_factor ** 2)
                    self.P2 *= (expansion_factor ** 2)
                    # Also nudge prop RPM down — large hulls want slower, larger props
                    self.N2 *= 0.97
                    self.N1 *= 0.97
                
                self._mass()
                
                fuel_mass = self.calculated_fuel_mass if hasattr(self, 'calculated_fuel_mass') else 0
                new_lightship = (self.M1 + self.M2 + self.M3) * 1.02
                misc_mass = 13.0 * (self.M ** 0.35) 
                
                required_displacement = target_payload + new_lightship + fuel_mass + misc_mass
                
                self.M = required_displacement
                new_T = self.M / (self.L1 * self.B * C_safe * 1.025)
               
                if new_T > (self.D * 0.9): 
                    new_T = self.D * 0.9
                
                self.T = new_T

                req, avail, ratio = self._get_volume_status()
                
                if ratio <= 1.0:
                    self._log(f"-> Converged at L={self.L1:.1f}m after {self.vol_expansion_iters} iter(s)")
                    self._log(f"-> Draft adjusted to {self.T:.1f}m (New Disp: {int(self.M)}t)")
                    self.W1 = self.M - new_lightship - fuel_mass - misc_mass
                    return True 

            self._log(f"-> WARNING: Volume expansion limit reached after {self.vol_expansion_iters} iter(s).")
            return False
        finally:
            self.ignspd = prev_ignspd
            self.ignpth = prev_ignpth

    def _freeboard(self):
        """Port of Sub_freeboard"""

        ship_name = self.ship_name
        ship_data = ShipConfig.get(ship_name)
        
        eff_type = ship_data["ID"] 

        if self.L1 <= self._L2[0]: 
            l = 0
        elif self.L1 < self._L2[-1]:
            l = 0
            while l < 17 and self.L1 > self._L2[l]:
                l += 1
            if l > 0: l -= 1
        else:
            l = 16
        
        L2_l = self._L2[l]
        L2_l1 = self._L2[l+1]
        
        if eff_type == 1:
            F1_l = self._F1[l]
            F1_l1 = self._F1[l+1]
            self.F5 = F1_l + (self.L1 - L2_l) * (F1_l1 - F1_l) / (L2_l1 - L2_l)
        else:
            F2_l = self._F2[l]
            F2_l1 = self._F2[l+1]
            self.F5 = F2_l + (self.L1 - L2_l) * (F2_l1 - F2_l) / (L2_l1 - L2_l)
            
        if eff_type != 1 and self.L1 < 100:
             self.F5 += 0.75 * (100.0 - self.L1) * (0.35 - self._E5)
            
        T_safe = self.T if self.T != 0 else 1e-9
        C9 = self.C + (0.85 * self.D - self.T) / (10.0 * T_safe)
        if C9 >= 0.68:
            self.F5 *= (C9 + 0.68) / 1.36
            
        if self.D >= self.L1 / 15.0:
            if self.L1 <= 120:
                self.F5 += ((self.D - self.L1 / 15.0) * self.L1 / 0.48)
            else:
                self.F5 += ((self.D - self.L1 / 15.0) * 250.0)
                
        if self.L1 <= 85:
            E9 = 350 + (self.L1 - 24) * (860.0 - 350.0) / (85.0 - 24.0)
        elif self.L1 <= 122:
            E9 = 860 + (self.L1 - 85) * (1070.0 - 860.0) / (122.0 - 85.0)
        else:
            E9 = 1070
            
        if self.Kstype == 1:
            E9 *= (self._E5 ** 1.23)
        else:
            E9 *= (self._E5 ** 1.3)
            
        self.F5 -= E9
        E0 = (self.L1 / 3.0 + 10.0) * (8.3375 * (1.0 - self._Y1) + 4.16875 * (1.0 - self._Y2))
        E0 *= (0.75 - 0.5 * self._E5)
        self.F5 += E0
        self.F5 *= 0.001
        
        return True

    def _stability(self):
        """Port of Sub_stability"""
        ship_name = self.ship_name
        ship_data = ShipConfig.get(ship_name)
        
        G3 = ship_data["Stability_Factor"] * self.D
        C7 = 0.67 * self.C + 0.32
        C_safe = self.C if self.C != 0 else 1e-9
        T_safe = self.T if self.T != 0 else 1e-9
        G4 = self.T * (5.0 * C7 - 2.0 * self.C) / (6.0 * C7)
        C8 = 1.1 * self.C - 0.12
        G5 = C8 * self.B * self.B / (12.0 * T_safe * C_safe)
        self.G6 = G4 + G5 - G3
        return True
        
    def _cost(self):
        """Port of Sub_cost - extended with retrofit cost discount,
        LNG methane-slip handling for chapter 5 sensitivity analysis,
        and a fuel-specific maintenance split (chapter 5 OPEX fix).

        Maintenance was previously a flat percentage of total build cost
        (m_H3_Maint_Percent * self.S). That over-inflated nuclear OPEX
        because reactor capex (S0_nuclear) is an order of magnitude larger
        than diesel machinery, yet real nuclear plant non-fuel O&M is
        ~1-2% of capex/yr, not 4%. We now split:
          - Hull + outfit maintenance: m_H3_Maint_Percent * (S8 + S9)
          - Machinery maintenance:     fuel["MaintenancePct"] * S0
        Core replacement and decommissioning continue to flow through H7.
        """

        C_safe = self.C if self.C != 0 else 1e-9
        
        S8 = self.m_S1_Steel1 * (self.M1 ** (2/3)) * (self.L1 ** (1/3)) / C_safe + self.m_S2_Steel2 * self.M1
        
        S9 = self.m_S3_Outfit1 * (self.M2 ** (2/3)) + self.m_S4_Outfit2 * (self.M2 ** 0.95)
        
        S0_nuclear = 0.0
        if self.Ketype == 4: # Nuclear
            installed_power_kw = self.P2 * 0.7457
            S0_nuclear = self.m_Reactor_Cost_per_kW * installed_power_kw
            S0 = S0_nuclear
        else: # Fossil
            S0 = self.m_S5_Machinery1 * (self.P1 ** 0.82) + self.m_S6_Machinery2 * (self.P1 ** 0.82)

        # ----------------------------------------------------------------
        # Retrofit machinery cost discount (sec 5.4).
        # In a retrofit, the existing hull (steel S8 + outfit S9) is reused;
        # only the machinery package (S0) is replaced. Industry norm is that
        # a conversion costs 30-50% of the equivalent new-build machinery
        # package, so we multiply S0 by m_RetrofitFactor (default 0.40) when
        # Retrofit Mode is on. Also applies to nuclear conversions, though
        # those are obviously hypothetical.
        # ----------------------------------------------------------------
        if self.m_RetrofitMode:
            S0 *= self.m_RetrofitFactor
            if self.Ketype == 4:
                # If we ever model a nuclear retrofit, the discounted reactor
                # cost flows through to the per-core annual cost too.
                S0_nuclear *= self.m_RetrofitFactor

        self.S = S8 + S9 + S0
        # Expose the cost decomposition for CSV export and reporting.
        self.cost_steel_M     = S8 / 1.0e6
        self.cost_outfit_M    = S9 / 1.0e6
        self.cost_machinery_M = S0 / 1.0e6
        
        I_rate = self.I * 0.01
        H0 = (1.0 + I_rate) ** self.N
        if (H0 - 1.0) == 0: H0 = 1e-9 # Avoid div by zero
        H0 = I_rate * H0 / (H0 - 1.0)
        
        self.H1 = H0 * self.S 

        # Maintenance split (see _cost docstring). Hull + outfit at the
        # legacy flat percentage; machinery at a fuel-specific percentage
        # from FuelConfig. Falling back to m_H3_Maint_Percent if a fuel
        # entry is missing the new field keeps user-defined fuels working.
        _fuel_for_maint = FuelConfig.get(self.engine_name)
        _machinery_maint_pct = _fuel_for_maint.get(
            "MaintenancePct", self.m_H3_Maint_Percent
        )
        H3 = self.m_H3_Maint_Percent * (S8 + S9) + _machinery_maint_pct * S0
        self.annual_maint = H3

        self.annual_opex = self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.m_H8_Other
        self.annual_fuel_cost_only = 0.0
        self.annual_carbon_tax = 0.0
        # Physical quantities behind the costs, kept separate from prices so
        # the cash flow can apply a different price in each year.
        self.annual_fuel_tonnes = 0.0
        self.annual_co2e_tonnes = 0.0
        self.annual_core_cost = 0.0
        self.annual_decom_fund = 0.0

        engine_name = self.engine_name
        fuel_data = FuelConfig.get(engine_name)
        
        if fuel_data["IsNuclear"]:
            core_life_safe = self.m_Core_Life if self.m_Core_Life > 0 else 1e-9
            annual_core_cost = S0_nuclear / core_life_safe
            # Decommissioning is funded over the operating life (equal to
            # the loan term unless the user sets a separate ship life).
            life_years_safe = self.ship_life if self.ship_life > 0 else 1e-9
            annual_decom_fund = (self.m_Decom_Cost * 1.0e6) / life_years_safe
            self.annual_core_cost = annual_core_cost
            self.annual_decom_fund = annual_decom_fund
            self.H7 = annual_core_cost + annual_decom_fund
            self.annual_fuel_cost_only = annual_core_cost
            
        else:         
            service_power_kw = self.P1 * 0.7457
            annual_energy_MJ = service_power_kw * (self.D1 * 24.0) * 3.6
            if self.m_LHV > 0:
                 annual_fuel_tonnes = (annual_energy_MJ / (self.m_LHV * fuel_data["Efficiency"])) / 1000.0
            else:
                annual_fuel_tonnes = 0
            
            annual_fuel_tonnes *= self.m_Power_Factor
            self.annual_fuel_tonnes = annual_fuel_tonnes

            self.annual_fuel_cost_only = annual_fuel_tonnes * self.F8
            self.H7 = self.annual_fuel_cost_only

            # ------------------------------------------------------------
            # Effective carbon factor includes methane slip for LNG only.
            # CO2-equivalent factor = base CO2 + (slip_fraction * GWP100).
            # The slip mass is methane that escapes unburnt; multiplied by
            # GWP100 it's expressed as CO2-equivalent tonnes per tonne fuel.
            # Non-LNG fuels see no effect because m_MethaneSlip is irrelevant
            # to their combustion chemistry.
            # ------------------------------------------------------------
            effective_carbon = self._effective_carbon_factor(fuel_data)
            is_lng = (engine_name == "LNG (Dual Fuel)")
            if is_lng and self.m_MethaneSlip > 0:
                slip_frac = self.m_MethaneSlip / 100.0
                effective_carbon = effective_carbon + slip_frac * self.m_GWP_methane
            self.annual_co2e_tonnes = annual_fuel_tonnes * effective_carbon

            if self.m_CarbonTaxOn:
                annual_tax_bill = self.annual_co2e_tonnes * self.m_CarbonTax
                self.annual_carbon_tax = annual_tax_bill 
                self.H7 += annual_tax_bill

        if hasattr(self, 'aux_cost_annual'):
            self.H7 += self.aux_cost_annual
            self.annual_fuel_cost_only += self.aux_cost_annual
        
        self.annual_premium_income = 0.0
        try:
            if self.m_AuxEnabled:
                prem_rate = float(self.m_AuxPrem)
                
                if prem_rate > 0:
                    is_teu = (self.design_mode == 2)
                    total_cargo_units = self.m_TEU if is_teu else self.W1
                    
                    pct_refrigerated = float(self.m_AuxP1) / 100.0
                    
                    income_per_voyage = (total_cargo_units * pct_refrigerated) * prem_rate
                    self.annual_premium_income = income_per_voyage * self.V7
        except (ValueError, TypeError):
            self.annual_premium_income = 0.0

        Rt = self.H1 + self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.H7 + self.m_H8_Other
        
        Rt_adjusted = Rt - self.annual_premium_income
        
        self.S *= 1.0e-6
        
        W1_safe = self.W1 if self.W1 != 0 else 1e-9
        W7 = self.V7 * W1_safe
        
        if W7 == 0: W7 = 1e-9 

        # Legacy single-year RFR, kept for comparison with the cash flow.
        self.Rf_annualised = Rt_adjusted / W7

        # Year-by-year cash flow. With constant inputs and ship life equal
        # to the loan term this reproduces Rf_annualised.
        self.cash_flow = build_cash_flow(CashFlowInputs(
            capex=S8 + S9 + S0,
            loan_rate=I_rate,
            loan_term=self.N,
            ship_life=self.ship_life,
            discount_rate=I_rate,
            cargo_per_year=W7,
            fixed_opex=(self.m_H2_Crew + self.m_H4_Port + self.m_H5_Stores
                        + self.m_H6_Overhead + self.m_H8_Other),
            maintenance=H3,
            fuel_tonnes=self.annual_fuel_tonnes,
            fuel_price=self.F8,
            co2e_tonnes=self.annual_co2e_tonnes,
            carbon_price=self.m_CarbonTax if self.m_CarbonTaxOn else 0.0,
            aux_fuel_tonnes=getattr(self, 'aux_fuel_annual_tonnes', 0.0),
            aux_price=getattr(self, 'aux_fuel_price', 0.0),
            nuclear=self.annual_core_cost + self.annual_decom_fund,
            premium_income=self.annual_premium_income,
        ))
        self.Rf = self.cash_flow.rfr

        return True

    def _apply_resistance_breakdown(self):
        """
        Method-agnostic resistance breakdown + ESD application.

        Reads the components dict that the active _calc_pe_<method>() stored
        on self.resistance_components. For components that are None (the active
        method did not natively compute that piece — the Taylor case), falls
        back to the legacy back-fit logic for that component. For non-None
        components (Holtrop case), uses the stored value directly.

        ESD application logic at the bottom is method-agnostic and unchanged:
        air lubrication still targets self.res_friction, wind assist still
        reduces self.res_total.
        """

        rho_sw = 1025.0       # Seawater density (kg/m3)
        rho_air = 1.225       # Air density (kg/m3)
        viscosity = 1.188e-6  # Kinematic viscosity (15C seawater)

        V_ms = self.V * 0.5144 # Knots to m/s
        if V_ms <= 0: V_ms = 0.1

        eff_propulsive = self.Q if self.Q > 0 else 0.65

        pe_kw = self.P * 0.7457 # Effective Power in kW

        cb_safe = self.C if self.C > 0 else 0.8
        self.area_wetted = 1.025 * self.L1 * (cb_safe * self.B + 1.7 * self.T)

        # ------------------------------------------------------------------
        # Pull components from whichever _calc_pe_<method>() ran
        # ------------------------------------------------------------------
        comps = getattr(self, 'resistance_components', {}) or {}

        # Total: prefer the natively-computed value; fall back to deriving
        # from PE (matches the legacy Taylor convention exactly — pe_kw/V_ms).
        if comps.get('total') is not None:
            self.res_total = comps['total']
        else:
            self.res_total = pe_kw / V_ms if V_ms > 0 else 0.0

        # ----- Friction (with form factor under Holtrop, bare under Taylor) -----
        if comps.get('friction') is not None:
            self.res_friction = comps['friction']
        else:
            # Legacy ITTC 1957 back-fit (Taylor path)
            Re = (V_ms * self.L1) / viscosity
            if Re > 0:
                log_re = math.log10(Re)
                cf = 0.075 / ((log_re - 2.0)**2)
            else:
                cf = 0.0015
            rf_newtons = 0.5 * rho_sw * self.area_wetted * (V_ms**2) * cf
            self.res_friction = rf_newtons / 1000.0

        # ----- Air -----
        if comps.get('air') is not None:
            self.res_air = comps['air']
        else:
            frontal_area = self.B * ((self.D - self.T) + 10.0)
            cd_air = 0.8
            r_air_newtons = 0.5 * rho_air * frontal_area * (V_ms**2) * cd_air
            self.res_air = r_air_newtons / 1000.0

        # ----- Appendage -----
        if comps.get('appendage') is not None:
            self.res_app = comps['appendage']
        else:
            # Legacy Taylor assumption: 4% of total resistance
            self.res_app = self.res_total * 0.04

        # ----- Wave (back-fit residual for Taylor; native for Holtrop) -----
        if comps.get('wave') is not None:
            self.res_wave = comps['wave']
        else:
            calc_sum = self.res_friction + self.res_air + self.res_app
            self.res_wave = self.res_total - calc_sum
            if self.res_wave < 0:
                # Negative residual means friction+air+appendage already
                # exceeds total Pe-derived resistance.  The validated
                # behaviour is to clamp wave to zero and force friction
                # to 70% of total so the displayed breakdown stays
                # internally consistent with the Pe number.  Only fires
                # under the Taylor back-fit; Holtrop populates wave
                # natively and skips this branch.
                self.res_wave = 0.0
                self.res_friction = self.res_total * 0.70

        # ----- Holtrop-only components (zero under Taylor) -----
        self.res_bulb        = comps.get('bulb')        or 0.0
        self.res_transom     = comps.get('transom')     or 0.0
        self.res_correlation = comps.get('correlation') or 0.0

        # ------------------------------------------------------------------
        # ESD application — method-agnostic, unchanged from legacy
        # ------------------------------------------------------------------
        if getattr(self, '_esd_applied', False):
            return # Prevent compounding ESD reductions on multiple passes

        self.p_savings_kw = 0.0
        self.esd_log = []

        if self.m_ALS:
            try:
                eff_pct = float(self.m_ALSEff)
            except:
                eff_pct = 5.0

            area_bottom = self.L1 * self.B * cb_safe

            ratio_bottom = area_bottom / (self.area_wetted if self.area_wetted > 0 else 1.0)
            if ratio_bottom > 1.0: ratio_bottom = 1.0

            r_f_bottom = self.res_friction * ratio_bottom

            drag_reduction_kn = r_f_bottom * (eff_pct / 100.0)

            power_saved = drag_reduction_kn * V_ms

            self.p_savings_kw += power_saved
            self.esd_log.append(f"Air Lubrication: -{power_saved:.1f} kW (on {ratio_bottom*100:.0f}% of hull)")

            self.res_total -= drag_reduction_kn
            self.res_friction -= drag_reduction_kn

        if self.m_Wind:
            try:
                sav_pct = float(self.m_WindSav)
            except:
                sav_pct = 10.0

            pe_current = pe_kw - self.p_savings_kw
            wind_sav_kw = pe_current * (sav_pct / 100.0)

            self.p_savings_kw += wind_sav_kw
            self.esd_log.append(f"Wind Assist: -{wind_sav_kw:.1f} kW ({sav_pct}%)")

            wind_drag_red_kn = wind_sav_kw / V_ms
            self.res_total -= wind_drag_red_kn

        savings_bhp = self.p_savings_kw / 0.7457

        self.P1_Original = self.P1
        self.P1 -= savings_bhp

        if self.P1 < 0: self.P1 = 100.0

        self.P2_Original = self.P2
        self.P2 -= savings_bhp

        self._esd_applied = True

    def _effective_carbon_factor(self, fuel_data):
        """Return the carbon factor (tCO2 / t fuel) to use for this run.

        Honours self.m_CarbonOverride when the Battle Mode dialog has
        injected a per-engine override; otherwise falls back to the
        FuelConfig default.  Methane-slip handling for LNG is *not*
        applied here — it is added on top at each call site so the
        accounting matches the existing (and well-tested) behaviour.
        """
        if self.m_CarbonOverride is not None:
            return self.m_CarbonOverride
        return fuel_data["Carbon"]

    def _mass(self):
        """Port of Sub_mass - FIXED to restore legacy C++ math for standard engines"""

        E1 = self.L1 * (self.B + self.T) + 0.85 * self.L1 * (self.D - self.T) + 250
        T_safe = self.T if self.T != 0 else 1e-9
        C1 = self.C + (0.8 * self.D - self.T) / (10.0 * T_safe)
        
        ship_name = self.ship_name
        ship_data = ShipConfig.get(ship_name)
        
        K1 = ship_data["Steel_K1"]
        
        if ship_data["Outfit_Slope"] > 0.001:
            K2 = ship_data["Outfit_Intercept"] - (self.L1 / ship_data["Outfit_Slope"])
        else:
            K2 = ship_data["Outfit_Intercept"]
            
        self.M1 = K1 * (E1 ** 1.36) * (1.0 + 0.5 * (C1 - 0.7))
        self.M2 = K2 * self.L1 * self.B

        if ship_data["ID"] == 1:
            K3 = 0.59
        else:
            K3 = 0.56

        engine_name = self.engine_name
        fuel_data = FuelConfig.get(engine_name)

        # Fuel-specific structure / outfit penalty (Option B).
        # M1 (steel) and M2 (outfit) above are pure hull-geometry regressions
        # and know nothing about the engine choice. For nuclear we need to
        # capture the reinforced reactor-compartment subdivision (extra hull
        # steel) and the specialised systems outfit (radiation monitoring,
        # shielded control room, redundant safety I&C, dedicated HVAC) that
        # the L*B and cubic-number regressions do not see.
        # Defaults are 1.0 for every conventional fuel, so the legacy
        # diesel/steam baseline (and every alt-fuel comparison case) is
        # numerically unchanged. Nuclear gets +8% on M1 and +4% on M2.
        # The aux-outfit additive term at line ~3878 is applied *after*
        # this scaling, which is what we want (refrigerated-hold insulation
        # is not subject to the nuclear outfit penalty).
        self.M1 *= fuel_data.get("StructureFactor", 1.0)
        self.M2 *= fuel_data.get("OutfitFactor", 1.0)

        is_legacy_diesel = (self.Ketype == 1 or self.Ketype == 2)
        is_legacy_steam = (self.Ketype == 3)
        
        V_safe = self.V if self.V > 0.1 else 0.1
        
        installed_power_kw = self.P2 * 0.7457 

        # ----------------------------------------------------------------
        # Machinery mass M3 (tonnes).  Restores the legacy C++ regressions
        # validated against the original tool:
        #   - Direct/geared diesel:  9.38*(P2/N1)^0.84 + K3*P2^0.7
        #     (Watson/Gilfillan-style; P2 in HP, N1 in RPM, so slow-speed
        #      direct-drive engines come out heavier than high-rev geared
        #      ones, which is the correct physics for marine diesels).
        #   - Steam turbines:        0.16*P2^0.89  (P2 in HP)
        #   - Alternative fuels:     200 t base + per-kW scaling from
        #     FuelConfig.Machinery (kg/kW).
        #   - Nuclear:               2000 t base (reactor vessel + shielding)
        #     plus per-kW scaling.
        # The earlier uniform K3*kg_per_kw*kW/1000 formula under-predicted
        # diesel machinery by roughly an order of magnitude and ignored
        # engine RPM entirely.
        # ----------------------------------------------------------------
        if is_legacy_diesel:
            N1_safe = self.N1 if self.N1 > 0 else 1e-9
            term1 = 9.38 * ((self.P2 / N1_safe) ** 0.84)
            term2 = K3 * (self.P2 ** 0.7)
            self.M3 = term1 + term2
        elif is_legacy_steam:
            self.M3 = 0.16 * (self.P2 ** 0.89)
        else:
            if fuel_data["IsNuclear"]:
                # ~2000 t base for a naval-grade SMR pressure vessel + shielding
                self.M3 = 2000.0 + (fuel_data["Machinery"] * installed_power_kw * 0.001)
            else:
                base_machinery = 200.0
                self.M3 = base_machinery + (installed_power_kw * fuel_data["Machinery"] * 0.001)

        if is_legacy_diesel:
            self.calculated_fuel_mass = 0.0011 * (0.15 * self.P1 * self.R / V_safe)
            self.raw_fuel_mass = self.calculated_fuel_mass   # ADDED: legacy has no separate tank multiplier
            W3 = self.calculated_fuel_mass
            
        elif is_legacy_steam:
            self.calculated_fuel_mass = 0.0011 * (0.28 * self.P1 * self.R / V_safe)
            self.raw_fuel_mass = self.calculated_fuel_mass   # ADDED
            W3 = self.calculated_fuel_mass
            
        else:
            if fuel_data["IsNuclear"]:
                W3 = 0.0
                self.raw_fuel_mass = 0.0                     # ADDED
                self.calculated_fuel_mass = 0.0              # ADDED (was implicitly leftover)
            else:
                voyage_hours = self.R / V_safe
                service_power_kw = self.P1 * 0.7457
                total_energy_MJ = service_power_kw * voyage_hours * 3.6
                
                efficiency = fuel_data["Efficiency"]
                lhv = self.m_LHV 
                if lhv <= 0.001: lhv = 42.7
                
                if lhv > 0 and efficiency > 0:
                    raw_fuel_mass_tonnes = (total_energy_MJ / (lhv * efficiency)) / 1000.0
                else:
                    raw_fuel_mass_tonnes = 0.0
                
                self.raw_fuel_mass = raw_fuel_mass_tonnes    # ADDED: pure fuel only, no tank
                W3 = raw_fuel_mass_tonnes * fuel_data["TankFactor"]  # fuel + tank steel mass
                self.calculated_fuel_mass = W3

        # Aux-machinery contributions (diesel genset, etc.) get folded into
        # M3 / M2 here; M0 is computed once afterwards so the lightship
        # total reflects everything.
        if hasattr(self, 'M_aux_mach'):
            self.M3 += self.M_aux_mach
            
        if hasattr(self, 'M_aux_outfit'):
            self.M2 += self.M_aux_outfit
        
        M0 = (self.M1 + self.M2 + self.M3) * 1.02

        if hasattr(self, 'W_aux_fuel'):
            W3 += self.W_aux_fuel # Add generator fuel to total fuel weight

        W4 = 13.0 * (abs(self.M) ** 0.35)
        
        self.W1 = self.M - M0 - W3 - W4 # Cargo deadweight
        self.W5 = self.M - M0 # Total deadweight
        
        return True

    def _power(self):
        """Port of Sub_power.

        Method-agnostic shell:
          1. Computes shared hydrodynamic quantities (Fn, Re, optimal LCB)
             that downstream code reads regardless of resistance method.
          2. Dispatches to the active resistance method's _calc_pe_<method>()
             via a name->bound-method table. Adding a new method is one new
             entry here + a new _calc_pe_<m>() function + a new entry in
             ResistanceMethodConfig.DATA. No other structural changes.
          3. Runs Wageningen B-series propeller pitch optimisation.
          4. Applies SCF and transmission efficiency to produce installed
             power P1 and P2, plus a 30% sea margin.

        Steps 3 and 4 are method-agnostic — they only consume self.P,
        self.Q (computed below), and self.Ketype.
        """
        self.Kpwrerr = 1
        L1_safe = self.L1 if self.L1 > 0 else 1e-9
        g = 9.81
        v_ms = self.V * 0.5144  # knots to m/s
        viscosity = 1.188e-6    # Seawater kinematic viscosity

        # Shared quantities used by both resistance methods AND by downstream
        # reporting code (_outvdu reads self.froude_number and friends).
        self.froude_number = v_ms / math.sqrt(g * L1_safe)
        self.reynolds_number = (v_ms * L1_safe) / viscosity
        self.lcb_optimal = 8.8 * (self.froude_number - 0.18)

        # ------------------------------------------------------------------
        # Resistance method dispatcher
        # ------------------------------------------------------------------
        # Maps display-name -> bound method. Must contain one entry per
        # ResistanceMethodConfig.DATA entry. Silent fallback to Taylor on
        # an unknown name is intentionally NOT done — that would mask
        # configuration bugs. We raise a loud error instead.
        pe_dispatch = {
            "Taylor's Series (Legacy)":  self._calc_pe_taylor,
            "Holtrop-Mennen (1984)":     self._calc_pe_holtrop,
        }
        method_name = getattr(self, 'resistance_method', "Taylor's Series (Legacy)")
        if method_name not in pe_dispatch:
            self._show_error(
                f"Unknown resistance method: {method_name!r}\n"
                f"Known methods: {list(pe_dispatch.keys())}",
                "Configuration error",
            )
            return False

        result = pe_dispatch[method_name]()
        # _calc_pe_<method>() returns False on validation failure (e.g. V0
        # out of range, Fn outside Holtrop's regression band) OR a tuple
        # (pe_hp, components_dict) on success. In both cases self.P and
        # self.resistance_components are set as side effects, so the
        # dispatcher only needs the success/failure signal.
        if result is False:
            return False

        # ------------------------------------------------------------------
        # Resistance uncertainty multiplier (Holtrop ±10% sensitivity).
        # Scales effective power Pe before propeller sizing so that downstream
        # fuel mass, installed power, and built cost all respond consistently.
        # If the user picks +10% the propeller solver receives a 10% larger
        # thrust target, which is exactly what a "10% pessimistic resistance"
        # case would require physically. The components dict is also scaled so
        # the reported breakdown stays internally consistent.
        # ------------------------------------------------------------------
        if abs(self.m_ResUncertPct) > 1e-9:
            mult = 1.0 + (self.m_ResUncertPct / 100.0)
            # Defensive clamp — keep multiplier strictly positive so the prop
            # solver doesn't try to push a backwards-thrusting prop.
            if mult < 0.05:
                mult = 0.05
            self.P *= mult
            for k, v in list(self.resistance_components.items()):
                if v is not None:
                    self.resistance_components[k] = v * mult

        # ------------------------------------------------------------------
        # Wageningen B-series propeller optimisation (method-agnostic)
        # ------------------------------------------------------------------
        m0 = 0
        mm = self.maxit

        D5 = self.Pdt * self.T; N5 = self.N2 / 60.0
        W9 = 1.1 - 3.4 * self.C + 3.1 * (self.C ** 1.9)
        T9 = 0.6 * W9; V5 = self.V * 0.515 * (1.0 - W9)
        V_safe = self.V if self.V != 0 else 1e-9
        T5 = 0.7461 * self.P / (0.515 * V_safe * (1.0 - T9))

        J1 = 0.4581238; P4 = 0.9304762; L3 = 0.5; L4 = 1.4
        D5_safe = D5 if D5 != 0 else 1e-9
        N5_safe = N5 if N5 != 0 else 1e-9
        J3 = V5 / (N5_safe * D5_safe)
        J2 = J3 - J1
        try: T3 = T5 / (1.025 * (N5_safe ** 2) * (D5_safe ** 4))
        except ZeroDivisionError: T3 = 0

        A6 = self._A6; B6 = self._B6; C6 = self._C6; D6 = self._D6
        Z4 = A6[1] + J2 * (A6[2] + J2 * (A6[3] + J2 * A6[4]))
        Y4 = B6[1] + J2 * (B6[2] + J2 * B6[3])
        X4 = C6[1] + J2 * C6[2]
        Z5 = A6[5] + J2 * (A6[6] + J2 * (A6[7] + J2 * A6[8]))
        Y5 = B6[5] + J2 * (B6[6] + J2 * B6[7])
        X5 = C6[5] + J2 * C6[6]
        P3 = 1.0; P5 = P3 - P4
        A9 = Z4 + P5 * (Y4 + P5 * (X4 + P5 * D6[1])) - T3

        while m0 < mm and abs(A9) > 0.00001:
            m0 += 1
            B9 = Y4 + P5 * (2.0 * X4 + 3.0 * P5 * D6[1])
            if B9 == 0: B9 = 1e-9
            P6 = P5 - A9 / B9; P5 = P6
            A9 = Z4 + P5 * (Y4 + P5 * (X4 + P5 * D6[1])) - T3

        if m0 >= mm:
            self.Kpwrerr = self.NOT_CONVERGE
            if (not self.ignspd and not self.dbgmd): # Only show error if not in range mode
                self._show_error("Iteration for A9 did not converge!", "Fatal error")
            return False

        T3 = Z4 + P5 * (Y4 + P5 * (X4 + P5 * D6[1]))
        Q3 = Z5 + P5 * (Y5 + P5 * (X5 + P5 * D6[5]))
        if Q3 == 0: Q3 = 1e-9
        self.Q1 = T3 * J3 / (2.0 * math.pi * Q3)
        self.Q2 = (1.0 - T9) / (1.0 - W9)
        self.Q = self.Q1 * self.Q2; P5 += P4

        if self.dbgmd and self.m_Cargo == 0:
            msg = f"P5={P5:7.4f} (range {L3:4.2f}-{L4:4.2f})"
            self._debug_info(msg, "Debug P5")
        if P5 > L4:
            self.Kpwrerr *= self.PITCH_LOW
            if (not self.ignpth and not self.dbgmd) or self.m_Cargo == 1:
                self._show_error(f"Prop. pitch out of range: {P5:7.4f}", "Fatal error")
                return False
        if P5 < L3:
            self.Kpwrerr *= self.PITCH_HIGH
            if (not self.ignpth and not self.dbgmd) or self.m_Cargo == 1:
                self._show_error(f"Prop. pitch out of range: {P5:7.4f}", "Fatal error")
                return False

        self.F0 = 1.2 - math.sqrt(L1_safe) / 47.0 # SCF

        if self.Ketype == 1: self.F9 = 0.98   # Direct Diesel
        elif self.Ketype == 2: self.F9 = 0.95 # Geared Diesel
        elif self.Ketype == 3: self.F9 = 0.95 # Steam
        elif self.Ketype == 4: self.F9 = 0.95 # Nuclear
        else:
            self.F9 = 0.96

        Q_safe = self.Q if self.Q != 0 else 1e-9
        F9_safe = self.F9 if self.F9 != 0 else 1e-9

        self.P1 = (self.P / Q_safe) * self.F0 / F9_safe
        F6 = 30.0 # Margin %
        self.P2 = self.P1 * (1.0 + 0.01 * F6)

        return True

    # ======================================================================
    # Resistance method implementations
    # ======================================================================
    # Each _calc_pe_<method>() must:
    #   - Return (pe_hp, components_dict) on success, or False on failure.
    #   - Set self.P (effective power in HP) as a side effect.
    #   - Populate self.resistance_components (kN; None for components the
    #     method doesn't natively compute).
    #   - Set self.Kpwrerr to encode any out-of-range conditions.

    def _calc_pe_taylor(self):
        """Effective power from D.W. Taylor's Standard Series (legacy).

        This is the ORIGINAL Taylor block from _power() relocated verbatim
        into a method, so that downstream regression tests against the legacy
        C++ implementation produce byte-identical numbers. Do not modify the
        arithmetic here without re-validating those reference cases.

        Taylor outputs only the total resistance (effectively R_total via PE).
        Friction, wave, appendage, and air components are flagged as None in
        the components dict; _apply_resistance_breakdown() back-fits them
        using ITTC 1957 friction and a constant-fraction appendage model.

        Returns:
            (pe_hp, components_dict) on success, False on out-of-range failure.
        """
        L1_safe = self.L1 if self.L1 > 0 else 1e-9
        X0 = 20.0 * (self.C - 0.675)

        V0 = self.V / math.sqrt(3.28 * L1_safe)
        hull_vol = self.L1 * self.B * self.T * self.C
        W0 = (abs(hull_vol)) ** (1/3)
        if W0 == 0: W0 = 1e-9

        if self.dbgmd and self.m_Cargo == 0:
            msg = f"V0={V0:6.3f} (range 0.35-0.90)"
            self._debug_info(msg, "Debug V0")
        if V0 < 0.35:
            self.Kpwrerr = self.SPEED_LOW
            if (not self.ignspd and not self.dbgmd) or self.m_Cargo == 1:
                self._show_error(f"Ship speed too low: V0 is {V0:6.3f}", "Fatal error")
                return False
        if V0 > 0.90:
            self.Kpwrerr = self.SPEED_HIGH
            if (not self.ignspd and not self.dbgmd) or self.m_Cargo == 1:
                self._show_error(f"Ship speed too high: V0 is {V0:6.3f}", "Fatal error")
                return False

        if V0 < self._V1[1]: l = 1
        elif V0 < self._V1[7]:
            i = 1; l = 1
            while i < 8 and V0 > self._V1[i]:
                l = i; i += 1
        else: l = 6

        A = [0.0] * 9
        A[l] = self._resist(16 * (l - 1), W0, X0)
        A[l+1] = self._resist(16 * l, W0, X0)

        R6 = A[l] + (V0 - self._V1[l]) * (A[l+1] - A[l]) / (self._V1[l+1] - self._V1[l])
        R7 = R6 * W0 / (2.4938 * L1_safe)

        if self.L1 >= 122.0: R8 = R7 - 0.1 * (self.L1 - 122.0) / (self.L1 + 66.0)
        else: R8 = R7 + 1.8e-4 * ((122.0 - self.L1) ** 1.3)

        M5 = abs(self.M) * 2204.0 / 2240.0
        pe_hp = R8 * (self.V ** 3) * (M5 ** (2/3)) / 427.1
        self.P = pe_hp

        # Build components dict. Only 'total' is natively computed under
        # Taylor; the rest are None and _apply_resistance_breakdown will
        # back-fit them. 'total' is in kN: pe_kw / V_ms.
        v_ms = self.V * 0.5144 if self.V > 0 else 0.1
        if v_ms <= 0: v_ms = 0.1
        pe_kw = pe_hp * 0.7457
        total_kn = pe_kw / v_ms
        components = {
            'total':       total_kn,
            'friction':    None,
            'wave':        None,
            'appendage':   None,
            'air':         None,
            'bulb':        None,
            'transom':     None,
            'correlation': None,
        }
        self.resistance_components = components
        return (pe_hp, components)

    def _calc_pe_holtrop(self):
        """Effective power from Holtrop & Mennen (1982) with 1984 form-factor
        and wave-resistance updates.

        Sources:
          - Holtrop, J. and Mennen, G.G.J. (1982),
            "An Approximate Power Prediction Method",
            International Shipbuilding Progress, Vol. 29, No. 335, pp.166-170.
          - Holtrop, J. (1984),
            "A Statistical Re-analysis of Resistance and Propulsion Data",
            International Shipbuilding Progress, Vol. 31, No. 363, pp.272-276.

        Component breakdown (paper notation):
          R_total = R_F*(1+k_1) + R_APP + R_W + R_B + R_TR + R_A

        Block sources:
          1. Form factor (1+k_1)             -- 1984 paper p.3
          2. Appendage resistance R_APP      -- 1982 paper p.167
          3. Wave resistance R_W             -- 1984 paper pp.3-4
                (low-speed Fn<=0.40, high-speed Fn>=0.55, linear blend between)
          4. Bulb-near-surface R_B           -- 1982 paper p.168
                (with 1984 recommendation: clamp h_B to 0.6*T_F)
          5. Immersed-transom R_TR           -- 1982 paper p.168
          6. Model-ship correlation R_A      -- 1982 paper p.168
                (paper text uses S only; some implementations use S+S_APP)

        Sanity-check target: Holtrop & Mennen (1982) worked example,
        L=205m, B=32m, T=10m, C_P=0.5833, C_M=0.98, V=25kn -> P_E ~= 23 MW.
        The 1982 paper's example used the 1982 form factor (1+k_1=1.156)
        and the 1982 hump/hollow term m_2; this implementation uses the
        1984 form factor and m_4, so R_total will sit ~1-2% above the
        paper's 1793 kN. Per-component intermediates (c_1..c_17, lambda,
        m_1, m_3) all reproduce the paper to <0.1%.

        Returns:
            (pe_hp, components_dict) on success, False on out-of-range failure.
        """
        # ---------- Constants & inputs ----------
        L = self.L1 if self.L1 > 0 else 1e-9
        B = self.B if self.B > 0 else 1e-9
        T = self.T if self.T > 0 else 1e-9
        C_B = self.C if self.C > 0 else 1e-9
        g = 9.81
        rho_sw = 1025.0
        rho_air = 1.225
        nu = 1.188e-6
        V_ms = self.V * 0.5144
        if V_ms <= 0: V_ms = 0.1
        Fn = self.froude_number
        Re = self.reynolds_number

        # ---------- Validate Fn against method's regression range ----------
        cfg = ResistanceMethodConfig.get(self.resistance_method)
        fn_lo, fn_hi = cfg["valid_fn_range"]
        if Fn < fn_lo or Fn > fn_hi:
            # Multiply (don't assign) so this code can co-exist with other
            # error codes already encoded in Kpwrerr.
            self.Kpwrerr *= self.RESISTANCE_OUT_OF_RANGE
            if (not self.ignspd and not self.dbgmd) or self.m_Cargo == 1:
                self._show_error(
                    f"Fn={Fn:.3f} outside Holtrop range [{fn_lo:.2f}, {fn_hi:.2f}]",
                    "Fatal error",
                )
                return False

        # ---------- Auto-derived hull-form parameters ----------
        # User overrides (from the Holtrop panel) take precedence; otherwise
        # we compute sensible defaults from the main dimensions.
        C_M = self.cm if self.cm is not None else (0.977 + 0.085 * (C_B - 0.60))
        if C_M <= 0: C_M = 0.98
        C_P = C_B / C_M
        C_WP = self.cwp if self.cwp is not None else (0.763 * (C_P + 0.34))

        # LCB as percent of L from midships, +fwd. Default mirrors the
        # Taylor-era heuristic (line in _power(): 8.8*(Fn - 0.18)).
        lcb = self.lcb_pct if self.lcb_pct is not None else (8.8 * (Fn - 0.18))

        # Length of run L_R per Holtrop:
        #   L_R = L*(1 - C_P + 0.06*C_P*lcb / (4*C_P - 1))
        denom_LR = 4.0 * C_P - 1.0
        if abs(denom_LR) < 1e-9: denom_LR = 1e-9 if denom_LR >= 0 else -1e-9
        L_R = L * (1.0 - C_P + 0.06 * C_P * lcb / denom_LR)
        if L_R <= 0: L_R = 0.001 * L  # nonsense-input guard

        # Displaced volume
        nabla = C_B * L * B * T
        if nabla <= 0: nabla = 1e-9

        # Half-angle of waterline entrance i_E. Auto-default uses Holtrop's
        # regression (this one IS implemented; only the per-component R_*
        # regressions are TODO).
        if self.iE_deg is not None:
            i_E = self.iE_deg
        else:
            try:
                wp_term  = max(1.0 - C_WP, 1e-9) ** 0.30484
                cp_base  = max(1.0 - C_P - 0.0225 * lcb, 1e-9)
                cp_term  = cp_base ** 0.6367
                exponent = (
                    (L/B) ** 0.80856
                    * wp_term
                    * cp_term
                    * (L_R/B) ** 0.34574
                    * (100.0 * nabla / (L**3)) ** 0.16302
                )
                i_E = 1.0 + 89.0 * math.exp(-exponent)
            except (ValueError, ZeroDivisionError):
                # Pathological inputs — fall back to a typical merchant value
                i_E = 25.0

        # Bulb parameters (only if checkbox is on)
        if self.has_bulb:
            A_BT = self.abt if self.abt > 0 else 0.08 * B * T
            h_B  = self.hb  if self.hb  > 0 else 0.6  * T
        else:
            A_BT = 0.0
            h_B  = 0.0
        T_F = T  # forward draught — level keel assumption (TODO if trim varies)

        # Transom parameters
        if self.has_transom:
            A_T = self.at if self.at > 0 else 0.05 * B * T
        else:
            A_T = 0.0

        # CSTERN — already an int from _update_ui_to_data
        C_stern = self.cstern

        # ---------- Wetted surface S (Holtrop regression) ----------
        # This formula IS in the 1982 paper exactly as written:
        #   S = L*(2T+B)*sqrt(C_M)*(0.453 + 0.4425*C_B - 0.2862*C_M
        #                            - 0.003467*B/T + 0.3696*C_WP)
        #       + 2.38*A_BT/C_B
        S = L * (2.0*T + B) * math.sqrt(C_M) * (
            0.453 + 0.4425*C_B - 0.2862*C_M - 0.003467*B/T + 0.3696*C_WP
        ) + 2.38 * A_BT / C_B
        if S <= 0: S = 1e-9

        # Appendage wetted area
        S_APP = self.s_app_override if self.s_app_override is not None else 0.04 * S

        # ============================================================
        # BLOCK 1 — Form factor (1+k_1)   [Holtrop 1984, p.3]
        # ============================================================
        # c_14   = 1 + 0.011 * C_stern
        # 1+k_1  = 0.93 + 0.487118 * c_14
        #          * (B/L)^1.06806
        #          * (T/L)^0.46106
        #          * (L/L_R)^0.121563
        #          * (L^3/nabla)^0.36486
        #          * (1 - C_P)^(-0.604247)
        c_14 = 1.0 + 0.011 * C_stern
        one_minus_CP = 1.0 - C_P
        if one_minus_CP <= 0:
            # Pathological C_P >= 1 — clamp to avoid complex/inf result.
            one_minus_CP = 1e-6
        one_plus_k1 = (
            0.93
            + 0.487118 * c_14
            * (B / L) ** 1.06806
            * (T / L) ** 0.46106
            * (L / L_R) ** 0.121563
            * (L ** 3 / nabla) ** 0.36486
            * one_minus_CP ** (-0.604247)
        )

        # ---------- Frictional resistance (ITTC 1957) ----------
        if Re > 1:
            C_F = 0.075 / ((math.log10(Re) - 2.0) ** 2)
        else:
            C_F = 0.0015
        R_F = 0.5 * rho_sw * V_ms**2 * S * C_F            # bare-hull friction (N)
        R_F_with_form = R_F * one_plus_k1                  # with form factor (N)

        # ============================================================
        # BLOCK 2 — Appendage resistance R_APP   [Holtrop 1982, p.167]
        # ============================================================
        # R_APP = 0.5 * rho * V^2 * S_APP * (1+k_2)_eq * C_F
        # Holtrop 1982 tabulates (1+k_2)_i per appendage type:
        #   rudder behind skeg     1.5-2.0
        #   rudder behind stern    1.3-1.5
        #   twin-screw rudder      2.8
        #   shaft brackets         3.0
        #   skeg                   1.5-2.0
        #   strut bossings         3.0
        #   hull bossings          2.0
        #   shafts                 2.0-4.0
        #   stabilizer fins        2.8
        #   dome                   2.7
        #   bilge keels            1.4
        # Combination rule: (1+k_2)_eq = sum((1+k_2)_i * S_i) / sum(S_i).
        # We use a single equivalent value here (default 1.5, "rudder behind
        # skeg" lower bound). When the user has a real appendage breakdown,
        # expose this in the UI and replace the constant. The 1984 paper
        # explicitly defers to the 1982 formulae for appendage resistance
        # ("no new analysis was made", 1984 p.3).
        one_plus_k2_eq = 1.5
        R_APP = 0.5 * rho_sw * V_ms**2 * S_APP * one_plus_k2_eq * C_F

        # ============================================================
        # BLOCK 3 — Wave resistance R_W   [Holtrop 1984, pp.3-4]
        # ============================================================
        # Three regimes:
        #   Fn <= 0.40                 : R_W_low  using m_1, m_4 (1984), c_1
        #   Fn >= 0.55                 : R_W_high using m_3, m_4 (1984), c_17
        #   0.40 < Fn < 0.55           : linear interpolation between
        #                                R_W_low(0.40) and R_W_high(0.55)
        #
        # The 1984 paper REPLACES the 1982 hump/hollow term m_2 with
        # m_4 = c_15 * 0.4 * exp(-0.034 * Fn^-3.29). Everything else
        # (c_1..c_5, c_7, c_15, c_16, lambda, d) is shared between both
        # speed regimes and unchanged from 1982.

        # c_7 piecewise on B/L
        BL_ratio = B / L
        if BL_ratio < 0.11:
            c_7 = 0.229577 * BL_ratio ** 0.33333
        elif BL_ratio > 0.25:
            c_7 = 0.5 - 0.0625 * L / B
        else:
            c_7 = BL_ratio

        # c_1 (uses i_E in degrees, not radians)
        ie_arg = 90.0 - i_E
        if ie_arg <= 0:
            ie_arg = 1e-6   # i_E should never reach 90 deg, but guard anyway
        c_1 = 2223105.0 * c_7 ** 3.78613 * (T / B) ** 1.07961 * ie_arg ** (-1.37565)

        # c_3 (bulb effect) and c_2
        if A_BT > 0:
            c_3_denom = B * T * (0.31 * math.sqrt(A_BT) + T_F - h_B)
            if abs(c_3_denom) < 1e-9:
                c_3_denom = 1e-9 if c_3_denom >= 0 else -1e-9
            c_3 = 0.56 * A_BT ** 1.5 / c_3_denom
        else:
            c_3 = 0.0
        c_2 = math.exp(-1.89 * math.sqrt(max(c_3, 0.0)))

        # c_5 (transom effect)
        c_5 = 1.0 - 0.8 * A_T / (B * T * C_M)

        # lambda (wavelength parameter), piecewise on L/B
        LB_ratio = L / B
        if LB_ratio < 12.0:
            lambda_coef = 1.446 * C_P - 0.03 * LB_ratio
        else:
            lambda_coef = 1.446 * C_P - 0.36

        # c_16 piecewise on C_P
        if C_P < 0.80:
            c_16 = 8.07981 * C_P - 13.8673 * C_P ** 2 + 6.984388 * C_P ** 3
        else:
            c_16 = 1.73014 - 0.7067 * C_P

        # m_1 (low-speed exponent term)
        m_1 = (
            0.0140407 * L / T
            - 1.75254 * nabla ** (1.0 / 3.0) / L
            - 4.79323 * B / L
            - c_16
        )

        # c_15 piecewise on L^3/nabla
        slenderness = L ** 3 / nabla
        if slenderness < 512.0:
            c_15 = -1.69385
        elif slenderness > 1726.91:
            c_15 = 0.0
        else:
            c_15 = -1.69385 + (L / nabla ** (1.0 / 3.0) - 8.0) / 2.36

        # m_3 (high-speed exponent term, Fn >= 0.55)
        m_3 = -7.2035 * (B / L) ** 0.326869 * (T / B) ** 0.605375

        # c_17 (high-speed prefactor, Fn >= 0.55)
        LB_minus_2 = L / B - 2.0
        if LB_minus_2 <= 0:
            # L/B <= 2 is non-physical for displacement hulls; protect the
            # power operation and the high-speed formula will just return ~0.
            LB_minus_2 = 1e-6
        c_17 = (
            6919.3 * C_M ** (-1.3346)
            * (nabla / L ** 3) ** 2.00977
            * LB_minus_2 ** 1.40692
        )

        d_exp = -0.9   # constant exponent on Fn in both speed regimes

        def _m4(fn_eval):
            """1984 hump/hollow term, replaces 1982's m_2."""
            return c_15 * 0.4 * math.exp(-0.034 * fn_eval ** (-3.29))

        def _R_W_low(fn_eval):
            """Wave resistance for Fn <= 0.40 (Holtrop 1984)."""
            return (
                c_1 * c_2 * c_5 * nabla * rho_sw * g
                * math.exp(
                    m_1 * fn_eval ** d_exp
                    + _m4(fn_eval) * math.cos(lambda_coef * fn_eval ** (-2))
                )
            )

        def _R_W_high(fn_eval):
            """Wave resistance for Fn >= 0.55 (Holtrop 1984)."""
            return (
                c_17 * c_2 * c_5 * nabla * rho_sw * g
                * math.exp(
                    m_3 * fn_eval ** d_exp
                    + _m4(fn_eval) * math.cos(lambda_coef * fn_eval ** (-2))
                )
            )

        if Fn <= 0.40:
            R_W = _R_W_low(Fn)
        elif Fn >= 0.55:
            R_W = _R_W_high(Fn)
        else:
            # Linear interpolation between R_W_low(0.40) and R_W_high(0.55)
            R_W_lo = _R_W_low(0.40)
            R_W_hi = _R_W_high(0.55)
            R_W = R_W_lo + (10.0 * Fn - 4.0) / 1.5 * (R_W_hi - R_W_lo)

        # ============================================================
        # BLOCK 4 — Bulb-near-surface resistance R_B   [Holtrop 1982, p.168]
        # ============================================================
        # P_B  = 0.56*sqrt(A_BT) / (T_F - 1.5*h_B)
        # F_ni = V / sqrt(g*(T_F - h_B - 0.25*sqrt(A_BT)) + 0.15*V^2)
        # R_B  = 0.11*exp(-3*P_B^(-2)) * F_ni^3 * A_BT^1.5 * rho*g / (1 + F_ni^2)
        #
        # 1984 paper recommendation (p.4 right column): clamp h_B to 0.6*T_F
        # in this calculation. Without the clamp, an unusually high bulb
        # centroid combined with shallow draft would drive (T_F - 1.5*h_B)
        # negative or near-zero, blowing up P_B.
        if A_BT > 0:
            h_B_eff = min(h_B, 0.6 * T_F)
            pb_denom = T_F - 1.5 * h_B_eff
            if pb_denom <= 0:
                pb_denom = 1e-6  # belt-and-braces; clamp above usually prevents this
            P_B = 0.56 * math.sqrt(A_BT) / pb_denom
            fni_inside = g * (T_F - h_B_eff - 0.25 * math.sqrt(A_BT)) + 0.15 * V_ms ** 2
            if fni_inside <= 0:
                fni_inside = 1e-6
            F_ni = V_ms / math.sqrt(fni_inside)
            R_B = (
                0.11 * math.exp(-3.0 * P_B ** (-2))
                * F_ni ** 3 * A_BT ** 1.5 * rho_sw * g
                / (1.0 + F_ni ** 2)
            )
        else:
            R_B = 0.0

        # ============================================================
        # BLOCK 5 — Immersed-transom resistance R_TR   [Holtrop 1982, p.168]
        # ============================================================
        # F_nT = V / sqrt(2*g*A_T / (B + B*C_WP))
        # c_6  = 0.2*(1 - 0.2*F_nT)   if F_nT < 5, else 0
        # R_TR = 0.5 * rho * V^2 * A_T * c_6
        if A_T > 0:
            fnt_denom = B + B * C_WP
            if fnt_denom <= 0:
                fnt_denom = 1e-9
            F_nT = V_ms / math.sqrt(2.0 * g * A_T / fnt_denom)
            if F_nT < 5.0:
                c_6 = 0.2 * (1.0 - 0.2 * F_nT)
            else:
                c_6 = 0.0
            R_TR = 0.5 * rho_sw * V_ms ** 2 * A_T * c_6
        else:
            R_TR = 0.0

        # ============================================================
        # BLOCK 6 — Model-ship correlation R_A   [Holtrop 1982, p.168]
        # ============================================================
        # c_4 = T_F/L  if T_F/L <= 0.04 else 0.04
        # C_A = 0.006*(L+100)^(-0.16) - 0.00205
        #       + 0.003*sqrt(L/7.5) * C_B^4 * c_2 * (0.04 - c_4)
        # R_A = 0.5 * rho * V^2 * S * C_A
        #
        # Note on wetted-area choice: the 1982 paper text writes R_A with
        # bare-hull S only. Reproducing the paper's worked example value of
        # R_A = 221.98 kN actually requires (S + S_APP) -- using S alone gives
        # ~220.5 kN (0.7% off). Either is defensible (the deviation is well
        # below the method's inherent ~5-10% accuracy); we follow the paper
        # text literally with S only. If the calling convention elsewhere in
        # the project assumes total wetted area, change S below to (S + S_APP).
        #
        # 1984 update note (p.5): newer trial data suggests C_A averages ~91%
        # of the 1982 formula's value, but the 1984 paper itself recommends
        # keeping the 1982 formula for practical use, which is what we do.
        if T_F / L <= 0.04:
            c_4 = T_F / L
        else:
            c_4 = 0.04
        C_A = (
            0.006 * (L + 100.0) ** (-0.16) - 0.00205
            + 0.003 * math.sqrt(L / 7.5) * C_B ** 4 * c_2 * (0.04 - c_4)
        )
        R_A = 0.5 * rho_sw * V_ms ** 2 * S * C_A

        # ---------- Air resistance ----------
        # Same formulation as the legacy Taylor-era back-fit, kept consistent
        # so the air component is comparable across resistance methods.
        frontal_area = self.B * ((self.D - T) + 10.0)
        cd_air = 0.8
        R_AIR = 0.5 * rho_air * frontal_area * V_ms**2 * cd_air

        # ---------- Sum (Holtrop's R_total excludes air, per the 1982 paper) ----------
        R_total = R_F_with_form + R_APP + R_W + R_B + R_TR + R_A   # Newtons
        P_E_watts = R_total * V_ms
        # Convert to HP for legacy pipeline compatibility (downstream code
        # consumes self.P in HP regardless of the resistance method).
        pe_hp = P_E_watts / 745.7
        self.P = pe_hp

        # Components dict in kN. 'total' here is Holtrop's hydrodynamic total
        # (no air), matching the convention self.res_total = pe_kw/V_ms used
        # by the legacy Taylor pipeline. Air is reported separately.
        components = {
            'total':       R_total / 1000.0,
            'friction':    R_F_with_form / 1000.0,
            'wave':        R_W / 1000.0,
            'appendage':   R_APP / 1000.0,
            'air':         R_AIR / 1000.0,
            'bulb':        R_B / 1000.0,
            'transom':     R_TR / 1000.0,
            'correlation': R_A / 1000.0,
        }
        self.resistance_components = components
        return (pe_hp, components)

    def _calculate_detailed_efficiency(self):
        """
        Calculates diagnostic efficiency components based on current ship state.
        Does not feed back into P1/P2 to avoid changing original results.
        """
        try:
            if self.Kstype == 1: # Tanker
                w = 0.5 * self.C - 0.05
            else: # Bulk/Cargo
                w = 0.5 * self.C - 0.12
            
            t = 0.8 * w # Standard approximation
            self.diag_eta_h = (1.0 - t) / (1.0 - w) if (1.0 - w) != 0 else 1.0
            
            eta_r = 1.0
            if self.diag_eta_h > 0:
                self.diag_eta_o = self.Q / (self.diag_eta_h * eta_r)
            else:
                self.diag_eta_o = 0.0

        except Exception:
            self.diag_eta_h = 0.0
            self.diag_eta_o = 0.0

    def _resist(self, base_idx, W0, X0):
        """Port of Sub_resist helper function"""
        Z1 = 1.0
        Z2 = (self.L1 / W0 - 5.296) / 1.064
        Z3 = 10.0 * (self.B / self.T - 3.025) / 9.05
        Z4 = 1000.0 * (self.C - 0.725) / 75.0
        Z5 = (X0 - 0.77) / 2.77
        X1 = self._X1
        R1 = (X1[base_idx + 1] * Z1 + X1[base_idx + 2] * Z2 + X1[base_idx + 3] * Z3 + X1[base_idx + 4] * Z4)
        R2 = (X1[base_idx + 5] * Z5 + X1[base_idx + 6] * Z2 * Z2 + X1[base_idx + 7] * Z3 * Z3 + X1[base_idx + 8] * Z4 * Z4)
        R3 = (X1[base_idx + 9] * Z5 * Z5 + X1[base_idx + 10] * Z2 * Z3 + X1[base_idx + 11] * Z2 * Z4)
        R4 = (X1[base_idx + 12] * Z2 * Z5 + X1[base_idx + 13] * Z3 * Z4 + X1[base_idx + 14] * Z3 * Z5)
        R5 = (X1[base_idx + 15] * Z4 * Z5 + X1[base_idx + 16] * Z5 * Z4 * Z4)
        A_val = R1 + R2 + R3 + R4 + R5
        A_val = A_val * 5.1635 + 13.1035
        return A_val

    def _auxiliary(self):
        """
        Calculates Auxiliary Power, Mass, and Cost.
        Handles Nuclear integration (sizing P2 instead of adding Gensets).
        """

        self.P_aux_total = 0.0
        self.M_aux_mach = 0.0      # Diesel Gen Mass
        self.M_aux_outfit = 0.0    # Insulation
        self.W_aux_fuel = 0.0      # Diesel Fuel Wt
        self.aux_cost_annual = 0.0 # Diesel Cost
        
        self.P_hotel = 0.0
        self.P_cargo_cooling = 0.0
        self.aux_fuel_annual_tonnes = 0.0
        self.aux_fuel_price = 0.0
        
        if not self.m_AuxEnabled:
            return

        try:
            self.P_hotel = float(self.m_AuxBase)
            
            p_cargo = 0.0
            mode_text = self.m_AuxMode
            
            pct = float(self.m_AuxP1) / 100.0
            load_factor = float(self.m_AuxP2)
            
            if "Reefer" in mode_text:
                base_units = self.m_TEU if (self.design_mode == 2) else (self.W / 14.0)
                p_cargo = base_units * pct * load_factor
                
            elif "Hold" in mode_text:
                vol_est = self.W * 1.5 # approx stowage factor
                p_cargo = (vol_est / 1000.0) * load_factor
                self.M_aux_outfit = vol_est * 0.02 # Insulation weight
            
            self.P_cargo_cooling = p_cargo
                
            self.P_aux_total = self.P_hotel + self.P_cargo_cooling

            is_nuclear = (self.Ketype == 4) 
            
            if is_nuclear:
                self.P2 += self.P_aux_total
                
            else:
                self.M_aux_mach = (self.P_aux_total * 1.25 * 12.0) / 1000.0
                
                sfc_aux = 0.220 # kg/kWh
                voyage_hours = self.R / (self.V if self.V > 0.1 else 0.1)
                self.W_aux_fuel = (self.P_aux_total * voyage_hours * sfc_aux) / 1000.0
                
                hours_year = 365.0 * 24.0
                
                self.aux_fuel_annual_tonnes = (self.P_aux_total * hours_year * sfc_aux) / 1000.0
                
                price = self.F8 if self.F8 > 1 else 600.0
                self.aux_fuel_price = price
                self.aux_cost_annual = self.aux_fuel_annual_tonnes * price

        except Exception as e:
            self._show_error(f"Aux Calc Error: {e}")

    def _initdata(self, i):
        """Port of Sub_initdata"""
        
        if i == 0:
            self.L1=self.m_Length; self.B=self.m_Breadth; self.D=self.m_Depth; self.T=self.m_Draught; self.C=self.m_Block
            
            self.R=self.m_Range; self.V=self.m_Speed; self.N1=self.m_Erpm; self.N2=self.m_Prpm; self.V7=self.m_Voyages
            self.D1=self.m_Seadays; self.F8=self.m_Fuel; self.I=self.m_Interest; self.N=int(self.m_Repay)
            self.ship_life=int(self.m_ShipLife)
            self.Pdt=self.m_PdtratioV
        else:
            self.m_Length=1.0e-5*int(1.0e5*self.L1+0.5)
            self.m_Breadth=1.0e-6*int(1.0e6*self.B+0.5)
            self.m_Depth=1.0e-6*int(1.0e6*self.D+0.5)
            self.m_Draught=1.0e-6*int(1.0e6*self.T+0.5)
            self.m_Block=1.0e-6*int(1.0e6*self.C+0.5)
            self.m_BvalueV=self.m_Breadth
            self.m_PdtratioV=self.Pdt
            self.m_Repay=float(self.N)
            self.m_ShipLife=float(self.ship_life)
        
        B_safe = self.B if self.B != 0 else 1e-9
        T_safe = self.T if self.T != 0 else 1e-9
        L1_safe = self.L1 if self.L1 != 0 else 1e-9
        
        is_ship_mode = (self.design_mode == 1)
        
        if not self.m_Lbratio or is_ship_mode:
            self.m_LbratioV=1.0e-6*int(1.0e6*L1_safe/B_safe+0.5)
        if not self.m_Bvalue or is_ship_mode:
            self.m_BvalueV=1.0e-6*int(1.0e6*self.B+0.5)
        if not self.m_Btratio or is_ship_mode:
            self.m_BtratioV=1.0e-6*int(1.0e6*B_safe/T_safe+0.5)
        if not self.m_Cbvalue or is_ship_mode:
            self.m_CbvalueV=1.0e-6*int(1.0e6*self.C+0.5)

    # --------------------------------------------------------------------
    # Helpers added for chapter 5 analysis. These centralise calculations
    # that were previously buried inside _outvdu so that batch/plot/battle
    # callers can read the values directly via get_result_value().
    # --------------------------------------------------------------------
    def _compute_cii(self):
        """Compute attained CII, required CII, and rating ratio.

        Stores results on:
          self.attained_cii
          self.required_cii
          self.cii_ratio       (attained / required; ratio of 1.0 == on the
                                C-rating midline before reduction factor)
          self.cii_rating      (string, "A".."E" with descriptor)

        Returns True on success, False if the ship type has no CII reference
        line. Safe to call before _outvdu — no UI side effects.
        """
        # Default-safe values so callers can read these even on failure.
        self.attained_cii = 0.0
        self.required_cii = 0.0
        self.cii_ratio = 0.0
        self.cii_rating = "N/A"

        try:
            ship_data = ShipConfig.get(self.ship_name)
            fuel_data = FuelConfig.get(self.engine_name)

            # Effective carbon factor: include LNG methane slip on the same
            # basis as _cost so CII tracks the same GHG accounting the user
            # selected for the carbon-tax calc.
            effective_carbon = self._effective_carbon_factor(fuel_data)
            if self.engine_name == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                slip_frac = self.m_MethaneSlip / 100.0
                effective_carbon += slip_frac * self.m_GWP_methane

            service_power_kw = self.P1 * 0.7457
            annual_hours = self.D1 * 24.0
            annual_energy_MJ = service_power_kw * annual_hours * 3.6

            lhv = self.m_LHV if self.m_LHV > 0 else 42.7
            eff = fuel_data["Efficiency"]
            if lhv <= 0 or eff <= 0:
                return False

            annual_fuel_tonnes = (annual_energy_MJ / (lhv * eff)) / 1000.0
            annual_co2 = annual_fuel_tonnes * effective_carbon

            annual_dist = self.V * annual_hours

            cii_type = ship_data.get("CII_Type", "DWT")
            if cii_type == "GT":
                # Gross-tonnage proxy used in _outvdu — replicate it here.
                gt_volume = self.L1 * self.B * self.D
                if gt_volume <= 0:
                    return False
                K = 0.2 + 0.02 * math.log10(gt_volume) if gt_volume > 1 else 0.22
                gross_tonnage = K * gt_volume
                capacity = gross_tonnage
            else:
                capacity = self.W1
            if capacity < 1.0:
                capacity = 1.0

            if annual_dist <= 0:
                return False

            self.attained_cii = (annual_co2 * 1_000_000) / (capacity * annual_dist)

            a = ship_data.get("CII_a", 0.0)
            c = ship_data.get("CII_c", 0.0)
            if a <= 0:
                return False

            reduction_factor = 0.05  # Year 2023 basis
            self.required_cii = (a * (capacity ** -c)) * (1.0 - reduction_factor)
            if self.required_cii <= 0:
                return False

            self.cii_ratio = self.attained_cii / self.required_cii
            r = self.cii_ratio
            if   r < 0.83: self.cii_rating = "A (Major Superior)"
            elif r < 0.94: self.cii_rating = "B (Minor Superior)"
            elif r <= 1.06: self.cii_rating = "C (Compliant)"
            elif r < 1.19: self.cii_rating = "D (Minor Inferior)"
            else:           self.cii_rating = "E (Inferior)"
            return True
        except Exception:
            return False

    def _capture_volume_budget(self):
        """Snapshot the post-convergence volume budget for CSV export.

        Reads the same numbers _solve_volume_limit / _get_volume_status use
        but stores them in fields with stable names so the result dropdowns
        can pick them up. Safe to call repeatedly.
        """
        try:
            ship_data = ShipConfig.get(self.ship_name)
            fuel_data = FuelConfig.get(self.engine_name)

            vol_hull = self.L1 * self.B * self.D * self.C
            vol_avail = vol_hull * ship_data.get("Profile_Factor", 1.0)

            # Cargo volume (mirrors _get_volume_status).
            if self.design_mode == 2:
                vol_cargo = self.m_TEU * 33.0
            elif ship_data.get("Design_Type") == "Volume":
                if ship_data["ID"] == 5:
                    vol_cargo = self.W * 50.0
                else:
                    vol_cargo = self.W / 0.5
            else:
                if self.m_CustomDensity > 0:
                    density = self.m_CustomDensity
                else:
                    density = ship_data.get("Cargo_Density", 1.0)
                vol_cargo = (self.W / density) * 1.10  # 10% stowage factor

            # Fuel volume from RAW fuel mass (not tank-inclusive).
            raw_mass = getattr(self, 'raw_fuel_mass', 0.0) or 0.0
            if raw_mass > 0 and fuel_data["Density"] > 0:
                vol_fuel = (raw_mass * 1000.0) / fuel_data["Density"] * fuel_data["VolFactor"]
            else:
                vol_fuel = 0.0

            vol_mach = (self.P2 * 0.7457) * 0.4
            lightship = (getattr(self, 'M1', 0.0) +
                         getattr(self, 'M2', 0.0) +
                         getattr(self, 'M3', 0.0))
            vol_stores = lightship * 0.05

            vol_req = vol_cargo + vol_fuel + vol_mach + vol_stores
            ratio = vol_req / (vol_avail if vol_avail > 0 else 1.0)

            self.vol_cargo = vol_cargo
            self.vol_fuel = vol_fuel
            self.vol_mach = vol_mach
            self.vol_stores = vol_stores
            self.vol_avail = vol_avail
            self.vol_required = vol_req
            self.vol_utilisation_pct = ratio * 100.0

            # Fuel volume as percent of bare hull volume (matches _outvdu).
            if vol_hull > 0 and vol_fuel > 0:
                self.fuel_vol_pct_hull = (vol_fuel / vol_hull) * 100.0
            else:
                self.fuel_vol_pct_hull = 0.0
            return True
        except Exception:
            self.vol_cargo = self.vol_fuel = self.vol_mach = 0.0
            self.vol_stores = self.vol_avail = self.vol_required = 0.0
            self.vol_utilisation_pct = 0.0
            self.fuel_vol_pct_hull = 0.0
            return False
