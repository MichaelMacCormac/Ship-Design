import sys
import math
import csv
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QTextEdit, QPushButton, QVBoxLayout, QGroupBox, QRadioButton,
    QHBoxLayout, QMessageBox, QFileDialog, QLabel, QGridLayout,
    QApplication, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QInputDialog
)

from PySide6.QtCore import Qt

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d import Axes3D 
except ImportError:
    print("Matplotlib not found. Plotting will be disabled.")
    print("Please install it: pip install matplotlib")
    FigureCanvas = None
    Figure = None

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
            "IsNuclear": False
        },
        "Nuclear Steam Turbine": {
            "LHV": 0.0,
            "Density": 0.0,
            "Efficiency": 0.35, # Saturated steam cycle
            "TankFactor": 0.0,
            "VolFactor": 0.0,
            "Carbon": 0.0,
            "Machinery": 20.0, # Scaling factor (Base mass of ~2000t covers the reactor)
            "IsNuclear": True
        },
        "Methanol (ICE)": {
            "LHV": 19.9,       # Low Energy Density (Alcohol)
            "Density": 792.0,  # Liquid at room temp
            "Efficiency": 0.45,# Similar to Diesel ICE
            "TankFactor": 1.20,# Tanks need special coatings but aren't pressure vessels
            "VolFactor": 1.15, # Cofferdams required for safety
            "Carbon": 1.375,   # Chemical carbon content. (Set to 0.0 for "Green Methanol")
            "Machinery": 15.0, # Slightly heavier engine block (compression ratio)
            "IsNuclear": False
        },
        "Hydrogen (ICE)": {
            "LHV": 120.0,      # High Energy
            "Density": 71.0,   # Liquid H2
            "Efficiency": 0.38,# Combustion is less efficient than Fuel Cell (0.50)
            "TankFactor": 5.0, # Still needs massive cryogenic tanks
            "VolFactor": 3.0,  
            "Carbon": 0.0,     
            "Machinery": 13.0, # LIGHTER than Fuel Cell (No heavy stack/batteries)
            "IsNuclear": False
        },
        
        "LNG (Dual Fuel)": {
            "LHV": 50.0,       # Higher energy than diesel!
            "Density": 450.0,  # Light liquid
            "Efficiency": 0.48,# Very efficient engines
            "TankFactor": 1.6, # Cryogenic tanks (heavy but mature tech)
            "VolFactor": 1.9,  # Insulation takes space
            "Carbon": 2.75,    # Lower carbon than diesel, but not zero
            "Machinery": 16.0, # Heavy: Engine + Gas Valve Unit + Vaporizers
            "IsNuclear": False
        },
        "Hydrogen (Fuel Cell)": {
            "LHV": 120.0,      # Highest energy per kg
            "Density": 71.0,   # Liquid H2 (-253C)
            "Efficiency": 0.50,# PEM Fuel Cell system efficiency
            "TankFactor": 5.0, # CRITICAL: Cryogenic tanks weigh 4-5x the fuel they hold
            "VolFactor": 3.0,  # CRITICAL: Insulation thickness triples the volume
            "Carbon": 0.0,
            "Machinery": 18.0, # HEAVIER than Diesel: Stack + Compressors + Humidifiers + Radiators
            "IsNuclear": False
        },
        "Ammonia (Combustion)": {
            "LHV": 18.6,       # Low energy density
            "Density": 682.0,  # Liquid (-33C)
            "Efficiency": 0.42,# Ammonia burns slow; slightly lower eff than Diesel
            "TankFactor": 1.4, # Type C tanks (Pressure vessels) are heavy steel
            "VolFactor": 1.4,  # Cylindrical tanks waste hull space
            "Carbon": 0.0,     # Zero Carbon molecule
            "Machinery": 16.0, # Diesel engine + massive SCR catalyst system + Scrubber
            "IsNuclear": False
        },
        "Electric (Battery)": {
            "LHV": 0.6,        # PACK Level Density (approx 160 Wh/kg)
            "Density": 2000.0, # Battery packs are dense solids
            "Efficiency": 0.92,# Battery-to-Shaft efficiency
            "TankFactor": 1.0, # "Fuel" mass is the battery mass.
            "VolFactor": 1.0,  # Packs are modular blocks
            "Carbon": 0.0,
            "Machinery": 3.0,  # Electric Motors are incredibly light
            "IsNuclear": False
        }
    }

    @staticmethod
    def get(name):
        return FuelConfig.DATA.get(name, FuelConfig.DATA["Direct diesel"])

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
            "Profile_Factor": 1.60,
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

class GraphWindow(QWidget):
    """
    Displays either a 2D line graph or a 3D wireframe plot.
    """
    def __init__(self, x_data, y_data, z_data=None, x_label="", y_label="", z_label="", title=""):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(900, 700)
        
        layout = QVBoxLayout(self)
        fig = Figure(figsize=(8, 6), dpi=100)
        canvas = FigureCanvas(fig)
        
        if z_data is not None:
            ax = fig.add_subplot(111, projection='3d')
            ax.plot_wireframe(x_data, y_data, z_data, color='blue', linewidth=0.5)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            ax.set_zlabel(z_label)
        else:
            ax = fig.add_subplot(111)
            if x_data is not None and y_data is not None:
                ax.plot(x_data, y_data, marker='o', linestyle='-')
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            
        ax.set_title(title)
        if z_data is None: ax.grid(True)
        
        layout.addWidget(canvas)

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
        self.m_H3_Maint_Percent = 0.04 # Maintenance as % of build cost (was 0.05)
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

        tax_layout.addWidget(self.check_eedi)
        tax_layout.addWidget(self.check_cii)

        eco_layout.addRow(eco_grid)
        eco_group.setLayout(eco_layout)
        left_col.addWidget(eco_group)

        range_group = QGroupBox("Range Analysis (2D Line or 3D Surface)")
        range_layout = QGridLayout()

        range_layout.addWidget(QLabel("<b>Input 1 (X-Axis):</b>"), 0, 0)
        self.combo_param_vary = QComboBox()
        self.param_list = [
            "Block Co.", "Speed(knts)", "Cargo deadweight(t)", 
            "TEU Capacity", "L/B Ratio", "B(m)", "B/T Ratio",
            "Reactor Cost ($/kW)" 
        ]
        self.combo_param_vary.addItems(self.param_list)
        range_layout.addWidget(self.combo_param_vary, 0, 1, 1, 3)

        range_layout.addWidget(QLabel("Start:"), 1, 0)
        self.edit_range_start = QLineEdit("14.0") # Example speed
        range_layout.addWidget(self.edit_range_start, 1, 1)
        range_layout.addWidget(QLabel("End:"), 1, 2)
        self.edit_range_end = QLineEdit("22.0")
        range_layout.addWidget(self.edit_range_end, 1, 3)
        range_layout.addWidget(QLabel("Steps:"), 2, 0)
        self.edit_range_steps = QLineEdit("8")
        range_layout.addWidget(self.edit_range_steps, 2, 1)

        range_layout.addWidget(QLabel("<b>Input 2 (Y-Axis / 3D Only):</b>"), 3, 0)
        self.check_enable_3d = QCheckBox("Enable 2nd Input")
        range_layout.addWidget(self.check_enable_3d, 3, 1, 1, 2)

        self.combo_param_vary_2 = QComboBox()
        self.combo_param_vary_2.addItems(self.param_list) # Same list
        self.combo_param_vary_2.setCurrentText("Reactor Cost ($/kW)") # Default
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

        range_layout.addWidget(QLabel("<b>Output (Y or Z Axis):</b>"), 7, 0)
        self.combo_param_y = QComboBox()
        self.combo_param_y.addItems([
            "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB", "Displacement(t)",
            "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)", "InstalledPower(kW)",
            "BuildCost(M$)", "RFR($/tonne or $/TEU)"
        ])
        self.combo_param_y.setCurrentText("RFR($/tonne or $/TEU)")
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
        toggle_3d_inputs(False) # Default off

        range_group.setLayout(range_layout)
        left_col.addWidget(range_group)
        comp_group = QGroupBox("Competitive Analysis (Battle Mode)")
        comp_layout = QGridLayout()
        
        comp_layout.addWidget(QLabel("Engine A (Red):"), 0, 0)
        self.combo_battle_A = QComboBox()
        self.combo_battle_A.addItems(list(FuelConfig.DATA.keys()))
        self.combo_battle_A.setCurrentIndex(0) # Default: Diesel
        comp_layout.addWidget(self.combo_battle_A, 0, 1)

        comp_layout.addWidget(QLabel("Engine B (Green):"), 1, 0)
        self.combo_battle_B = QComboBox()
        self.combo_battle_B.addItems(list(FuelConfig.DATA.keys()))
        self.combo_battle_B.setCurrentIndex(4) # Default: Hydrogen (or similar)
        comp_layout.addWidget(self.combo_battle_B, 1, 1)

        comp_layout.addWidget(QLabel("Speed Range (knots):"), 2, 0)
        
        speed_layout = QHBoxLayout()
        self.edit_comp_start = QLineEdit("14.0")
        self.edit_comp_start.setFixedWidth(40)
        self.edit_comp_end = QLineEdit("24.0")
        self.edit_comp_end.setFixedWidth(40)
        self.edit_comp_steps = QLineEdit("10") 
        self.edit_comp_steps.setFixedWidth(30)
        
        speed_layout.addWidget(QLabel("Start:"))
        speed_layout.addWidget(self.edit_comp_start)
        speed_layout.addWidget(QLabel("End:"))
        speed_layout.addWidget(self.edit_comp_end)
        speed_layout.addWidget(QLabel("Steps:"))
        speed_layout.addWidget(self.edit_comp_steps)
        
        comp_layout.addLayout(speed_layout, 2, 1)

        self.btn_run_battle = QPushButton("Run Comparison Battle")
        self.btn_run_battle.setStyleSheet("font-weight: bold; color: darkblue;")
        self.btn_run_battle.clicked.connect(self.on_run_battle)
        comp_layout.addWidget(self.btn_run_battle, 3, 0, 1, 2)

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

        # Create a final main layout for the actual window to hold the scroll area
        window_layout = QVBoxLayout(self)
        window_layout.addWidget(scroll_area)
        
        # Connect Signals... (Existing code follows here)
        
        # --- Connect Signals to Methods ---
        self.btn_calculate.clicked.connect(self.on_calculate)
        self.btn_run_range.clicked.connect(self.on_run_range)
        self.btn_run_plot.clicked.connect(self.on_run_plot) # <-- NEW
        self.btn_save.clicked.connect(self.on_button_save)
        self.btn_modify.clicked.connect(self.on_dialog_modify)
        self.btn_outopt.clicked.connect(self.on_dialog_outopt)
        
        #
        self.radio_cargo.toggled.connect(self._reset_dlg)
        self.radio_ship.toggled.connect(self._reset_dlg)
        self.radio_teu.toggled.connect(self._reset_dlg)
        
        #
        self.combo_ship.currentIndexChanged.connect(self._reset_dlg)
        self.combo_engine.currentIndexChanged.connect(self._reset_dlg) # IMPORTANT
        #
        
        self.check_econom.toggled.connect(self.on_check_econom) #
        self.check_lbratio.toggled.connect(self.on_check_lbratio) #
        self.check_vol_limit.toggled.connect(self._reset_dlg)
        self.check_bvalue.toggled.connect(self.on_check_bvalue) #
        self.check_btratio.toggled.connect(self.on_check_btratio) #
        self.check_cbvalue.toggled.connect(self.on_check_cbvalue) #
        self.check_pdtratio.toggled.connect(self.on_check_pdtratio) #
        
        self.edit_erpm.editingFinished.connect(self.on_killfocus_edit_erpm) #
        self.edit_prpm.editingFinished.connect(self.on_killfocus_edit_prpm) #

        # --- Final UI Setup ---
        self._update_data_to_ui() # Load all C++ defaults into the UI fields
        self._reset_dlg()         # Run the UI logic to enable/disable fields
        
    def _update_ui_to_data(self):
        """Port of UpdateData(TRUE) - Pulls values from UI to members"""
        
        # Helper to safely convert text to float (returns 0.0 if empty)
        def _safe_float(widget, default=0.0):
            try:
                text = widget.text().strip()
                if not text:
                    return default
                return float(text)
            except ValueError:
                # If it's not a number (e.g. "abc"), let the main try/except catch it
                # or raise it now to be caught below.
                raise ValueError(f"Invalid number in field")

        try:
            # 1. Read Main Inputs (Use safe float to avoid crashes on hidden fields)
            self.m_Weight = _safe_float(self.edit_weight)
            self.m_Error = _safe_float(self.edit_error)
            
            self.m_TEU = _safe_float(self.edit_teu)
            self.m_TEU_Avg_Weight = _safe_float(self.edit_teu_weight)
            
            # 2. Read Constraints
            self.m_LbratioV = _safe_float(self.edit_lbratio)
            self.m_BvalueV = _safe_float(self.edit_bvalue)
            self.m_BtratioV = _safe_float(self.edit_btratio)
            self.m_CbvalueV = _safe_float(self.edit_cbvalue)
            self.m_PdtratioV = _safe_float(self.edit_pdtratio)
            
            # 3. Read Dimensions
            self.m_Length = _safe_float(self.edit_length)
            self.m_Breadth = _safe_float(self.edit_breadth)
            self.m_Draught = _safe_float(self.edit_draught)
            self.m_Depth = _safe_float(self.edit_depth)
            self.m_Block = _safe_float(self.edit_block)
            
            # 4. Read Operational
            self.m_Speed = _safe_float(self.edit_speed)
            
            # Handle "Infinite" Range
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

            # 5. Read Economics
            self.m_Fuel = _safe_float(self.edit_fuel)
            
            # Default LHV if empty
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

            # 6. Read Volume Limit
            self.m_VolumeLimit = self.check_vol_limit.isChecked()
            
            # Only read density if it is visible, otherwise use default
            if self.edit_density.isVisible():
                 self.m_CustomDensity = _safe_float(self.edit_density, default=-1.0)
            else:
                 self.m_CustomDensity = -1.0 

            # 7. Set Mode Flags
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
        
        # (self.edit_range is handled by _reset_dlg)
        
        self.edit_prpm.setText(f"{self.m_Prpm:.6g}")
        self.edit_erpm.setText(f"{self.m_Erpm:.6g}")
        self.edit_voyages.setText(f"{self.m_Voyages:.6g}")
        self.edit_seadays.setText(f"{self.m_Seadays:.6g}")
        
        # --- FIX START ---
        # 1. Set Fuel COST (m_Fuel) to the Fuel Cost Box
        self.edit_fuel.setText(f"{self.m_Fuel:.6g}")
        
        # 2. Set Energy Density (m_LHV) to the LHV Box
        self.edit_lhv.setText(f"{self.m_LHV:.6g}")
        # --- FIX END ---
        
        # --- MODIFIED: Set $/kW rate ---
        self.edit_reactor_cost.setText(f"{self.m_Reactor_Cost_per_kW:.6g}")
        
        self.edit_core_life.setText(f"{self.m_Core_Life:.6g}")
        self.edit_decom_cost.setText(f"{self.m_Decom_Cost:.6g}")
        self.edit_interest.setText(f"{self.m_Interest:.6g}")
        self.edit_repay.setText(f"{self.m_Repay:.6g}")
        # --- NEW: Write Volume Limit ---
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
        
        self.text_results.setText(self.m_Results)

    def _show_error(self, message, title="Input error"):
        """Helper for porting MessageBox"""
        QMessageBox.critical(self, title, message)
        
    def _show_debug_msg(self, message, title="Info. from OnButtonCal in debug mode"):
        """Helper for porting debug MessageBox"""
        #
        ret = QMessageBox.question(self, title, message,
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.No: #
            self.dbgmd = False
            self.dlg_modify.data['dbgmd'] = False # Sync with dialog
            return False
        return True

    # --- PORTED C++ LOGIC ---

    def _check_data(self):
        """Port of Sub_checkdata"""
        # FIX: Get the count dynamically from your config
        num_types = len(ShipConfig.DATA)
        
        if self.Kstype < 1 or self.Kstype > num_types:
            self._show_error(f"Fatal error: Ship type {self.Kstype} unknown!", "Input error")
            return False
        # Get the total number of engines dynamically from your config
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
                # --- MODIFIED: Check $/kW rate ---
                if self.m_Reactor_Cost_per_kW <= 0 or self.m_Core_Life <= 0 or self.m_Decom_Cost < 0:
                    self._show_error("Fatal error: Nuclear costs must be positive!", "Input error")
                    self.edit_reactor_cost.setFocus()
                    return False
            else: # Fossil
                if self.F8 <= 0.0:
                    self._show_error("Fatal error: Fuel cost must be positive!", "Input error")
                    self.edit_fuel.setFocus()
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
            # The paper's regression formula (38) for LBD (L*B*D) is:
            # LBD = -20143.62 + 104.422 * (TEU ** 0.9) 
            LBD_product = L * B * D
            
            if LBD_product <= 0:
                return 0
                
            # We invert the formula to solve for TEU:
            # (LBD_product + 20143.62) / 104.422 = TEU ** 0.9
            # TEU = ( (LBD_product + 20143.62) / 104.422 ) ** (1.0 / 0.9)
            
            teu_est = ( (LBD_product + 20143.62) / 104.422 ) ** (1.0 / 0.9)
            
            return teu_est
            
        except (ValueError, OverflowError):
            # Fallback in case of math errors (e.g., negative log)
            return 0

    # --- NEW: Volume Solver Logic ---

    def _get_volume_status(self):
        """
        Calculates Required vs Available Volume.
        """
        ship_data = ShipConfig.get(self.combo_ship.currentText())
        fuel_data = FuelConfig.get(self.combo_engine.currentText())
        
        # 1. Available Volume
        vol_hull = self.L1 * self.B * self.D * self.C
        vol_avail = vol_hull * ship_data.get("Profile_Factor", 1.0)
        
        # 2. Required Volume
        vol_cargo = 0.0
        
        if self.design_mode == 2: # TEU Mode
            vol_cargo = self.m_TEU * 33.0 
        elif ship_data.get("Design_Type") == "Volume": 
            if ship_data["ID"] == 5: # Cruise
                vol_cargo = self.W * 50.0 
            else:
                vol_cargo = self.W / 0.5
        else:
            # Standard Deadweight Mode (Tanker, Bulk, Cargo)
            # --- FIX: Prioritize User Input Density ---
            if self.m_CustomDensity > 0:
                density = self.m_CustomDensity
            else:
                density = ship_data.get("Cargo_Density", 1.0)
            
            # Physics: Low Density = High Volume (Requires Expansion)
            #          High Density = Low Volume (Fits easily)
            vol_cargo = self.W / density
            vol_cargo *= 1.10 # Stowage Factor

        # Add Fuel/Machinery Volume
        vol_fuel = 0.0
        if hasattr(self, 'calculated_fuel_mass') and self.calculated_fuel_mass > 0:
            if fuel_data["Density"] > 0:
                vol_fuel = (self.calculated_fuel_mass * 1000.0) / fuel_data["Density"] * fuel_data["VolFactor"]
        
        vol_mach = (self.P2 * 0.7457) * 0.4 
        vol_stores = self.W1 * 0.05 
        
        vol_req = vol_cargo + vol_fuel + vol_mach + vol_stores
        
        ratio = vol_req / (vol_avail if vol_avail > 0 else 1.0)
        return vol_req, vol_avail, ratio

    def _solve_volume_limit(self):
        """
        Phase 3 Expansion Loop (ROBUST):
        Expands dimensions if volume is insufficient.
        Handles power calculation failures gracefully.
        """
        if not self.m_VolumeLimit:
            return True 

        req, avail, ratio = self._get_volume_status()
        
        # If ratio <= 1.0, we fit!
        if ratio <= 1.0:
            return True 

        self.text_results.append(f"\n--- VOLUME LIMIT DETECTED ---")
        self.text_results.append(f"Required: {int(req)} m3 | Available: {int(avail)} m3")
        self.text_results.append(f"Expanding ship dimensions...")

        # Store original payload and state to revert if needed
        target_payload = self.W 
        L_orig, B_orig, D_orig = self.L1, self.B, self.D
        
        # Safety: Limit iterations
        for i in range(50):
            # 1. Expand Dimensions
            expansion_factor = 1.02 # Expand by 2% per step
            self.L1 *= expansion_factor
            
            if self.L1 > 0:
                if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                else: self.B *= expansion_factor
                self.D *= expansion_factor

            # 2. Estimate Draft (T) for this new hull
            # We assume similar block coefficient (C)
            C_safe = self.C if self.C > 0 else 0.8
            # Estimate T based on scaling (Volume grows by cube, Mass roughly by cube)
            # Just keeping the D/T ratio constant is a safe bet for the solver
            self.T = self.D * 0.7 

            # 3. Try to Calculate Power for this new shape
            # If the prop pitch fails here, we catch it and force a "safe" assumption
            power_ok = self._power()
            
            if not power_ok:
                # If power failed (likely prop pitch), assume Power scales with Displacement^2/3
                # This allows the loop to continue resizing without crashing
                self.P1 *= (expansion_factor ** 2) 
                self.P2 *= (expansion_factor ** 2)
            
            # 4. Recalculate Weights (Now that we have new Power/Size)
            self._mass() 
            
            # 5. Check Displacement Requirement
            # M = Payload + Lightship + Fuel + Margin
            fuel_mass = self.calculated_fuel_mass if hasattr(self, 'calculated_fuel_mass') else 0
            # Note: M3 (Machinery) is updated in _mass, M2 (Outfit) updated in _mass
            new_lightship = (self.M1 + self.M2 + self.M3) * 1.02
            misc_mass = 13.0 * (self.M ** 0.35) 
            
            required_displacement = target_payload + new_lightship + fuel_mass + misc_mass
            
            # 6. Update actual Draft required to float this mass
            self.M = required_displacement
            new_T = self.M / (self.L1 * self.B * C_safe * 1.025)
            
            # Check freeboard constraint roughly
            if new_T > (self.D * 0.9): 
                new_T = self.D * 0.9 # Cap draft
            
            self.T = new_T

            # 7. Check Volume Again
            req, avail, ratio = self._get_volume_status()
            
            if ratio <= 1.0:
                self.text_results.append(f"-> Converged at L={self.L1:.1f}m")
                self.text_results.append(f"-> Draft adjusted to {self.T:.1f}m (New Disp: {int(self.M)}t)")
                self.W1 = self.M - new_lightship - fuel_mass - misc_mass
                return True 

        self.text_results.append("-> WARNING: Volume expansion limit reached.")
        # Restore originals if it went crazy? No, keep the expanded one but warn.
        return False

    def on_calculate(self):
        """Port of OnButtonCal"""

        # --- FIX: CLEAR STALE DATA ---
        # Reset auxiliary variables so they don't corrupt the solver loop
        keys_to_reset = ['M_aux_mach', 'M_aux_outfit', 'W_aux_fuel', 
                         'aux_cost_annual', 'calculated_fuel_mass']
        for k in keys_to_reset:
            if hasattr(self, k):
                delattr(self, k)
        # -----------------------------

        # 1. Update members from UI
        if not self._update_ui_to_data():
            return # Stop if input is invalid

        # Store the original design mode
        self.design_mode = self.m_Cargo # 0=Cargo, 1=Ship, 2=TEU
        self.target_teu = 0

        # --- MODIFIED: Design Mode Logic ---
        if self.design_mode == 2: # If in TEU mode
            # Calculate the total cargo weight *from* the TEU inputs
            self.W = self.m_TEU * self.m_TEU_Avg_Weight
            self.target_teu = self.m_TEU # Store for post-check
            
            # Use the SAME error calculation as cargo mode
            self.E = 0.01 * self.W * self.m_Error
            
            # Trick the solver into running in "Cargo Deadweight" mode
            self.m_Cargo = 0
            
            # Update UI for clarity
            self.edit_weight.setText(str(self.W))
            self.edit_error.setText(str(self.m_Error))
        
        elif self.design_mode == 0: # If in Cargo Deadweight mode
            # --- THIS IS THE FIX ---
            # These lines were missing. We must set W and E
            # from the member variables.
            self.W = self.m_Weight
            self.E = 0.01 * self.W * self.m_Error
        
        # (No action needed for design_mode == 1 (Ship), as W and E aren't used)
            
        if self.Ketype == 1: #
            self.m_Prpm = self.m_Erpm
            self.edit_prpm.setText(str(self.m_Prpm)) # Push change back to UI
            
        # 2. Run logic
        self._initdata(0) #
        self.CalculatedOk = False #
        self.btn_save.setEnabled(False) #
        
        if not self._check_data(): #
             # Restore original mode if check fails
            self.m_Cargo = self.design_mode
            return
            
        if self.m_Cargo == 0: # Cargo deadweight or TEU mode
            # --- Start of Cargo Iteration Loop ---
            W1 = self.W + 2.0 * self.E + 10.0 #
            Z = 0; Y = 1; J = 10.0; L3 = 0.0; W2 = 0.0 #
            self.Kcount = 0 #
            
            # Initial L1 guess
            if self.Kstype == 1: #
                self.L1 = self.L111 + self.L112 * ((self.W / self.L113) ** (1/3)) #
            elif self.Kstype == 2: #
                self.L1 = self.L121 + self.L122 * ((self.W / self.L123) ** (1/3)) #
            else: #
                self.L1 = self.L131 + self.L132 * ((self.W / self.L133) ** (1/3)) #
                
            if self.dbgmd:
                msg = f"Initial ship length: L1={self.L1:7.2f}\r\n"
                msg += f"and the target DW = {self.W:8.2f}\r\n"
                QMessageBox.information(self, "Info. from OnButtonCal in debug mode", msg)

            while self.Kcount < 500 and abs(self.W - W1) > self.E: #
                self.Kcount += 1
                
                # ... (Iteration logic - UNCHANGED) ...
                if self.Kcount > 1:
                    if Y != Z + 1: #
                        self.L1 -= 0.5 * J; Y += 1
                    elif self.W >= W1: #
                        L3 = self.L1; W2 = W1; self.L1 += J
                    else: #
                        if (W1 - W2) == 0: W1 = W2 + 1e-9 # Avoid division by zero
                        L = L3 + (self.W - W2) * (self.L1 - L3) / (W1 - W2)
                        self.L1 = L; J = 0.25 * J; Y += 1; Z += 2
                
                if self.L1 == 0: self.L1 = 1e-9 # Avoid division by zero
                vosl = self.V / (math.sqrt(self.L1) if self.L1 > 0 else 1e-9)
                
                # ... (Kstype-dependent calculations - UNCHANGED) ...
                if self.Kstype == 1: # Tanker
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV #
                    elif self.m_Bvalue: self.B = self.m_BvalueV #
                    else: #
                        if self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03)) #
                        else: self.B = self.L1 / self.Lb04 #
                    if self.m_Cbvalue: self.C = self.m_CbvalueV #
                    else: #
                        if vosl < self.Cb15: self.C = self.Cb11 - self.Cb12 * vosl #
                        else: self.C = self.Cb13 - self.Cb14 * vosl #
                    if self.m_Btratio: #
                        self.T = self.B / self.m_BtratioV
                        self.D = self.T / 0.78
                        if not self._freeboard(): return
                    else: #
                        self.D = self.L1 / 13.5
                        self.T = 0.78 * self.D
                        if not self._freeboard(): return
                        self.T = self.D - self.F5 #
                elif self.Kstype == 2: # Bulk carrier
                    if self.m_Lbratio: self.B = self.L1 / self.m_LbratioV
                    elif self.m_Bvalue: self.B = self.m_BvalueV
                    else:
                        if self.L1 <= self.Lb05: self.B = self.L1 / (self.Lb01 + self.Lb02 * (self.L1 - self.Lb03))
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
                        self.D = self.L1 / 11.75
                        self.T = 0.7 * self.D
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
                        # C++ code missing T=D-F5 here

                self.M = 1.025 * self.L1 * self.B * self.T * self.C #
                if not self._stability(): return #
                
                # _power() will return False on fatal error
                if not self._power():
                     return
                
                # _mass() will now use Ketype to check for nuclear
                if not self._mass(): return #
                
                W1 = self.W1 # Update W1 for the next loop check
                
                # ... (Debug message logic - UNCHANGED) ...
                if self.dbgmd: #
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
            
            # --- End of Cargo Iteration Loop ---
            
            if self.Kpwrerr != 1: #
                msg = "The program tried its best but\r\n"
                msg += "calculation has failed because\r\n"
                if self.Kpwrerr % self.SPEED_LOW == 0: msg += " -- ship speed is too low!\r\n"
                if self.Kpwrerr % self.SPEED_HIGH == 0: msg += " -- ship speed is too high!\r\n"
                if self.Kpwrerr % self.PITCH_LOW == 0: msg += " -- prop. pitch out of range (|->)!\r\n"
                if self.Kpwrerr % self.PITCH_HIGH == 0: msg += " -- prop. pitch out of range (<-|)!\r\n"
                self._show_error(msg, "Fatal error (Input data wrong?)")
                # Restore original mode
                self.m_Cargo = self.design_mode
                return

            if self.Kcount >= 500: #
                QMessageBox.warning(self, "Warning", "Warning: Allowable error too small!")

        elif self.m_Cargo == 1: # Ship dimension specified
            if not self._freeboard(): return #
            self.M = 1.025 * self.L1 * self.B * self.T * self.C #
            if not self._stability(): return #
            if not self._power(): return #
            if not self._mass(): return #
        
        # ... (Previous code) ...
        
        # --- NEW: Apply ESD ---
        self._apply_resistance_breakdown()

        # --- NEW: Calculate Aux Loads ---
        # Must be before Mass (adds weight) and Cost (adds fuel)
        self._auxiliary()
        # -------------------------------

        if not self._mass(): return

        # Restore original design mode
        self.m_Cargo = self.design_mode
            
        # --- NEW: Phase 3 Volume Solver ---
        self._solve_volume_limit()
        
        if not self._power(): 
            self.text_results.append("\n[Auto-Correcting Propeller RPM for larger hull...]")
            self.N2 *= 0.9 # Reduce Prop RPM by 10%
            self.N1 *= 0.9 # Reduce Engine RPM by 10%
            
            if not self._power():
                self.text_results.append("ERROR: Propeller design failed even after adjustment.")
                self.text_results.append("Try reducing 'Engine RPM' or unchecking 'Prop.dia./T ratio'.")
                return # Stop to show errors
        
        # --- NEW: Apply ESD and Resistance Breakdown ---
        self._apply_resistance_breakdown()
        # -----------------------------------------------

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


        self._apply_resistance_breakdown()

        if not self._mass(): return
        self._mass()

        if self.m_Econom: #
            # _cost() will now use Ketype to check for nuclear
            if not self._cost(): return
            
        self.CalculatedOk = True #
        # ... (Rest of function) ...
        self.Ksaved = False #
        
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
            # Optional: Mark as failed so graphs don't plot nonsense
            # self.CalculatedOk = False

        # --- NEW: TEU Post-Calculation Check ---
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
                # We need to prepend the warning if we are not appending
                if self.m_Append and self.Kcases > 0:
                    self.m_Results += warning
                else:
                    self.m_Results = warning + self.m_Results

        
        self.text_results.setEnabled(True) #
        self._outvdu() #
        self.btn_save.setEnabled(True) #
        
        self._initdata(1) #
        self._update_data_to_ui() #
        self._reset_dlg() #
        
    def on_run_range(self):
        """
        Runs a calculation over a range of values
        and saves the results to a CSV file.
        Pop-up errors are suppressed during this run.
        """
        
        # 1. Get parameter and range inputs
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

        # 2. Get file name
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Range Analysis CSV",
            "ship_range_analysis.csv", "CSV Files (*.csv);;All Files (*)")
        
        if not fileName:
            return # User cancelled

        # 3. Create the list of values to iterate over
        value_range = np.linspace(start, end, steps)

        # 4. Define CSV Header
        header = [
            param_name, "Lbp(m)", "B(m)", "D(m)", "T(m)", "CB", 
            "Displacement(t)", "CargoDW(t)", "TotalDW(t)", "ServicePower(kW)", 
            "InstalledPower(kW)", "BuildCost(M$)"
        ]
        
        # Add economic-specific outputs if analysis is on
        is_econom_on = self.check_econom.isChecked()
        if is_econom_on:
            if self.radio_teu.isChecked():
                header.append("RFR($/TEU)")
            else:
                header.append("RFR($/tonne)")

        # 5. Run the loop
        self.m_Results = f"Running range analysis for '{param_name}'...\r\nSaving to {fileName}\r\n"
        self.text_results.setText(self.m_Results)
        self.Kcases = 0 # Reset case counter for this run
        
        # --- Store original UI state ---
        # We must restore the UI after the loop is done
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
            # --- Store error flag state ---
            'ignspd': self.ignspd,
            'ignpth': self.ignpth,
        }
        # --- Temporarily suppress pop-up errors for the loop ---
        self.ignspd = True
        self.ignpth = True

        try:
            with open(fileName, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                
                is_teu_mode = original_ui_state['teu_r'] # Check original mode
                
                for i, value in enumerate(value_range):
                    # Update progress in the UI
                    self.text_results.append(f"Running step {i+1}/{steps} ({param_name} = {value:.4f})...")
                    QApplication.processEvents() # Allow UI to refresh

                    # --- A. Set the parameter in the UI ---
                    # This is how we pass the new value to the calculation logic
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
                        self.check_lbratio.setChecked(True) # Ensure it's active
                        self.edit_lbratio.setText(str(value))
                    
                    elif param_name == "B(m)":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_bvalue.setChecked(True) # Ensure it's active
                        self.edit_bvalue.setText(str(value))

                    elif param_name == "B/T Ratio":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_btratio.setChecked(True) # Ensure it's active
                        self.edit_btratio.setText(str(value))
                    
                    elif param_name == "Block Co.":
                        if not (is_teu_mode or original_ui_state['cargo_r']): self.radio_cargo.setChecked(True)
                        self.check_cbvalue.setChecked(True) # Ensure it's active
                        self.edit_cbvalue.setText(str(value))
                    
                    
                    # --- B. Run the main calculation ---
                    self.on_calculate() 
                    
                    # --- C. Extract results ---
                    row = [f"{value:.6g}"]
                    if not self.CalculatedOk:
                        row.extend(["CALCULATION FAILED"] * (len(header) - 1))
                    else:
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
                            f"{self.S:.3f}" if is_econom_on else "N/A" # BuildCost(M$)
                        ])
                        if is_econom_on:
                            if is_teu_mode: # Use the mode active at the *start* of the run
                                rfr_val = self.Rf * self.m_TEU_Avg_Weight
                            else:
                                rfr_val = self.Rf
                            row.append(f"{rfr_val:.4f}" if self.CalculatedOk else "N/A")

                    writer.writerow(row)
            
            self.text_results.append(f"\r\n... Range analysis complete. ...")
            QMessageBox.information(self, "Range Analysis Complete", f"Successfully saved {steps} results to {fileName}")

        except Exception as e:
            self._show_error(f"Failed to write CSV file: {e}")
        
        finally:
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
            # --- Input 1 (X) ---
            param_name_1 = self.combo_param_vary.currentText()
            start_1 = float(self.edit_range_start.text())
            end_1 = float(self.edit_range_end.text())
            steps_1 = int(self.edit_range_steps.text())
            
            # --- Input 2 (Y - Optional) ---
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

            y_param_name = self.combo_param_y.currentText()  # Result Axis
            
            if steps_1 < 2: raise ValueError("Steps must be >= 2")

        except ValueError as e:
            self._show_error(f"Invalid input: {e}")
            return

        # --- Store UI State ---
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
        }
        self.ignspd = True; self.ignpth = True

        try:
            # Generate Ranges
            range_1 = np.linspace(start_1, end_1, steps_1)
            
            if is_3d:
                range_2 = np.linspace(start_2, end_2, steps_2)
                # Create Meshgrid for plotting
                X, Y = np.meshgrid(range_1, range_2)
                Z = np.zeros((steps_2, steps_1)) # Rows=Input2, Cols=Input1
                
                total_steps = steps_1 * steps_2
                current_step = 0
            else:
                X, Y, Z = [], [], None

            # --- Helper to set parameter ---
            def set_param_value(name, val):
                if name == "Speed(knts)": self.edit_speed.setText(str(val))
                elif name == "Cargo deadweight(t)": self.edit_weight.setText(str(val)); self.radio_cargo.setChecked(True)
                elif name == "TEU Capacity": self.edit_teu.setText(str(val)); self.radio_teu.setChecked(True)
                elif name == "Reactor Cost ($/kW)": self.edit_reactor_cost.setText(str(val))
                elif name == "L/B Ratio": self.edit_lbratio.setText(str(val)); self.check_lbratio.setChecked(True)
                elif name == "B(m)": self.edit_bvalue.setText(str(val)); self.check_bvalue.setChecked(True)
                elif name == "B/T Ratio": self.edit_btratio.setText(str(val)); self.check_btratio.setChecked(True)
                elif name == "Block Co.": self.edit_cbvalue.setText(str(val)); self.check_cbvalue.setChecked(True)

            # --- Helper to get result (FIXED) ---
            def get_result_value(name):
                if not self.CalculatedOk: return np.nan # Return NaN if failed
                is_econom = self.check_econom.isChecked()
                is_teu = self.radio_teu.isChecked()
                
                if name == "RFR($/tonne or $/TEU)":
                    if not is_econom: return np.nan
                    return self.Rf * self.m_TEU_Avg_Weight if is_teu else self.Rf
                
                # --- ADDED THESE MAPPINGS ---
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
                
                return 0.0 # Fallback

            # --- Execution Loop ---
            self.text_results.append("Starting analysis...")
            
            if is_3d:
                # Nested Loop for Surface
                for i in range(steps_2): # Y-Axis (Input 2) rows
                    val_2 = range_2[i]
                    set_param_value(param_name_2, val_2)
                    
                    for j in range(steps_1): # X-Axis (Input 1) cols
                        val_1 = range_1[j]
                        set_param_value(param_name_1, val_1)
                        
                        self.on_calculate()
                        Z[i, j] = get_result_value(y_param_name)
                        
                        current_step += 1
                        if current_step % 5 == 0: QApplication.processEvents()
                        
                # Open 3D Window
                self.graph_window = GraphWindow(X, Y, Z, param_name_1, param_name_2, y_param_name, 
                                              f"{y_param_name} (Wireframe)")
            else:
                # Standard 1D Loop
                x_data = []; y_data = []
                for val in range_1:
                    set_param_value(param_name_1, val)
                    self.on_calculate()
                    res = get_result_value(y_param_name)
                    if not np.isnan(res):
                        x_data.append(val)
                        y_data.append(res)
                
                self.graph_window = GraphWindow(x_data, y_data, None, param_name_1, y_param_name, "", 
                                              f"{y_param_name} vs {param_name_1}")

            self.graph_window.show()
            self.text_results.append("Plot complete.")

        except Exception as e:
            self._show_error(f"Error during plot: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Restore State
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

            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            self._reset_dlg()
    
    def on_run_battle(self):
        """
        Runs the 'Battle Mode': Plots RFR vs Speed for two selected engines.
        """
        if FigureCanvas is None:
            self._show_error("Matplotlib not found.")
            return

        # 1. Get Speed Range
        try:
            start_speed = float(self.edit_comp_start.text())
            end_speed = float(self.edit_comp_end.text())
            steps = int(self.edit_comp_steps.text())
            if steps < 2: raise ValueError("Steps must be >= 2")
        except ValueError:
            self._show_error("Invalid speed range inputs.")
            return
            
        # 2. Get Selected Engines
        idx_A = self.combo_battle_A.currentIndex()
        idx_B = self.combo_battle_B.currentIndex()
        name_A = self.combo_battle_A.currentText()
        name_B = self.combo_battle_B.currentText()
        
        if idx_A == idx_B:
            self._show_error("Please select two different engines to compare.")
            return

        # 3. Store Original State
        original_ui_state = {
            'engine_idx': self.combo_engine.currentIndex(),
            'speed': self.edit_speed.text(),
            'ignspd': self.ignspd, 'ignpth': self.ignpth,
            'econom': self.check_econom.isChecked()
        }
        
        # 4. Prepare for Battle
        self.ignspd = True; self.ignpth = True 
        self.check_econom.setChecked(True)     
        
        speeds = np.linspace(start_speed, end_speed, steps)
        
        rfr_A = []; rfr_B = []
        valid_speeds_A = []; valid_speeds_B = []

        try:
            self.text_results.append(f"\n--- BATTLE: {name_A} vs {name_B} ---")
            
            # --- ROUND 1: ENGINE A ---
            self.text_results.append(f"Calculating {name_A}...")
            self.combo_engine.setCurrentIndex(idx_A) 
            QApplication.processEvents()
            
            for v in speeds:
                self.edit_speed.setText(str(v))
                self.on_calculate()
                if self.CalculatedOk:
                    val = self.Rf * self.m_TEU_Avg_Weight if self.radio_teu.isChecked() else self.Rf
                    rfr_A.append(val)
                    valid_speeds_A.append(v)
            
            # --- ROUND 2: ENGINE B ---
            self.text_results.append(f"Calculating {name_B}...")
            self.combo_engine.setCurrentIndex(idx_B)
            QApplication.processEvents()
            
            for v in speeds:
                self.edit_speed.setText(str(v))
                self.on_calculate()
                if self.CalculatedOk:
                    val = self.Rf * self.m_TEU_Avg_Weight if self.radio_teu.isChecked() else self.Rf
                    rfr_B.append(val)
                    valid_speeds_B.append(v)

            # 5. Plot the Battle (Passing names now)
            self._show_battle_graph(valid_speeds_A, rfr_A, valid_speeds_B, rfr_B, name_A, name_B)
            self.text_results.append("Battle Complete.\n")

        except Exception as e:
            self._show_error(f"Error during comparison: {e}")
            
        finally:
            # 6. Restore Original State
            self.combo_engine.setCurrentIndex(original_ui_state['engine_idx'])
            self.edit_speed.setText(original_ui_state['speed'])
            self.check_econom.setChecked(original_ui_state['econom'])
            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            self._reset_dlg()

    def _show_battle_graph(self, x1, y1, x2, y2, name1="Engine A", name2="Engine B"):
        """
        Helper to launch a specialized graph window for 2 lines.
        """
        # Create a generic container if it doesn't exist
        if not hasattr(self, 'battle_window') or self.battle_window is None:
            self.battle_window = QWidget()
            self.battle_window.setWindowTitle("Battle Mode")
            self.battle_window.resize(900, 600)
            layout = QVBoxLayout(self.battle_window)
            
            fig = Figure(figsize=(8, 6), dpi=100)
            self.battle_canvas = FigureCanvas(fig)
            self.battle_ax = fig.add_subplot(111)
            layout.addWidget(self.battle_canvas)
        
        # Clear and Plot
        ax = self.battle_ax
        ax.clear()
        
        # Plot Lines
        if x1 and y1:
            ax.plot(x1, y1, 'r-o', label=name1, linewidth=2)
        if x2 and y2:
            ax.plot(x2, y2, 'g-s', label=name2, linewidth=2)
            
        ax.grid(True)
        ax.legend()
        
        ylabel = "RFR ($/TEU)" if self.radio_teu.isChecked() else "RFR ($/tonne)"
        ax.set_xlabel("Ship Speed (knots)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Economic Battle: {name1} vs {name2}")
        
        # Refresh canvas
        self.battle_canvas.draw()
        self.battle_window.show()

    def _freeboard(self):
        """Port of Sub_freeboard"""
        # ... (UNCHANGED) ...
        ship_name = self.combo_ship.currentText()
        ship_data = ShipConfig.get(ship_name)
        
        # Use the ID from config (Tanker=1, Bulk=2, etc)
        # This ensures 'Container Ship' (ID 4) will behave like 'Cargo' (not Tanker)
        # in the logic below, assuming we handle ID > 3 as "Standard"
        eff_type = ship_data["ID"] 
        
        # Update references to self.Kstype in this function to use eff_type
        # ... (Existing logic) ...
        # CHANGE: if self.Kstype == 1:  --> if eff_type == 1:
        if self.L1 <= self._L2[0]: # 30
            l = 0
        elif self.L1 < self._L2[-1]: # 360
            l = 0
            while l < 17 and self.L1 > self._L2[l]:
                l += 1
            if l > 0: l -= 1 # We need the lower bound
        else:
            l = 16 # Use last full segment
        
        L2_l = self._L2[l]
        L2_l1 = self._L2[l+1]
        
        if eff_type == 1: # Tanker
            F1_l = self._F1[l]
            F1_l1 = self._F1[l+1]
            self.F5 = F1_l + (self.L1 - L2_l) * (F1_l1 - F1_l) / (L2_l1 - L2_l)
        else: # Bulk carrier (2), Cargo (3), Container (4), Cruise (5)
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
            
        if self.Kstype == 1: # Tanker
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
        
        # Calculate G3 (KG of ship)
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
        """Port of Sub_cost"""
        # H3 = 0.05
        H3 = self.m_H3_Maint_Percent # Use member variable
        
        C_safe = self.C if self.C != 0 else 1e-9
        
        S8 = self.m_S1_Steel1 * (self.M1 ** (2/3)) * (self.L1 ** (1/3)) / C_safe + self.m_S2_Steel2 * self.M1
        
        S9 = self.m_S3_Outfit1 * (self.M2 ** (2/3)) + self.m_S4_Outfit2 * (self.M2 ** 0.95)
        
        # --- MODIFIED: Nuclear Capital Cost (v2, from $/kW) ---
        S0_nuclear = 0.0 # Will store the calculated nuclear cost
        if self.Ketype == 4: # Nuclear
            installed_power_kw = self.P2 * 0.7457
            S0_nuclear = self.m_Reactor_Cost_per_kW * installed_power_kw
            S0 = S0_nuclear # This is the capital cost in $
        else: # Fossil
            S0 = self.m_S5_Machinery1 * (self.P1 ** 0.82) + self.m_S6_Machinery2 * (self.P1 ** 0.82)
        
        self.S = S8 + S9 + S0
        
        I_rate = self.I * 0.01
        H0 = (1.0 + I_rate) ** self.N
        if (H0 - 1.0) == 0: H0 = 1e-9 # Avoid div by zero
        H0 = I_rate * H0 / (H0 - 1.0)
        
        self.H1 = H0 * self.S # Annual capital charges
        H3 = H3 * self.S #
        
        # ... (Existing Capital Cost S calculation stays the same) ...

        # --- MODIFIED: Operating Cost (H7) ---
        engine_name = self.combo_engine.currentText()
        fuel_data = FuelConfig.get(engine_name)
        
        if fuel_data["IsNuclear"]:
             # (Existing Nuclear Logic - Keep as is)
            core_life_safe = self.m_Core_Life if self.m_Core_Life > 0 else 1e-9
            annual_core_cost = S0_nuclear / core_life_safe
            repay_years_safe = self.N if self.N > 0 else 1e-9
            annual_decom_fund = (self.m_Decom_Cost * 1.0e6) / repay_years_safe 
            self.H7 = annual_core_cost + annual_decom_fund
            
        else: 
            # FOSSIL / H2 / AMMONIA / ELECTRIC
            
            # 1. Calculate Annual Fuel Consumption (Tonnes)           
            service_power_kw = self.P1 * 0.7457
            annual_energy_MJ = service_power_kw * (self.D1 * 24.0) * 3.6
            
            # Mass = Energy / (LHV * Eff)
            if self.m_LHV > 0:
                 annual_fuel_tonnes = (annual_energy_MJ / (self.m_LHV * fuel_data["Efficiency"])) / 1000.0
            else:
                annual_fuel_tonnes = 0
            
            # Adjust for Power Factor (Slow steaming)
            annual_fuel_tonnes *= self.m_Power_Factor
            
            # 2. Calculate Fuel Cost
            self.H7 = annual_fuel_tonnes * self.F8
            
            # 3. Calculate Carbon Tax
            if self.check_carbon_tax.isChecked():
                co2_tonnes = annual_fuel_tonnes * fuel_data["Carbon"]
                annual_tax_bill = co2_tonnes * self.m_CarbonTax
                self.H7 += annual_tax_bill

        if hasattr(self, 'aux_cost_annual'):
            self.H7 += self.aux_cost_annual
        
        # --- NEW: Calculate Refrigerated Premium Income ---
        self.annual_premium_income = 0.0 # Store for display later
        try:
            # Only apply if Aux analysis is enabled
            if self.check_aux_enable.isChecked():
                prem_rate = float(self.edit_aux_prem.text())
                
                # Only proceed if there is a positive premium entered
                if prem_rate > 0:
                    # Determine units (TEU vs Tonnes)
                    is_teu = (self.design_mode == 2)
                    total_cargo_units = self.m_TEU if is_teu else self.W1
                    
                    # Determine what % of cargo gets the premium
                    # (Reefer Plugs % or Cooled Vol %)
                    pct_refrigerated = float(self.edit_aux_p1.text()) / 100.0
                    
                    # Calculate Income: Units * %Reefer * PremiumRate * Voyages
                    # Note: Premium is usually per voyage. 
                    # If the input is "Per Unit Per Voyage":
                    income_per_voyage = (total_cargo_units * pct_refrigerated) * prem_rate
                    self.annual_premium_income = income_per_voyage * self.V7
        except ValueError:
            self.annual_premium_income = 0.0

        Rt = self.H1 + self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.H7 + self.m_H8_Other
        
        # --- NEW: Subtract Premium from Total Cost (Subsidize the RFR) ---
        Rt_adjusted = Rt - self.annual_premium_income
        
        self.S *= 1.0e-6 # Convert total build cost to M$ for output
        
        W1_safe = self.W1 if self.W1 != 0 else 1e-9
        W7 = self.V7 * W1_safe
        
        if W7 == 0: W7 = 1e-9 # Avoid division by zero
        
        # We calculate Rf based on the Adjusted cost (Net Cost)
        self.Rf = Rt_adjusted / W7
        
        return True

    def _apply_resistance_breakdown(self):
        """
        Calculates resistance components (Friction, Wave, Air) 
        and applies Energy Saving Device (ESD) reductions.
        """
        # 1. Physics Constants
        rho_sw = 1025.0       # Seawater density (kg/m3)
        rho_air = 1.225       # Air density (kg/m3)
        viscosity = 1.188e-6  # Kinematic viscosity (15C seawater)
        g = 9.81
        
        # 2. Kinematics
        V_ms = self.V * 0.5144 # Knots to m/s
        if V_ms <= 0: V_ms = 0.1
        
        # 3. Calculate Total Resistance (R_Total) from the Solver's Power        
        eff_propulsive = self.Q if self.Q > 0 else 0.65
        
        # Note: self.P is "Service Power" at the propeller (delivered).         
        pe_kw = self.P * 0.7457 # Effective Power in kW
        
        # Total Resistance (kN) = PE (kW) / V (m/s)
        self.res_total = pe_kw / V_ms 
        
        # 4. Calculate Frictional Resistance (R_F)
        # S = 1.025 * Lpp * (Cb * B + 1.7 * T)
        cb_safe = self.C if self.C > 0 else 0.8
        self.area_wetted = 1.025 * self.L1 * (cb_safe * self.B + 1.7 * self.T)
        
        # Reynolds Number
        Re = (V_ms * self.L1) / viscosity
        
        # Friction Coefficient (ITTC-57)
        if Re > 0:
            import math
            log_re = math.log10(Re)
            cf = 0.075 / ((log_re - 2.0)**2)
        else:
            cf = 0.0015
            
        # R_F = 0.5 * rho * S * V^2 * Cf  (Newtons) -> Divide by 1000 for kN
        rf_newtons = 0.5 * rho_sw * self.area_wetted * (V_ms**2) * cf
        self.res_friction = rf_newtons / 1000.0
        
        # 5. Calculate Air Resistance (R_Air)
        frontal_area = self.B * ((self.D - self.T) + 10.0)
        cd_air = 0.8 # Typical ship drag coef
        
        r_air_newtons = 0.5 * rho_air * frontal_area * (V_ms**2) * cd_air
        self.res_air = r_air_newtons / 1000.0
        
        # 6. Appendage Resistance (Approximation)
        self.res_app = self.res_total * 0.04 
        
        # 7. Wave/Residual Resistance (The Remainder)
        # R_Wave = R_Total - (R_F + R_Air + R_App)
        # Ensure it doesn't go negative (if approximations are off)
        calc_sum = self.res_friction + self.res_air + self.res_app
        self.res_wave = self.res_total - calc_sum
        if self.res_wave < 0:
            # Adjustment if friction calc was too aggressive compared to regression
            self.res_wave = 0.0
            self.res_friction = self.res_total * 0.70 # Force balance
        
        # --- ENERGY SAVING DEVICES (ESD) ---
        
        self.p_savings_kw = 0.0
        self.esd_log = []
        
        # A. Air Lubrication
        if self.check_als.isChecked():
            try:
                eff_pct = float(self.edit_als_eff.text())
            except:
                eff_pct = 5.0
            
            # 1. Estimate Flat Bottom Area
            area_bottom = self.L1 * self.B * cb_safe
            
            # 2. Ratio of Bottom Friction
            ratio_bottom = area_bottom / (self.area_wetted if self.area_wetted > 0 else 1.0)
            if ratio_bottom > 1.0: ratio_bottom = 1.0
            
            r_f_bottom = self.res_friction * ratio_bottom
            
            # 3. Apply Savings
            drag_reduction_kn = r_f_bottom * (eff_pct / 100.0)
            
            # 4. Convert to Power Savings
            power_saved = drag_reduction_kn * V_ms
            
            self.p_savings_kw += power_saved
            self.esd_log.append(f"Air Lubrication: -{power_saved:.1f} kW (on {ratio_bottom*100:.0f}% of hull)")
            
            # Reduce Total Resistance for display
            self.res_total -= drag_reduction_kn
            self.res_friction -= drag_reduction_kn

        # B. Wind Assist
        if self.check_wind.isChecked():
            try:
                sav_pct = float(self.edit_wind_sav.text())
            except:
                sav_pct = 10.0
                
            # Simple Power Reduction
            pe_current = pe_kw - self.p_savings_kw # Apply sequentially
            wind_sav_kw = pe_current * (sav_pct / 100.0)
            
            self.p_savings_kw += wind_sav_kw
            self.esd_log.append(f"Wind Assist: -{wind_sav_kw:.1f} kW ({sav_pct}%)")
            
            # Treat wind as negative drag
            wind_drag_red_kn = wind_sav_kw / V_ms
            self.res_total -= wind_drag_red_kn

        # --- APPLY TO SHIP STATE ---
        # Reduce the Service Power (P1) and Installed Power (P2)
        # Note: P1 is in HP in the member variables? 
        # _power sets P1 = (P / Q) * ...
        # P1 is Brake Horse Power (BHP).
        
        # Convert total savings (kW) to BHP
        savings_bhp = self.p_savings_kw / 0.7457
        
        # Apply Savings
        self.P1_Original = self.P1 # Store for reference
        self.P1 -= savings_bhp
        
        if self.P1 < 0: self.P1 = 100.0 # Safety floor
        
        # Usually we keep Installed Power (P2) same for safety (Wind might die),
        # but ALS allows smaller engines. Let's reduce P2 proportionally.
        self.P2_Original = self.P2
        self.P2 -= savings_bhp

    def _mass(self):
        """Port of Sub_mass - FIXED to restore legacy C++ math for standard engines"""
        # 1. Calculate Hull Mass (Steel)
        E1 = self.L1 * (self.B + self.T) + 0.85 * self.L1 * (self.D - self.T) + 250
        T_safe = self.T if self.T != 0 else 1e-9
        C1 = self.C + (0.8 * self.D - self.T) / (10.0 * T_safe)
        
        # Retrieve Ship Constants
        ship_name = self.combo_ship.currentText()
        ship_data = ShipConfig.get(ship_name)
        
        # Steel Coefficient (K1)
        K1 = ship_data["Steel_K1"]
        
        # Outfit Coefficient (K2)
        if ship_data["Outfit_Slope"] > 0.001:
            K2 = ship_data["Outfit_Intercept"] - (self.L1 / ship_data["Outfit_Slope"])
        else:
            K2 = ship_data["Outfit_Intercept"]
            
        self.M1 = K1 * (E1 ** 1.36) * (1.0 + 0.5 * (C1 - 0.7)) # Steel Mass
        self.M2 = K2 * self.L1 * self.B # Outfit Mass
        
        # --- MACHINERY MASS (M3) CALCULATION ---
        
        # In C++, K3 depends on Ship Type (Tanker vs Bulk), not Engine
        # Tanker (Type 1): K3 = 0.59
        # Bulk (Type 2):   K3 = 0.56
        # Cargo (Type 3):  K3 = 0.56
        # We map this from our ShipConfig ID
        if ship_data["ID"] == 1:
            K3 = 0.59
        else:
            K3 = 0.56

        engine_name = self.combo_engine.currentText()
        fuel_data = FuelConfig.get(engine_name)
        
        # Check if this is a "Legacy" engine (Direct diesel, Geared diesel, Steam)
        # We use the index or name to decide. 
        # C++ Ketype: 1=Direct, 2=Geared, 3=Steam
        is_legacy_diesel = (self.Ketype == 1 or self.Ketype == 2)
        is_legacy_steam = (self.Ketype == 3)
        
        installed_power_kw = self.P2 * 0.7457 

        if is_legacy_diesel:
            # --- RESTORED C++ FORMULA for DIESEL ---
            # M3 = 9.38 * (P2/N1)^0.84 + K3 * P2^0.7
            # Note: C++ uses P2 (BHP) and N1 (Engine RPM)
            term1 = 9.38 * ((self.P2 / self.N1) ** 0.84)
            term2 = K3 * (self.P2 ** 0.7)
            self.M3 = term1 + term2
            
        elif is_legacy_steam:
            # --- RESTORED C++ FORMULA for STEAM ---
            # M3 = 0.16 * P2^0.89
            self.M3 = 0.16 * (self.P2 ** 0.89)
            
        else:
            # --- NEW PHYSICS LOGIC (Nuclear, Hydrogen, etc) ---
            if fuel_data["IsNuclear"]:
                self.M3 = 2000.0 + (fuel_data["Machinery"] * installed_power_kw * 0.001)
            else:
                base_machinery = 200.0 
                self.M3 = base_machinery + (installed_power_kw * fuel_data["Machinery"] * 0.001)

        M0 = (self.M1 + self.M2 + self.M3) * 1.02 # Lightship mass (+2% margin)
        
        # --- MODIFIED: Add Aux Weights ---
        # Add Gensets to Machinery
        if hasattr(self, 'M_aux_mach'):
            self.M3 += self.M_aux_mach
            
        # Add Insulation to Outfit
        if hasattr(self, 'M_aux_outfit'):
            self.M2 += self.M_aux_outfit
        # --------------------------------
        
        M0 = (self.M1 + self.M2 + self.M3) * 1.02

        # --- FUEL MASS (W3) CALCULATION ---
        
        V_safe = self.V if self.V > 0.1 else 0.1
        
        if is_legacy_diesel:
            # --- RESTORED C++ FORMULA for DIESEL FUEL ---
            # W3 = 0.0011 * (0.15 * P1 * R / V)
            # 0.15 is roughly the SFC constant used in the legacy code
            self.calculated_fuel_mass = 0.0011 * (0.15 * self.P1 * self.R / V_safe)
            W3 = self.calculated_fuel_mass
            
        elif is_legacy_steam:
            # --- RESTORED C++ FORMULA for STEAM FUEL ---
            # W3 = 0.0011 * (0.28 * P1 * R / V)
            # 0.28 is the SFC constant for Steam
            self.calculated_fuel_mass = 0.0011 * (0.28 * self.P1 * self.R / V_safe)
            W3 = self.calculated_fuel_mass
            
        else:
            # --- NEW PHYSICS LOGIC ---
            if fuel_data["IsNuclear"]:
                W3 = 0.0 
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
                
                W3 = raw_fuel_mass_tonnes * fuel_data["TankFactor"]
                self.calculated_fuel_mass = W3

        if hasattr(self, 'W_aux_fuel'):
            W3 += self.W_aux_fuel # Add generator fuel to total fuel weight

        W4 = 13.0 * (self.M ** 0.35) 
        
        self.W1 = self.M - M0 - W3 - W4 # Cargo deadweight
        self.W5 = self.M - M0 # Total deadweight
        
        return True

    def _power(self):
        """Port of Sub_power"""
        self.Kpwrerr = 1
        m0 = 0
        mm = self.maxit
        X0 = 20.0 * (self.C - 0.675)
        L1_safe = self.L1 if self.L1 > 0 else 1e-9
        g = 9.81
        v_ms = self.V * 0.5144  # knots to m/s
        viscosity = 1.188e-6    # Seawater kinematic viscosity
        
        self.froude_number = v_ms / math.sqrt(g * L1_safe)
        self.reynolds_number = (v_ms * L1_safe) / viscosity
        
        self.lcb_optimal = 8.8 * (self.froude_number - 0.18)
        
        V0 = self.V / math.sqrt(3.28 * L1_safe)
        W0 = (self.L1 * self.B * self.T * self.C) ** (1/3)
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
            
        M5 = self.M * 2204.0 / 2240.0
        self.P = R8 * (self.V ** 3) * (M5 ** (2/3)) / 427.1
        
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
        # ... (UNCHANGED) ...
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

        # --- MODIFIED: Removed check for self.m_Cargo ---
        # We should be able to modify cost params in *any* mode.
        if self.dlg_modify.exec():
            data = self.dlg_modify.get_data()
            self.Lb01 = data['Lb01']; self.Lb02 = data['Lb02']; self.Lb03 = data['Lb03']; self.Lb04 = data['Lb04']; self.Lb05 = data['Lb05']
            self.maxit = data['Maxit']; self.ignspd = data['Ignspd']; self.ignpth = data['Ignpth']; self.dbgmd = data['dbgmd']
            
            # --- MODIFIED: Retrieve cost parameters ---
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
                 # This will happen if dialog_modify.py is not updated.
                 # We'll just skip the error and keep the defaults.
                 pass 
            except ValueError:
                self._show_error("Invalid number in one of the new cost fields.")
            # --- End of MODIFICATION ---
            
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
        # ... (UNCHANGED) ...
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
        
        # Dynamic Labels based on Text
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

        # ... (Rest of function logic: Cargo/Ship Mode, ESD, etc.) ...
        # [Copy the rest of the original _reset_dlg logic here starting from "3. Determine Modes"]
        
        is_cargo_mode = self.radio_cargo.isChecked()
        is_ship_mode = self.radio_ship.isChecked()
        is_teu_mode = self.radio_teu.isChecked()
        is_design_mode = is_cargo_mode or is_teu_mode 
        is_econom_on = self.check_econom.isChecked()
        is_nuclear = (self.combo_engine.currentIndex() == 3) 

        self.edit_als_eff.setEnabled(self.check_als.isChecked())
        self.edit_wind_sav.setEnabled(self.check_wind.isChecked())
        self.label_wind_sav.setEnabled(self.check_wind.isChecked())

        # Toggle Visibility of TEU Inputs
        if hasattr(self, 'layout_teu_container'):
            self.layout_teu_container.setVisible(is_teu_mode)
        else:
            self.edit_teu.setVisible(is_teu_mode)
            self.edit_teu_weight.setVisible(is_teu_mode)
        
        self.edit_weight.setEnabled(is_cargo_mode)
        self.edit_error.setEnabled(is_cargo_mode)

        # Volume Limit / Density Logic
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
        # 1. Reset Defaults (Initialize ALL attributes used in output)
        self.P_aux_total = 0.0
        self.M_aux_mach = 0.0      # Diesel Gen Mass
        self.M_aux_outfit = 0.0    # Insulation
        self.W_aux_fuel = 0.0      # Diesel Fuel Wt
        self.aux_cost_annual = 0.0 # Diesel Cost
        
        # --- FIX: Initialize display variables to prevent AttributeError ---
        self.P_hotel = 0.0
        self.P_cargo_cooling = 0.0
        self.aux_fuel_annual_tonnes = 0.0
        # -----------------------------------------------------------------
        
        if not self.check_aux_enable.isChecked():
            return

        try:
            # --- 2. Calculate POWER Requirement ---
            # Hotel Load
            # --- FIX: Store as self.P_hotel for output ---
            self.P_hotel = float(self.edit_aux_base.text())
            
            # Cargo/Reefer Load
            p_cargo = 0.0
            # --- NEW: Use Text Matching instead of Index ---
            mode_text = self.combo_aux_mode.currentText()
            
            pct = float(self.edit_aux_p1.text()) / 100.0
            load_factor = float(self.edit_aux_p2.text())
            
            if "Reefer" in mode_text: # Reefer Plugs (Container)
                # If in TEU mode use TEU, else estimate from Target Weight
                base_units = self.m_TEU if (self.design_mode == 2) else (self.W / 14.0)
                p_cargo = base_units * pct * load_factor
                
            elif "Hold" in mode_text: # Insulated Hold (Bulk)
                # Estimate volume from Target Weight (approximate)
                vol_est = self.W * 1.5 # approx stowage factor
                p_cargo = (vol_est / 1000.0) * load_factor
                self.M_aux_outfit = vol_est * 0.02 # Insulation weight
            
            self.P_cargo_cooling = p_cargo
                
            self.P_aux_total = self.P_hotel + self.P_cargo_cooling

            is_nuclear = (self.Ketype == 4) 
            
            if is_nuclear:
                self.P2 += self.P_aux_total
                
            else:
                # 1. Add Mass for Diesel Generators
                self.M_aux_mach = (self.P_aux_total * 1.25 * 12.0) / 1000.0
                
                # 2. Add Mass for Diesel Fuel (Range dependent)
                sfc_aux = 0.220 # kg/kWh
                voyage_hours = self.R / (self.V if self.V > 0.1 else 0.1)
                self.W_aux_fuel = (self.P_aux_total * voyage_hours * sfc_aux) / 1000.0
                
                # 3. Add Annual Cost
                hours_year = 365.0 * 24.0
                
                # --- FIX: Store as self.aux_fuel_annual_tonnes for output ---
                self.aux_fuel_annual_tonnes = (self.P_aux_total * hours_year * sfc_aux) / 1000.0
                
                # Use Fuel Price (handle if hidden/zero)
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
            # User clicked "Apply"
            res = dlg.result_data
            
            # 1. Update UI Fields
            self.edit_voyages.setText(f"{res['voyages']:.2f}")
            self.edit_seadays.setText(f"{res['seadays']:.1f}")
            
            # 2. Update Range (Optional, but useful)
            # If not nuclear, set range to route distance
            if self.combo_engine.currentIndex() != 3: # Not Nuclear
                self.edit_range.setText(f"{res['range']:.0f}")
            
            # 3. Store Power Factor
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
        if checked and self.combo_ship.currentText() != "Cargo vessel": #
            ret = QMessageBox.question(self, "Warning:",
                "This option should really be\r\n"
                "used for CARGO ships only!\r\n\r\n"
                "Are you sure you want to use\r\n"
                f"this option for a {self.combo_ship.currentText()}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No: #
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
        if self.Ketype == 1: #
            if self._update_ui_to_data():
                self.m_Erpm = self.m_Prpm #
                self.edit_erpm.setText(str(self.m_Erpm)) #

    def on_killfocus_edit_erpm(self):
        self.Ketype = 1 + self.combo_engine.currentIndex()
        if self.Ketype == 1: #
            if self._update_ui_to_data():
                self.m_Prpm = self.m_Erpm #
                self.edit_prpm.setText(str(self.m_Prpm)) #

    def _initdata(self, i):
        """Port of Sub_initdata"""
        #
        if i == 0:
            self.L1=self.m_Length; self.B=self.m_Breadth; self.D=self.m_Depth; self.T=self.m_Draught; self.C=self.m_Block
            
            # self.W and self.E are now correctly set in on_calculate()
            # for BOTH cargo and TEU modes before this is called.
            
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

    def _outvdu(self):
        """Port of Sub_outvdu - UPDATED for GT and EEDI"""
        output_lines = []
        
        Stype = self.combo_ship.currentText()
        Etype = self.combo_engine.currentText()
        
        # Load Config Data
        ship_data = ShipConfig.get(Stype)
        
        # --- NEW: Calculate Gross Tonnage (GT) ---
        # Formula: GT = V * (0.2 + 0.02 * log10(V))
        # V = Enclosed Volume = L * B * D * Profile_Factor
        # (Profile factor accounts for superstructure volume above main deck)
        pf = ship_data.get("Profile_Factor", 1.0)
        vol_enclosed = self.L1 * self.B * self.D * pf
        
        if vol_enclosed > 0:
            import math
            gt_factor = 0.2 + 0.02 * math.log10(vol_enclosed)
            gross_tonnage = vol_enclosed * gt_factor
        else:
            gross_tonnage = 0.0
        # -----------------------------------------
        
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
            
            # --- NEW: Resistance Breakdown Output ---
            # Check if we have calculated resistance (check for attribute)
            if hasattr(self, 'res_total'):
                output_lines.append("\r\n  ------- Resistance Breakdown:")
                output_lines.append(f"   Total Resistance: {self.res_total:.1f} kN")
                
                # Percentages
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
                
                # Show ESD Log
                if hasattr(self, 'esd_log') and self.esd_log:
                    output_lines.append("   [ESD Active]")
                    for log in self.esd_log:
                        output_lines.append(f"     -> {log}")
                    # Show Power Delta
                    orig_kw = self.P1_Original * 0.7457
                    new_kw = self.P1 * 0.7457
                    output_lines.append(f"     -> New Service Power: {int(new_kw)} kW (was {int(orig_kw)})")
            # ----------------------------------------

            # Call the diagnostic calculator before printing
        self._calculate_detailed_efficiency()

        if opt['ope'] or opt['oqpc']: # Trigger if power options are selected
            output_lines.append("\r\n  ------- Physics & Hydrodynamics:")
            output_lines.append(f"   Froude Number (Fn) = {self.froude_number:.3f}")
            output_lines.append(f"   Reynolds Number (Re)= {self.reynolds_number:.2e}")
            
            # Warn if Fn is outside regression reliability
            if self.froude_number > 0.30:
                output_lines.append("   !! WARNING: Fn > 0.30. Resistance data may be unstable.")
                
            output_lines.append(f"   Estimated Opt. LCB = {self.lcb_optimal:+.2f}% Lbp")
            
            output_lines.append("  ------- Efficiency Breakdown (Diagnostic):")
            output_lines.append(f"   Hull Efficiency (nH) = {self.diag_eta_h:.3f}")
            output_lines.append(f"   Open Water Eff. (nO) = {self.diag_eta_o:.3f}")
            output_lines.append(f"   Total QPC (Original) = {self.Q:.3f}")

            # --- NEW: Auxiliary Analysis Output ---
            if self.check_aux_enable.isChecked():
                output_lines.append("\r\n  ------- Power & Hotel Analysis:")
                
                # Compare Prop vs Aux
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
                
                # Freight Premium Analysis
                try:
                    prem_rate = float(self.edit_aux_prem.text())
                    if prem_rate > 0:
                        is_teu = (self.design_mode == 2)
                        cargo_units = self.m_TEU if is_teu else self.W1
                        
                        extra_income = cargo_units * prem_rate
                        # Only apply premium to the refrigerated portion? 
                        # Usually premium applies to reefer boxes only.
                        mode = self.combo_aux_mode.currentIndex()
                        pct = float(self.edit_aux_p1.text()) / 100.0
                        extra_income *= pct
                        
                        net_profit_delta = extra_income - self.aux_cost_annual
                        
                        output_lines.append(f"   Reefer Premium:   +{extra_income/1e6:.3f} M$")
                        output_lines.append(f"   Net Aux Impact:   {net_profit_delta/1e6:+.3f} M$")
                except:
                    pass
            # --------------------------------------

            # --- TEU Output ---
            if self.design_mode == 2:
                est_teu = self._estimate_teu_capacity(self.L1, self.B, self.D)
                output_lines.append(f"   Target TEU = {int(self.target_teu)}")
                output_lines.append(f"   Est. Capacity = {int(est_teu)} TEU")
                output_lines.append(f"   Avg. Weight = {self.m_TEU_Avg_Weight:5.2f} t/TEU")
                output_lines.append(f"   -> Target Cargo DW = {self.W:7.0f} tonnes")
            
            # --- MODIFIED: Show GT next to Deadweight ---
            if opt['ocdw']: output_lines.append(f"   Cargo DW(tonnes) = {self.W1:7.0f}")
            
            if opt['otdw']: 
                # Display GT on the same line or next line
                gt_str = f"   (GT = {int(gross_tonnage)})"
                output_lines.append(f"   Total DW(tonnes) = {self.W5:7.0f} {gt_str}")
            # --------------------------------------------

            if opt['opdt']: output_lines.append(f"   Prop.dia./T = {self.Pdt:7.2f}")
            if opt['ospeed']: output_lines.append(f"   Speed (knots) = {self.V:7.2f}")
            
            if self.Ketype == 4: # Nuclear
                 if opt['orange']: output_lines.append("   Range(N.M.) = Infinite")
            else:
                if opt['orange']: output_lines.append(f"   Range(N.M.) = {self.R:8.1f}")
            
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
                if opt['oacc']: output_lines.append(f"   Annual capital charges = {self.H1:5.2f}")
                
                if self.Ketype == 4:
                    if opt['oafc']: output_lines.append(f"   Annual Core/Decom Cost = {self.H7:5.2f}")
                else:
                    if opt['oafc']: output_lines.append(f"   Annual fuel costs = {self.H7:5.2f}")
                    if self.check_carbon_tax.isChecked():
                         output_lines.append(f"   (Includes Carbon Tax @ {self.m_CarbonTax} $/tCO2)")
                
                if opt['orfr']:
                    # Determine Unit Label and Conversion Factor
                    if self.design_mode == 2: # TEU Mode
                        unit_label = "$/TEU"
                        conv_factor = self.m_TEU_Avg_Weight # Convert $/tonne to $/TEU
                    else: # Deadweight Mode
                        unit_label = "$/tonne"
                        conv_factor = 1.0

                    base_rfr = self.Rf * conv_factor
                    
                    # Check if we have a premium to display
                    if hasattr(self, 'annual_premium_income') and self.annual_premium_income > 0:
                        # Reconstruct the "Gross" RFR (without premium) for comparison
                        # Rf = (Rt - Premium) / Cargo
                        # So, Premium_Impact = Premium / Cargo
                        
                        W7 = self.V7 * self.W1
                        if W7 > 0:
                            premium_savings_per_tonne = self.annual_premium_income / W7
                            savings_display = premium_savings_per_tonne * conv_factor
                            
                            gross_rfr = base_rfr + savings_display
                            
                            output_lines.append(f"   Req. Freight Rate = {base_rfr:5.2f} {unit_label}")
                            output_lines.append(f"       (Base: {gross_rfr:5.2f} - Premium: {savings_display:5.2f})")
                    else:
                        # Standard Output if no premium
                        output_lines.append(f"   Req. Freight Rate = {base_rfr:5.2f} {unit_label}")

                # --- NEW: CII Calculation ---
                if self.check_cii.isChecked():
                    output_lines.append("\r\n  ------- CII Rating (Operational Carbon Intensity):")
                    
                    try:
                        # 1. Calculate Annual CO2 Emissions
                        # Re-calculate annual energy to be explicit
                        service_power_kw = self.P1 * 0.7457
                        annual_hours = self.D1 * 24.0
                        annual_energy_MJ = service_power_kw * annual_hours * 3.6
                        
                        fuel_data = FuelConfig.get(self.combo_engine.currentText())
                        lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                        eff = fuel_data["Efficiency"]
                        
                        if lhv > 0 and eff > 0:
                            annual_fuel_tonnes = (annual_energy_MJ / (lhv * eff)) / 1000.0
                        else:
                            annual_fuel_tonnes = 0.0
                            
                        annual_co2 = annual_fuel_tonnes * fuel_data["Carbon"] # tonnes CO2
                        
                        # 2. Calculate Distance Sailed (nautical miles)
                        annual_dist = self.V * annual_hours
                        
                        # 3. Determine Capacity (DWT or GT)
                        cii_type = ship_data.get("CII_Type", "DWT")
                        if cii_type == "GT":
                            capacity = gross_tonnage
                        else:
                            capacity = self.W1
                            
                        if capacity < 1.0: capacity = 1.0
                        
                        # 4. Calculate Attained CII (grams CO2 / capacity-mile)
                        if annual_dist > 0:
                            attained_cii = (annual_co2 * 1_000_000) / (capacity * annual_dist)
                        else:
                            attained_cii = 0.0
                            
                        # 5. Calculate Required CII (2023 Baseline)
                        # Reduction factor for 2023-2026 increases every year. Using 5% (2023) as base.
                        reduction_factor = 0.05 
                        
                        a = ship_data.get("CII_a", 0.0)
                        c = ship_data.get("CII_c", 0.0)
                        
                        if a > 0:
                            required_cii = (a * (capacity ** -c)) * (1.0 - reduction_factor)
                            
                            # 6. Determine Rating
                            # A: < 0.83 * Req
                            # B: < 0.94 * Req
                            # C: < 1.06 * Req (Compliance Zone)
                            # D: < 1.19 * Req
                            # E: > 1.19 * Req
                            
                            ratio = attained_cii / required_cii
                            
                            if ratio < 0.83: rating = "A (Major Superior)"
                            elif ratio < 0.94: rating = "B (Minor Superior)"
                            elif ratio <= 1.06: rating = "C (Moderate/Compliant)"
                            elif ratio < 1.19: rating = "D (Minor Inferior)"
                            else: rating = "E (Inferior)"
                            
                            output_lines.append(f"   Annual CO2 = {annual_co2:,.1f} tonnes")
                            output_lines.append(f"   Attained CII = {attained_cii:6.2f}")
                            output_lines.append(f"   Required CII = {required_cii:6.2f} (Year 2023 Basis)")
                            output_lines.append(f"   CII Rating: {rating}")
                            
                            if "D" in rating or "E" in rating:
                                output_lines.append("   -> WARNING: Ship is non-compliant. Needs corrective plan.")
                        else:
                            output_lines.append("   (CII Reference not available for this type)")
                            
                    except Exception as e:
                        output_lines.append(f"   CII Error: {str(e)}")

                # --- NEW: EEDI Calculation with GT Support ---
                if self.check_eedi.isChecked():
                    output_lines.append("\r\n  ------- EEDI Compliance (IMO Phase 3):")
                    
                    try:
                        fuel_data = FuelConfig.get(self.combo_engine.currentText())
                        
                        # 1. Calculate SFC (g/kWh)
                        lhv = self.m_LHV if self.m_LHV > 0 else 42.7
                        eff = fuel_data["Efficiency"]
                        sfc_g_kwh = 3600.0 / (lhv * eff)
                        
                        # 2. Determine Capacity (DWT or GT)
                        eedi_type = ship_data.get("EEDI_Type", "DWT")
                        if eedi_type == "GT":
                            capacity = gross_tonnage
                            cap_label = "GT"
                        else:
                            capacity = self.W1
                            cap_label = "DWT"
                            
                        # Safety check
                        if capacity <= 1.0: capacity = 1.0
                        
                        # 3. Calculate Attained EEDI
                        p_me = 0.75 * (self.P2 * 0.7457) # 75% MCR in kW
                        cf = fuel_data["Carbon"]         
                        v_ref = self.V                   
                        
                        attained_eedi = (p_me * cf * sfc_g_kwh) / (capacity * v_ref)
                        
                        # 4. Calculate Required EEDI (Reference Line)
                        a = ship_data.get("EEDI_a", 0.0)
                        c = ship_data.get("EEDI_c", 0.0)
                        
                        if a > 0:
                            # Reduction factor (30% for Phase 3)
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
             
        output_lines.append("------- End of output results.")
        
        formatted_output = "\r\n".join(output_lines)
        
        if self.m_Append and self.Kcases > 1:
            self.m_Results += "\r\n" + formatted_output
        else:
            self.m_Results = formatted_output
            
        self.text_results.setText(self.m_Results)
        self.text_results.verticalScrollBar().setValue(self.text_results.verticalScrollBar().maximum())
            
        return True