"""Static configuration tables for the ship design solver.

Fuel/engine properties, ship-type constants, resistance-method metadata and
the empirical dimensional bases.  Pure data - no Qt, no solver state.
"""


class FuelConfig:
    """
    Central database for fuel properties.
    Replaces empirical constants with physics-based density/energy values.
    Sources: 
      - IMO 4th GHG Study (Carbon Factors)
      - MAN Energy Solutions (Ammonia/H2 Engine masses)
      - Corvus Energy (Battery densities)
    """
    DATA = {
        "Direct diesel": {
            "LHV": 42.7,       # Standard Marine Diesel Oil
            "Density": 850.0,  # kg/m3
            "Efficiency": 0.50,# Slow speed 2-stroke diesel (Very efficient)
            "TankFactor": 1.10,# Steel tanks are structurally integrated (light penalty)
            "VolFactor": 1.02, # Frames/structure take little space
            "Carbon": 3.206,   # tCO2 per tonne fuel (MDO)
            "Machinery": 14.0, # kg/kW (Heavy block, crankshaft)
            "MaintenancePct": 0.035, # Slow-speed 2-stroke; mature, well-spared (% of S0/yr)
            "StructureFactor": 1.00, # Baseline hull steel - reference case
            "OutfitFactor": 1.00,    # Baseline outfit - reference case
            "IsNuclear": False
        },
        "Geared diesel": {
            "LHV": 42.7,
            "Density": 850.0,
            "Efficiency": 0.45,# Higher RPM = Lower thermal eff + Gearbox losses
            "TankFactor": 1.10,
            "VolFactor": 1.02,
            "Carbon": 3.206,
            "Machinery": 11.0, # Medium speed engines are lighter per kW
            "MaintenancePct": 0.045, # Adds gearbox + medium-speed engine wear (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Steam turbines": {
            "LHV": 40.0,       # HFO (Heavy Fuel Oil)
            "Density": 980.0,  # Very dense
            "Efficiency": 0.33,# Rankine cycle limit
            "TankFactor": 1.05,# Heating coils add slight weight
            "VolFactor": 1.02,
            "Carbon": 3.114,   # HFO Carbon factor
            "Machinery": 9.0,  # Turbines are light; Boilers are the heavy part
            "MaintenancePct": 0.030, # Mature; main wear is boiler tubes (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Nuclear SMR": {
            "LHV": 0.0,
            "Density": 0.0,
            "Efficiency": 0.35,
            "TankFactor": 0.0,
            "VolFactor": 0.0,
            "Carbon": 0.0,
            "Machinery": 20.0, # Scaling factor (Base mass of ~2000t covers the reactor)
            # Machinery maintenance % applied to S0 (reactor capex). Set
            # deliberately low because (a) SMR service intervals are long
            # and (b) the dominant recurring nuclear cost — periodic core
            # replacement — is already amortised separately into H7 via
            # annual_core_cost. Applying a flat 4% to reactor capex would
            # double-count and inflate OPEX by an order of magnitude.
            # Reference: civilian nuclear plant non-fuel O&M is ~1-2%
            # of reactor capex per year (IAEA, EPRI benchmarks).
            "MaintenancePct": 0.015,
            # Hull steel penalty: reinforced reactor-compartment subdivision,
            # double-wall collision/grounding protection on both sides of the
            # compartment, dedicated cofferdams. ~8% added to M1 is consistent
            # with NS Savannah as-built data and ABS Advisory on Nuclear Power
            # design guidance for civilian merchant nuclear ships.
            "StructureFactor": 1.08,
            # Outfit penalty: shielded control room, redundant safety I&C,
            # radiation monitoring, specialised HVAC for the reactor
            # compartment. ~4% on M2 matches typical naval-architecture
            # estimates for nuclear merchant outfit (Gravina et al., 2012).
            "OutfitFactor": 1.04,
            "IsNuclear": True
        },
        "Methanol (ICE)": {
            "LHV": 19.9,       # Low Energy Density (Alcohol)
            "Density": 792.0,  # Liquid at room temp
            "Efficiency": 0.48,# Similar to Diesel ICE
            "TankFactor": 1.20,# Tanks need special coatings but aren't pressure vessels
            "VolFactor": 1.15, # Cofferdams required for safety
            "Carbon": 1.375,   # Chemical carbon content. (Set to 0.0 for "Green Methanol")
            "Machinery": 15.0, # Slightly heavier engine block (compression ratio)
            "MaintenancePct": 0.040, # Diesel-like with newer fuel handling (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Hydrogen (ICE)": {
            "LHV": 120.0,      # High Energy
            "Density": 71.0,   # Liquid H2
            "Efficiency": 0.38,# Combustion is less efficient than Fuel Cell (0.50)
            "TankFactor": 8.0, # Still needs massive cryogenic tanks
            "VolFactor": 3.0,  
            "Carbon": 0.0,     
            "Machinery": 15.0, # LIGHTER than Fuel Cell (No heavy stack/batteries)
            "MaintenancePct": 0.055, # Cryogenic handling, tighter inspection (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        
        "LNG (Dual Fuel)": {
            "LHV": 50.0,       # Higher energy than diesel!
            "Density": 450.0,  # Light liquid
            "Efficiency": 0.48,# Very efficient engines
            "TankFactor": 1.8, # Cryogenic tanks (heavy but mature tech)
            "VolFactor": 1.9,  # Insulation takes space
            "Carbon": 2.75,    # Lower carbon than diesel, but not zero
            "Machinery": 16.0, # Heavy: Engine + Gas Valve Unit + Vaporizers
            "MaintenancePct": 0.045, # Cryogenic + gas-handling adds complexity (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Hydrogen (Fuel Cell)": {
            "LHV": 120.0,      # Highest energy per kg
            "Density": 71.0,   # Liquid H2 (-253C)
            "Efficiency": 0.50,# PEM Fuel Cell system efficiency
            "TankFactor": 8.0, # CRITICAL: Cryogenic tanks weigh 4-5x the fuel they hold
            "VolFactor": 3.0,  # CRITICAL: Insulation thickness triples the volume
            "Carbon": 0.0,
            "Machinery": 18.0, # HEAVIER than Diesel: Stack + Compressors + Humidifiers + Radiators
            "MaintenancePct": 0.060, # Stack replacement, emerging tech (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Ammonia (Combustion)": {
            "LHV": 18.6,       # Low energy density
            "Density": 682.0,  # Liquid (-33C)
            "Efficiency": 0.46,# Ammonia burns slow; slightly lower eff than Diesel
            "TankFactor": 1.4, # Type C tanks (Pressure vessels) are heavy steel
            "VolFactor": 1.4,  # Cylindrical tanks waste hull space
            "Carbon": 0.0,     # Zero Carbon molecule
            "Machinery": 16.0, # Diesel engine + massive SCR catalyst system + Scrubber
            "MaintenancePct": 0.050, # SCR catalyst service, toxicity handling (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        },
        "Electric (Battery)": {
            "LHV": 0.6,        # PACK Level Density (approx 160 Wh/kg)
            "Density": 2000.0, # Battery packs are dense solids
            "Efficiency": 0.92,# Battery-to-Shaft efficiency
            "TankFactor": 1.0, # "Fuel" mass is the battery mass.
            "VolFactor": 1.0,  # Packs are modular blocks
            "Carbon": 0.0,
            "Machinery": 8.0,  # Electric Motors are incredibly light
            "MaintenancePct": 0.025, # Few moving parts; cell replacement is a separate capex cycle (% of S0/yr)
            "StructureFactor": 1.00,
            "OutfitFactor": 1.00,
            "IsNuclear": False
        }
    }

    @staticmethod
    def get(name):
        return FuelConfig.DATA.get(name, FuelConfig.DATA["Direct diesel"])


# Per-fuel default market prices ($/tonne, mid-2020s figures). Single
# source of truth: BattleFuelConfigDialog uses these to pre-fill its
# per-engine table, and _on_fuel_changed uses them to auto-populate
# the main fuel-price field whenever the engine dropdown changes —
# fixing the silent mismatch where direct calc kept a stale global
# price (e.g. $625 for everything) while battle mode swapped to the
# fuel-appropriate value behind the scenes.
DEFAULT_FUEL_PRICE = {
    "Direct diesel":         650.0,    # MGO/MDO
    "Geared diesel":         650.0,
    "Steam turbines":        500.0,    # HFO
    "Nuclear SMR":             0.0,    # No fuel cost (reactor cost handles it)
    "Methanol (ICE)":        500.0,    # Grey methanol
    "Hydrogen (ICE)":       4000.0,    # Grey/blue H2 mid-range
    "LNG (Dual Fuel)":       700.0,
    "Hydrogen (Fuel Cell)": 4000.0,
    "Ammonia (Combustion)":  700.0,    # Grey ammonia
    "Electric (Battery)":    150.0,    # Pack-equivalent grid energy
}

class ShipConfig:
    DATA = {
        "Tanker": {
            "ID": 1,
            "Steel_K1": 0.032,
            "Outfit_Intercept": 0.37, "Outfit_Slope": 1765.0,
            "Stability_Factor": 0.63,
            "Design_Type": "Deadweight",
            "Profile_Factor": 1.10,
            "Cargo_Density": 0.85,
            "EEDI_a": 1218.80, "EEDI_c": 0.488, "EEDI_Enabled": True, "EEDI_Type": "DWT",
            "CII_a": 5247.0, "CII_c": 0.610, "CII_Type": "DWT" 
        },
        "Bulk carrier": {
            "ID": 2,
            "Steel_K1": 0.032,
            "Outfit_Intercept": 0.32, "Outfit_Slope": 1765.0,
            "Stability_Factor": 0.57,
            "Design_Type": "Deadweight",
            "Profile_Factor": 1.15,
            "Cargo_Density": 1.50,
            "EEDI_a": 961.79, "EEDI_c": 0.477, "EEDI_Enabled": True, "EEDI_Type": "DWT",
            "CII_a": 4745.0, "CII_c": 0.622, "CII_Type": "DWT"
        },
        "Cargo vessel": {
            "ID": 3,
            "Steel_K1": 0.034,
            "Outfit_Intercept": 0.41, "Outfit_Slope": 0.0,
            "Stability_Factor": 0.62,
            "Design_Type": "Deadweight",
            "Profile_Factor": 1.30,
            "Cargo_Density": 0.60,
            "EEDI_a": 107.48, "EEDI_c": 0.216, "EEDI_Enabled": True, "EEDI_Type": "DWT",
            "CII_a": 588.0, "CII_c": 0.216, "CII_Type": "DWT" 
        },
        "Container Ship": {
            "ID": 4,
            "Steel_K1": 0.036,
            "Outfit_Intercept": 0.45, "Outfit_Slope": 0.0,
            "Stability_Factor": 0.60,
            "Design_Type": "Volume",
            "Profile_Factor": 1.40,
            "Cargo_Density": 0.0,
            "EEDI_a": 174.22, "EEDI_c": 0.201, "EEDI_Enabled": True, "EEDI_Type": "DWT",
            "CII_a": 1984.0, "CII_c": 0.489, "CII_Type": "DWT"
        },
        "Cruise Ship": {
            "ID": 5,
            "Steel_K1": 0.045,
            "Outfit_Intercept": 0.80, "Outfit_Slope": 0.0,
            "Stability_Factor": 0.70,
            "Design_Type": "Volume",
            "Profile_Factor": 2.40,
            "Cargo_Density": 0.0,
            "EEDI_a": 170.84, "EEDI_c": 0.214, "EEDI_Enabled": True, "EEDI_Type": "GT",
            "CII_a": 930.0, "CII_c": 0.383, "CII_Type": "GT" # Uses GT
        },
        "Superyacht": {
            "ID": 6,
            "Steel_K1": 0.042,
            "Outfit_Intercept": 0.90, "Outfit_Slope": 0.0,
            "Stability_Factor": 0.68,
            "Design_Type": "Volume",
            "Profile_Factor": 2.20,
            "Cargo_Density": 0.0,
            "EEDI_a": 170.84, "EEDI_c": 0.214, "EEDI_Enabled": True, "EEDI_Type": "GT",
            "CII_a": 930.0, "CII_c": 0.383, "CII_Type": "GT"
        }
    }

    @staticmethod
    def get(name):
        return ShipConfig.DATA.get(name, ShipConfig.DATA["Tanker"])


class ResistanceMethodConfig:
    """
    Central registry of resistance prediction methods.

    Mirrors the dict-of-dicts pattern used by FuelConfig and ShipConfig.
    Adding a new method (e.g. Hollenbach) requires:
      1. A new entry here with display_name / valid ranges / description
      2. A new _calc_pe_<method>() function on ShipDesViewWidget
      3. One line in the dispatcher table inside _power()

    No other structural changes are needed for additional methods.

    Each entry stores:
      - display_name:              text shown in the UI dropdown
      - is_legacy:                 True only for Taylor (the legacy reference)
      - requires_advanced_params:  True if the Holtrop-style hull-form panel
                                   should be shown when this method is active
      - valid_fn_range:            (min, max) Froude numbers where the method
                                   is considered reliable
      - valid_cb_range:            (min, max) block coefficient validity range
      - description:               multi-line tooltip / readme text
    """
    DATA = {
        "Taylor's Series (Legacy)": {
            "display_name": "Taylor's Series (Legacy)",
            "is_legacy": True,
            "requires_advanced_params": False,
            # Taylor uses V0 = V/sqrt(3.28*L) in roughly 0.35-0.90.
            # Converting V0 -> Fn via Fn = V0/sqrt(3.28*g/g) ~= V0/sqrt(3.28*0.3048)
            # gives approximate Fn limits 0.10 - 0.45.
            "valid_fn_range": (0.10, 0.45),
            "valid_cb_range": (0.55, 0.85),
            "description": (
                "Taylor's Standard Series (D.W. Taylor, 1933 / Gertler 1954 re-fit).\n"
                "Polynomial regression on residuary resistance for displacement\n"
                "merchant hull forms. Default and reference method - used for\n"
                "validation against the legacy C++ implementation."
            ),
        },
        "Holtrop-Mennen (1984)": {
            "display_name": "Holtrop-Mennen (1984)",
            "is_legacy": False,
            "requires_advanced_params": True,
            # Holtrop is documented as valid up to Fn ~ 0.80 (1984 update).
            # Lower bound ~ 0.05; below that the wave term is negligible anyway.
            "valid_fn_range": (0.05, 0.80),
            "valid_cb_range": (0.55, 0.85),
            "description": (
                "Holtrop & Mennen (1982) statistical resistance method, with\n"
                "wave-resistance refinements from Holtrop (1984).\n"
                "Decomposes total resistance into friction + form, appendage,\n"
                "wave, bulb, transom, and model-ship correlation components.\n"
                "Requires hull-form parameters (LCB, iE, CM, CWP, CSTERN);\n"
                "sensible defaults are auto-derived from main dimensions."
            ),
        },
    }

    @staticmethod
    def get(name):
        return ResistanceMethodConfig.DATA.get(
            name, ResistanceMethodConfig.DATA["Taylor's Series (Legacy)"]
        )


class EmpiricalBasisConfig:
    """
    Selectable empirical basis for the dimensional regressions that drive
    the initial-guess and convergence loop.

    Two bases are provided:

    - "Legacy (Watson/Gilfillan 1977)": the historical regressions that
      have been embedded in this tool since the original C++/BASIC
      versions.  Coefficients here are duplicated from the per-Kstype
      hardcoded paths so the legacy code path can read from the same
      source if desired.

    - "Japan Dataset (2020s)": coefficients fitted to the curated
      Japanese newsletter dataset of ~1,400 modern merchant ships.
      Only Bulk carrier, Tanker and Container Ship had enough data
      (n >= 30) to fit; Cruise Ship, Cargo vessel and Superyacht fall
      back to legacy automatically via .get().  Length data is in
      Lbp (LOA scaled by 0.96 in the offline fitting script).

    Functional forms (per ship type):
        L = L_a + L_b * (DWT / L_c)^(1/3)
        B = LB_m * L + LB_c
        D = LD_m * L + LD_c
        T = DT_m * D + DT_c

    A coefficient may be None when the underlying fit had R^2 below the
    reliability threshold (currently MIN_R2 = 0.50 in the fitting
    script).  Consumers must treat None as "fall back to legacy formula
    for this single coefficient pair".

    Mirrors the dict-of-dicts pattern used by FuelConfig, ShipConfig and
    ResistanceMethodConfig so that adding new bases (e.g. a UK-fleet
    fit) is purely additive.
    """

    DATA = {
        "Legacy (Watson/Gilfillan 1977)": {
            "Tanker": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.8,
                "LB_m": None, "LB_c": None,    # use legacy piecewise B(L)
                "LD_m": None, "LD_c": None,    # use legacy L1/13.5
                "DT_m": None, "DT_c": None,    # use legacy 0.78*D
            },
            "Bulk carrier": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.8,
                "LB_m": None, "LB_c": None,
                "LD_m": None, "LD_c": None,    # use legacy L1/11.75
                "DT_m": None, "DT_c": None,    # use legacy 0.7*D
            },
            "Container Ship": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.7,
                "LB_m": None, "LB_c": None,
                "LD_m": None, "LD_c": None,    # use legacy L1/13.5
                "DT_m": None, "DT_c": None,    # use legacy 0.72*D
            },
            "Cargo vessel": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.7,
                "LB_m": None, "LB_c": None,
                "LD_m": None, "LD_c": None,
                "DT_m": None, "DT_c": None,
            },
            "Cruise Ship": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.7,
                "LB_m": None, "LB_c": None,
                "LD_m": None, "LD_c": None,
                "DT_m": None, "DT_c": None,
            },
            "Superyacht": {
                "L_a": 0.0, "L_b": 5.0, "L_c": 0.7,
                "LB_m": None, "LB_c": None,
                "LD_m": None, "LD_c": None,
                "DT_m": None, "DT_c": None,
            },
        },
        "Japan Dataset (2020s)": {
            # Generated by fit_japan_dataset.py from
            # boat_database_cleaned_final_V10_0.csv; LOA scaled to Lbp
            # by 0.96 before fitting.  R^2 of each fit is recorded
            # in the offline summary CSV.
            "Bulk carrier": {
                "L_a": 16.698,  "L_b": 4.6063, "L_c": 1.0,    # R^2 0.974, n=456
                "LB_m": 0.1660, "LB_c": -0.304,                # R^2 0.843, n=461
                "LD_m": 0.0796, "LD_c": 2.675,                 # R^2 0.743, n=448
                "DT_m": 0.7561, "DT_c": -0.512,                # R^2 0.843, n=449
            },
            "Tanker": {
                "L_a": 47.731,  "L_b": 4.1836, "L_c": 1.0,    # R^2 0.863, n=280
                "LB_m": 0.1868, "LB_c": -1.821,                # R^2 0.971, n=282
                "LD_m": 0.0852, "LD_c": 3.161,                 # R^2 0.761, n=280
                "DT_m": 0.7851, "DT_c": -2.260,                # R^2 0.657, n=281
            },
            "Container Ship": {
                "L_a": -78.472, "L_b": 8.4696, "L_c": 1.0,    # R^2 0.951, n=85
                "LB_m": 0.1000, "LB_c": 13.784,                # R^2 0.916, n=82
                "LD_m": 0.0696, "LD_c": 4.396,                 # R^2 0.750, n=85
                "DT_m": None,   "DT_c": None,                  # R^2 0.395 < 0.50, fall back
            },
            # Cargo vessel, Cruise Ship, Superyacht: insufficient data,
            # falls back to Legacy automatically via .get().
        },
    }

    @staticmethod
    def get(basis, ship_type):
        """Return coefficient dict for (basis, ship_type).

        If the ship_type isn't present in the chosen basis, fall back to
        the Legacy basis for that ship type.  If even that's missing,
        return the Legacy Tanker entry as a last resort.
        """
        b = EmpiricalBasisConfig.DATA.get(
            basis,
            EmpiricalBasisConfig.DATA["Legacy (Watson/Gilfillan 1977)"],
        )
        if ship_type in b:
            return b[ship_type]
        legacy = EmpiricalBasisConfig.DATA["Legacy (Watson/Gilfillan 1977)"]
        return legacy.get(ship_type, legacy["Tanker"])
