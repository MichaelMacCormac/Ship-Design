import sys
import math
import csv
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QTextEdit, QPushButton, QVBoxLayout, QGroupBox, QRadioButton,
    QHBoxLayout, QMessageBox, QFileDialog, QLabel, QGridLayout,
    QApplication, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QInputDialog, QListWidget, QAbstractItemView, QScrollArea
)

from PySide6.QtCore import Qt

try:
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
        NavigationToolbar2QT as NavigationToolbar,
    )
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d import Axes3D 
except ImportError:
    print("Matplotlib not found. Plotting will be disabled.")
    print("Please install it: pip install matplotlib")
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None


# Pretty axis-label lookup — maps internal dropdown keys to publication-quality labels.
LABEL_MAP = {
    # X-axis (RANGE_DEFAULTS keys)
    "Speed(knts)":         "Service Speed (knots)",
    "Block Co.":           "Block Coefficient (Cb)",
    "Cargo deadweight(t)": "Cargo Deadweight (t)",
    "TEU Capacity":        "TEU Capacity",
    "L/B Ratio":           "Length / Beam Ratio",
    "B(m)":                "Beam (m)",
    "B/T Ratio":           "Beam / Draught Ratio",
    "Reactor Cost ($/kW)": "Reactor Cost ($/kW)",
    "Range (nm)":          "Range (nautical miles)",
    "Fuel Cost ($/t)":     "Fuel Cost ($/tonne)",
    "Interest Rate (%)":   "Interest Rate (%)",
    "Carbon Tax ($/t)":    "Carbon Tax ($/tonne CO\u2082)",
    "Sea days/year":       "Sea Days per Year",
    "Air Lub Eff. (%)":    "Air-Lubrication Saving (%)",
    "Wind Power Sav. (%)": "Wind-Assist Saving (%)",
    "Methane Slip (%)":    "Methane Slip (%)",
    # Y-axis (output combo boxes)
    "RFR($/tonne or $/TEU)": "Required Freight Rate",
    "BuildCost(M$)":         "Build Cost (M$)",
    "AnnualFuelCost(M$)":    "Annual Fuel Cost (M$)",
    "AnnualCarbonTax(M$)":   "Annual Carbon Tax (M$)",
    "AnnualisedCAPEX(M$)":   "Annualised CAPEX (M$)",
    "AnnualOPEX(M$)":        "Annual OPEX (M$)",
    "Lbp(m)":                "Length B.P. (m)",
    "D(m)":                  "Depth (m)",
    "T(m)":                  "Draught (m)",
    "CB":                    "Block Coefficient (Cb)",
    "Displacement(t)":       "Displacement (t)",
    "CargoDW(t)":            "Cargo Deadweight (t)",
    "TotalDW(t)":            "Total Deadweight (t)",
    "ServicePower(kW)":      "Service Power (kW)",
    "InstalledPower(kW)":    "Installed Power (kW)",
    "EEDI(gCO2/t.nm)":       "Attained EEDI (g CO\u2082 / t\u00B7nm)",
    "AttainedCII":           "Attained CII",
    "FuelVolume(m3)":        "Fuel Volume (m\u00B3)",
    "FuelVol%Hull":          "Fuel Volume / Hull (%)",
    "VolCargo(m3)":          "Cargo Volume (m\u00B3)",
    "VolFuel(m3)":           "Fuel Volume (m\u00B3)",
    "VolMachinery(m3)":      "Machinery Volume (m\u00B3)",
    "VolStores(m3)":         "Stores Volume (m\u00B3)",
    "VolUtilisation%":       "Volume Utilisation (%)",
}


def pretty_label(key: str) -> str:
    """Return a publication-quality label for an internal dropdown key."""
    return LABEL_MAP.get(key, key)


def mpl_safe(s: str) -> str:
    """Escape characters that trigger matplotlib's mathtext mode.

    matplotlib treats '$...$' as TeX math delimiters: text between two
    unescaped dollar signs is rendered italic, whitespace is collapsed,
    and the '$' characters themselves are hidden. Several axis labels
    here carry a literal '$' in unit strings (e.g. '$/TEU',
    '$/tonne CO2'), which produced titles like
    'Required Freight Rate (/TEU)vsCarbonTax(/tonne CO2)'. Escaping every
    '$' as '\\$' tells matplotlib to render a literal dollar instead.
    """
    return s.replace("$", r"\$")


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


class GraphWindow(QWidget):
    """
    Displays either a 2D line graph or a 3D wireframe plot.
    Includes interactive matplotlib toolbar (zoom/pan/save) and a
    high-resolution PNG export button.
    """
    def __init__(self, x_data, y_data, z_data=None, x_label="", y_label="", z_label="", title=""):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(900, 720)

        # Convert internal dropdown codes to readable labels, then escape
        # any '$' so matplotlib doesn't enter mathtext mode (see mpl_safe).
        x_label = mpl_safe(pretty_label(x_label))
        y_label = mpl_safe(pretty_label(y_label))
        z_label = mpl_safe(pretty_label(z_label))
        # Title comes pre-formatted from caller (e.g. "RFR(...) vs Speed");
        # it's not a LABEL_MAP key, so just escape '$' for the figure
        # title without remapping. Window title (Qt) is unaffected.
        mpl_title = mpl_safe(title)

        layout = QVBoxLayout(self)
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.fig.patch.set_facecolor('white')
        canvas = FigureCanvas(self.fig)

        if z_data is not None:
            ax = self.fig.add_subplot(111, projection='3d')
            ax.plot_wireframe(x_data, y_data, z_data, color='#1f4e79', linewidth=0.6)
            ax.set_xlabel(x_label, fontsize=11, labelpad=10)
            ax.set_ylabel(y_label, fontsize=11, labelpad=10)
            ax.set_zlabel(z_label, fontsize=11, labelpad=10)
        else:
            ax = self.fig.add_subplot(111)
            if x_data is not None and y_data is not None:
                ax.plot(x_data, y_data, marker='o', linestyle='-',
                        color='#1f4e79', markersize=6, linewidth=2)
            ax.set_xlabel(x_label, fontsize=11)
            ax.set_ylabel(y_label, fontsize=11)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        ax.set_title(mpl_title, fontsize=13, fontweight='bold', pad=15)
        self.fig.tight_layout()

        # Matplotlib's built-in toolbar gives free zoom / pan / save / home
        layout.addWidget(NavigationToolbar(canvas, self))
        layout.addWidget(canvas)

        # Dedicated one-click high-res PNG export
        btn_save = QPushButton("Save as PNG (300 dpi)")
        btn_save.clicked.connect(self._save_png)
        layout.addWidget(btn_save)

    def _save_png(self):
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Graph", "graph.png",
            "PNG Image (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if fileName:
            self.fig.savefig(fileName, dpi=300, bbox_inches='tight', facecolor='white')

class RouteDialog(QDialog):
    """
    Popup to define route segments and calculate operational profile.
    """
    def __init__(self, parent=None, current_speed=15.0):
        super().__init__(parent)
        self.setWindowTitle("Voyage & Route Profiler")
        self.resize(600, 500)
        self.design_speed = current_speed # The ship's max speed
        
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(["Custom", "Asia-Europe (Suez)", "Asia-US East (Panama)", "Southampton to Singapore", "Transatlantic"])
        top_layout.addWidget(QLabel("Route Preset:"))
        top_layout.addWidget(self.combo_preset)
        
        top_layout.addWidget(QLabel("Days in Service/Year:"))
        self.edit_days_year = QLineEdit("355") # Allow 10 days maintenance
        self.edit_days_year.setFixedWidth(50)
        top_layout.addWidget(self.edit_days_year)
        
        top_layout.addWidget(QLabel("Port Days/Voyage:"))
        self.edit_port_days = QLineEdit("3.0")
        self.edit_port_days.setFixedWidth(50)
        top_layout.addWidget(self.edit_port_days)
        
        layout.addLayout(top_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Segment Name", "Distance (nm)", "Speed Profile (%)"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        btn_box = QHBoxLayout()
        btn_add = QPushButton("Add Segment")
        btn_del = QPushButton("Remove Segment")
        btn_add.clicked.connect(self.add_row)
        btn_del.clicked.connect(self.remove_row)
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_del)
        btn_box.addStretch()
        layout.addLayout(btn_box)
        
        result_group = QGroupBox("Projected Annual Performance")
        res_layout = QGridLayout()
        
        self.lbl_total_dist = QLabel("0 nm")
        self.lbl_avg_power = QLabel("100%")
        self.lbl_voyages = QLabel("0")
        self.lbl_seadays = QLabel("0")
        
        res_layout.addWidget(QLabel("Total Distance:"), 0, 0); res_layout.addWidget(self.lbl_total_dist, 0, 1)
        res_layout.addWidget(QLabel("Avg Power Factor:"), 0, 2); res_layout.addWidget(self.lbl_avg_power, 0, 3)
        res_layout.addWidget(QLabel("<b>Voyages/Year:</b>"), 1, 0); res_layout.addWidget(self.lbl_voyages, 1, 1)
        res_layout.addWidget(QLabel("<b>Sea Days/Year:</b>"), 1, 2); res_layout.addWidget(self.lbl_seadays, 1, 3)
        
        result_group.setLayout(res_layout)
        layout.addWidget(result_group)
        
        dlg_btns = QHBoxLayout()
        self.btn_apply = QPushButton("Apply to Analysis")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        dlg_btns.addWidget(self.btn_apply)
        dlg_btns.addWidget(self.btn_cancel)
        layout.addLayout(dlg_btns)
        
        self.combo_preset.currentIndexChanged.connect(self.load_preset)
        self.table.itemChanged.connect(self.recalc_stats)
        self.edit_days_year.editingFinished.connect(self.recalc_stats)
        self.edit_port_days.editingFinished.connect(self.recalc_stats)
        
        self.load_preset() # Load default

    def add_row(self, name="New Segment", dist="1000", speed="100"):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(dist))
        self.table.setItem(row, 2, QTableWidgetItem(speed))
        self.recalc_stats()

    def remove_row(self):
        cr = self.table.currentRow()
        if cr >= 0: 
            self.table.removeRow(cr)
            self.recalc_stats()

    def load_preset(self):
        """Loads predefined routes"""
        preset = self.combo_preset.currentText()
        self.table.setRowCount(0) # Clear
        
        if preset == "Asia-Europe (Suez)":
            self.add_row("Open Ocean (East)", "8000", "100")
            self.add_row("Canal Transit (Slow)", "100", "10") # 10% speed in canal
            self.add_row("Mediterranean/Coastal", "3000", "85") # Slower in busy waters
        elif preset == "Asia-US East (Panama)":
            self.add_row("Pacific Ocean", "9500", "100")
            self.add_row("Panama Transit", "50", "10")
            self.add_row("US East Coast", "1500", "90")
        elif preset == "Transatlantic":
            self.add_row("North Atlantic", "3500", "100")
            self.add_row("ECA Zone (Slow/Clean)", "500", "70")
        elif preset == "Southampton to Singapore":
            self.add_row("To Suez", "3300", "100")
            self.add_row("Canal Transit (Slow)", "100", "10")
            self.add_row("To Singapore", "8000", "100")
        elif preset == "Custom":
            self.add_row("Segment 1", "1000", "100")

    def recalc_stats(self):
        """Calculates the cubic power factor and voyage times."""
        try:
            total_dist = 0.0
            total_time_hours = 0.0
            weighted_power_sum = 0.0
            
            design_v = float(self.design_speed)
            if design_v <= 0: design_v = 15.0
            
            rows = self.table.rowCount()
            for r in range(rows):
                try:
                    d = float(self.table.item(r, 1).text())
                    spd_pct = float(self.table.item(r, 2).text()) / 100.0
                except:
                    continue # Skip bad rows
                
                if spd_pct <= 0.01: spd_pct = 0.01 # Avoid div by zero
                
                real_speed = design_v * spd_pct
                segment_time = d / real_speed # Hours
                
                total_dist += d
                total_time_hours += segment_time
                
                power_factor = spd_pct ** 3
                weighted_power_sum += (power_factor * segment_time)

            if total_time_hours == 0: return

            self.avg_power_factor = weighted_power_sum / total_time_hours
            
            port_days = float(self.edit_port_days.text())
            avail_days = float(self.edit_days_year.text())
            
            sea_days_per_voyage = total_time_hours / 24.0
            total_voyage_days = sea_days_per_voyage + port_days
            
            if total_voyage_days == 0: voyages = 0
            else: voyages = avail_days / total_voyage_days
            
            total_sea_days_year = voyages * sea_days_per_voyage
            
            self.lbl_total_dist.setText(f"{total_dist:,.0f} nm")
            self.lbl_avg_power.setText(f"{self.avg_power_factor:.3f}")
            self.lbl_voyages.setText(f"{voyages:.2f}")
            self.lbl_seadays.setText(f"{total_sea_days_year:.1f}")
            
            self.result_data = {
                'voyages': voyages,
                'seadays': total_sea_days_year,
                'power_factor': self.avg_power_factor,
                'range': total_dist
            }
            
        except Exception as e:
            self.lbl_total_dist.setText("Error")

class BattleFuelConfigDialog(QDialog):
    """
    Popup to configure specific economic parameters (Fuel Price, Carbon Tax,
    Carbon Factor) for each engine involved in the Battle Mode.

    Fuel prices and carbon factors are auto-filled per engine from rough
    market figures / FuelConfig respectively, so each fuel arrives with a
    sensible default rather than a single global value.  All three columns
    are editable.  Default fuel prices live at module level
    (DEFAULT_FUEL_PRICE) so the main widget can use the same figures when
    the engine dropdown changes — keeping direct-calc and battle-mode
    consistent.
    """

    def __init__(self, engines, default_fuel_price, default_carbon_tax, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Battle Fuel Inputs")
        self.resize(640, 320)
        self.engines = engines
        self.result_data = {}

        # Coerce the global defaults to floats once so we can fall back to
        # them for any fuel we don't have a hard-coded figure for.
        try:
            global_price = float(default_fuel_price)
        except (TypeError, ValueError):
            global_price = 600.0
        try:
            global_tax = float(default_carbon_tax)
        except (TypeError, ValueError):
            global_tax = 0.0

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Set the specific economic parameters for each selected fuel.\n"
            "Carbon Factor (tCO2 per tonne fuel) overrides the FuelConfig "
            "default for this run only."
        ))

        self.table = QTableWidget(len(engines), 4)
        self.table.setHorizontalHeaderLabels([
            "Engine / Fuel",
            "Fuel Price ($/t)",
            "Carbon Tax ($/tCO2)",
            "Carbon Factor (tCO2/t)",
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        for i, engine in enumerate(engines):
            fuel_data = FuelConfig.get(engine)

            # Engine Name (Read-Only)
            item_name = QTableWidgetItem(engine)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item_name)

            # Per-fuel default price (module-level dict, shared with
            # _on_fuel_changed in the main widget).
            price = DEFAULT_FUEL_PRICE.get(engine, global_price)
            self.table.setItem(i, 1, QTableWidgetItem(f"{price:.1f}"))

            # Carbon tax: zero-carbon fuels get 0 by default since the tax
            # bill is tax * carbon_factor and the factor is 0 anyway —
            # showing 0 here makes the "no tax exposure" case visually
            # obvious.  User can still edit if they want to test
            # sensitivity to a non-zero factor.
            if fuel_data["Carbon"] <= 0.0:
                tax_default = 0.0
            else:
                tax_default = global_tax
            self.table.setItem(i, 2, QTableWidgetItem(f"{tax_default:.1f}"))

            # Carbon Factor — pre-filled from FuelConfig, fully editable.
            cf = fuel_data["Carbon"]
            self.table.setItem(i, 3, QTableWidgetItem(f"{cf:.3f}"))

        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Start Battle")
        btn_cancel = QPushButton("Cancel")

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def accept(self):
        """Validates inputs before closing."""
        for i, engine in enumerate(self.engines):
            try:
                price  = float(self.table.item(i, 1).text())
                tax    = float(self.table.item(i, 2).text())
                carbon = float(self.table.item(i, 3).text())
                if carbon < 0:
                    raise ValueError("Carbon factor must be non-negative.")
                self.result_data[engine] = {
                    'price':  price,
                    'tax':    tax,
                    'carbon': carbon,
                }
            except ValueError as e:
                QMessageBox.critical(
                    self, "Input Error",
                    f"Invalid number entered for {engine}.\n{e}"
                )
                return
        super().accept()

class ShipDesViewWidget(QWidget):
    """
    Replaces CShipDesView.
    This is the main form, holding all UI and logic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

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

        self.graph_window = None # Holds reference to graph window
        self.Kcases = 0 #
        self.Ketype = 1 #
        self.Kstype = 1 #
        self.Kpwrerr = 1 #
        self.CalculatedOk = False #
        self.Ksaved = True #
        self.Savefile = "SDout.txt" #
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
        self.MdfEnable = [False] * 10 #;]

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

        from dialog_outopt import OutoptDialog
        self.outopt_data = OutoptDialog().get_data() # Get defaults

        self.L1 = 0.0; self.B = 0.0; self.D = 0.0; self.T = 0.0; self.C = 0.0
        self.R = 0.0; self.V = 0.0; self.N1 = 0.0; self.N2 = 0.0; self.V7 = 0.0
        self.D1 = 0.0; self.F8 = 0.0; self.I = 0.0; self.N = 0
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

        from dialog_modify import ModifyDialog
        from dialog_readme import ReadmeDialog

        self.dlg_modify = ModifyDialog(self)
        self.dlg_outopt = OutoptDialog(self)
        self.dlg_readme = ReadmeDialog(self)

        self.combo_ship = QComboBox()
        self.combo_ship.addItems(list(ShipConfig.DATA.keys()))
        
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(list(FuelConfig.DATA.keys()))

        # --- NEW: Resistance prediction method selector ---
        # Dropdown sits next to the engine combo. Default is the legacy Taylor's
        # Series so the tool reproduces the original C++ program's outputs.
        # Switching to Holtrop-Mennen (or any future method) reveals an
        # advanced hull-form parameter panel below.
        self.combo_resistance_method = QComboBox()
        self.combo_resistance_method.addItems(list(ResistanceMethodConfig.DATA.keys()))
        self.combo_resistance_method.setCurrentText("Taylor's Series (Legacy)")
        self.combo_resistance_method.setToolTip(
            "Resistance prediction method.\n"
            "Taylor's Series is the legacy default and matches the original\n"
            "C++ tool. Holtrop-Mennen (1984) gives a full component breakdown\n"
            "but requires hull-form parameters."
        )

        # --- NEW: Empirical-basis selector ---
        # Sits next to the resistance method dropdown.  Switches the
        # dimensional regressions (initial L guess, B(L), D(L), T(D))
        # between Watson/Gilfillan 1977 and the Japan-dataset 2020s fits.
        self.combo_basis = QComboBox()
        self.combo_basis.addItems(list(EmpiricalBasisConfig.DATA.keys()))
        self.combo_basis.setCurrentText("Legacy (Watson/Gilfillan 1977)")
        self.combo_basis.setToolTip(
            "Empirical basis for hull dimensional regressions.\n"
            "Legacy uses Watson/Gilfillan 1977 (1970s/80s ship data).\n"
            "Japan Dataset uses regressions fitted to ~1,400 modern\n"
            "merchant ships from the Japan Ship Exporters' Association\n"
            "newsletters (covers Bulk Carrier, Tanker, Container Ship;\n"
            "other types fall back to legacy)."
        )
        
        self.btn_calculate = QPushButton("&Calculate")
        self.btn_save = QPushButton("&Save the output")
        self.check_append = QCheckBox("&Append")
        self.radio_cargo = QRadioButton("Cargo deadweight")
        self.radio_ship = QRadioButton("Ship dimensions") #
        self.radio_teu = QRadioButton("TEU Capacity") # NEW
        self.edit_weight = QLineEdit() #
        self.edit_error = QLineEdit() #
        self.edit_teu = QLineEdit()
        self.edit_teu_weight = QLineEdit()
        self.check_lbratio = QCheckBox("L/B") #
        self.edit_lbratio = QLineEdit() #
        self.check_bvalue = QCheckBox("B") #
        self.edit_bvalue = QLineEdit() #
        self.check_btratio = QCheckBox("B/T") #
        self.edit_btratio = QLineEdit() #
        self.check_cbvalue = QCheckBox("CB") #
        self.edit_cbvalue = QLineEdit() #
        self.check_pdtratio = QCheckBox("Prop.dia. to T ratio") #
        self.edit_pdtratio = QLineEdit() #
        self.edit_length = QLineEdit() #
        self.edit_breadth = QLineEdit() #
        self.edit_draught = QLineEdit() #
        self.edit_depth = QLineEdit() #
        self.edit_block = QLineEdit() #
        self.edit_speed = QLineEdit() #
        self.edit_range = QLineEdit() #
        self.edit_prpm = QLineEdit() #
        self.edit_erpm = QLineEdit() #
        self.check_econom = QCheckBox("Economic analysis required")
        self.edit_voyages = QLineEdit() #
        self.edit_seadays = QLineEdit() #
        self.label_fuel = QLabel("Fuel cost per tonne:")
        self.edit_fuel = QLineEdit() #
        self.label_reactor_cost = QLabel("Reactor Cost ($/kW):") # <-- CHANGED
        self.edit_reactor_cost = QLineEdit()
        self.label_core_life = QLabel("Core Life (years):")
        self.edit_core_life = QLineEdit()
        self.label_decom_cost = QLabel("Decomm. Cost (M$):")
        self.edit_decom_cost = QLineEdit()
        self.edit_interest = QLineEdit() #
        self.edit_repay = QLineEdit() #
        self.text_results = QTextEdit()
        self.text_results.setReadOnly(True)
        self.text_results.setFontFamily("Courier New")
        self.btn_modify = QPushButton("&Modify parameters") #
        self.btn_outopt = QPushButton("&Output options") #

        main_layout = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("Ship type:")) #
        top_bar_layout.addWidget(self.combo_ship)
        top_bar_layout.addWidget(QLabel("Engine type:")) #
        top_bar_layout.addWidget(self.combo_engine)
        top_bar_layout.addWidget(QLabel("Resistance:"))
        top_bar_layout.addWidget(self.combo_resistance_method)
        top_bar_layout.addWidget(QLabel("Basis:"))
        top_bar_layout.addWidget(self.combo_basis)
        top_bar_layout.addWidget(self.btn_calculate)
        top_bar_layout.addWidget(self.check_append)
        left_col.addLayout(top_bar_layout)
        
        input_group = QGroupBox("Input:") #
        input_layout = QFormLayout()
        input_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.radio_cargo)
        radio_layout.addWidget(self.radio_ship)
        radio_layout.addWidget(self.radio_teu) # NEW
        radio_layout.addStretch()
        input_layout.addRow(radio_layout)
        
        dw_layout = QHBoxLayout()
        dw_layout.addWidget(QLabel("Deadweight of cargo (tonnes):")) #
        dw_layout.addWidget(self.edit_weight)
        dw_layout.addWidget(QLabel("Allowable error (%):")) #
        dw_layout.addWidget(self.edit_error)
        input_layout.addRow(dw_layout)
        
        self.layout_teu_container = QWidget() # Wrapper to hide/show the whole row
        teu_layout = QHBoxLayout(self.layout_teu_container)
        teu_layout.setContentsMargins(0, 0, 0, 0) # Remove padding so it fits nicely
        
        self.label_teu_target = QLabel("Target TEU:")
        self.label_teu_weight = QLabel("Avg. Weight/TEU (tonnes):")
        
        teu_layout.addWidget(self.label_teu_target)
        teu_layout.addWidget(self.edit_teu)
        teu_layout.addWidget(self.label_teu_weight)
        teu_layout.addWidget(self.edit_teu_weight)
        
        input_layout.addRow(self.layout_teu_container) # Add the container, not the layout

        constraints_group = QGroupBox("And you can also specify:") #
        constraints_layout = QGridLayout()
        constraints_layout.addWidget(self.check_lbratio, 0, 0)
        constraints_layout.addWidget(self.edit_lbratio, 1, 0)
        constraints_layout.addWidget(self.check_bvalue, 0, 1)
        constraints_layout.addWidget(self.edit_bvalue, 1, 1)
        constraints_layout.addWidget(self.check_btratio, 0, 2)
        constraints_layout.addWidget(self.edit_btratio, 1, 2)
        constraints_layout.addWidget(self.check_cbvalue, 0, 3)
        constraints_layout.addWidget(self.edit_cbvalue, 1, 3)

        self.check_vol_limit = QCheckBox("Enforce Volume Limit")
        self.check_vol_limit.setChecked(True)
        self.check_vol_limit.setToolTip("If checked, dimensions will expand to fit Cargo volume.")
        
        self.label_density = QLabel("Cargo Density (t/m³):")
        self.edit_density = QLineEdit()
        self.edit_density.setFixedWidth(60) 
        self.edit_density.setToolTip("Override density.\n(Ore ~2.5, Grain ~0.75, Oil ~0.85)")
        
        constraints_layout.addWidget(self.check_vol_limit, 2, 0, 1, 2) 
        constraints_layout.addWidget(self.label_density, 2, 2)
        constraints_layout.addWidget(self.edit_density, 2, 3)

        constraints_group.setLayout(constraints_layout)
        input_layout.addRow(constraints_group)
        
        pd_layout = QHBoxLayout()
        pd_layout.addWidget(self.check_pdtratio)
        pd_layout.addWidget(self.edit_pdtratio)
        input_layout.addRow(pd_layout)

        dims_layout = QGridLayout()
        dims_layout.addWidget(QLabel("Length(m):"), 0, 0) #
        dims_layout.addWidget(self.edit_length, 0, 1)
        dims_layout.addWidget(QLabel("Breadth(m):"), 1, 0) #
        dims_layout.addWidget(self.edit_breadth, 1, 1)
        dims_layout.addWidget(QLabel("Draught(m):"), 2, 0) #
        dims_layout.addWidget(self.edit_draught, 2, 1)
        dims_layout.addWidget(QLabel("Depth(m):"), 1, 2) #
        dims_layout.addWidget(self.edit_depth, 1, 3)
        dims_layout.addWidget(QLabel("Block Co.:"), 2, 2) #
        dims_layout.addWidget(self.edit_block, 2, 3)
        input_layout.addRow(dims_layout)

        dims_layout_2 = QGridLayout()
        dims_layout_2.addWidget(QLabel("Speed(knts):"), 0, 0) #
        dims_layout_2.addWidget(self.edit_speed, 0, 1)
        dims_layout_2.addWidget(QLabel("Range(nm):"), 0, 2) #
        dims_layout_2.addWidget(self.edit_range, 0, 3)
        dims_layout_2.addWidget(QLabel("Propeller RPM:"), 1, 0) #
        dims_layout_2.addWidget(self.edit_prpm, 1, 1)
        dims_layout_2.addWidget(QLabel("Engine RPM:"), 1, 2) #
        dims_layout_2.addWidget(self.edit_erpm, 1, 3)
        input_layout.addRow(dims_layout_2)

        input_group.setLayout(input_layout)
        left_col.addWidget(input_group)

        # ------------------------------------------------------------------
        # Advanced Hull Form Parameters (Holtrop-Mennen)
        # ------------------------------------------------------------------
        # This panel is hidden when Taylor's Series is the active resistance
        # method, and shown when Holtrop-Mennen (or any future method whose
        # config has requires_advanced_params=True) is selected.
        #
        # Empty fields = "use the auto-derived default" (computed lazily inside
        # _calc_pe_holtrop()). Filling a field overrides the auto-derivation.
        # This lets the user override any subset of parameters without
        # being forced to provide all of them.
        #
        # NOTE: When more methods are added in future (e.g. Hollenbach), each
        # gets its OWN panel toggled by its own config flag. This panel is
        # specific to Holtrop, not "non-Taylor methods generally".
        self.group_holtrop_params = QGroupBox("Holtrop-Mennen Hull Form Parameters (advanced)")
        holtrop_layout = QGridLayout()

        # --- Row 0: LCB and entrance angle ---
        self.label_lcb_pct = QLabel("LCB (% of L, +fwd):")
        self.edit_lcb_pct = QLineEdit()
        self.edit_lcb_pct.setPlaceholderText("auto")
        self.edit_lcb_pct.setToolTip(
            "Longitudinal Centre of Buoyancy as a percent of L from midships.\n"
            "Positive = forward of midships.\n"
            "Auto default: 8.8 * (Fn - 0.18) per the existing Taylor-era formula.\n"
            "Holtrop's regression range is approximately -5% .. +5%."
        )
        self.label_iE_deg = QLabel("Entrance angle iE (deg):")
        self.edit_iE_deg = QLineEdit()
        self.edit_iE_deg.setPlaceholderText("auto")
        self.edit_iE_deg.setToolTip(
            "Half-angle of waterline entrance, in degrees.\n"
            "Auto default uses Holtrop's regression on L/B, CWP, CP, LCB,\n"
            "LR/B and 100*disp/L^3."
        )
        holtrop_layout.addWidget(self.label_lcb_pct, 0, 0)
        holtrop_layout.addWidget(self.edit_lcb_pct, 0, 1)
        holtrop_layout.addWidget(self.label_iE_deg, 0, 2)
        holtrop_layout.addWidget(self.edit_iE_deg, 0, 3)

        # --- Row 1: section coefficients ---
        self.label_cm = QLabel("Midship coeff. CM:")
        self.edit_cm = QLineEdit()
        self.edit_cm.setPlaceholderText("auto")
        self.edit_cm.setToolTip(
            "Midship section coefficient.\n"
            "Auto default: 0.977 + 0.085*(CB - 0.60), typical of full-form merchants."
        )
        self.label_cwp = QLabel("Waterplane coeff. CWP:")
        self.edit_cwp = QLineEdit()
        self.edit_cwp.setPlaceholderText("auto")
        self.edit_cwp.setToolTip(
            "Waterplane area coefficient.\n"
            "Auto default: 0.763*(CP + 0.34) for typical merchants."
        )
        holtrop_layout.addWidget(self.label_cm, 1, 0)
        holtrop_layout.addWidget(self.edit_cm, 1, 1)
        holtrop_layout.addWidget(self.label_cwp, 1, 2)
        holtrop_layout.addWidget(self.edit_cwp, 1, 3)

        # --- Row 2: bulbous bow ---
        self.check_bulb = QCheckBox("Bulbous bow")
        self.check_bulb.setToolTip(
            "Enable if the vessel has a bulbous bow.\n"
            "When unchecked, R_B is forced to 0."
        )
        self.label_abt = QLabel("ABT (m^2):")
        self.edit_abt = QLineEdit()
        self.edit_abt.setPlaceholderText("auto: 0.08*B*T")
        self.edit_abt.setToolTip(
            "Transverse bulb cross-sectional area at the forward perpendicular."
        )
        self.label_hb = QLabel("hB (m):")
        self.edit_hb = QLineEdit()
        self.edit_hb.setPlaceholderText("auto: 0.6*T")
        self.edit_hb.setToolTip(
            "Height of the centroid of ABT above the keel.\n"
            "Must be less than the forward draught T_F."
        )
        holtrop_layout.addWidget(self.check_bulb, 2, 0)
        holtrop_layout.addWidget(self.label_abt, 2, 1)
        holtrop_layout.addWidget(self.edit_abt, 2, 2)
        holtrop_layout.addWidget(self.label_hb, 2, 3)
        holtrop_layout.addWidget(self.edit_hb, 2, 4)

        # --- Row 3: transom ---
        self.check_transom = QCheckBox("Immersed transom")
        self.check_transom.setToolTip(
            "Enable if the vessel has an immersed (wet) transom stern.\n"
            "When unchecked (cruiser stern), R_TR is forced to 0."
        )
        self.label_at = QLabel("AT (m^2):")
        self.edit_at = QLineEdit()
        self.edit_at.setPlaceholderText("auto: 0.05*B*T")
        self.edit_at.setToolTip("Immersed transom area at zero speed.")
        holtrop_layout.addWidget(self.check_transom, 3, 0)
        holtrop_layout.addWidget(self.label_at, 3, 1)
        holtrop_layout.addWidget(self.edit_at, 3, 2)

        # --- Row 4: stern shape & appendage area ---
        self.label_cstern = QLabel("CSTERN:")
        self.combo_cstern = QComboBox()
        # Holtrop's tabulated values: -25 V-shaped, 0 normal, +10 U with Hogner stern
        self.combo_cstern.addItems([
            "-25  V-shaped sections",
            "0    Normal section shape",
            "+10  U-shaped with Hogner stern",
        ])
        self.combo_cstern.setCurrentIndex(1)  # Normal default
        self.combo_cstern.setToolTip(
            "Afterbody form parameter from Holtrop's table.\n"
            "Affects the form factor (1+k1) via c14 = 1 + 0.011*CSTERN."
        )
        self.label_sapp = QLabel("S_app (m^2):")
        self.edit_sapp = QLineEdit()
        self.edit_sapp.setPlaceholderText("auto: 4% of S")
        self.edit_sapp.setToolTip(
            "Appendage wetted area (rudder, bilge keels, shafts, etc).\n"
            "Auto default: 4% of bare-hull wetted area, matching the existing\n"
            "Taylor-era assumption for backward compatibility."
        )
        holtrop_layout.addWidget(self.label_cstern, 4, 0)
        holtrop_layout.addWidget(self.combo_cstern, 4, 1, 1, 2)
        holtrop_layout.addWidget(self.label_sapp, 4, 3)
        holtrop_layout.addWidget(self.edit_sapp, 4, 4)

        # Status line: shows the active method's valid Fn/CB ranges
        self.label_resistance_status = QLabel("")
        self.label_resistance_status.setStyleSheet("color: #555; font-style: italic;")
        holtrop_layout.addWidget(self.label_resistance_status, 5, 0, 1, 5)

        self.group_holtrop_params.setLayout(holtrop_layout)
        # Hidden by default — Taylor is the default method.
        self.group_holtrop_params.setVisible(False)
        left_col.addWidget(self.group_holtrop_params)

        esd_group = QGroupBox("Energy Saving Devices (ESD)")
        esd_layout = QGridLayout()
        
        self.check_als = QCheckBox("Air Lubrication")
        self.check_als.setToolTip("Injects air bubbles under the hull to reduce friction.")
        self.check_als.toggled.connect(self._reset_dlg)
        
        self.label_als_eff = QLabel("Friction Red. (%):")
        self.edit_als_eff = QLineEdit("5.0") # Default 5% reduction on wetted surface
        self.edit_als_eff.setFixedWidth(50)
        self.edit_als_eff.setToolTip("Reduction applied to the Bottom Friction component.")
        
        self.check_wind = QCheckBox("Wind Assist")
        self.check_wind.setToolTip("Sails/Rotors to reduce engine load.")
        self.check_wind.toggled.connect(self._reset_dlg)
        
        self.label_wind_sav = QLabel("Power Sav. (%):")
        self.edit_wind_sav = QLineEdit("10.0")
        self.edit_wind_sav.setFixedWidth(50)
        
        esd_layout.addWidget(self.check_als, 0, 0)
        esd_layout.addWidget(self.label_als_eff, 0, 1)
        esd_layout.addWidget(self.edit_als_eff, 0, 2)
        
        esd_layout.addWidget(self.check_wind, 1, 0)
        esd_layout.addWidget(self.label_wind_sav, 1, 1)
        esd_layout.addWidget(self.edit_wind_sav, 1, 2)
        
        esd_group.setLayout(esd_layout)
        left_col.addWidget(esd_group) # Add to main column

        # ------------------------------------------------------------------
        # Sensitivity & Retrofit panel — new for dissertation chapter 5.
        # ------------------------------------------------------------------
        # Adds three knobs that previously required hand-editing FuelConfig
        # or post-processing CSVs:
        #   1. Methane slip % (LNG only) — inflates effective Carbon factor
        #      via GWP100 = 30 to capture lifecycle GHG (sec 5.5).
        #   2. Resistance uncertainty % — global multiplier on Pe to support
        #      Holtrop ±10% sensitivity (cross-cutting sensitivity table).
        #   3. Retrofit machinery cost factor — discounts the machinery
        #      component of build cost when the vessel is being modelled as
        #      a retrofit rather than a new build (sec 5.4).
        # All three default to "no effect" so existing analyses are untouched.
        sens_group = QGroupBox("Sensitivity & Retrofit Knobs")
        sens_layout = QGridLayout()

        sens_layout.addWidget(QLabel("Methane Slip (%):"), 0, 0)
        self.edit_methane_slip = QLineEdit("0.0")
        self.edit_methane_slip.setFixedWidth(60)
        self.edit_methane_slip.setToolTip(
            "LNG only. Fraction of fuel released unburnt as methane.\n"
            "Multiplied by GWP100 = 30 and added to LNG's CO2 carbon factor.\n"
            "Has no effect for non-LNG fuels."
        )
        sens_layout.addWidget(self.edit_methane_slip, 0, 1)

        sens_layout.addWidget(QLabel("Resistance Uncert. (%):"), 0, 2)
        self.edit_res_uncert = QLineEdit("0.0")
        self.edit_res_uncert.setFixedWidth(60)
        self.edit_res_uncert.setToolTip(
            "Global +/- multiplier on effective power Pe (Holtrop ±10% style).\n"
            "Positive = penalise resistance, negative = optimistic case.\n"
            "Applied AFTER the resistance method runs but BEFORE propeller sizing."
        )
        sens_layout.addWidget(self.edit_res_uncert, 0, 3)

        self.check_retrofit = QCheckBox("Retrofit Mode")
        self.check_retrofit.setToolTip(
            "When ticked, the machinery-cost component of build cost\n"
            "is multiplied by the factor below to represent a conversion\n"
            "rather than a new build. Combine with Ship Mode (fixed L/B/D/T)\n"
            "and 'Enforce Volume Limit' OFF for a realistic retrofit run."
        )
        self.check_retrofit.toggled.connect(self._reset_dlg)
        sens_layout.addWidget(self.check_retrofit, 1, 0)

        sens_layout.addWidget(QLabel("Retrofit Cost Factor:"), 1, 1)
        self.edit_retrofit_factor = QLineEdit("0.40")
        self.edit_retrofit_factor.setFixedWidth(60)
        self.edit_retrofit_factor.setToolTip(
            "Multiplier applied to the machinery cost component when\n"
            "Retrofit Mode is on. Typical conversion-vs-newbuild range is\n"
            "0.30 - 0.50. Steel and outfit components are unchanged because\n"
            "the existing hull is reused."
        )
        sens_layout.addWidget(self.edit_retrofit_factor, 1, 2)

        sens_group.setLayout(sens_layout)
        left_col.addWidget(sens_group)

        aux_group = QGroupBox("Auxiliary & Hotel Loads")
        aux_layout = QGridLayout()
        
        self.check_aux_enable = QCheckBox("Include Auxiliary Power Analysis")
        self.check_aux_enable.setToolTip("Calculates electrical loads for crew, hotel, and reefers.\nAdds weight for generators and fuel.")
        self.check_aux_enable.toggled.connect(self._reset_dlg)
        aux_layout.addWidget(self.check_aux_enable, 0, 0, 1, 3)
        
        self.label_aux_base = QLabel("Base Hotel Load (kW):")
        self.edit_aux_base = QLineEdit("250.0") # Default for small cargo
        self.edit_aux_base.setToolTip("Lighting, pumps, nav, crew AC (excluding cargo).")
        aux_layout.addWidget(self.label_aux_base, 1, 0)
        aux_layout.addWidget(self.edit_aux_base, 1, 1)
        
        self.label_aux_mode_title = QLabel("Cargo Cooling:") 
        aux_layout.addWidget(self.label_aux_mode_title, 2, 0)
        self.combo_aux_mode = QComboBox()
        self.combo_aux_mode.addItems(["None", "Reefer Plugs (Container)", "Insulated Hold (Bulk)"])
        self.combo_aux_mode.currentIndexChanged.connect(self._reset_dlg)
        aux_layout.addWidget(self.combo_aux_mode, 2, 1, 1, 2)
        
        self.label_aux_p1 = QLabel("Reefer Capacity (%):")
        self.edit_aux_p1 = QLineEdit("10.0") # % of TEU or Vol
        self.label_aux_p2 = QLabel("Load (kW/unit):")
        self.edit_aux_p2 = QLineEdit("3.0") # kW/TEU or kW/m3
        
        aux_layout.addWidget(self.label_aux_p1, 3, 0)
        aux_layout.addWidget(self.edit_aux_p1, 3, 1)
        
        aux_layout.addWidget(self.label_aux_p2, 4, 0)
        aux_layout.addWidget(self.edit_aux_p2, 4, 1)
        
        self.label_aux_prem = QLabel("Freight Premium($):")
        self.edit_aux_prem = QLineEdit("0.0")
        self.edit_aux_prem.setToolTip("Extra income per tonne/TEU for refrigerated cargo")
        aux_layout.addWidget(self.label_aux_prem, 5, 0)
        aux_layout.addWidget(self.edit_aux_prem, 5, 1)
        
        aux_group.setLayout(aux_layout)
        left_col.addWidget(aux_group)
        eco_group = QGroupBox()
        eco_layout = QFormLayout()
        eco_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        eco_group.setTitle("") # Groupbox is just for visual separation
        eco_layout.addRow(self.check_econom)
        
        eco_grid = QGridLayout()

        eco_grid.addWidget(QLabel("Voyages per year:"), 0, 0)
        eco_grid.addWidget(self.edit_voyages, 0, 1)

        self.btn_route_cfg = QPushButton("Route..")
        self.btn_route_cfg.setMaximumWidth(60)
        self.btn_route_cfg.clicked.connect(self.on_config_route)
        eco_grid.addWidget(self.btn_route_cfg, 0, 2) 

        eco_grid.addWidget(QLabel("Sea days per year:"), 0, 3)
        eco_grid.addWidget(self.edit_seadays, 0, 4)

        eco_grid.addWidget(self.label_fuel, 1, 0)
        eco_grid.addWidget(self.edit_fuel, 1, 1)

        self.label_lhv = QLabel("Energy Density (MJ/kg):")
        self.edit_lhv = QLineEdit() 
        eco_grid.addWidget(self.label_lhv, 1, 3)
        eco_grid.addWidget(self.edit_lhv, 1, 4)

        tax_layout = QHBoxLayout()
        self.check_carbon_tax = QCheckBox("Carbon Tax?")
        self.check_carbon_tax.toggled.connect(self._reset_dlg)
        self.label_ctax_rate = QLabel("Tax($/tCO2):")
        self.edit_ctax_rate = QLineEdit(str(self.m_CarbonTax))
        
        tax_layout.addWidget(self.check_carbon_tax)
        tax_layout.addWidget(self.label_ctax_rate)
        tax_layout.addWidget(self.edit_ctax_rate)
        tax_layout.addStretch()
        
        eco_grid.addLayout(tax_layout, 2, 0, 1, 5)

        eco_grid.addWidget(self.label_reactor_cost, 3, 0)
        eco_grid.addWidget(self.edit_reactor_cost, 3, 1)
        eco_grid.addWidget(self.label_core_life, 3, 3)
        eco_grid.addWidget(self.edit_core_life, 3, 4)
        
        eco_grid.addWidget(QLabel("Interest rate (%):"), 4, 0)
        eco_grid.addWidget(self.edit_interest, 4, 1)
        eco_grid.addWidget(QLabel("No. years to repay:"), 4, 3)
        eco_grid.addWidget(self.edit_repay, 4, 4)

        eco_grid.addWidget(self.label_decom_cost, 5, 0)
        eco_grid.addWidget(self.edit_decom_cost, 5, 1)

        self.check_eedi = QCheckBox("Calculate EEDI (Phase 3)")
        self.check_eedi.setToolTip("Calculates Energy Efficiency Design Index against IMO Reference Lines")
        self.check_eedi.toggled.connect(self._reset_dlg) # Connect to reset logic
        
        self.check_cii = QCheckBox("Calculate CII Rating")
        self.check_cii.setToolTip("Calculates Carbon Intensity Indicator (A-E Rating) based on operational profile.")
        self.check_cii.toggled.connect(self._reset_dlg)

        self.check_fuel_vol = QCheckBox("Show Fuel Volume")
        self.check_fuel_vol.setToolTip("Displays the required fuel volume and % of internal hull volume.")

        tax_layout.addWidget(self.check_eedi)
        tax_layout.addWidget(self.check_cii)
        tax_layout.addWidget(self.check_fuel_vol)

        eco_layout.addRow(eco_grid)
        eco_group.setLayout(eco_layout)
        left_col.addWidget(eco_group)

        range_group = QGroupBox("Range Analysis (2D Line or 3D Surface)")
        range_layout = QGridLayout()

        # 1. Define Smart Defaults for Auto-fill
        self.RANGE_DEFAULTS = {
            "Speed(knts)":         ("12.0", "24.0", "13"), # 1 kt steps
            "Block Co.":           ("0.60", "0.85", "6"),
            "Cargo deadweight(t)": ("35000", "120000", "6"),
            "TEU Capacity":        ("1000", "14000", "8"),
            "L/B Ratio":           ("5.0", "8.0", "7"),    # 0.5 steps
            "B(m)":                ("25.0", "50.0", "6"),
            "B/T Ratio":           ("2.2", "3.8", "5"),
            "Reactor Cost ($/kW)": ("3000", "20000", "8"), # Upper bound 20k for SMR sensitivity
            # -- NEW PARAMETERS --
            "Range (nm)":          ("3000", "15000", "5"), # Crucial for alt fuels
            "Fuel Cost ($/t)":     ("400", "1500", "6"),   # Sensitivity analysis
            "Interest Rate (%)":   ("2.0", "10.0", "5"),   # Finance check
            "Carbon Tax ($/t)":    ("0", "300", "7"),      # Regulatory check
            # -- DISSERTATION ANALYSIS PARAMETERS (added for sec 5.2/5.3/5.6) --
            "Sea days/year":       ("200", "340", "8"),    # Nuclear utilisation crossover
            "Air Lub Eff. (%)":    ("0", "10", "6"),       # ESD sensitivity (sec 5.6)
            "Wind Power Sav. (%)": ("0", "15", "6"),       # ESD sensitivity (sec 5.6)
            "Methane Slip (%)":    ("0", "4", "5")         # LNG GWP sensitivity (sec 5.5)
        }

        # 2. Setup Input 1 (X-Axis)
        range_layout.addWidget(QLabel("<b>Input 1 (X-Axis):</b>"), 0, 0)
        self.combo_param_vary = QComboBox()
        self.param_list = list(self.RANGE_DEFAULTS.keys()) # Use keys from dict
        self.combo_param_vary.addItems(self.param_list)
        range_layout.addWidget(self.combo_param_vary, 0, 1, 1, 3)

        range_layout.addWidget(QLabel("Start:"), 1, 0)
        self.edit_range_start = QLineEdit() 
        range_layout.addWidget(self.edit_range_start, 1, 1)
        range_layout.addWidget(QLabel("End:"), 1, 2)
        self.edit_range_end = QLineEdit()
        range_layout.addWidget(self.edit_range_end, 1, 3)
        range_layout.addWidget(QLabel("Steps:"), 2, 0)
        self.edit_range_steps = QLineEdit()
        range_layout.addWidget(self.edit_range_steps, 2, 1)

        # 3. Setup Input 2 (Y-Axis / 3D Only)
        range_layout.addWidget(QLabel("<b>Input 2 (Y-Axis / 3D Only):</b>"), 3, 0)
        self.check_enable_3d = QCheckBox("Enable 2nd Input")
        range_layout.addWidget(self.check_enable_3d, 3, 1, 1, 2)

        self.combo_param_vary_2 = QComboBox()
        self.combo_param_vary_2.addItems(self.param_list)
        self.combo_param_vary_2.setCurrentText("Reactor Cost ($/kW)") 
        range_layout.addWidget(self.combo_param_vary_2, 4, 1, 1, 3)
        range_layout.addWidget(QLabel("Param:"), 4, 0)

        range_layout.addWidget(QLabel("Start:"), 5, 0)
        self.edit_range_start_2 = QLineEdit("3000") 
        range_layout.addWidget(self.edit_range_start_2, 5, 1)
        range_layout.addWidget(QLabel("End:"), 5, 2)
        self.edit_range_end_2 = QLineEdit("6000")
        range_layout.addWidget(self.edit_range_end_2, 5, 3)
        range_layout.addWidget(QLabel("Steps:"), 6, 0)
        self.edit_range_steps_2 = QLineEdit("8")
        range_layout.addWidget(self.edit_range_steps_2, 6, 1)

        # 4. Connect Auto-fill Signals
        self.combo_param_vary.currentTextChanged.connect(
            lambda: self._apply_range_defaults(self.combo_param_vary, 
                                               self.edit_range_start, 
                                               self.edit_range_end, 
                                               self.edit_range_steps))

        self.combo_param_vary_2.currentTextChanged.connect(
            lambda: self._apply_range_defaults(self.combo_param_vary_2, 
                                               self.edit_range_start_2, 
                                               self.edit_range_end_2, 
                                               self.edit_range_steps_2))
        
        # Trigger once to fill initial defaults
        self._apply_range_defaults(self.combo_param_vary, self.edit_range_start, self.edit_range_end, self.edit_range_steps)

        # 5. Output Selection
        range_layout.addWidget(QLabel("<b>Output (Y or Z Axis):</b>"), 7, 0)
        self.combo_param_y = QComboBox()
        self.combo_param_y.addItems([
            "RFR($/tonne or $/TEU)", "BuildCost(M$)", "AnnualFuelCost(M$)",
            "AnnualCarbonTax(M$)", "AnnualisedCAPEX(M$)", "AnnualOPEX(M$)",
            "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB", "Displacement(t)",
            "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)", "InstalledPower(kW)",
            "EEDI(gCO2/t.nm)", "AttainedCII",
            "FuelVolume(m3)", "FuelVol%Hull", "VolCargo(m3)", "VolFuel(m3)",
            "VolMachinery(m3)", "VolStores(m3)", "VolUtilisation%"
        ])
        range_layout.addWidget(self.combo_param_y, 7, 1, 1, 3)

        self.btn_run_range = QPushButton("Run & Save CSV")
        range_layout.addWidget(self.btn_run_range, 8, 0, 1, 2)
        self.btn_run_plot = QPushButton("Run & Plot Graph")
        range_layout.addWidget(self.btn_run_plot, 8, 2, 1, 2)

        def toggle_3d_inputs(checked):
            self.combo_param_vary_2.setEnabled(checked)
            self.edit_range_start_2.setEnabled(checked)
            self.edit_range_end_2.setEnabled(checked)
            self.edit_range_steps_2.setEnabled(checked)
        
        self.check_enable_3d.toggled.connect(toggle_3d_inputs)
        toggle_3d_inputs(False) 

        range_group.setLayout(range_layout)
        left_col.addWidget(range_group)
        
        comp_group = QGroupBox("Competitive Analysis")
        comp_layout = QGridLayout()
        
        comp_layout.addWidget(QLabel("Select Engines (Click to toggle):"), 0, 0, 1, 2)
        
        self.list_battle_engines = QListWidget()
        self.list_battle_engines.setSelectionMode(QAbstractItemView.MultiSelection)
        self.list_battle_engines.addItems(list(FuelConfig.DATA.keys()))
        self.list_battle_engines.setMaximumHeight(100)
        
        self.list_battle_engines.item(0).setSelected(True)
        self.list_battle_engines.item(5).setSelected(True) 
        
        comp_layout.addWidget(self.list_battle_engines, 1, 0, 1, 2)

        # --- NEW: Configurable X-Axis (Input) ---
        comp_layout.addWidget(QLabel("X-Axis (Input):"), 2, 0)
        self.combo_battle_x = QComboBox()
        self.combo_battle_x.addItems(self.param_list) # Reuses your RANGE_DEFAULTS keys
        comp_layout.addWidget(self.combo_battle_x, 2, 1)

        # Configurable Range Setup
        range_layout = QHBoxLayout()
        self.edit_battle_start = QLineEdit()
        self.edit_battle_start.setFixedWidth(50)
        self.edit_battle_end = QLineEdit()
        self.edit_battle_end.setFixedWidth(50)
        self.edit_battle_steps = QLineEdit() 
        self.edit_battle_steps.setFixedWidth(40)
        
        range_layout.addWidget(QLabel("Start:")); range_layout.addWidget(self.edit_battle_start)
        range_layout.addWidget(QLabel("End:")); range_layout.addWidget(self.edit_battle_end)
        range_layout.addWidget(QLabel("Steps:")); range_layout.addWidget(self.edit_battle_steps)
        comp_layout.addLayout(range_layout, 3, 0, 1, 2)

        # Connect the auto-fill defaults for the selected X-Axis variable
        self.combo_battle_x.currentTextChanged.connect(
            lambda: self._apply_range_defaults(self.combo_battle_x, 
                                               self.edit_battle_start, 
                                               self.edit_battle_end, 
                                               self.edit_battle_steps))
        self._apply_range_defaults(self.combo_battle_x, self.edit_battle_start, self.edit_battle_end, self.edit_battle_steps)

        # --- NEW: Configurable Y-Axis (Output) ---
        comp_layout.addWidget(QLabel("Y-Axis (Output):"), 4, 0)
        self.combo_battle_y = QComboBox()
        self.combo_battle_y.addItems([
            "RFR($/tonne or $/TEU)", "BuildCost(M$)", "AnnualFuelCost(M$)",
            "AnnualCarbonTax(M$)", "AnnualisedCAPEX(M$)", "AnnualOPEX(M$)",
            "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB", "Displacement(t)",
            "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)", "InstalledPower(kW)",
            "EEDI(gCO2/t.nm)", "AttainedCII",
            "FuelVolume(m3)", "FuelVol%Hull", "VolCargo(m3)", "VolFuel(m3)",
            "VolMachinery(m3)", "VolStores(m3)", "VolUtilisation%"
        ])
        comp_layout.addWidget(self.combo_battle_y, 4, 1)

        self.btn_run_battle = QPushButton("Run Comparison Battle")
        self.btn_run_battle.setStyleSheet("font-weight: bold; color: darkblue;")
        self.btn_run_battle.clicked.connect(self.on_run_battle)
        self.btn_export_battle = QPushButton("Export Battle CSV")
        self.btn_export_battle.setEnabled(False) 
        self.btn_export_battle.clicked.connect(self.on_export_battle_csv)

        battle_btn_layout = QHBoxLayout()
        battle_btn_layout.addWidget(self.btn_run_battle)
        battle_btn_layout.addWidget(self.btn_export_battle)
        
        comp_layout.addLayout(battle_btn_layout, 5, 0, 1, 2)

        comp_group.setLayout(comp_layout)
        left_col.addWidget(comp_group)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_modify)
        button_layout.addWidget(self.btn_outopt)
        button_layout.addWidget(self.btn_save)
        left_col.addLayout(button_layout)
        
        left_col.addStretch(1) # Pushes everything up
        
        main_layout.addLayout(left_col)
        main_layout.addWidget(self.text_results, 1) # Add results box with stretch
        content_widget = QWidget()
        content_widget.setLayout(main_layout)

        from PySide6.QtWidgets import QScrollArea 
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)

        window_layout = QVBoxLayout(self)
        window_layout.addWidget(scroll_area)
        
        self.btn_calculate.clicked.connect(self.on_calculate)
        self.btn_run_range.clicked.connect(self.on_run_range)
        self.btn_run_plot.clicked.connect(self.on_run_plot) 
        self.btn_save.clicked.connect(self.on_button_save)
        self.btn_modify.clicked.connect(self.on_dialog_modify)
        self.btn_outopt.clicked.connect(self.on_dialog_outopt)
        
        self.radio_cargo.toggled.connect(self._reset_dlg)
        self.radio_ship.toggled.connect(self._reset_dlg)
        self.radio_teu.toggled.connect(self._reset_dlg)
        
        self.combo_ship.currentIndexChanged.connect(self._reset_dlg)
        self.combo_engine.currentIndexChanged.connect(self._reset_dlg) 
        self.combo_engine.currentTextChanged.connect(self._on_fuel_changed)
        # Fire once with the initial selection so the LHV and fuel-price
        # fields are correct at startup, not just after the user changes
        # the dropdown. Connection above only fires on subsequent changes.
        self._on_fuel_changed(self.combo_engine.currentText())

        self.combo_resistance_method.currentTextChanged.connect(self._on_resistance_method_changed)
        self.combo_resistance_method.currentIndexChanged.connect(self._reset_dlg)
        self.combo_basis.currentTextChanged.connect(self._on_basis_changed)
        self.combo_basis.currentIndexChanged.connect(self._reset_dlg)
        self.check_bulb.toggled.connect(self._reset_dlg)
        self.check_transom.toggled.connect(self._reset_dlg)
        
        self.check_econom.toggled.connect(self.on_check_econom) 
        self.check_lbratio.toggled.connect(self.on_check_lbratio) 
        self.check_vol_limit.toggled.connect(self._reset_dlg)
        self.check_bvalue.toggled.connect(self.on_check_bvalue) 
        self.check_btratio.toggled.connect(self.on_check_btratio)
        self.check_cbvalue.toggled.connect(self.on_check_cbvalue) 
        self.check_pdtratio.toggled.connect(self.on_check_pdtratio) 

        # ---- Sensitivity & retrofit signals ----
        # check_retrofit is already connected to _reset_dlg in the UI builder.
        # The line-edit fields don't need toggle hooks because they're read at
        # calculate-time inside _update_ui_to_data().
        
        self.edit_erpm.editingFinished.connect(self.on_killfocus_edit_erpm) 
        self.edit_prpm.editingFinished.connect(self.on_killfocus_edit_prpm) 

        self._update_data_to_ui() 
        self._reset_dlg()
        
    def _on_fuel_changed(self, fuel_name):
        """Auto-populate the LHV and fuel-price fields when the engine
        selection changes.

        The fuel price uses DEFAULT_FUEL_PRICE — the same per-fuel figures
        that BattleFuelConfigDialog injects in battle mode. Previously the
        main widget kept a single global price (default $625) regardless
        of fuel, so direct-calc RFR for, say, hydrogen ($4000/t) silently
        used $625 while a battle-mode sweep used $4000. Auto-injecting
        here closes that gap. The field stays editable, so the user can
        still type a custom price after switching engines.
        """
        fuel_data = FuelConfig.get(fuel_name)
        if fuel_data["LHV"] > 0:
            self.edit_lhv.setText(str(fuel_data["LHV"]))

        # Skip nuclear: it has no fuel cost line (reactor capex flows
        # through H7 separately) and the edit_fuel field is hidden for
        # nuclear anyway. Writing 0 here is harmless but pointless.
        if not fuel_data.get("IsNuclear", False):
            price = DEFAULT_FUEL_PRICE.get(fuel_name)
            if price is not None:
                self.edit_fuel.setText(f"{price:.1f}")

    def _on_resistance_method_changed(self, method_name):
        """Show/hide the Holtrop hull-form parameter panel and update the
        status line when the resistance method dropdown changes.

        Hooked into combo_resistance_method.currentTextChanged.
        """
        cfg = ResistanceMethodConfig.get(method_name)
        # Show the advanced panel only for methods that need extra hull-form
        # parameters. (Today: only Holtrop. Future methods will get their own
        # panels - this flag is per-method, not "non-Taylor".)
        self.group_holtrop_params.setVisible(cfg["requires_advanced_params"])
        # Update the status label with valid Fn/CB ranges so the user can
        # immediately see when their inputs are out of regression range.
        fn_lo, fn_hi = cfg["valid_fn_range"]
        cb_lo, cb_hi = cfg["valid_cb_range"]
        self.label_resistance_status.setText(
            f"Method valid for Fn in [{fn_lo:.2f}, {fn_hi:.2f}], "
            f"CB in [{cb_lo:.2f}, {cb_hi:.2f}]."
        )

    def _on_basis_changed(self, basis_name):
        """Cache the selected empirical basis on self.

        Hooked into combo_basis.currentTextChanged.  The actual coefficient
        lookup happens lazily in OnButtonCal via EmpiricalBasisConfig.get(),
        so nothing further is needed here beyond updating the cache.  This
        keeps the dropdown safe to read from headless callers (range and
        battle modes) without driving the Qt event loop.
        """
        if basis_name in EmpiricalBasisConfig.DATA:
            self.empirical_basis = basis_name

    def _update_ui_to_data(self):
        """Port of UpdateData(TRUE) - Pulls values from UI to members"""

        def _safe_float(widget, default=0.0):
            try:
                text = widget.text().strip()
                if not text:
                    return default
                return float(text)
            except ValueError:
                raise ValueError(f"Invalid number in field")

        try:
            self.m_Weight = _safe_float(self.edit_weight)
            self.m_Error = _safe_float(self.edit_error)
            
            self.m_TEU = _safe_float(self.edit_teu)
            self.m_TEU_Avg_Weight = _safe_float(self.edit_teu_weight)
            
            self.m_LbratioV = _safe_float(self.edit_lbratio)
            self.m_BvalueV = _safe_float(self.edit_bvalue)
            self.m_BtratioV = _safe_float(self.edit_btratio)
            self.m_CbvalueV = _safe_float(self.edit_cbvalue)
            self.m_PdtratioV = _safe_float(self.edit_pdtratio)
            
            self.m_Length = _safe_float(self.edit_length)
            self.m_Breadth = _safe_float(self.edit_breadth)
            self.m_Draught = _safe_float(self.edit_draught)
            self.m_Depth = _safe_float(self.edit_depth)
            self.m_Block = _safe_float(self.edit_block)
            
            self.m_Speed = _safe_float(self.edit_speed)
            
            if self.edit_range.text() == "Infinite":
                self.m_Range = float('inf')
            else:
                new_range = _safe_float(self.edit_range)
                self.m_Range = new_range
                if not (self.combo_engine.currentIndex() == 3): # Not Nuclear
                     self.m_conventional_Range = new_range
            
            self.m_Prpm = _safe_float(self.edit_prpm)
            self.m_Erpm = _safe_float(self.edit_erpm)
            self.m_Voyages = _safe_float(self.edit_voyages)
            self.m_Seadays = _safe_float(self.edit_seadays)

            self.m_Fuel = _safe_float(self.edit_fuel)

            val_lhv = _safe_float(self.edit_lhv, default=-1.0)
            if val_lhv > 0:
                self.m_LHV = val_lhv
            else:
                self.m_LHV = 42.7
            
            self.m_CarbonTax = _safe_float(self.edit_ctax_rate)
            self.m_Reactor_Cost_per_kW = _safe_float(self.edit_reactor_cost)
            self.m_Core_Life = _safe_float(self.edit_core_life)
            self.m_Decom_Cost = _safe_float(self.edit_decom_cost)
            self.m_Interest = _safe_float(self.edit_interest)
            self.m_Repay = _safe_float(self.edit_repay)

            # Sensitivity & retrofit knobs (chapter 5 additions).
            self.m_MethaneSlip   = _safe_float(self.edit_methane_slip,   default=0.0)
            self.m_ResUncertPct  = _safe_float(self.edit_res_uncert,     default=0.0)
            self.m_RetrofitMode  = self.check_retrofit.isChecked()
            self.m_RetrofitFactor = _safe_float(self.edit_retrofit_factor, default=0.40)
            # Clamp retrofit factor to a sane band so a typo can't produce
            # negative or runaway costs.
            if self.m_RetrofitFactor < 0.0:
                self.m_RetrofitFactor = 0.0
            if self.m_RetrofitFactor > 1.5:
                self.m_RetrofitFactor = 1.5

            self.m_VolumeLimit = self.check_vol_limit.isChecked()
            
            if self.edit_density.isVisible():
                 self.m_CustomDensity = _safe_float(self.edit_density, default=-1.0)
            else:
                 self.m_CustomDensity = -1.0 

            if self.radio_cargo.isChecked():
                self.m_Cargo = 0
            elif self.radio_ship.isChecked():
                self.m_Cargo = 1
            elif self.radio_teu.isChecked():
                self.m_Cargo = 2

            self.m_Econom = self.check_econom.isChecked()
            self.m_Lbratio = self.check_lbratio.isChecked()
            self.m_Bvalue = self.check_bvalue.isChecked()
            self.m_Btratio = self.check_btratio.isChecked()
            self.m_Cbvalue = self.check_cbvalue.isChecked()
            self.m_Pdtratio = self.check_pdtratio.isChecked()
            self.m_Append = self.check_append.isChecked()
            
            self.Kstype = self.combo_ship.currentIndex() + 1
            self.Ketype = self.combo_engine.currentIndex() + 1

            # ----------------------------------------------------------------
            # Resistance method state
            # ----------------------------------------------------------------
            self.resistance_method = self.combo_resistance_method.currentText()

            # Holtrop hull-form overrides. Empty field = None = "auto-derive"
            # inside _calc_pe_holtrop(). This lets the user override any subset
            # of parameters without being forced to fill in all of them.
            def _opt_float(widget):
                txt = widget.text().strip()
                if not txt:
                    return None
                try:
                    return float(txt)
                except ValueError:
                    raise ValueError(f"Invalid number in Holtrop field")

            self.lcb_pct = _opt_float(self.edit_lcb_pct)
            self.iE_deg = _opt_float(self.edit_iE_deg)
            self.cm = _opt_float(self.edit_cm)
            self.cwp = _opt_float(self.edit_cwp)
            self.has_bulb = self.check_bulb.isChecked()
            self.abt = _safe_float(self.edit_abt) if self.edit_abt.text().strip() else 0.0
            self.hb = _safe_float(self.edit_hb) if self.edit_hb.text().strip() else 0.0
            self.has_transom = self.check_transom.isChecked()
            self.at = _safe_float(self.edit_at) if self.edit_at.text().strip() else 0.0
            # combo_cstern items are "-25 ..", "0 ..", "+10 .."; first token is the value
            cstern_text = self.combo_cstern.currentText().split()[0]
            try:
                self.cstern = int(cstern_text)
            except ValueError:
                self.cstern = 0
            self.s_app_override = _opt_float(self.edit_sapp)

            return True
            
        except ValueError as e:
            self._show_error(f"Invalid input format.\n\nPlease check that all visible fields contain valid numbers.\n(Error: {e})")
            return False

    def _update_data_to_ui(self):
        """Port of UpdateData(FALSE) - Pushes member values to UI"""
        self.combo_ship.setCurrentIndex(self.Kstype - 1)
        self.combo_engine.setCurrentIndex(self.Ketype - 1)
        
        self.edit_weight.setText(f"{self.m_Weight:.6g}")
        self.edit_error.setText(f"{self.m_Error:.6g}")
        self.edit_teu.setText(f"{self.m_TEU:.6g}")
        self.edit_teu_weight.setText(f"{self.m_TEU_Avg_Weight:.6g}")
        self.edit_lbratio.setText(f"{self.m_LbratioV:.6g}")
        self.edit_bvalue.setText(f"{self.m_BvalueV:.6g}")
        self.edit_btratio.setText(f"{self.m_BtratioV:.6g}")
        self.edit_cbvalue.setText(f"{self.m_CbvalueV:.6g}")
        self.edit_pdtratio.setText(f"{self.m_PdtratioV:.6g}")
        self.edit_length.setText(f"{self.m_Length:.6g}")
        self.edit_breadth.setText(f"{self.m_Breadth:.6g}")
        self.edit_draught.setText(f"{self.m_Draught:.6g}")
        self.edit_depth.setText(f"{self.m_Depth:.6g}")
        self.edit_block.setText(f"{self.m_Block:.6g}")
        self.edit_speed.setText(f"{self.m_Speed:.6g}")
        
        self.edit_prpm.setText(f"{self.m_Prpm:.6g}")
        self.edit_erpm.setText(f"{self.m_Erpm:.6g}")
        self.edit_voyages.setText(f"{self.m_Voyages:.6g}")
        self.edit_seadays.setText(f"{self.m_Seadays:.6g}")

        self.edit_fuel.setText(f"{self.m_Fuel:.6g}")

        self.edit_lhv.setText(f"{self.m_LHV:.6g}")
        self.edit_reactor_cost.setText(f"{self.m_Reactor_Cost_per_kW:.6g}")
        
        self.edit_core_life.setText(f"{self.m_Core_Life:.6g}")
        self.edit_decom_cost.setText(f"{self.m_Decom_Cost:.6g}")
        self.edit_interest.setText(f"{self.m_Interest:.6g}")
        self.edit_repay.setText(f"{self.m_Repay:.6g}")

        self.check_vol_limit.setChecked(self.m_VolumeLimit)
        
        self.check_econom.setChecked(self.m_Econom)
        self.radio_cargo.setChecked(self.m_Cargo == 0)
        self.radio_ship.setChecked(self.m_Cargo == 1)
        self.radio_teu.setChecked(self.m_Cargo == 2)
        self.check_lbratio.setChecked(self.m_Lbratio)
        self.check_bvalue.setChecked(self.m_Bvalue)
        self.check_btratio.setChecked(self.m_Btratio)
        self.check_cbvalue.setChecked(self.m_Cbvalue)
        self.check_pdtratio.setChecked(self.m_Pdtratio)
        self.check_append.setChecked(self.m_Append)

        # ---- Resistance method state ----
        # Push the selected method back to the dropdown. The signal handler
        # (_on_resistance_method_changed) will hide/show the Holtrop panel
        # automatically — no need to repeat that logic here.
        method_name = getattr(self, 'resistance_method', "Taylor's Series (Legacy)")
        if method_name in ResistanceMethodConfig.DATA:
            self.combo_resistance_method.setCurrentText(method_name)

        # Holtrop hull-form fields. None -> blank (the placeholder "auto"
        # text remains visible). Numeric values are stamped into the field.
        def _opt_text(val):
            return "" if val is None else f"{val:.6g}"

        self.edit_lcb_pct.setText(_opt_text(self.lcb_pct))
        self.edit_iE_deg.setText(_opt_text(self.iE_deg))
        self.edit_cm.setText(_opt_text(self.cm))
        self.edit_cwp.setText(_opt_text(self.cwp))
        self.check_bulb.setChecked(self.has_bulb)
        self.edit_abt.setText("" if self.abt == 0.0 else f"{self.abt:.6g}")
        self.edit_hb.setText("" if self.hb == 0.0 else f"{self.hb:.6g}")
        self.check_transom.setChecked(self.has_transom)
        self.edit_at.setText("" if self.at == 0.0 else f"{self.at:.6g}")
        # combo_cstern: items are "-25 ..", "0 ..", "+10 .."
        cstern_idx = {-25: 0, 0: 1, 10: 2}.get(self.cstern, 1)
        self.combo_cstern.setCurrentIndex(cstern_idx)
        self.edit_sapp.setText(_opt_text(self.s_app_override))

        # ---- Sensitivity & retrofit state (chapter 5) ----
        # Push these back so reload-from-saved-state preserves them.
        self.edit_methane_slip.setText(f"{self.m_MethaneSlip:.6g}")
        self.edit_res_uncert.setText(f"{self.m_ResUncertPct:.6g}")
        self.check_retrofit.setChecked(self.m_RetrofitMode)
        self.edit_retrofit_factor.setText(f"{self.m_RetrofitFactor:.6g}")

        self.text_results.setText(self.m_Results)

    def _show_error(self, message, title="Input error"):
        """Helper for porting MessageBox"""
        if getattr(self, 'is_batch_mode', False):
            return 
            
        QMessageBox.critical(self, title, message)
        
    def _show_debug_msg(self, message, title="Info. from OnButtonCal in debug mode"):
        """Helper for porting debug MessageBox"""
        #
        ret = QMessageBox.question(self, title, message,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.No: 
            self.dbgmd = False
            self.dlg_modify.data['dbgmd'] = False
            return False
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
                self.edit_weight.setFocus()
                return False
        elif self.m_Cargo == 2: # TEU mode
             if self.m_TEU <= 0.0 or self.m_TEU_Avg_Weight <= 0.0:
                self._show_error("Fatal error: TEU and Avg. Weight must be positive!", "Input error")
                self.edit_teu.setFocus()
                return False
        elif self.m_Cargo == 1: # Ship dimensions mode
            if self.L1 <= 0.0 or self.B <= 0.0 or self.D <= 0.0 or self.T <= 0.0 or self.C <= 0.0:
                self._show_error("Fatal error: Ship dimensions must be positive!", "Input error")
                self.edit_length.setFocus()
                return False
            if self.C > 1.0:
                self._show_error("Fatal error: CB should be less than 1.0!", "Input error")
                self.edit_block.setFocus()
                return False
        
        if self.m_Cargo != 1: # Cargo or TEU mode
            if self.m_Lbratio and self.m_LbratioV <= 0:
                self._show_error("Fatal error: L/B ratio must be positive!", "Input error")
                self.edit_lbratio.setFocus()
                return False
            if self.m_Bvalue and self.m_BvalueV <= 0:
                self._show_error("Fatal error: B value must be positive!", "Input error")
                self.edit_bvalue.setFocus()
                return False
            if self.m_Btratio and self.m_BtratioV <= 0:
                self._show_error("Fatal error: B/T ratio must be positive!", "Input error")
                self.edit_btratio.setFocus()
                return False
            if self.m_Cbvalue and (self.m_CbvalueV <= 0 or self.m_CbvalueV > 1.0):
                self._show_error("Fatal error: CB must be positive and < 1.0!", "Input error")
                self.edit_cbvalue.setFocus()
                return False
        
        if self.m_Pdtratio and self.m_PdtratioV <= 0.0:
            self._show_error("Fatal error: Prop.dia ratio must be positive!", "Input error")
            self.edit_pdtratio.setFocus()
            return False
        
        if self.V <= 0.0 or self.R <= 0.0 or self.N1 <= 0.0 or self.N2 <= 0.0:
            self._show_error("Fatal error: Speed, Range, and RPMs must be positive!", "Input error")
            self.edit_speed.setFocus()
            return False
            
        if self.m_Econom:
            if self.V7 <= 0.0 or self.D1 <= 0.0 or self.I < 0.0 or self.N < 1:
                self._show_error("Fatal error: Economic values must be positive (Interest >= 0)!", "Input error")
                self.edit_voyages.setFocus()
                return False
            
            if self.Ketype == 4: # Nuclear
                if self.m_Reactor_Cost_per_kW <= 0 or self.m_Core_Life <= 0 or self.m_Decom_Cost < 0:
                    self._show_error("Fatal error: Nuclear costs must be positive!", "Input error")
                    self.edit_reactor_cost.setFocus()
                    return False
            else: # Fossil
                if self.F8 <= 0.0:
                    self._show_error("Fatal error: Fuel cost must be positive!", "Input error")
                    self.edit_fuel.setFocus()
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
                self.edit_lcb_pct.setFocus()
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
                    self.edit_abt.setFocus()
                    return False
                if self.hb >= self.T:
                    self._show_error(
                        f"Holtrop validation: bulb height hB ({self.hb}) must be "
                        f"less than draught T ({self.T}). The bulb must be submerged.",
                        "Input error",
                    )
                    self.edit_hb.setFocus()
                    return False
            if self.has_transom and self.at <= 0.0:
                self._show_error(
                    "Holtrop validation: transom is enabled but AT is not positive.",
                    "Input error",
                )
                self.edit_at.setFocus()
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
        ship_data = ShipConfig.get(self.combo_ship.currentText())
        fuel_data = FuelConfig.get(self.combo_engine.currentText())
        
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

        self.text_results.append(f"\n--- VOLUME LIMIT DETECTED ---")
        self.text_results.append(f"Required: {int(req)} m3 | Available: {int(avail)} m3")
        self.text_results.append(f"Expanding ship dimensions...")

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
                fuel_data_local = FuelConfig.get(self.combo_engine.currentText())
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
                    self.text_results.append(f"-> Converged at L={self.L1:.1f}m after {self.vol_expansion_iters} iter(s)")
                    self.text_results.append(f"-> Draft adjusted to {self.T:.1f}m (New Disp: {int(self.M)}t)")
                    self.W1 = self.M - new_lightship - fuel_mass - misc_mass
                    return True 

            self.text_results.append(f"-> WARNING: Volume expansion limit reached after {self.vol_expansion_iters} iter(s).")
            return False
        finally:
            self.ignspd = prev_ignspd
            self.ignpth = prev_ignpth

    def _apply_range_defaults(self, combo, edit_start, edit_end, edit_steps):
        """Helper to auto-fill range fields based on selection."""
        param = combo.currentText()
        if param in self.RANGE_DEFAULTS:
            start, end, steps = self.RANGE_DEFAULTS[param]
            edit_start.setText(start)
            edit_end.setText(end)
            edit_steps.setText(steps)

    def on_calculate(self):
        """Port of OnButtonCal"""

        keys_to_reset = ['M_aux_mach', 'M_aux_outfit', 'W_aux_fuel', 
                         'aux_cost_annual', 'calculated_fuel_mass', 'raw_fuel_mass',
                         '_esd_applied']
        for k in keys_to_reset:
            if hasattr(self, k):
                delattr(self, k)

        if not self._update_ui_to_data():
            return

        self.design_mode = self.m_Cargo # 0=Cargo, 1=Ship, 2=TEU
        self.target_teu = 0

        if self.design_mode == 2:
            self.W = self.m_TEU * self.m_TEU_Avg_Weight
            self.target_teu = self.m_TEU
            
            self.E = 0.01 * self.W * self.m_Error
            
            self.m_Cargo = 0
            
            self.edit_weight.setText(str(self.W))
            self.edit_error.setText(str(self.m_Error))
        
        elif self.design_mode == 0:
            self.W = self.m_Weight
            self.E = 0.01 * self.W * self.m_Error
            
        if self.Ketype == 1: 
            self.m_Prpm = self.m_Erpm
            self.edit_prpm.setText(str(self.m_Prpm))
            
        self._initdata(0) 
        self.CalculatedOk = False 
        self.btn_save.setEnabled(False) 
        
        if not self._check_data(): 
            self.m_Cargo = self.design_mode
            return
            
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
                QMessageBox.information(self, "Info. from OnButtonCal in debug mode", msg)

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
                        if not self._freeboard(): return
                    else:
                        _D = _basis_D(self.L1)
                        self.D = _D if _D is not None else self.L1 / 13.5
                        _T = _basis_T(self.D)
                        self.T = _T if _T is not None else 0.78 * self.D
                        if not self._freeboard(): return
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
                        if not self._freeboard(): return
                    else:
                        _D = _basis_D(self.L1)
                        self.D = _D if _D is not None else self.L1 / 11.75
                        _T = _basis_T(self.D)
                        self.T = _T if _T is not None else 0.7 * self.D
                        if not self._freeboard(): return
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
                    if not self._freeboard(): return
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
                        if not self._freeboard(): return
                    else:
                        self.D = (self.B - 2.74) / 1.4; self.T = 0.7 * self.D
                        if not self._freeboard(): return

                self.M = 1.025 * self.L1 * self.B * self.T * self.C 
                if not self._stability(): return 
                
                if not self._power():
                     return
                
                if not self._mass(): return 
                
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
                        QMessageBox.critical(self, "Info. from OnButtonCal in debug mode", msg)
                        self.dbgmd = False; self.dlg_modify.data['dbgmd'] = False
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
                return

            if self.Kcount >= 500: 
                QMessageBox.warning(self, "Warning", "Warning: Allowable error too small!")

        elif self.m_Cargo == 1: 
            if not self._freeboard(): return 
            self.M = 1.025 * self.L1 * self.B * self.T * self.C 
            if not self._stability(): return 
            if not self._power(): return 
            if not self._mass(): return 

        self._apply_resistance_breakdown()

        self._auxiliary()

        if not self._mass(): return

        self.m_Cargo = self.design_mode

        self._solve_volume_limit()
        
        retries = 0
        while not self._power() and retries < 15:
            
            if self.Kpwrerr % self.PITCH_LOW == 0:
                self.text_results.append(f"[Auto-Correcting: Pitch > 1.4. Increasing RPM from {self.N2:.1f} to {self.N2*1.05:.1f}]")
                self.N2 *= 1.05
                self.N1 *= 1.05
                
            elif self.Kpwrerr % self.PITCH_HIGH == 0:
                self.text_results.append(f"[Auto-Correcting: Pitch < 0.5. Decreasing RPM from {self.N2:.1f} to {self.N2*0.95:.1f}]")
                self.N2 *= 0.95
                self.N1 *= 0.95
                
            else:
                break
                
            retries += 1
            
        if self.Kpwrerr != 1:
            self.text_results.append("\nERROR: Propeller design fundamentally failed!")
            self.text_results.append("The physics engine cannot balance the thrust required for this weight/speed.")
            self.text_results.append("Try: 1) Reducing Speed, 2) Reducing Range, or 3) Unchecking 'Prop.dia. to T ratio'.")
            return
        self._apply_resistance_breakdown()

        if not self._mass(): return

        self._power() 

        if not self._power(): return

        self._apply_resistance_breakdown()

        self._auxiliary() 

        if not self._mass(): return

        if self.W1 <= 0:
             self.m_Results += "\n!!! CRITICAL WARNING !!!\n"
             self.m_Results += "Auxiliary weight > Cargo Capacity.\n"
             self.m_Results += "Increase Ship Dimensions or decrease Aux Load.\n"

        if self.m_Econom: 
            if not self._cost(): return
            
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

        
        self.text_results.setEnabled(True) 
        # Capture CII and volume-budget snapshots so batch callers can read
        # them via get_result_value without depending on _outvdu running first
        # or on output checkboxes being ticked.
        self._compute_cii()
        self._capture_volume_budget()
        self._outvdu() 
        self.btn_save.setEnabled(True) 
        
        self._initdata(1) 
        self._update_data_to_ui() 
        self._reset_dlg() 
        
    def on_run_range(self):
        """
        Runs a calculation over a range of values
        and saves the results to a CSV file.
        Pop-up errors are suppressed during this run.
        """

        try:
            param_name = self.combo_param_vary.currentText()
            start = float(self.edit_range_start.text())
            end = float(self.edit_range_end.text())
            steps = int(self.edit_range_steps.text())
            
            if steps < 2:
                self._show_error("Steps must be 2 or more.")
                return
            if start == end:
                self._show_error("Start and End values cannot be the same.")
                return
                
        except ValueError as e:
            self._show_error(f"Invalid number in range inputs: {e}")
            return

        fileName, _ = QFileDialog.getSaveFileName(self, "Save Range Analysis CSV",
            "ship_range_analysis.csv", "CSV Files (*.csv);;All Files (*)")
        
        if not fileName:
            return 

        value_range = np.linspace(start, end, steps)

        # CSV header — extended for chapter 5. New columns are appended at the
        # end so prior CSVs remain readable and column indexes stay backward
        # compatible up to "BuildCost(M$)".
        header = [
            param_name, "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB", 
            "Displacement(t)", "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)", 
            "InstalledPower(kW)", "BuildCost(M$)",
            # --- new columns ---
            "SteelCost(M$)", "OutfitCost(M$)", "MachineryCost(M$)",
            "AnnualisedCAPEX($)", "AnnualOPEX($)",
            "AnnualFuelCost($)", "AnnualCarbonTax($)",
            "VolCargo(m3)", "VolFuel(m3)", "VolMachinery(m3)", "VolStores(m3)",
            "VolAvail(m3)", "VolUtilisation%",
            "FuelVolume(m3)", "FuelVol%Hull",
            "VolExpansionIters",
            "AttainedCII", "RequiredCII", "CIIRating",
            "EEDI(gCO2/t.nm)",
        ]
        
        is_econom_on = self.check_econom.isChecked()
        if is_econom_on:
            if self.radio_teu.isChecked():
                header.append("RFR($/TEU)")
            else:
                header.append("RFR($/tonne)")

        self.m_Results = f"Running range analysis for '{param_name}'...\r\nSaving to {fileName}\r\n"
        self.text_results.setText(self.m_Results)
        self.Kcases = 0 

        original_ui_state = {
            'speed': self.edit_speed.text(),
            'weight': self.edit_weight.text(),
            'teu': self.edit_teu.text(),
            'lbratio_v': self.edit_lbratio.text(),
            'bvalue_v': self.edit_bvalue.text(),
            'btratio_v': self.edit_btratio.text(),
            'cbvalue_v': self.edit_cbvalue.text(),
            'cargo_r': self.radio_cargo.isChecked(),
            'ship_r': self.radio_ship.isChecked(),
            'teu_r': self.radio_teu.isChecked(),
            'lbratio_c': self.check_lbratio.isChecked(),
            'bvalue_c': self.check_bvalue.isChecked(),
            'btratio_c': self.check_btratio.isChecked(),
            'cbvalue_c': self.check_cbvalue.isChecked(),
            'ignspd': self.ignspd,
            'ignpth': self.ignpth,
            'fuel_vol_c': self.check_fuel_vol.isChecked(),
        }
        self.ignspd = True
        self.ignpth = True

        self.is_batch_mode = True
        total_skipped = 0

        try:
            with open(fileName, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                
                is_teu_mode = original_ui_state['teu_r']
                
                for i, value in enumerate(value_range):
                    self.text_results.append(f"Running step {i+1}/{steps} ({param_name} = {value:.4f})...")
                    QApplication.processEvents()

                    if param_name == "Speed(knts)":
                        self.edit_speed.setText(str(value))
                    elif param_name == "Cargo deadweight(t)":
                        self.radio_cargo.setChecked(True)
                        self.edit_weight.setText(str(value))
                    elif param_name == "TEU Capacity":
                        self.radio_teu.setChecked(True)
                        self.edit_teu.setText(str(value))
                    elif param_name == "L/B Ratio":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_lbratio.setChecked(True)
                        self.edit_lbratio.setText(str(value))
                    elif param_name == "B(m)":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_bvalue.setChecked(True)
                        self.edit_bvalue.setText(str(value))
                    elif param_name == "B/T Ratio":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_btratio.setChecked(True)
                        self.edit_btratio.setText(str(value))
                    elif param_name == "Block Co.":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_cbvalue.setChecked(True)
                        self.edit_cbvalue.setText(str(value))
                    
                    elif param_name == "Reactor Cost ($/kW)":
                        self.edit_reactor_cost.setText(str(value))
                    elif param_name == "Range (nm)":
                        self.edit_range.setText(str(value))
                    elif param_name == "Fuel Cost ($/t)":
                        self.edit_fuel.setText(str(value))
                    elif param_name == "Interest Rate (%)":
                        self.edit_interest.setText(str(value))
                    elif param_name == "Carbon Tax ($/t)":
                        self.edit_ctax_rate.setText(str(value))
                        self.check_carbon_tax.setChecked(True)
                    # ----- New chapter-5 sweep parameters -----
                    elif param_name == "Sea days/year":
                        self.edit_seadays.setText(str(value))
                    elif param_name == "Air Lub Eff. (%)":
                        # Auto-tick the checkbox so the ESD physics actually engages.
                        # Sweeping the percentage with the checkbox unticked would
                        # silently produce flat curves and confuse the user.
                        self.check_als.setChecked(True)
                        self.edit_als_eff.setText(str(value))
                    elif param_name == "Wind Power Sav. (%)":
                        self.check_wind.setChecked(True)
                        self.edit_wind_sav.setText(str(value))
                    elif param_name == "Methane Slip (%)":
                        self.edit_methane_slip.setText(str(value))
                        # Methane slip only matters if the carbon tax is on,
                        # since it's applied through the effective carbon factor.
                        # Tick it automatically so the user sees the effect.
                        self.check_carbon_tax.setChecked(True)
                    
                    self.on_calculate() 
                    
                    row = [f"{value:.6g}"]
                    if not self.CalculatedOk:
                        total_skipped += 1
                        row.extend(["CALCULATION FAILED"] * (len(header) - 1))
                    else:
                        # Core dimensional / mass / power block (unchanged
                        # column order so old CSVs and existing scripts still
                        # parse).
                        row.extend([
                            f"{self.L1:.2f}",
                            f"{self.B:.2f}",
                            f"{self.D:.2f}",
                            f"{self.T:.2f}",
                            f"{self.C:.4f}",
                            f"{self.M:.0f}",  # Displacement
                            f"{self.W1:.0f}", # Cargo DW
                            f"{self.W5:.0f}", # Total DW
                            f"{0.7457 * self.P1:.0f}", # ServicePower(kW)
                            f"{0.7457 * self.P2:.0f}", # InstalledPower(kW)
                            f"{self.S:.3f}" if is_econom_on else "N/A", # BuildCost(M$)
                        ])

                        # ----- New cost decomposition (chapter 5) -----
                        if is_econom_on:
                            row.extend([
                                f"{getattr(self, 'cost_steel_M', 0.0):.3f}",
                                f"{getattr(self, 'cost_outfit_M', 0.0):.3f}",
                                f"{getattr(self, 'cost_machinery_M', 0.0):.3f}",
                                f"{getattr(self, 'H1', 0.0):.0f}",
                                f"{getattr(self, 'annual_opex', 0.0):.0f}",
                                f"{getattr(self, 'annual_fuel_cost_only', 0.0):.0f}",
                                f"{getattr(self, 'annual_carbon_tax', 0.0):.0f}",
                            ])
                        else:
                            row.extend(["N/A"] * 7)

                        # ----- Volume budget (sec 5.1) -----
                        row.extend([
                            f"{getattr(self, 'vol_cargo', 0.0):.0f}",
                            f"{getattr(self, 'vol_fuel', 0.0):.0f}",
                            f"{getattr(self, 'vol_mach', 0.0):.0f}",
                            f"{getattr(self, 'vol_stores', 0.0):.0f}",
                            f"{getattr(self, 'vol_avail', 0.0):.0f}",
                            f"{getattr(self, 'vol_utilisation_pct', 0.0):.2f}",
                            f"{getattr(self, 'vol_fuel', 0.0):.0f}",  # FuelVolume(m3)
                            f"{getattr(self, 'fuel_vol_pct_hull', 0.0):.2f}",
                            f"{getattr(self, 'vol_expansion_iters', 0)}",
                        ])

                        # ----- CII (sec 5.2 / 5.5) -----
                        row.extend([
                            f"{getattr(self, 'attained_cii', 0.0):.3f}",
                            f"{getattr(self, 'required_cii', 0.0):.3f}",
                            getattr(self, 'cii_rating', 'N/A'),
                        ])

                        # ----- EEDI (computed inline; matches battle code) -----
                        try:
                            fd = FuelConfig.get(self.combo_engine.currentText())
                            lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                            sfc_g_kwh = 3600.0 / (lhv * fd["Efficiency"])
                            cap = self.W1 if self.W1 > 1.0 else 1.0
                            p_me = 0.75 * (self.P2 * 0.7457)
                            cf = fd["Carbon"]
                            if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                                cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
                            eedi = (p_me * cf * sfc_g_kwh) / (cap * self.V) if self.V > 0 else 0.0
                            row.append(f"{eedi:.2f}")
                        except Exception:
                            row.append("N/A")

                        # ----- RFR (kept last, matches legacy column position
                        # when the econom flag is on) -----
                        if is_econom_on:
                            if is_teu_mode:
                                rfr_val = self.Rf * self.m_TEU_Avg_Weight
                            else:
                                rfr_val = self.Rf
                            row.append(f"{rfr_val:.4f}")

                    writer.writerow(row)
            
            self.text_results.append(f"\r\n... Range analysis complete. ...")
            
            msg = f"Successfully saved {steps} rows to {fileName}"
            if total_skipped > 0:
                msg += f"\n\nNote: {total_skipped} calculation(s) failed due to physical constraints and were marked as FAILED."
            QMessageBox.information(self, "Range Analysis Complete", msg)

        except Exception as e:
            self._show_error(f"Failed to write CSV file: {e}")
        
        finally:
            self.is_batch_mode = False
            
            self.edit_speed.setText(original_ui_state['speed'])
            self.edit_weight.setText(original_ui_state['weight'])
            self.edit_teu.setText(original_ui_state['teu'])
            self.edit_lbratio.setText(original_ui_state['lbratio_v'])
            self.edit_bvalue.setText(original_ui_state['bvalue_v'])
            self.edit_btratio.setText(original_ui_state['btratio_v'])
            self.edit_cbvalue.setText(original_ui_state['cbvalue_v'])
            
            self.radio_cargo.setChecked(original_ui_state['cargo_r'])
            self.radio_ship.setChecked(original_ui_state['ship_r'])
            self.radio_teu.setChecked(original_ui_state['teu_r'])
            self.check_lbratio.setChecked(original_ui_state['lbratio_c'])
            self.check_bvalue.setChecked(original_ui_state['bvalue_c'])
            self.check_btratio.setChecked(original_ui_state['btratio_c'])
            self.check_cbvalue.setChecked(original_ui_state['cbvalue_c'])
            self.check_fuel_vol.setChecked(original_ui_state['fuel_vol_c'])
            
            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            
            self.m_Results = "Press the Calculate button\r\nto find ship dimensions ..."
            self.text_results.setText(self.m_Results)
            self.CalculatedOk = False
            self.Kcases = 0
            self._reset_dlg()

    def on_run_plot(self):
        """
        Runs a calculation over a range (1D or 2D) and plots the results.
        """
        if FigureCanvas is None:
            self._show_error("Matplotlib not found.")
            return

        try:
            param_name_1 = self.combo_param_vary.currentText()
            start_1 = float(self.edit_range_start.text())
            end_1 = float(self.edit_range_end.text())
            steps_1 = int(self.edit_range_steps.text())
            
            is_3d = self.check_enable_3d.isChecked()
            param_name_2 = ""
            start_2, end_2, steps_2 = 0.0, 0.0, 0
            
            if is_3d:
                param_name_2 = self.combo_param_vary_2.currentText()
                start_2 = float(self.edit_range_start_2.text())
                end_2 = float(self.edit_range_end_2.text())
                steps_2 = int(self.edit_range_steps_2.text())
                if steps_2 < 2: raise ValueError("Steps must be >= 2")
                if param_name_1 == param_name_2:
                    self._show_error("Input 1 and Input 2 cannot be the same parameter.")
                    return

            y_param_name = self.combo_param_y.currentText() 
            
            if steps_1 < 2: raise ValueError("Steps must be >= 2")

        except ValueError as e:
            self._show_error(f"Invalid input: {e}")
            return

        original_ui_state = {
            'speed': self.edit_speed.text(),
            'weight': self.edit_weight.text(),
            'teu': self.edit_teu.text(),
            'reactor_cost': self.edit_reactor_cost.text(),
            'lbratio_v': self.edit_lbratio.text(),
            'bvalue_v': self.edit_bvalue.text(),
            'btratio_v': self.edit_btratio.text(),
            'cbvalue_v': self.edit_cbvalue.text(),
            'ignspd': self.ignspd, 'ignpth': self.ignpth,
            'cargo_r': self.radio_cargo.isChecked(),
            'ship_r': self.radio_ship.isChecked(),
            'teu_r': self.radio_teu.isChecked(),
            'lbratio_c': self.check_lbratio.isChecked(),
            'bvalue_c': self.check_bvalue.isChecked(),
            'btratio_c': self.check_btratio.isChecked(),
            'cbvalue_c': self.check_cbvalue.isChecked(),
            'fuel_vol_c': self.check_fuel_vol.isChecked(),
            # ----- New chapter-5 state to restore -----
            'seadays': self.edit_seadays.text(),
            'als_eff': self.edit_als_eff.text(),
            'als_chk': self.check_als.isChecked(),
            'wind_sav': self.edit_wind_sav.text(),
            'wind_chk': self.check_wind.isChecked(),
            'methane_slip': self.edit_methane_slip.text(),
            'ctax_chk': self.check_carbon_tax.isChecked(),
        }
        self.ignspd = True; self.ignpth = True

        self.is_batch_mode = True
        total_skipped = 0

        try:
            range_1 = np.linspace(start_1, end_1, steps_1)
            
            if is_3d:
                range_2 = np.linspace(start_2, end_2, steps_2)
                X, Y = np.meshgrid(range_1, range_2)
                Z = np.zeros((steps_2, steps_1))
                
                total_steps = steps_1 * steps_2
                current_step = 0
            else:
                X, Y, Z = [], [], None

            def set_param_value(name, val):
                if name == "Speed(knts)": 
                    self.edit_speed.setText(str(val))
                elif name == "Cargo deadweight(t)": 
                    self.edit_weight.setText(str(val)); self.radio_cargo.setChecked(True)
                elif name == "TEU Capacity": 
                    self.edit_teu.setText(str(val)); self.radio_teu.setChecked(True)
                elif name == "L/B Ratio": 
                    self.edit_lbratio.setText(str(val)); self.check_lbratio.setChecked(True)
                elif name == "B(m)": 
                    self.edit_bvalue.setText(str(val)); self.check_bvalue.setChecked(True)
                elif name == "B/T Ratio": 
                    self.edit_btratio.setText(str(val)); self.check_btratio.setChecked(True)
                elif name == "Block Co.": 
                    self.edit_cbvalue.setText(str(val)); self.check_cbvalue.setChecked(True)
                
                elif name == "Reactor Cost ($/kW)": 
                    self.edit_reactor_cost.setText(str(val))
                elif name == "Range (nm)":
                    self.edit_range.setText(str(val))
                elif name == "Fuel Cost ($/t)":
                    self.edit_fuel.setText(str(val))
                elif name == "Interest Rate (%)":
                    self.edit_interest.setText(str(val))
                elif name == "Carbon Tax ($/t)":
                    self.edit_ctax_rate.setText(str(val)); self.check_carbon_tax.setChecked(True)
                # ----- New chapter-5 sweep parameters -----
                elif name == "Sea days/year":
                    self.edit_seadays.setText(str(val))
                elif name == "Air Lub Eff. (%)":
                    self.check_als.setChecked(True)
                    self.edit_als_eff.setText(str(val))
                elif name == "Wind Power Sav. (%)":
                    self.check_wind.setChecked(True)
                    self.edit_wind_sav.setText(str(val))
                elif name == "Methane Slip (%)":
                    self.edit_methane_slip.setText(str(val))
                    self.check_carbon_tax.setChecked(True)

            def get_result_value(name):
                if not self.CalculatedOk: return np.nan
                is_econom = self.check_econom.isChecked()
                is_teu = self.radio_teu.isChecked()
                
                if name == "RFR($/tonne or $/TEU)":
                    if not is_econom: return np.nan
                    return self.Rf * self.m_TEU_Avg_Weight if is_teu else self.Rf
                
                elif name == "Lbp(m)": return self.L1
                elif name == "B(m)": return self.B
                elif name == "D(m)": return self.D
                elif name == "T(m)": return self.T
                elif name == "CB": return self.C
                elif name == "Displacement(t)": return self.M
                elif name == "CargoDW(t)": return self.W1
                elif name == "TotalDW(t)": return self.W5
                
                elif name == "ServicePower(kW)": return 0.7457 * self.P1
                elif name == "InstalledPower(kW)": return 0.7457 * self.P2
                
                elif name == "BuildCost(M$)": return self.S if is_econom else np.nan
                # ----- New chapter-5 result options -----
                elif name == "AnnualFuelCost(M$)":
                    return (self.H7 / 1e6) if is_econom else np.nan
                elif name == "AnnualCarbonTax(M$)":
                    return (getattr(self, 'annual_carbon_tax', 0.0) / 1e6) if is_econom else np.nan
                elif name == "AnnualisedCAPEX(M$)":
                    return (getattr(self, 'H1', 0.0) / 1e6) if is_econom else np.nan
                elif name == "AnnualOPEX(M$)":
                    return (getattr(self, 'annual_opex', 0.0) / 1e6) if is_econom else np.nan
                elif name == "EEDI(gCO2/t.nm)":
                    try:
                        fd = FuelConfig.get(self.combo_engine.currentText())
                        lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                        sfc_g_kwh = 3600.0 / (lhv * fd["Efficiency"])
                        cap = self.W1 if self.W1 > 1.0 else 1.0
                        p_me = 0.75 * (self.P2 * 0.7457)
                        cf = fd["Carbon"]
                        if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                            cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
                        return (p_me * cf * sfc_g_kwh) / (cap * self.V) if self.V > 0 else np.nan
                    except Exception:
                        return np.nan
                elif name == "AttainedCII":
                    return getattr(self, 'attained_cii', np.nan)
                elif name == "FuelVolume(m3)":
                    return getattr(self, 'vol_fuel', np.nan)
                elif name == "FuelVol%Hull":
                    return getattr(self, 'fuel_vol_pct_hull', np.nan)
                elif name == "VolCargo(m3)":
                    return getattr(self, 'vol_cargo', np.nan)
                elif name == "VolFuel(m3)":
                    return getattr(self, 'vol_fuel', np.nan)
                elif name == "VolMachinery(m3)":
                    return getattr(self, 'vol_mach', np.nan)
                elif name == "VolStores(m3)":
                    return getattr(self, 'vol_stores', np.nan)
                elif name == "VolUtilisation%":
                    return getattr(self, 'vol_utilisation_pct', np.nan)
                
                return 0.0

            self.text_results.append("Starting analysis...")
            
            if is_3d:
                for i in range(steps_2):
                    val_2 = range_2[i]
                    set_param_value(param_name_2, val_2)
                    
                    for j in range(steps_1):
                        val_1 = range_1[j]
                        set_param_value(param_name_1, val_1)
                        
                        self.on_calculate()
                    
                        if not self.CalculatedOk:
                            total_skipped += 1
                            
                        Z[i, j] = get_result_value(y_param_name)
                        
                        current_step += 1
                        if current_step % 5 == 0: QApplication.processEvents()
                        
                self.graph_window = GraphWindow(X, Y, Z, param_name_1, param_name_2, y_param_name, 
                                              f"{y_param_name} (Wireframe)")
            else:
                x_data = []; y_data = []
                for val in range_1:
                    set_param_value(param_name_1, val)
                    self.on_calculate()
                    
                    if not self.CalculatedOk:
                        total_skipped += 1
                        
                    res = get_result_value(y_param_name)
                    if not np.isnan(res):
                        x_data.append(val)
                        y_data.append(res)
                
                self.graph_window = GraphWindow(x_data, y_data, None, param_name_1, y_param_name, "", 
                                              f"{y_param_name} vs {param_name_1}")

            self.graph_window.show()
            self.text_results.append("Plot complete.")
            
            if total_skipped > 0:
                summary_msg = f"{total_skipped} calculation(s) were skipped/omitted from the plot due to physical constraints."
                self.text_results.append(f"Note: {summary_msg}")
                QMessageBox.warning(self, "Plot Missing Data", summary_msg)

        except Exception as e:
            self._show_error(f"Error during plot: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.is_batch_mode = False
            
            self.edit_speed.setText(original_ui_state['speed'])
            self.edit_weight.setText(original_ui_state['weight'])
            self.edit_teu.setText(original_ui_state['teu'])
            self.edit_reactor_cost.setText(original_ui_state['reactor_cost'])
            self.edit_lbratio.setText(original_ui_state['lbratio_v'])
            self.edit_bvalue.setText(original_ui_state['bvalue_v'])
            self.edit_btratio.setText(original_ui_state['btratio_v'])
            self.edit_cbvalue.setText(original_ui_state['cbvalue_v'])
            
            self.radio_cargo.setChecked(original_ui_state['cargo_r'])
            self.radio_ship.setChecked(original_ui_state['ship_r'])
            self.radio_teu.setChecked(original_ui_state['teu_r'])
            self.check_lbratio.setChecked(original_ui_state['lbratio_c'])
            self.check_bvalue.setChecked(original_ui_state['bvalue_c'])
            self.check_btratio.setChecked(original_ui_state['btratio_c'])
            self.check_cbvalue.setChecked(original_ui_state['cbvalue_c'])
            self.check_fuel_vol.setChecked(original_ui_state['fuel_vol_c'])

            # Restore chapter-5 fields if present (older saved-state dicts
            # won't have them — keys() guard avoids KeyError on legacy paths).
            if 'seadays' in original_ui_state:
                self.edit_seadays.setText(original_ui_state['seadays'])
                self.edit_als_eff.setText(original_ui_state['als_eff'])
                self.check_als.setChecked(original_ui_state['als_chk'])
                self.edit_wind_sav.setText(original_ui_state['wind_sav'])
                self.check_wind.setChecked(original_ui_state['wind_chk'])
                self.edit_methane_slip.setText(original_ui_state['methane_slip'])
                self.check_carbon_tax.setChecked(original_ui_state['ctax_chk'])

            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            self._reset_dlg()
    
    def on_run_battle(self):
        """
        Runs the 'Battle Mode': Plots a selected output against a selected input for any number of engines.
        """
        if FigureCanvas is None:
            self._show_error("Matplotlib not found.")
            return

        try:
            param_x = self.combo_battle_x.currentText()
            param_y = self.combo_battle_y.currentText()
            start_val = float(self.edit_battle_start.text())
            end_val = float(self.edit_battle_end.text())
            steps = int(self.edit_battle_steps.text())
            if steps < 2: raise ValueError("Steps must be >= 2")
        except ValueError:
            self._show_error("Invalid range inputs. Ensure start, end, and steps are valid numbers.")
            return
            
        selected_items = self.list_battle_engines.selectedItems()
        if len(selected_items) < 2:
            self._show_error("Please select at least two engines to compare.")
            return

        selected_engines = [item.text() for item in selected_items]
        
        # Launch the Configuration Dialog for fuel prices / taxes
        config_dlg = BattleFuelConfigDialog(
            selected_engines, 
            self.edit_fuel.text(), 
            self.edit_ctax_rate.text(), 
            self
        )
        
        if not config_dlg.exec():
            return # User pressed cancel
            
        engine_configs = config_dlg.result_data

        # Save original UI state to restore later
        original_ui_state = {
            'engine_idx': self.combo_engine.currentIndex(),
            'speed': self.edit_speed.text(),
            'weight': self.edit_weight.text(),
            'teu': self.edit_teu.text(),
            'fuel_price': self.edit_fuel.text(),
            'carbon_tax': self.edit_ctax_rate.text(),
            'reactor_cost': self.edit_reactor_cost.text(),
            'range': self.edit_range.text(),
            'interest': self.edit_interest.text(),
            'lbratio_v': self.edit_lbratio.text(),
            'bvalue_v': self.edit_bvalue.text(),
            'btratio_v': self.edit_btratio.text(),
            'cbvalue_v': self.edit_cbvalue.text(),
            'ignspd': self.ignspd, 'ignpth': self.ignpth,
            'econom': self.check_econom.isChecked(),
            'cargo_r': self.radio_cargo.isChecked(),
            'ship_r': self.radio_ship.isChecked(),
            'teu_r': self.radio_teu.isChecked(),
            'lbratio_c': self.check_lbratio.isChecked(),
            'bvalue_c': self.check_bvalue.isChecked(),
            'btratio_c': self.check_btratio.isChecked(),
            'cbvalue_c': self.check_cbvalue.isChecked(),
            'ctax_c': self.check_carbon_tax.isChecked(),
            'fuel_vol_c': self.check_fuel_vol.isChecked(),
            # ----- New chapter-5 state to restore -----
            'seadays': self.edit_seadays.text(),
            'als_eff': self.edit_als_eff.text(),
            'als_chk': self.check_als.isChecked(),
            'wind_sav': self.edit_wind_sav.text(),
            'wind_chk': self.check_wind.isChecked(),
            'methane_slip': self.edit_methane_slip.text(),
        }
        
        self.ignspd = True; self.ignpth = True 
        self.check_econom.setChecked(True)     
        
        x_values = np.linspace(start_val, end_val, steps)
        battle_results = {}

        self.is_batch_mode = True
        total_skipped = 0

        # Helpers for setting and getting dynamic parameters
        def set_param_value(name, val):
            if name == "Speed(knts)": self.edit_speed.setText(str(val))
            elif name == "Cargo deadweight(t)": self.edit_weight.setText(str(val)); self.radio_cargo.setChecked(True)
            elif name == "TEU Capacity": self.edit_teu.setText(str(val)); self.radio_teu.setChecked(True)
            elif name == "L/B Ratio": self.edit_lbratio.setText(str(val)); self.check_lbratio.setChecked(True)
            elif name == "B(m)": self.edit_bvalue.setText(str(val)); self.check_bvalue.setChecked(True)
            elif name == "B/T Ratio": self.edit_btratio.setText(str(val)); self.check_btratio.setChecked(True)
            elif name == "Block Co.": self.edit_cbvalue.setText(str(val)); self.check_cbvalue.setChecked(True)
            elif name == "Reactor Cost ($/kW)": self.edit_reactor_cost.setText(str(val))
            elif name == "Range (nm)": self.edit_range.setText(str(val))
            elif name == "Fuel Cost ($/t)": self.edit_fuel.setText(str(val))
            elif name == "Interest Rate (%)": self.edit_interest.setText(str(val))
            elif name == "Carbon Tax ($/t)": self.edit_ctax_rate.setText(str(val)); self.check_carbon_tax.setChecked(True)
            # ----- New chapter-5 sweep parameters -----
            elif name == "Sea days/year": self.edit_seadays.setText(str(val))
            elif name == "Air Lub Eff. (%)":
                self.check_als.setChecked(True); self.edit_als_eff.setText(str(val))
            elif name == "Wind Power Sav. (%)":
                self.check_wind.setChecked(True); self.edit_wind_sav.setText(str(val))
            elif name == "Methane Slip (%)":
                self.edit_methane_slip.setText(str(val))
                self.check_carbon_tax.setChecked(True)

        def get_result_value(name):
            if not self.CalculatedOk: return np.nan
            is_econom = self.check_econom.isChecked()
            is_teu = self.radio_teu.isChecked()
            
            if name == "RFR($/tonne or $/TEU)":
                if not is_econom: return np.nan
                return self.Rf * self.m_TEU_Avg_Weight if is_teu else self.Rf
            elif name == "Lbp(m)": return self.L1
            elif name == "B(m)": return self.B
            elif name == "D(m)": return self.D
            elif name == "T(m)": return self.T
            elif name == "CB": return self.C
            elif name == "Displacement(t)": return self.M
            elif name == "CargoDW(t)": return self.W1
            elif name == "TotalDW(t)": return self.W5
            elif name == "ServicePower(kW)": return 0.7457 * self.P1
            elif name == "InstalledPower(kW)": return 0.7457 * self.P2
            elif name == "BuildCost(M$)": return self.S if is_econom else np.nan
            elif name == "AnnualFuelCost(M$)": return self.H7 / 1e6 if is_econom else np.nan
            elif name == "AnnualCarbonTax(M$)":
                return (getattr(self, 'annual_carbon_tax', 0.0) / 1e6) if is_econom else np.nan
            elif name == "AnnualisedCAPEX(M$)":
                return (getattr(self, 'H1', 0.0) / 1e6) if is_econom else np.nan
            elif name == "AnnualOPEX(M$)":
                return (getattr(self, 'annual_opex', 0.0) / 1e6) if is_econom else np.nan
            elif name == "EEDI(gCO2/t.nm)":
                try:
                    fuel_data = FuelConfig.get(self.combo_engine.currentText())
                    lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                    eff = fuel_data["Efficiency"]
                    sfc_g_kwh = 3600.0 / (lhv * eff)
                    capacity = self.W1 if self.W1 > 1.0 else 1.0
                    p_me = 0.75 * (self.P2 * 0.7457)
                    cf = self._effective_carbon_factor(fuel_data)
                    if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                        cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
                    return (p_me * cf * sfc_g_kwh) / (capacity * self.V)
                except:
                    return np.nan
            elif name == "AttainedCII":
                return getattr(self, 'attained_cii', np.nan)
            elif name == "FuelVolume(m3)":
                return getattr(self, 'vol_fuel', np.nan)
            elif name == "FuelVol%Hull":
                return getattr(self, 'fuel_vol_pct_hull', np.nan)
            elif name == "VolCargo(m3)":
                return getattr(self, 'vol_cargo', np.nan)
            elif name == "VolFuel(m3)":
                return getattr(self, 'vol_fuel', np.nan)
            elif name == "VolMachinery(m3)":
                return getattr(self, 'vol_mach', np.nan)
            elif name == "VolStores(m3)":
                return getattr(self, 'vol_stores', np.nan)
            elif name == "VolUtilisation%":
                return getattr(self, 'vol_utilisation_pct', np.nan)
            return 0.0

        try:
            self.text_results.append(f"\n--- MULTI-ENGINE BATTLE ---")
            self.text_results.append(f"Comparing: {', '.join(selected_engines)}")
            self.text_results.append(f"X-Axis: {param_x} | Y-Axis: {param_y}")
            
            for engine_name in selected_engines:
                self.text_results.append(f"Calculating {engine_name}...")
                
                idx = self.combo_engine.findText(engine_name)
                self.combo_engine.setCurrentIndex(idx)
                
                custom_price = engine_configs[engine_name]['price']
                custom_tax = engine_configs[engine_name]['tax']
                custom_carbon = engine_configs[engine_name].get('carbon')
                self.edit_fuel.setText(str(custom_price))
                self.edit_ctax_rate.setText(str(custom_tax))
                # Override the carbon factor for the duration of this
                # engine's sweep.  Reset to None in the finally block so
                # subsequent ordinary calculations are unaffected.
                self.m_CarbonOverride = custom_carbon
                
                QApplication.processEvents() 
                
                valid_x = []
                valid_y = []
                
                for val in x_values:
                    set_param_value(param_x, val)
                    self.on_calculate()
                    
                    if self.CalculatedOk:
                        res = get_result_value(param_y)
                        if not np.isnan(res):
                            valid_x.append(val)
                            valid_y.append(res)
                    else:
                        total_skipped += 1
                
                battle_results[engine_name] = (valid_x, valid_y)

            # Store metadata for plotting and exporting
            self.last_battle_results = battle_results
            self.battle_x_label = param_x
            self.battle_y_label = param_y
            self.btn_export_battle.setEnabled(True)

            self._show_battle_graph(battle_results)
            self.text_results.append("Battle Complete.\n")
            
            if total_skipped > 0:
                summary_msg = f"{total_skipped} calculation(s) were skipped due to physical constraints."
                self.text_results.append(f"Note: {summary_msg}")
                QMessageBox.warning(self, "Calculations Skipped", summary_msg)

        except Exception as e:
            self._show_error(f"Error during comparison: {e}")
            
        finally:
            self.is_batch_mode = False 
            # Carbon-factor override only applies during a battle run; clear
            # it here so subsequent ordinary calculations use the FuelConfig
            # default again.
            self.m_CarbonOverride = None
            
            # Restore UI state completely
            self.combo_engine.setCurrentIndex(original_ui_state['engine_idx'])
            self.edit_speed.setText(original_ui_state['speed'])
            self.edit_weight.setText(original_ui_state['weight'])
            self.edit_teu.setText(original_ui_state['teu'])
            self.edit_fuel.setText(original_ui_state['fuel_price'])
            self.edit_ctax_rate.setText(original_ui_state['carbon_tax'])
            self.edit_reactor_cost.setText(original_ui_state['reactor_cost'])
            self.edit_range.setText(original_ui_state['range'])
            self.edit_interest.setText(original_ui_state['interest'])
            self.edit_lbratio.setText(original_ui_state['lbratio_v'])
            self.edit_bvalue.setText(original_ui_state['bvalue_v'])
            self.edit_btratio.setText(original_ui_state['btratio_v'])
            self.edit_cbvalue.setText(original_ui_state['cbvalue_v'])
            
            self.check_econom.setChecked(original_ui_state['econom'])
            self.radio_cargo.setChecked(original_ui_state['cargo_r'])
            self.radio_ship.setChecked(original_ui_state['ship_r'])
            self.radio_teu.setChecked(original_ui_state['teu_r'])
            self.check_lbratio.setChecked(original_ui_state['lbratio_c'])
            self.check_bvalue.setChecked(original_ui_state['bvalue_c'])
            self.check_btratio.setChecked(original_ui_state['btratio_c'])
            self.check_cbvalue.setChecked(original_ui_state['cbvalue_c'])
            self.check_carbon_tax.setChecked(original_ui_state['ctax_c'])
            self.check_fuel_vol.setChecked(original_ui_state['fuel_vol_c'])

            # Restore chapter-5 fields (guarded for forward-compat).
            if 'seadays' in original_ui_state:
                self.edit_seadays.setText(original_ui_state['seadays'])
                self.edit_als_eff.setText(original_ui_state['als_eff'])
                self.check_als.setChecked(original_ui_state['als_chk'])
                self.edit_wind_sav.setText(original_ui_state['wind_sav'])
                self.check_wind.setChecked(original_ui_state['wind_chk'])
                self.edit_methane_slip.setText(original_ui_state['methane_slip'])

            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            self._reset_dlg()

    def _show_battle_graph(self, results_dict):
        """
        Helper to launch a specialized graph window for multiple lines.
        """
        # Resolve clean labels up-front
        x_label = pretty_label(getattr(self, 'battle_x_label', "Input Variable"))
        y_label_raw = getattr(self, 'battle_y_label', "Output Variable")
        if y_label_raw == "RFR($/tonne or $/TEU)":
            unit = "$/TEU" if self.radio_teu.isChecked() else "$/tonne"
            y_label = f"Required Freight Rate ({unit})"
        else:
            y_label = pretty_label(y_label_raw)

        # Escape '$' so matplotlib doesn't pair the dollars in
        # ($/TEU)...($/tonne CO2) into a math-mode region (which would
        # collapse spaces and italicise everything between them).
        x_label = mpl_safe(x_label)
        y_label = mpl_safe(y_label)

        if not hasattr(self, 'battle_window') or self.battle_window is None:
            self.battle_window = QWidget()
            self.battle_window.setWindowTitle("Competitive Analysis")
            self.battle_window.resize(1000, 720)
            layout = QVBoxLayout(self.battle_window)

            self.battle_fig = Figure(figsize=(9, 6), dpi=100)
            self.battle_fig.patch.set_facecolor('white')
            self.battle_canvas = FigureCanvas(self.battle_fig)
            self.battle_ax = self.battle_fig.add_subplot(111)

            layout.addWidget(NavigationToolbar(self.battle_canvas, self.battle_window))
            layout.addWidget(self.battle_canvas)

            btn_save = QPushButton("Save as PNG (300 dpi)")
            btn_save.clicked.connect(self._save_battle_png)
            layout.addWidget(btn_save)

        ax = self.battle_ax
        ax.clear()

        markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'X', 'h', '+']
        # Wong 2011 colour-blind-safe palette
        colors = ['#0072B2', '#D55E00', '#009E73', '#CC79A7',
                  '#F0E442', '#56B4E9', '#E69F00', '#000000']

        for i, (engine_name, (x_data, y_data)) in enumerate(results_dict.items()):
            if x_data and y_data:
                ax.plot(x_data, y_data,
                        marker=markers[i % len(markers)],
                        color=colors[i % len(colors)],
                        label=engine_name,
                        linewidth=2, markersize=6)

        ax.set_xlabel(x_label, fontsize=11)
        ax.set_ylabel(y_label, fontsize=11)
        ax.set_title(f"{y_label} vs {x_label}", fontsize=13, fontweight='bold', pad=15)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(frameon=True, framealpha=0.9, edgecolor='gray', loc='best')

        self.battle_fig.tight_layout()
        self.battle_canvas.draw()
        self.battle_window.show()

    def _save_battle_png(self):
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Competitive Analysis", "competitive_analysis.png",
            "PNG Image (*.png);;PDF (*.pdf);;SVG (*.svg)"
        )
        if fileName and hasattr(self, 'battle_fig'):
            self.battle_fig.savefig(fileName, dpi=300, bbox_inches='tight', facecolor='white')

    def on_export_battle_csv(self):
        """
        Exports the stored multi-engine battle results to a CSV file.
        """
        if not hasattr(self, 'last_battle_results') or not self.last_battle_results:
            return
            
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Battle Results", "battle_comparison.csv", "CSV Files (*.csv);;All Files (*)"
        )
        
        if not fileName:
            return
            
        try:
            with open(fileName, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                engines = list(self.last_battle_results.keys())
                
                # Retrieve the longest X-array in case some engines failed early
                x_values = []
                for eng in engines:
                    if len(self.last_battle_results[eng][0]) > len(x_values):
                        x_values = self.last_battle_results[eng][0]
                
                x_label = getattr(self, 'battle_x_label', "Input Variable")
                y_label = getattr(self, 'battle_y_label', "Output Variable")
                if y_label == "RFR($/tonne or $/TEU)":
                    unit = "$/TEU" if self.radio_teu.isChecked() else "$/tonne"
                    y_label = f"RFR ({unit})"
                
                header = [x_label] + [f"{eng} - {y_label}" for eng in engines]
                writer.writerow(header)
                
                for i in range(len(x_values)):
                    row = [f"{x_values[i]:.4f}"]
                    for engine in engines:
                        eng_x = self.last_battle_results[engine][0]
                        eng_y = self.last_battle_results[engine][1]
                        
                        # Match X values exactly to handle differing failure points
                        try:
                            idx = eng_x.index(x_values[i])
                            row.append(f"{eng_y[idx]:.4f}")
                        except ValueError:
                            row.append("N/A")
                            
                    writer.writerow(row)
                    
            QMessageBox.information(self, "Export Complete", f"Successfully saved battle results to:\n{fileName}")
            
        except Exception as e:
            self._show_error(f"Failed to write CSV file: {e}")

    def _freeboard(self):
        """Port of Sub_freeboard"""

        ship_name = self.combo_ship.currentText()
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
        ship_name = self.combo_ship.currentText()
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
        _fuel_for_maint = FuelConfig.get(self.combo_engine.currentText())
        _machinery_maint_pct = _fuel_for_maint.get(
            "MaintenancePct", self.m_H3_Maint_Percent
        )
        H3 = self.m_H3_Maint_Percent * (S8 + S9) + _machinery_maint_pct * S0

        self.annual_opex = self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.m_H8_Other
        self.annual_fuel_cost_only = 0.0
        self.annual_carbon_tax = 0.0

        engine_name = self.combo_engine.currentText()
        fuel_data = FuelConfig.get(engine_name)
        
        if fuel_data["IsNuclear"]:
            core_life_safe = self.m_Core_Life if self.m_Core_Life > 0 else 1e-9
            annual_core_cost = S0_nuclear / core_life_safe
            repay_years_safe = self.N if self.N > 0 else 1e-9
            annual_decom_fund = (self.m_Decom_Cost * 1.0e6) / repay_years_safe 
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

            self.annual_fuel_cost_only = annual_fuel_tonnes * self.F8
            self.H7 = self.annual_fuel_cost_only
            
            if self.check_carbon_tax.isChecked():
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
                co2_tonnes = annual_fuel_tonnes * effective_carbon
                annual_tax_bill = co2_tonnes * self.m_CarbonTax
                self.annual_carbon_tax = annual_tax_bill 
                self.H7 += annual_tax_bill

        if hasattr(self, 'aux_cost_annual'):
            self.H7 += self.aux_cost_annual
            self.annual_fuel_cost_only += self.aux_cost_annual
        
        self.annual_premium_income = 0.0
        try:
            if self.check_aux_enable.isChecked():
                prem_rate = float(self.edit_aux_prem.text())
                
                if prem_rate > 0:
                    is_teu = (self.design_mode == 2)
                    total_cargo_units = self.m_TEU if is_teu else self.W1
                    
                    pct_refrigerated = float(self.edit_aux_p1.text()) / 100.0
                    
                    income_per_voyage = (total_cargo_units * pct_refrigerated) * prem_rate
                    self.annual_premium_income = income_per_voyage * self.V7
        except ValueError:
            self.annual_premium_income = 0.0

        Rt = self.H1 + self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.H7 + self.m_H8_Other
        
        Rt_adjusted = Rt - self.annual_premium_income
        
        self.S *= 1.0e-6
        
        W1_safe = self.W1 if self.W1 != 0 else 1e-9
        W7 = self.V7 * W1_safe
        
        if W7 == 0: W7 = 1e-9 

        self.Rf = Rt_adjusted / W7
        
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

        if self.check_als.isChecked():
            try:
                eff_pct = float(self.edit_als_eff.text())
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

        if self.check_wind.isChecked():
            try:
                sav_pct = float(self.edit_wind_sav.text())
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
        
        ship_name = self.combo_ship.currentText()
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

        engine_name = self.combo_engine.currentText()
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
            QMessageBox.information(self, "Debug P5", msg)
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
            QMessageBox.information(self, "Debug V0", msg)
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

    def on_button_save(self):
        """Port of OnButtonSave"""
        if not self.CalculatedOk and self.Ksaved:
            QMessageBox.warning(self, "System:", "No new data to save.")
            return
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Results",
            self.Savefile, "Text Files (*.txt);;All Files (*)")
        if fileName:
            self.Savefile = fileName
            try:
                with open(self.Savefile, 'w', encoding='utf-8') as f:
                    f.write(self.m_Results.replace('\r\n', '\n'))
                self.Ksaved = True
                self._reset_dlg()
            except Exception as e:
                QMessageBox.critical(self, "System:", f"Cannot save file!\n{e}")

    def on_dialog_modify(self):
        """Port of OnDialogModify"""
        self.Kstype = self.combo_ship.currentIndex() + 1
        self.MdfEnable[0] = (self.m_Lbratio or self.m_Bvalue)
        self.MdfEnable[1] = self.m_Cbvalue
        self.dlg_modify.set_enable(self.MdfEnable)
        
        data = {
            'Lb01': self.Lb01, 'Lb02': self.Lb02, 'Lb03': self.Lb03, 'Lb04': self.Lb04, 'Lb05': self.Lb05,
            'Maxit': self.maxit, 'Ignspd': self.ignspd, 'Ignpth': self.ignpth, 'dbgmd': self.dbgmd,
            'Note': f"({self.combo_ship.currentText()} with {self.combo_engine.currentText()})",
            
            'S1_Steel1': self.m_S1_Steel1,
            'S2_Steel2': self.m_S2_Steel2,
            'S3_Outfit1': self.m_S3_Outfit1,
            'S4_Outfit2': self.m_S4_Outfit2,
            'S5_Machinery1': self.m_S5_Machinery1,
            'S6_Machinery2': self.m_S6_Machinery2,
            'H3_Maint_Percent': self.m_H3_Maint_Percent,
            'H2_Crew': self.m_H2_Crew,
            'H4_Port': self.m_H4_Port,
            'H5_Stores': self.m_H5_Stores,
            'H6_Overhead': self.m_H6_Overhead,
        }
        
        if self.Kstype == 1:
            data.update({'Cb01': self.Cb11, 'Cb02': self.Cb12, 'Cb03': self.Cb13, 'Cb04': self.Cb14, 'Cb05': self.Cb15,
                         'L11': self.L111, 'L12': self.L112, 'L13': self.L113})
        elif self.Kstype == 2:
            data.update({'Cb01': self.Cb21, 'Cb02': self.Cb22, 'Cb03': self.Cb23, 'Cb04': self.Cb24, 'Cb05': self.Cb25,
                         'L11': self.L121, 'L12': self.L122, 'L13': self.L123})
        else:
            data.update({'Cb01': self.Cb31, 'Cb02': self.Cb32, 'Cb03': self.Cb33, 'Cb04': self.Cb34, 'Cb05': self.Cb35,
                         'L11': self.L131, 'L12': self.L132, 'L13': self.L133})
        self.dlg_modify.set_data(data)

        if self.dlg_modify.exec():
            data = self.dlg_modify.get_data()
            self.Lb01 = data['Lb01']; self.Lb02 = data['Lb02']; self.Lb03 = data['Lb03']; self.Lb04 = data['Lb04']; self.Lb05 = data['Lb05']
            self.maxit = data['Maxit']; self.ignspd = data['Ignspd']; self.ignpth = data['Ignpth']; self.dbgmd = data['dbgmd']
            
            try:
                # Capital Cost Params
                self.m_S1_Steel1 = float(data['S1_Steel1'])
                self.m_S2_Steel2 = float(data['S2_Steel2'])
                self.m_S3_Outfit1 = float(data['S3_Outfit1'])
                self.m_S4_Outfit2 = float(data['S4_Outfit2'])
                self.m_S5_Machinery1 = float(data['S5_Machinery1'])
                self.m_S6_Machinery2 = float(data['S6_Machinery2'])
                # Annual Cost Params
                self.m_H3_Maint_Percent = float(data['H3_Maint_Percent'])
                self.m_H2_Crew = float(data['H2_Crew'])
                self.m_H4_Port = float(data['H4_Port'])
                self.m_H5_Stores = float(data['H5_Stores'])
                self.m_H6_Overhead = float(data['H6_Overhead'])
            except KeyError:
                 pass 
            except ValueError:
                self._show_error("Invalid number in one of the new cost fields.")
            
            if self.Kstype == 1:
                self.Cb11=data['Cb01']; self.Cb12=data['Cb02']; self.Cb13=data['Cb03']; self.Cb14=data['Cb04']; self.Cb15=data['Cb05']
                self.L111=data['L11']; self.L112=data['L12']; self.L113=data['L13']
            elif self.Kstype == 2:
                self.Cb21=data['Cb01']; self.Cb22=data['Cb02']; self.Cb23=data['Cb03']; self.Cb24=data['Cb04']; self.Cb25=data['Cb05']
                self.L121=data['L11']; self.L122=data['L12']; self.L123=data['L13']
            else:
                self.Cb31=data['Cb01']; self.Cb32=data['Cb02']; self.Cb33=data['Cb03']; self.Cb34=data['Cb04']; self.Cb35=data['Cb05']
                self.L131=data['L11']; self.L132=data['L12']; self.L133=data['L13']

    def on_dialog_outopt(self):
        """Port of OnDialogOutopt"""

        self.dlg_outopt.set_data(self.outopt_data)
        if self.dlg_outopt.exec():
            self.outopt_data = self.dlg_outopt.get_data()
            
    def on_dialog_readme(self):
        """Called from main window menu"""

        self.dlg_readme.exec()

    def _reset_dlg(self, checked=None):
        """
        Refreshes the UI state (Enable/Disable/Hide) based on current selections.
        """
        ship_name = self.combo_ship.currentText()
        ship_data = ShipConfig.get(ship_name)
        ship_id = ship_data.get("ID", 0)

        supports_cooling = (ship_id in [2, 3, 4])
        
        wanted_items = ["None"]
        if ship_id == 4: # Container Ship
            wanted_items.append("Reefer Plugs (Container)")
        elif ship_id in [2, 3]: # Bulk Carrier (2) or Cargo Vessel (3)
            wanted_items.append("Insulated Hold (Bulk)")

        current_items = [self.combo_aux_mode.itemText(i) for i in range(self.combo_aux_mode.count())]
        if current_items != wanted_items:
            self.combo_aux_mode.blockSignals(True)
            self.combo_aux_mode.clear()
            self.combo_aux_mode.addItems(wanted_items)
            self.combo_aux_mode.setCurrentIndex(0) # Default to None
            self.combo_aux_mode.blockSignals(False)

        is_container_ship = (ship_id == 4)
        self.radio_teu.setEnabled(is_container_ship)
        
        if is_container_ship:
             if not self.radio_teu.isChecked() and not self.radio_cargo.isChecked():
                 self.radio_teu.setChecked(True)
        elif self.radio_teu.isChecked():
             self.radio_cargo.setChecked(True)

        is_aux_on = self.check_aux_enable.isChecked()
        
        self.label_aux_base.setVisible(is_aux_on)
        self.edit_aux_base.setVisible(is_aux_on)
        
        # B. Cooling Dropdown: Visible if Aux is ON -AND- Ship Supports it
        show_cooling_selector = is_aux_on and supports_cooling
        
        self.label_aux_mode_title.setVisible(show_cooling_selector)
        self.combo_aux_mode.setVisible(show_cooling_selector)
        
        # C. Cooling Inputs (p1, p2, prem): Visible if Selector is Visible -AND- Mode is not None
        current_mode_text = self.combo_aux_mode.currentText()
        show_ref_inputs = show_cooling_selector and ("None" not in current_mode_text)
        
        self.label_aux_p1.setVisible(show_ref_inputs)
        self.edit_aux_p1.setVisible(show_ref_inputs)
        self.label_aux_p2.setVisible(show_ref_inputs)
        self.edit_aux_p2.setVisible(show_ref_inputs)
        self.label_aux_prem.setVisible(show_ref_inputs)
        self.edit_aux_prem.setVisible(show_ref_inputs)
        
        if "Reefer" in current_mode_text: # Container Mode
            self.label_aux_p1.setText("Reefer Plugs (%TEU):")
            self.label_aux_p2.setText("Load (kW/TEU):")
            self.edit_aux_p2.setToolTip("Avg draw per reefer (typ. 2.5-4.0 kW)")
        elif "Hold" in current_mode_text: # Bulk Mode
            self.label_aux_p1.setText("Cooled Vol (%):")
            self.label_aux_p2.setText("Cooling (kW/1000m3):")
            self.edit_aux_p2.setToolTip("Typ. 10-20 kW per 1000m3")
        else: # Default/None
            self.label_aux_p1.setText("Reefer Capacity (%):") 
            self.label_aux_p2.setText("Load (kW/unit):")

        
        is_cargo_mode = self.radio_cargo.isChecked()
        is_ship_mode = self.radio_ship.isChecked()
        is_teu_mode = self.radio_teu.isChecked()
        is_design_mode = is_cargo_mode or is_teu_mode 
        is_econom_on = self.check_econom.isChecked()
        is_nuclear = (self.combo_engine.currentIndex() == 3) 

        self.edit_als_eff.setEnabled(self.check_als.isChecked())
        self.edit_wind_sav.setEnabled(self.check_wind.isChecked())
        self.label_wind_sav.setEnabled(self.check_wind.isChecked())

        if hasattr(self, 'layout_teu_container'):
            self.layout_teu_container.setVisible(is_teu_mode)
        else:
            self.edit_teu.setVisible(is_teu_mode)
            self.edit_teu_weight.setVisible(is_teu_mode)
        
        self.edit_weight.setEnabled(is_cargo_mode)
        self.edit_error.setEnabled(is_cargo_mode)

        show_density = (self.check_vol_limit.isChecked() and 
                        ship_data.get("Design_Type") == "Deadweight")
        
        self.label_density.setVisible(show_density)
        self.edit_density.setVisible(show_density)
        
        if show_density and (not self.edit_density.text() or self.edit_density.text() == "0.0"):
             self.edit_density.setText(str(ship_data.get("Cargo_Density", 0.0)))

        eedi_allowed = ship_data.get("EEDI_Enabled", False)
        
        if is_econom_on and eedi_allowed:
            self.check_eedi.setVisible(True)
            self.check_eedi.setEnabled(True)
            self.check_cii.setVisible(True)
            self.check_cii.setEnabled(True)
        else:
            self.check_eedi.setVisible(False)
            self.check_eedi.setChecked(False) 
            self.check_cii.setVisible(False)
            self.check_cii.setChecked(False)

        self.edit_length.setEnabled(is_ship_mode)
        self.edit_breadth.setEnabled(is_ship_mode)
        self.edit_depth.setEnabled(is_ship_mode)
        self.edit_draught.setEnabled(is_ship_mode)
        self.edit_block.setEnabled(is_ship_mode)
        
        self.check_lbratio.setEnabled(is_design_mode)
        self.check_bvalue.setEnabled(is_design_mode)
        self.check_btratio.setEnabled(is_design_mode)
        self.check_cbvalue.setEnabled(is_design_mode)
        self.btn_modify.setEnabled(is_design_mode)
        
        self.edit_lbratio.setEnabled(is_design_mode and self.check_lbratio.isChecked())
        self.edit_bvalue.setEnabled(is_design_mode and self.check_bvalue.isChecked())
        self.edit_btratio.setEnabled(is_design_mode and self.check_btratio.isChecked())
        self.edit_cbvalue.setEnabled(is_design_mode and self.check_cbvalue.isChecked())
        self.edit_pdtratio.setEnabled(self.check_pdtratio.isChecked())
        
        self.edit_voyages.setEnabled(is_econom_on)
        self.edit_seadays.setEnabled(is_econom_on)
        self.edit_interest.setEnabled(is_econom_on)
        self.edit_repay.setEnabled(is_econom_on)

        self.label_fuel.setVisible(is_econom_on and not is_nuclear)
        self.edit_fuel.setVisible(is_econom_on and not is_nuclear)
        self.label_lhv.setVisible(is_econom_on and not is_nuclear)
        self.edit_lhv.setVisible(is_econom_on and not is_nuclear)
        
        show_tax = is_econom_on and not is_nuclear
        self.check_carbon_tax.setVisible(show_tax)
        self.label_ctax_rate.setVisible(show_tax and self.check_carbon_tax.isChecked())
        self.edit_ctax_rate.setVisible(show_tax and self.check_carbon_tax.isChecked())
        
        self.label_reactor_cost.setVisible(is_econom_on and is_nuclear)
        self.edit_reactor_cost.setVisible(is_econom_on and is_nuclear)
        self.label_core_life.setVisible(is_econom_on and is_nuclear)
        self.edit_core_life.setVisible(is_econom_on and is_nuclear)
        self.label_decom_cost.setVisible(is_econom_on and is_nuclear)
        self.edit_decom_cost.setVisible(is_econom_on and is_nuclear)
        
        if is_nuclear:
            self.edit_range.setText("Infinite")
            self.edit_range.setEnabled(False)
        else:
            self.edit_range.setEnabled(True)
            current_text = self.edit_range.text().strip()
            if current_text == "Infinite" or not current_text:
                self.edit_range.setText(f"{self.m_conventional_Range:.6g}")
        
        self.btn_save.setEnabled(self.CalculatedOk and not self.Ksaved)

    def on_check_econom(self, checked):
        self.m_Econom = checked
        self._reset_dlg()

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
        
        if not self.check_aux_enable.isChecked():
            return

        try:
            self.P_hotel = float(self.edit_aux_base.text())
            
            p_cargo = 0.0
            mode_text = self.combo_aux_mode.currentText()
            
            pct = float(self.edit_aux_p1.text()) / 100.0
            load_factor = float(self.edit_aux_p2.text())
            
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
                self.aux_cost_annual = self.aux_fuel_annual_tonnes * price

        except Exception as e:
            self._show_error(f"Aux Calc Error: {e}")

    def on_config_route(self):
        """Opens the Route Profiler Dialog"""
        try:
            current_speed = float(self.edit_speed.text())
        except:
            current_speed = 15.0
            
        dlg = RouteDialog(self, current_speed)
        if dlg.exec():
            res = dlg.result_data
            
            self.edit_voyages.setText(f"{res['voyages']:.2f}")
            self.edit_seadays.setText(f"{res['seadays']:.1f}")
            
            if self.combo_engine.currentIndex() != 3: # Not Nuclear
                self.edit_range.setText(f"{res['range']:.0f}")
            
            self.m_Power_Factor = res['power_factor']
            
            QMessageBox.information(self, "Route Updated", 
                f"Route Applied.\n\n"
                f"Voyages: {res['voyages']:.2f}\n"
                f"Sea Days: {res['seadays']:.1f}\n"
                f"Avg Power Factor: {self.m_Power_Factor:.3f}\n"
                f"(Diesel fuel consumption will scale by {self.m_Power_Factor:.3f})")
    
    def on_check_cbvalue(self, checked):
        self.m_Cbvalue = checked
        self._reset_dlg()

    def on_check_lbratio(self, checked):
        self.m_Lbratio = checked
        if checked and self.check_bvalue.isChecked():
            self.m_Bvalue = False
            self.check_bvalue.setChecked(False)
        else:
            self._reset_dlg()

    def on_check_bvalue(self, checked):
        self.m_Bvalue = checked
        if checked and self.check_lbratio.isChecked():
            self.m_Lbratio = False
            self.check_lbratio.setChecked(False)
        else:
            self._reset_dlg()

    def on_check_btratio(self, checked):
        self.m_Btratio = checked
        if checked and self.combo_ship.currentText() != "Cargo vessel": 
            ret = QMessageBox.question(self, "Warning:",
                "This option should really be\r\n"
                "used for CARGO ships only!\r\n\r\n"
                "Are you sure you want to use\r\n"
                f"this option for a {self.combo_ship.currentText()}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No: 
                self.m_Btratio = False
                self.check_btratio.setChecked(False) # This will trigger reset
                return
        self._reset_dlg()
        
    def on_check_pdtratio(self, checked):
        """Port of OnCheckPdtratio - note the inverted logic"""
        self.m_Pdtratio = checked
        if checked:
            self.m_PdtratioV = 0.6
            self.Pdt = 0.6
            self.m_Pdtratio = False
            self.check_pdtratio.setChecked(False)
            self.edit_pdtratio.setText(str(self.m_PdtratioV))
        self._reset_dlg()

    def on_killfocus_edit_prpm(self):
        self.Ketype = 1 + self.combo_engine.currentIndex()
        if self.Ketype == 1: 
            if self._update_ui_to_data():
                self.m_Erpm = self.m_Prpm 
                self.edit_erpm.setText(str(self.m_Erpm)) 

    def on_killfocus_edit_erpm(self):
        self.Ketype = 1 + self.combo_engine.currentIndex()
        if self.Ketype == 1: 
            if self._update_ui_to_data():
                self.m_Prpm = self.m_Erpm 
                self.edit_prpm.setText(str(self.m_Prpm)) 

    def _initdata(self, i):
        """Port of Sub_initdata"""
        
        if i == 0:
            self.L1=self.m_Length; self.B=self.m_Breadth; self.D=self.m_Depth; self.T=self.m_Draught; self.C=self.m_Block
            
            self.R=self.m_Range; self.V=self.m_Speed; self.N1=self.m_Erpm; self.N2=self.m_Prpm; self.V7=self.m_Voyages
            self.D1=self.m_Seadays; self.F8=self.m_Fuel; self.I=self.m_Interest; self.N=int(self.m_Repay)
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
            ship_data = ShipConfig.get(self.combo_ship.currentText())
            fuel_data = FuelConfig.get(self.combo_engine.currentText())

            # Effective carbon factor: include LNG methane slip on the same
            # basis as _cost so CII tracks the same GHG accounting the user
            # selected for the carbon-tax calc.
            effective_carbon = self._effective_carbon_factor(fuel_data)
            if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
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
            ship_data = ShipConfig.get(self.combo_ship.currentText())
            fuel_data = FuelConfig.get(self.combo_engine.currentText())

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

    def _outvdu(self):
        """Port of Sub_outvdu - UPDATED for GT and EEDI"""
        output_lines = []
        
        Stype = self.combo_ship.currentText()
        Etype = self.combo_engine.currentText()
        
        ship_data = ShipConfig.get(Stype)
        
        pf = ship_data.get("Profile_Factor", 1.0)
        vol_enclosed = self.L1 * self.B * self.D * pf
        
        if vol_enclosed > 0:
            import math
            gt_factor = 0.2 + 0.02 * math.log10(vol_enclosed)
            gross_tonnage = vol_enclosed * gt_factor
        else:
            gross_tonnage = 0.0
        
        if self.m_Append and self.Kcases > 0:
            self.Kcases += 1
            output_lines.append("\r\n" + "="*40 + "\r\n")
        else:
            self.Kcases = 1
            
        output_lines.append(f"Case {self.Kcases:3d}: {Stype} with {Etype} engine")
        
        opt = self.outopt_data
        ob1 = (opt['ol'] or opt['ob'] or opt['olb'] or opt['od'] or opt['ot'] or opt['obt'] or opt['ocb'] or
               opt['odisp'] or opt['ocdw'] or opt['otdw'] or opt['opdt'] or opt['ospeed'] or opt['orange'] or
               opt['oerpm'] or opt['oprpm'] or opt['ospower'] or opt['oipower'] or opt['ope'] or
               opt['ono'] or opt['onh'] or opt['oqpc'] or opt['oscf'] or opt['ont'] or opt['omargin'] or
               opt['osmass'] or opt['oomass'] or opt['ommass'] or opt['ofbd'] or opt['oagm'])
        ob2 = (opt['ovyear'] or opt['osdyear'] or opt['ofcost'] or opt['oirate'] or opt['oreyear'] or
               opt['obcost'] or opt['oacc'] or opt['oafc'] or opt['orfr'])
        
        B_safe = self.B if self.B != 0 else 1e-9
        T_safe = self.T if self.T != 0 else 1e-9
        L1_safe = self.L1 if self.L1 != 0 else 1e-9

        if ob1 or (ob2 and self.m_Econom):
            if ob1:
                output_lines.append("  ------- Dimensions:")
            
            dim_parts1 = []
            if opt['ol']: dim_parts1.append(f"Lbp(m) = {self.L1:8.2f}")
            if opt['ob']: dim_parts1.append(f"B(m) = {self.B:7.2f}")
            if opt['olb']: dim_parts1.append(f"L/B = {L1_safe/B_safe:7.2f}")
            if dim_parts1: output_lines.append("   " + ", ".join(dim_parts1))
            
            dim_parts2 = []
            if opt['od']: dim_parts2.append(f"D(m) = {self.D:7.2f}")
            if opt['ot']: dim_parts2.append(f"T(m) = {self.T:7.2f}")
            if opt['obt']: dim_parts2.append(f"B/T = {B_safe/T_safe:7.2f}")
            if dim_parts2: output_lines.append("   " + ", ".join(dim_parts2))
            
            if opt['ocb']: output_lines.append(f"   CB = {self.C:5.3f}")
            if opt['odisp']: output_lines.append(f"   Disp. (tonnes) = {int(self.M + 0.5):7d}")
            
            if hasattr(self, 'res_total'):
                # Header includes the active resistance method so the report
                # is self-documenting in saved output (m_Results is just a
                # text dump — see on_button_save).
                method_label = getattr(self, 'resistance_method', "Taylor's Series (Legacy)")
                output_lines.append(f"\r\n  ------- Resistance Breakdown ({method_label}):")
                # Surface any active sensitivity knobs so saved reports remain
                # traceable. We only print non-zero/non-default values to keep
                # ordinary runs uncluttered.
                sens_lines = []
                if abs(getattr(self, 'm_ResUncertPct', 0.0)) > 1e-9:
                    sens_lines.append(f"     Resistance Uncertainty applied: {self.m_ResUncertPct:+.1f}%")
                if getattr(self, 'm_MethaneSlip', 0.0) > 1e-9 and self.combo_engine.currentText() == "LNG (Dual Fuel)":
                    eff_cf = FuelConfig.get("LNG (Dual Fuel)")["Carbon"] + (self.m_MethaneSlip/100.0) * self.m_GWP_methane
                    sens_lines.append(
                        f"     Methane Slip applied: {self.m_MethaneSlip:.1f}% "
                        f"(eff. carbon factor {eff_cf:.2f} tCO2e/t)"
                    )
                if getattr(self, 'm_RetrofitMode', False):
                    sens_lines.append(
                        f"     Retrofit Mode ON: machinery cost x {self.m_RetrofitFactor:.2f}"
                    )
                if sens_lines:
                    output_lines.append("   [Sensitivity Knobs Active]")
                    output_lines.extend(sens_lines)
                output_lines.append(f"   Total Resistance: {self.res_total:.1f} kN")
                
                if self.res_total > 0:
                    p_fric = (self.res_friction / self.res_total) * 100
                    p_wave = (self.res_wave / self.res_total) * 100
                    p_air = (self.res_air / self.res_total) * 100
                    p_app = (self.res_app / self.res_total) * 100
                else:
                    p_fric=0; p_wave=0; p_air=0; p_app=0
                
                output_lines.append(f"   - Friction:  {self.res_friction:.1f} kN ({p_fric:.1f}%)")
                output_lines.append(f"   - Wave/Res.: {self.res_wave:.1f} kN ({p_wave:.1f}%)")
                output_lines.append(f"   - Air/Wind:  {self.res_air:.1f} kN ({p_air:.1f}%)")
                output_lines.append(f"   - Appendage: {self.res_app:.1f} kN ({p_app:.1f}%)")

                # Method-native components (currently Holtrop-only). These
                # are zero under Taylor where they don't exist as separate
                # entities; only print the line if the value is non-trivial.
                bulb        = getattr(self, 'res_bulb',        0.0) or 0.0
                transom     = getattr(self, 'res_transom',     0.0) or 0.0
                correlation = getattr(self, 'res_correlation', 0.0) or 0.0
                if abs(bulb) + abs(transom) + abs(correlation) > 1e-6:
                    if self.res_total > 0:
                        p_b  = (bulb        / self.res_total) * 100
                        p_tr = (transom     / self.res_total) * 100
                        p_c  = (correlation / self.res_total) * 100
                    else:
                        p_b = p_tr = p_c = 0
                    output_lines.append(f"   - Bulb:      {bulb:.1f} kN ({p_b:.1f}%)")
                    output_lines.append(f"   - Transom:   {transom:.1f} kN ({p_tr:.1f}%)")
                    output_lines.append(f"   - Correl.:   {correlation:.1f} kN ({p_c:.1f}%)")

                if hasattr(self, 'esd_log') and self.esd_log:
                    output_lines.append("   [ESD Active]")
                    for log in self.esd_log:
                        output_lines.append(f"     -> {log}")
                    orig_kw = self.P1_Original * 0.7457
                    new_kw = self.P1 * 0.7457
                    output_lines.append(f"     -> New Service Power: {int(new_kw)} kW (was {int(orig_kw)})")

        self._calculate_detailed_efficiency()

        if opt['ope'] or opt['oqpc']: 
            output_lines.append("\r\n  ------- Physics & Hydrodynamics:")
            output_lines.append(f"   Froude Number (Fn) = {self.froude_number:.3f}")
            output_lines.append(f"   Reynolds Number (Re)= {self.reynolds_number:.2e}")
            
            if self.froude_number > 0.30:
                output_lines.append("   !! WARNING: Fn > 0.30. Resistance data may be unstable.")
                
            output_lines.append(f"   Estimated Opt. LCB = {self.lcb_optimal:+.2f}% Lbp")
            
            output_lines.append("  ------- Efficiency Breakdown (Diagnostic):")
            output_lines.append(f"   Hull Efficiency (nH) = {self.diag_eta_h:.3f}")
            output_lines.append(f"   Open Water Eff. (nO) = {self.diag_eta_o:.3f}")
            output_lines.append(f"   Total QPC (Original) = {self.Q:.3f}")

            if self.check_aux_enable.isChecked():
                output_lines.append("\r\n  ------- Power & Hotel Analysis:")
                
                prop_kw = self.P1 * 0.7457
                total_load = prop_kw + self.P_aux_total
                pct_aux = (self.P_aux_total / total_load) * 100 if total_load > 0 else 0
                
                output_lines.append(f"   Propulsion Power: {int(prop_kw):,} kW")
                output_lines.append(f"   Auxiliary Power:  {int(self.P_aux_total):,} kW ({pct_aux:.1f}% of total)")
                output_lines.append(f"     - Base Hotel:   {int(self.P_hotel)} kW")
                output_lines.append(f"     - Cargo Load:   {int(self.P_cargo_cooling)} kW")
                
                output_lines.append(f"   Aux Generator Wt: {self.M_aux_mach:.1f} tonnes")
                if self.M_aux_outfit > 0:
                    output_lines.append(f"   Insulation Wt:    {self.M_aux_outfit:.1f} tonnes")
                    
                output_lines.append(f"   Aux Fuel Annual:  {self.aux_fuel_annual_tonnes:,.1f} tonnes")
                output_lines.append(f"   Aux Fuel Cost:    {self.aux_cost_annual/1e6:.3f} M$")
                
                try:
                    prem_rate = float(self.edit_aux_prem.text())
                    if prem_rate > 0:
                        is_teu = (self.design_mode == 2)
                        cargo_units = self.m_TEU if is_teu else self.W1
                        
                        extra_income = cargo_units * prem_rate
                        mode = self.combo_aux_mode.currentIndex()
                        pct = float(self.edit_aux_p1.text()) / 100.0
                        extra_income *= pct
                        
                        net_profit_delta = extra_income - self.aux_cost_annual
                        
                        output_lines.append(f"   Reefer Premium:   +{extra_income/1e6:.3f} M$")
                        output_lines.append(f"   Net Aux Impact:   {net_profit_delta/1e6:+.3f} M$")
                except:
                    pass

            if self.design_mode == 2:
                est_teu = self._estimate_teu_capacity(self.L1, self.B, self.D)
                output_lines.append(f"   Target TEU = {int(self.target_teu)}")
                output_lines.append(f"   Est. Capacity = {int(est_teu)} TEU")
                output_lines.append(f"   Avg. Weight = {self.m_TEU_Avg_Weight:5.2f} t/TEU")
                output_lines.append(f"   -> Target Cargo DW = {self.W:7.0f} tonnes")
            
            if opt['ocdw']: output_lines.append(f"   Cargo DW(tonnes) = {self.W1:7.0f}")
            
            if opt['otdw']: 
                gt_str = f"   (GT = {int(gross_tonnage)})"
                output_lines.append(f"   Total DW(tonnes) = {self.W5:7.0f} {gt_str}")

            if opt['opdt']: output_lines.append(f"   Prop.dia./T = {self.Pdt:7.2f}")
            if opt['ospeed']: output_lines.append(f"   Speed (knots) = {self.V:7.2f}")
            
            if self.Ketype == 4: # Nuclear
                 if opt['orange']: output_lines.append("   Range(N.M.) = Infinite")
            else:
                if opt['orange']: output_lines.append(f"   Range(N.M.) = {self.R:8.1f}")
            
            if self.check_fuel_vol.isChecked() and self.Ketype != 4:
                fuel_data = FuelConfig.get(self.combo_engine.currentText())
                if hasattr(self, 'calculated_fuel_mass') and self.calculated_fuel_mass > 0 and fuel_data["Density"] > 0:
                    
                    raw_mass = getattr(self, 'raw_fuel_mass', None)
                    if raw_mass is None:
                        tf = fuel_data.get("TankFactor", 1.0) or 1.0
                        raw_mass = self.calculated_fuel_mass / tf
                    fuel_vol_m3 = (raw_mass * 1000.0) / fuel_data["Density"]
                    fuel_vol_m3 *= fuel_data["VolFactor"]
                    
                    hull_vol = self.L1 * self.B * self.D * self.C
                    
                    if hull_vol > 0:
                        vol_pct = (fuel_vol_m3 / hull_vol) * 100.0
                        output_lines.append(f"   Fuel Volume = {fuel_vol_m3:,.1f} m³ ({vol_pct:.2f}% of hull vol)")
                    else:
                        output_lines.append(f"   Fuel Volume = {fuel_vol_m3:,.1f} m³")

            # ----- Volume budget breakdown (chapter 5.1) -----
            # Always print this when the fuel-volume option is on; it gives
            # the user a single-glance view of where the hull volume goes,
            # which is the headline figure for the dimensional-penalty
            # comparison. Numbers come from _capture_volume_budget().
            if self.check_fuel_vol.isChecked() and getattr(self, 'vol_avail', 0.0) > 0:
                vc = getattr(self, 'vol_cargo', 0.0)
                vf = getattr(self, 'vol_fuel', 0.0)
                vm = getattr(self, 'vol_mach', 0.0)
                vs = getattr(self, 'vol_stores', 0.0)
                va = self.vol_avail
                vu = getattr(self, 'vol_utilisation_pct', 0.0)
                output_lines.append("   Volume Budget (m³):")
                output_lines.append(f"     - Cargo:     {vc:>10,.0f}  ({vc/va*100:5.1f}% of available)")
                output_lines.append(f"     - Fuel:      {vf:>10,.0f}  ({vf/va*100:5.1f}% of available)")
                output_lines.append(f"     - Machinery: {vm:>10,.0f}  ({vm/va*100:5.1f}% of available)")
                output_lines.append(f"     - Stores:    {vs:>10,.0f}  ({vs/va*100:5.1f}% of available)")
                output_lines.append(f"     - Available: {va:>10,.0f}")
                output_lines.append(f"     - Utilisation: {vu:.1f}%")
                if getattr(self, 'vol_expansion_iters', 0) > 0:
                    output_lines.append(f"     - Volume-limit expansion iters: {self.vol_expansion_iters}")

            if opt['oerpm']: output_lines.append(f"   Engine RPM = {self.N1:6.1f}")
            if opt['oprpm']: output_lines.append(f"   Propeller RPM = {self.N2:6.1f}")
            if opt['ospower']: output_lines.append(f"   Service power = {int(self.P1 + 0.5):6d} BHP / {int(0.7457 * self.P1 + 0.5):6d} KW")
            if opt['oipower']: output_lines.append(f"   Installed power = {int(self.P2 + 0.5):6d} BHP / {int(0.7457 * self.P2 + 0.5):6d} KW")
            
            power_parts1 = []
            if opt['ope']: power_parts1.append(f"Pe = {self.P:6.1f}/{0.7457*self.P:6.1f}")
            if opt['ono']: power_parts1.append(f"NO = {self.Q1:5.3f}")
            if opt['onh']: power_parts1.append(f"NH = {self.Q2:5.3f}")
            
            power_parts2 = []
            if opt['oqpc']: power_parts2.append(f"QPC = {self.Q:5.3f}")
            if opt['oscf']: power_parts2.append(f"SCF = {self.F0:5.3f}")
            if opt['ont']: power_parts2.append(f"NT = {self.F9:5.3f}")
            if opt['omargin']: power_parts2.append("Margin=30%")
            
            if power_parts1 or power_parts2:
                line1 = "    ( " + ", ".join(power_parts1)
                line2 = "      " + ", ".join(power_parts2)
                if power_parts1 and power_parts2:
                    output_lines.append(line1); output_lines.append(line2 + " )")
                elif power_parts1: output_lines.append(line1 + " )")
                elif power_parts2: output_lines.append("    ( " + line2.strip() + " )")

            if opt['osmass']: output_lines.append(f"   Steel mass(tonnes) = {int(self.M1 + 0.5):5d}")
            if opt['oomass']: output_lines.append(f"   Outfit mass(tonnes) = {int(self.M2 + 0.5):5d}")
            if opt['ommass']: output_lines.append(f"   Machy mass(tonnes) = {int(self.M3 + 0.5):5d}")
            if opt['ofbd']: output_lines.append(f"   Freeboard(m) = {self.F5:5.2f}")
            if opt['oagm']: output_lines.append(f"   Approx. GM(m) = {self.G6:5.1f}")
            
            if self.m_Econom and ob2:
                output_lines.append("  ------- Economic analysis:")
                if opt['ovyear']: output_lines.append(f"   Voyages/year = {self.V7:6.3f}")
                if opt['osdyear']: output_lines.append(f"   Sea days/year = {self.D1:6.2f}")
                
                if self.Ketype == 4: # Nuclear
                    if opt['ofcost']: 
                        installed_power_kw = self.P2 * 0.7457
                        total_reactor_cost_M = (self.m_Reactor_Cost_per_kW * installed_power_kw) / 1.0e6
                        output_lines.append(f"   Reactor Cost Rate = {self.m_Reactor_Cost_per_kW:,.2f} ($/kW)")
                        output_lines.append(f"   @ {installed_power_kw:,.0f} kW (Installed)")
                        output_lines.append(f"   -> Reactor CAPEX = {total_reactor_cost_M:6.2f} (M$)")
                    
                    if opt['oirate']: output_lines.append(f"   Core Life (years) = {self.m_Core_Life:3.0f}")
                else: # Fossil
                    if opt['ofcost']: output_lines.append(f"   Fuel cost/tonne = {self.F8:6.2f}")
                
                if opt['oirate']: output_lines.append(f"   Interest rate (%%) = {self.I:6.2f}")
                if opt['oreyear']: output_lines.append(f"   Repayment years = {self.N:3d}")
                if opt['obcost']: output_lines.append(f"   Build cost = {self.S:5.2f}(M)")
                if opt['oacc']: 
                    output_lines.append(f"   Annual capital charges = {self.H1:,.2f}")
                    output_lines.append(f"   Annual OPEX = {self.annual_opex:,.2f}")
                
                if self.Ketype == 4:
                    if opt['oafc']: 
                        output_lines.append(f"   Annual Core/Decom Cost = {self.H7:,.2f}")
                else:
                    if opt['oafc']: 
                        output_lines.append(f"   Annual fuel costs = {self.annual_fuel_cost_only:,.2f}")
                        if self.check_carbon_tax.isChecked():
                            output_lines.append(f"   Annual carbon taxes = {self.annual_carbon_tax:,.2f}")
                            output_lines.append(f"   Total Fuel + Tax = {self.H7:,.2f}")
                
                if opt['orfr']:
                    if self.design_mode == 2: # TEU Mode
                        unit_label = "$/TEU"
                        conv_factor = self.m_TEU_Avg_Weight # Convert $/tonne to $/TEU
                    else: # Deadweight Mode
                        unit_label = "$/tonne"
                        conv_factor = 1.0

                    base_rfr = self.Rf * conv_factor
                    
                    if hasattr(self, 'annual_premium_income') and self.annual_premium_income > 0:
                        
                        W7 = self.V7 * self.W1
                        if W7 > 0:
                            premium_savings_per_tonne = self.annual_premium_income / W7
                            savings_display = premium_savings_per_tonne * conv_factor
                            
                            gross_rfr = base_rfr + savings_display
                            
                            output_lines.append(f"   Req. Freight Rate = {base_rfr:5.2f} {unit_label}")
                            output_lines.append(f"       (Base: {gross_rfr:5.2f} - Premium: {savings_display:5.2f})")
                    else:
                        output_lines.append(f"   Req. Freight Rate = {base_rfr:5.2f} {unit_label}")

                if self.check_cii.isChecked():
                    output_lines.append("\r\n  ------- CII Rating (Operational Carbon Intensity):")
                    # Values are already computed by _compute_cii() in
                    # on_calculate. We just read them here, which keeps a
                    # single source of truth and means CII is also available
                    # to batch callers via get_result_value("AttainedCII").
                    if getattr(self, 'required_cii', 0.0) > 0:
                        # Recompute annual CO2 cheaply for display only.
                        try:
                            fuel_data = FuelConfig.get(self.combo_engine.currentText())
                            lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                            eff = fuel_data["Efficiency"]
                            service_power_kw = self.P1 * 0.7457
                            annual_hours = self.D1 * 24.0
                            annual_energy_MJ = service_power_kw * annual_hours * 3.6
                            annual_fuel_tonnes = (annual_energy_MJ / (lhv * eff)) / 1000.0
                            cf = self._effective_carbon_factor(fuel_data)
                            if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                                cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
                            annual_co2 = annual_fuel_tonnes * cf
                            output_lines.append(f"   Annual CO2 = {annual_co2:,.1f} tonnes")
                        except Exception:
                            pass
                        output_lines.append(f"   Attained CII = {self.attained_cii:6.2f}")
                        output_lines.append(f"   Required CII = {self.required_cii:6.2f} (Year 2023 Basis)")
                        output_lines.append(f"   CII Rating: {self.cii_rating}")
                        if "D" in self.cii_rating or "E" in self.cii_rating:
                            output_lines.append("   -> WARNING: Ship is non-compliant. Needs corrective plan.")
                    else:
                        output_lines.append("   (CII Reference not available for this type)")

                if self.check_eedi.isChecked():
                    output_lines.append("\r\n  ------- EEDI Compliance (IMO Phase 3):")
                    
                    try:
                        fuel_data = FuelConfig.get(self.combo_engine.currentText())
                        
                        lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                        eff = fuel_data["Efficiency"]
                        sfc_g_kwh = 3600.0 / (lhv * eff)
                        
                        eedi_type = ship_data.get("EEDI_Type", "DWT")
                        if eedi_type == "GT":
                            capacity = gross_tonnage
                            cap_label = "GT"
                        else:
                            capacity = self.W1
                            cap_label = "DWT"
                            
                        if capacity <= 1.0: capacity = 1.0
                        
                        p_me = 0.75 * (self.P2 * 0.7457) # 75% MCR in kW
                        cf = self._effective_carbon_factor(fuel_data)
                        # Apply methane slip on the same effective-carbon basis
                        # used by _cost / _compute_cii so all three GHG metrics
                        # tell a consistent story.
                        if self.combo_engine.currentText() == "LNG (Dual Fuel)" and self.m_MethaneSlip > 0:
                            cf += (self.m_MethaneSlip / 100.0) * self.m_GWP_methane
                        v_ref = self.V                   
                        
                        attained_eedi = (p_me * cf * sfc_g_kwh) / (capacity * v_ref)
                        
                        a = ship_data.get("EEDI_a", 0.0)
                        c = ship_data.get("EEDI_c", 0.0)
                        
                        if a > 0:
                            reduction = 0.30 
                            reference_line = a * (capacity ** -c)
                            required_eedi = reference_line * (1.0 - reduction)
                            
                            status = "PASS" if attained_eedi <= required_eedi else "FAIL"
                            
                            output_lines.append(f"   Capacity Used = {int(capacity)} ({cap_label})")
                            output_lines.append(f"   Attained EEDI = {attained_eedi:6.2f} (gCO2/t.nm)")
                            output_lines.append(f"   Required EEDI = {required_eedi:6.2f} (Phase 3 Limit)")
                            output_lines.append(f"   Status: {status}")
                            
                            if status == "FAIL":
                                output_lines.append("   -> Suggestion: Reduce Speed, Optimize Hull, or change Fuel.")
                        else:
                             output_lines.append("   (Reference line not available for this ship type)")

                    except Exception as e:
                        output_lines.append(f"   EEDI Error: Could not calculate ({str(e)})")

        else:
             output_lines.append("  --- No output is selected!")

        # ----- Sensitivity & retrofit knobs (chapter 5) -----
        # Print these whenever any of them is non-default so the saved report
        # self-documents the assumptions underlying the run. Sits outside the
        # main output-options branch so it always appears when active.
        active_knobs = []
        if self.m_MethaneSlip > 0:
            active_knobs.append(f"Methane slip = {self.m_MethaneSlip:.2f}% "
                                f"(GWP100 = {self.m_GWP_methane:.0f})")
        if abs(self.m_ResUncertPct) > 1e-9:
            active_knobs.append(f"Resistance uncertainty = {self.m_ResUncertPct:+.1f}%")
        if self.m_RetrofitMode:
            active_knobs.append(f"Retrofit Mode ON  (machinery cost x {self.m_RetrofitFactor:.2f})")
        if active_knobs:
            output_lines.append("\r\n  ------- Sensitivity & Retrofit Knobs:")
            for line in active_knobs:
                output_lines.append(f"   {line}")

        output_lines.append("------- End of output results.")
        
        formatted_output = "\r\n".join(output_lines)
        
        if self.m_Append and self.Kcases > 1:
            self.m_Results += "\r\n" + formatted_output
        else:
            self.m_Results = formatted_output
            
        self.text_results.setText(self.m_Results)
        self.text_results.verticalScrollBar().setValue(self.text_results.verticalScrollBar().maximum())
            
        return True