# ship_des_view_widget.py
# Port of CShipDesView (the main form)
# MODIFIED to include TEU, Nuclear Propulsion (v2, $/kW), and Plotting

import sys
import math
import csv
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QTextEdit, QPushButton, QVBoxLayout, QGroupBox, QRadioButton,
    QHBoxLayout, QMessageBox, QFileDialog, QLabel, QGridLayout,
    QApplication
)
# ...
from PySide6.QtCore import Qt

# --- NEW: Imports for Matplotlib Graphing ---
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
except ImportError:
    print("Matplotlib not found. Plotting will be disabled.")
    print("Please install it: pip install matplotlib")
    FigureCanvas = None
    Figure = None
# --- END: Imports for Matplotlib Graphing ---


# --- MODIFICATION: Dialog imports are moved inside __init__ to fix circular dependency ---
#
# from dialog_modify import ModifyDialog
# from dialog_outopt import OutoptDialog
# from dialog_readme import ReadmeDialog
#
# --- END MODIFICATION ---


# --- NEW: GraphWindow Class ---
# This class creates a new window to display the matplotlib plot
class GraphWindow(QWidget):
    """
    A simple window (QWidget) that holds a Matplotlib canvas
    for displaying the range analysis plot.
    """
    def __init__(self, x_data, y_data, x_label, y_label, title):
        super().__init__()
        self.setWindowTitle("Range Analysis Plot")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Create a matplotlib figure and canvas
        fig = Figure(figsize=(5, 4), dpi=100)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        
        # Plot the data
        if x_data and y_data:
            ax.plot(x_data, y_data, marker='o', linestyle='-')
        
        # Set labels and title
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(title)
        ax.grid(True)
        
        layout.addWidget(canvas)
# --- END: GraphWindow Class ---


class ShipDesViewWidget(QWidget):
    """
    Replaces CShipDesView.
    This is the main form, holding all UI and logic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Port C++ Error Constants ---
        #
        self.NOT_CONVERGE = 2
        self.SPEED_LOW = 3 #
        self.SPEED_HIGH = 5 #
        self.PITCH_LOW = 7 #
        self.PITCH_HIGH = 11 #

        # --- Port C++ Member Variables ---
        #
        # Default values from the constructor
        self.m_Econom = True #
        self.m_Block = 0.818525 #
        self.m_Breadth = 31.898924 #
        self.m_Depth = 15.358741 #
        self.m_Draught = 11.725275 #
        self.m_Erpm = 120.0 #
        self.m_Fuel = 80.0 #
        self.m_Interest = 10.0 #
        self.m_Length = 207.34301 #
        self.m_Prpm = 120.0 #
        self.m_Range = 12000.0 #
        
        # --- THIS IS THE MISSING LINE ---
        self.m_Repay = 15.0 #
        # ----------------------------------
        
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

        # --- NEW: TEU and Nuclear default variables ---
        self.m_TEU = 3000.0
        self.m_TEU_Avg_Weight = 14.0
        
        # --- MODIFIED: Nuclear cost is now per/kW ---
        self.m_Reactor_Cost_per_kW = 4000.0 # ($/kW)
        self.m_Core_Life = 20.0             # (Years)
        self.m_Decom_Cost = 200.0           # (M$)
        
        # --- NEW: Storage for conventional range ---
        self.m_conventional_Range = self.m_Range # Store the default
        
        # --- NEW: Storage for plot window ---
        self.graph_window = None # Holds reference to graph window

        # Internal calculation variables
        self.Kcases = 0 #
        self.Ketype = 1 #
        self.Kstype = 1 #
        self.Kpwrerr = 1 #
        self.CalculatedOk = False #
        self.Ksaved = True #
        self.Savefile = "SDout.txt" #
        self.design_mode = 0 # 0=Cargo, 1=Ship, 2=TEU
        self.target_teu = 0
        
        # ... (rest of __init__ is unchanged) ...

        # ... (rest of __init__ is unchanged) ...

        #
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

        # --- MODIFICATION: Import moved here ---
        from dialog_outopt import OutoptDialog
        # Output options (from COutopt)
        self.outopt_data = OutoptDialog().get_data() # Get defaults

        # Calculation state variables
        self.L1 = 0.0; self.B = 0.0; self.D = 0.0; self.T = 0.0; self.C = 0.0
        self.R = 0.0; self.V = 0.0; self.N1 = 0.0; self.N2 = 0.0; self.V7 = 0.0
        self.D1 = 0.0; self.F8 = 0.0; self.I = 0.0; self.N = 0
        self.Pdt = 0.0; self.W = 0.0; self.E = 0.0
        self.W1 = 0.0; self.M = 0.0; self.M1 = 0.0; self.M2 = 0.0; self.M3 = 0.0
        self.W5 = 0.0; self.P = 0.0; self.P1 = 0.0; self.P2 = 0.0
        self.Q = 0.0; self.Q1 = 0.0; self.Q2 = 0.0; self.Rf = 0.0
        self.S = 0.0; self.F0 = 0.0; self.F5 = 0.0; self.F9 = 0.0
        self.G6 = 0.0; self.H1 = 0.0; self.H7 = 0.0; self.Kcount = 0

        # --- Ported Static Data Arrays ---
        
        # From Sub_power
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
        
        # From Sub_freeboard
        self._E5=0.2; self._Y1=0.5; self._Y2=0.0
        self._L2 = (30, 40, 60, 80, 100, 120, 140, 160, 180, 200,
                    220, 240, 260, 280, 300, 320, 340, 360)
        self._F1 = (250, 334, 573, 841, 1135, 1459, 1803, 2126, 2393, 2612,
                    2792, 2946, 3072, 3176, 3262, 3331, 3382, 3425)
        self._F2 = (250, 334, 573, 887, 1271, 1690, 2109, 2520, 2915, 3264,
                    3586, 3880, 4152, 4397, 4630, 4844, 5055, 5260)

        # --- MODIFIED: Cost parameters (moved from static) ---
        # These are now member variables, accessible by the Modify dialog
        self.m_S1_Steel1 = 16000.0   # Steel cost param 1
        self.m_S2_Steel2 = 2420.0    # Steel cost param 2
        self.m_S3_Outfit1 = 180000.0 # Outfit cost param 1
        self.m_S4_Outfit2 = 35000.0  # Outfit cost param 2
        self.m_S5_Machinery1 = 7500.0  # Machinery cost param 1 (conventional)
        self.m_S6_Machinery2 = 17000.0 # Machinery cost param 2 (conventional)
        
        self.m_H2_Crew = 3000000.0    # Annual crew cost
        self.m_H3_Maint_Percent = 0.05 # Maintenance as % of build cost (was 0.05)
        self.m_H4_Port = 1500000.0   # Annual port/admin
        self.m_H5_Stores = 500000.0  # Annual stores
        self.m_H6_Overhead = 1250000.0 # Annual overhead
        self.m_H8_Other = 0.0       # Annual other

        # --- MODIFICATION: Imports moved here ---
        from dialog_modify import ModifyDialog
        from dialog_readme import ReadmeDialog

        # --- Create Dialog Instances ---
        self.dlg_modify = ModifyDialog(self)
        self.dlg_outopt = OutoptDialog(self)
        self.dlg_readme = ReadmeDialog(self)

        # --- Create UI Controls (from ShipDes.rc) ---
        #
        self.combo_ship = QComboBox()
        self.combo_ship.addItems(["Tanker", "Bulk carrier", "Cargo vessel"]) #
        
        #
        self.combo_engine = QComboBox()
        self.combo_engine.addItems([
            "Direct diesel", 
            "Geared diesel", 
            "Steam turbines", 
            "Nuclear Steam Turbine" # NEW
        ])
        
        #
        self.btn_calculate = QPushButton("&Calculate")
        #
        self.btn_save = QPushButton("&Save the output")
        #
        self.check_append = QCheckBox("&Append")
        
        #
        self.radio_cargo = QRadioButton("Cargo deadweight")
        self.radio_ship = QRadioButton("Ship dimensions") #
        self.radio_teu = QRadioButton("TEU Capacity") # NEW
        self.edit_weight = QLineEdit() #
        self.edit_error = QLineEdit() #
        
        # --- NEW: TEU UI ---
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
        
        #
        self.check_econom = QCheckBox("Economic analysis required")
        self.edit_voyages = QLineEdit() #
        self.edit_seadays = QLineEdit() #
        
        # --- MODIFIED: Nuclear and Fuel UI ---
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
        
        #
        self.text_results = QTextEdit()
        self.text_results.setReadOnly(True)
        self.text_results.setFontFamily("Courier New")
        
        # Buttons to open dialogs
        self.btn_modify = QPushButton("&Modify parameters") #
        self.btn_outopt = QPushButton("&Output options") #

        # --- Lay out the form ---
        main_layout = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        
        # Top bar
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("Ship type:")) #
        top_bar_layout.addWidget(self.combo_ship)
        top_bar_layout.addWidget(QLabel("Engine type:")) #
        top_bar_layout.addWidget(self.combo_engine)
        top_bar_layout.addWidget(self.btn_calculate)
        top_bar_layout.addWidget(self.check_append)
        left_col.addLayout(top_bar_layout)
        
        # Input Group
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
        
        # --- NEW: TEU Layout ---
        teu_layout = QHBoxLayout()
        teu_layout.addWidget(QLabel("Target TEU:"))
        teu_layout.addWidget(self.edit_teu)
        teu_layout.addWidget(QLabel("Avg. Weight/TEU (tonnes):"))
        teu_layout.addWidget(self.edit_teu_weight)
        input_layout.addRow(teu_layout)
        
        # Constraints Sub-Group
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

        # Economic Group
        eco_group = QGroupBox()
        eco_layout = QFormLayout()
        eco_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        eco_group.setTitle("") # Groupbox is just for visual separation
        eco_layout.addRow(self.check_econom)
        
        eco_grid = QGridLayout()
        eco_grid.addWidget(QLabel("Voyages per year:"), 0, 0) #
        eco_grid.addWidget(self.edit_voyages, 0, 1)
        eco_grid.addWidget(QLabel("Sea days per year:"), 0, 2) #
        eco_grid.addWidget(self.edit_seadays, 0, 3)
        
        # --- MODIFIED: Fuel/Nuclear grid layout ---
        eco_grid.addWidget(self.label_fuel, 1, 0)
        eco_grid.addWidget(self.edit_fuel, 1, 1)
        eco_grid.addWidget(self.label_reactor_cost, 1, 0) # Label text was changed in __init__
        eco_grid.addWidget(self.edit_reactor_cost, 1, 1)
        
        eco_grid.addWidget(self.label_core_life, 1, 2)
        eco_grid.addWidget(self.edit_core_life, 1, 3)
        
        eco_grid.addWidget(QLabel("Interest rate (%):"), 2, 0) #
        eco_grid.addWidget(self.edit_interest, 2, 1)
        eco_grid.addWidget(QLabel("No. years to repay:"), 2, 2) #
        eco_grid.addWidget(self.edit_repay, 2, 3)

        eco_grid.addWidget(self.label_decom_cost, 3, 0)
        eco_grid.addWidget(self.edit_decom_cost, 3, 1)

        eco_layout.addRow(eco_grid)
        
        eco_group.setLayout(eco_layout)
        left_col.addWidget(eco_group)
        # --- MODIFIED: Range Analysis Group ---
        range_group = QGroupBox("Range Analysis (CSV Export / Plot)")
        range_layout = QGridLayout()
        
        range_layout.addWidget(QLabel("X-Axis (Parameter to vary):"), 0, 0)
        self.combo_param_vary = QComboBox()
        self.combo_param_vary.addItems([
            "Block Co.",
            "Speed(knts)",
            "Cargo deadweight(t)",
            "TEU Capacity",
            "L/B Ratio",
            "B(m)",
            "B/T Ratio"
        ])
        range_layout.addWidget(self.combo_param_vary, 0, 1, 1, 3) # Span 3 cols

        # --- NEW: Y-Axis selection for plotting ---
        range_layout.addWidget(QLabel("Y-Axis (for Plot):"), 1, 0)
        self.combo_param_y = QComboBox()
        self.combo_param_y.addItems([
            "Lbp(m)",
            "B(m)",
            "D(m)",
            "T(m)",
            "CB",
            "Displacement(t)",
            "CargoDW(t)",
            "TotalDW(t)",
            "ServicePower(kW)",
            "InstalledPower(kW)",
            "BuildCost(M$)",
            "RFR($/tonne or $/TEU)"
        ])
        range_layout.addWidget(self.combo_param_y, 1, 1, 1, 3) # Span 3 cols

        range_layout.addWidget(QLabel("Start:"), 2, 0)
        self.edit_range_start = QLineEdit("0.75")
        range_layout.addWidget(self.edit_range_start, 2, 1)
        
        range_layout.addWidget(QLabel("End:"), 2, 2)
        self.edit_range_end = QLineEdit("0.85")
        range_layout.addWidget(self.edit_range_end, 2, 3)
        
        range_layout.addWidget(QLabel("Steps:"), 3, 0)
        self.edit_range_steps = QLineEdit("11") # 11 steps gives 10 intervals
        range_layout.addWidget(self.edit_range_steps, 3, 1)
        
        self.btn_run_range = QPushButton("Run & Save CSV")
        range_layout.addWidget(self.btn_run_range, 4, 0, 1, 2) # Span 2 cols
        
        # --- NEW: Plot Button ---
        self.btn_run_plot = QPushButton("Run & Plot Graph")
        range_layout.addWidget(self.btn_run_plot, 4, 2, 1, 2) # Span 2 cols
        
        # Disable plot button if matplotlib is not available
        if FigureCanvas is None:
            self.btn_run_plot.setEnabled(False)
            self.btn_run_plot.setText("Run & Plot (matplotlib needed)")
            self.btn_run_plot.setToolTip("Please install matplotlib to enable plotting")
        
        range_group.setLayout(range_layout)
        left_col.addWidget(range_group)
        # --- END: Range Analysis Group ---
        
        # Dialog Buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_modify)
        button_layout.addWidget(self.btn_outopt)
        button_layout.addWidget(self.btn_save)
        left_col.addLayout(button_layout)
        
        left_col.addStretch(1) # Pushes everything up
        
        main_layout.addLayout(left_col)
        main_layout.addWidget(self.text_results, 1) # Add results box with stretch
        self.setLayout(main_layout)
        
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
        self.combo_engine.currentIndexChanged.connect(self._reset_dlg) # IMPORTANT
        #
        
        self.check_econom.toggled.connect(self.on_check_econom) #
        self.check_lbratio.toggled.connect(self.on_check_lbratio) #
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
        try:
            self.m_Weight = float(self.edit_weight.text())
            self.m_Error = float(self.edit_error.text())
            self.m_TEU = float(self.edit_teu.text())
            self.m_TEU_Avg_Weight = float(self.edit_teu_weight.text())
            self.m_LbratioV = float(self.edit_lbratio.text())
            self.m_BvalueV = float(self.edit_bvalue.text())
            self.m_BtratioV = float(self.edit_btratio.text())
            self.m_CbvalueV = float(self.edit_cbvalue.text())
            self.m_PdtratioV = float(self.edit_pdtratio.text())
            self.m_Length = float(self.edit_length.text())
            self.m_Breadth = float(self.edit_breadth.text())
            self.m_Draught = float(self.edit_draught.text())
            self.m_Depth = float(self.edit_depth.text())
            self.m_Block = float(self.edit_block.text())
            self.m_Speed = float(self.edit_speed.text())
            
            # --- MODIFIED: Handle "Infinite" text ---
            if self.edit_range.text() == "Infinite":
                self.m_Range = float('inf')
            else:
                self.m_Range = float(self.edit_range.text())
            
            self.m_Prpm = float(self.edit_prpm.text())
            self.m_Erpm = float(self.edit_erpm.text())
            self.m_Voyages = float(self.edit_voyages.text())
            self.m_Seadays = float(self.edit_seadays.text())
            self.m_Fuel = float(self.edit_fuel.text())
            
            # --- MODIFIED: Read $/kW rate ---
            self.m_Reactor_Cost_per_kW = float(self.edit_reactor_cost.text())
            
            self.m_Core_Life = float(self.edit_core_life.text())
            self.m_Decom_Cost = float(self.edit_decom_cost.text())
            self.m_Interest = float(self.edit_interest.text())
            self.m_Repay = float(self.edit_repay.text())
            
            if self.radio_cargo.isChecked():
                self.m_Cargo = 0
            elif self.radio_ship.isChecked():
                self.m_Cargo = 1
            elif self.radio_teu.isChecked():
                self.m_Cargo = 2

            self.m_Econom = self.check_econom.isChecked() #
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
            self._show_error(f"Invalid number in one of the fields.\n\nDetails: {e}")
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
        self.edit_fuel.setText(f"{self.m_Fuel:.6g}")
        
        # --- MODIFIED: Set $/kW rate ---
        self.edit_reactor_cost.setText(f"{self.m_Reactor_Cost_per_kW:.6g}")
        
        self.edit_core_life.setText(f"{self.m_Core_Life:.6g}")
        self.edit_decom_cost.setText(f"{self.m_Decom_Cost:.6g}")
        self.edit_interest.setText(f"{self.m_Interest:.6g}")
        self.edit_repay.setText(f"{self.m_Repay:.6g}")
        
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
        if self.Kstype < 1 or self.Kstype > 3:
            self._show_error("Fatal error: Ship type unknown!", "Input error")
            return False
        if self.Ketype < 1 or self.Ketype > 4: # Now 4 engine types
            self._show_error("Fatal error: Engine type unknown!", "Input error")
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


    def on_calculate(self):
        """Port of OnButtonCal"""
        #
        
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
        
        # Restore original design mode
        self.m_Cargo = self.design_mode
            
        if self.m_Econom: #
            # _cost() will now use Ketype to check for nuclear
            if not self._cost(): return
            
        self.CalculatedOk = True #
        self.Ksaved = False #
        
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
        # This is the feature from request 1
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
                    # on_calculate() reads from the UI fields we just set
                    self.on_calculate() 
                    
                    # --- C. Extract results ---
                    row = [f"{value:.6g}"]
                    if not self.CalculatedOk:
                        # This is the other part of request 1:
                        # Write "CALCULATION FAILED" for anomalous results
                        row.extend(["CALCULATION FAILED"] * (len(header) - 1))
                    else:
                        # Extract results from member variables
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
            # --- Restore original UI state ---
            # This is crucial so the user's form is not left
            # in the state of the loop's last run.
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
            
            # --- Restore error flag state ---
            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            
            # Reset the main results window
            self.m_Results = "Press the Calculate button\r\nto find ship dimensions ..."
            # ... (rest of the finally block) ...
            # Reset the main results window
            self.m_Results = "Press the Calculate button\r\nto find ship dimensions ..."
            self.text_results.setText(self.m_Results)
            self.CalculatedOk = False
            self.Kcases = 0
            self._reset_dlg()
            # --- End restoring state ---

    # --- NEW: Plotting Function ---
    def on_run_plot(self):
        """
        Runs a calculation over a range of values
        and plots the results in a new window.
        Pop-up errors are suppressed, and failed
        calculations are not plotted.
        """
        
        # 1. Get parameter and range inputs
        try:
            param_name = self.combo_param_vary.currentText() # X-Axis
            y_param_name = self.combo_param_y.currentText()  # Y-Axis
            
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
        
        # Check if matplotlib is available
        if FigureCanvas is None:
            self._show_error("Matplotlib library not found. Cannot plot graph.")
            return

        # 3. Create the list of values to iterate over
        value_range = np.linspace(start, end, steps)

        # 4. Define data storage for plot
        x_data = []
        y_data = []

        # 5. Run the loop
        self.m_Results = f"Running plot analysis for '{y_param_name}' vs. '{param_name}'...\r\n"
        self.text_results.setText(self.m_Results)
        self.Kcases = 0 # Reset case counter for this run
        
        # --- Store original UI state ---
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
        }
        # --- Temporarily suppress pop-up errors for the loop ---
        self.ignspd = True
        self.ignpth = True

        try:
            is_econom_on = self.check_econom.isChecked() # Check once at start
            is_teu_mode = original_ui_state['teu_r'] # Check original mode
            
            for i, value in enumerate(value_range):
                # Update progress in the UI
                self.text_results.append(f"Running step {i+1}/{steps} ({param_name} = {value:.4f})...")
                QApplication.processEvents() # Allow UI to refresh

                # --- A. Set the parameter in the UI ---
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
                
                
                # --- B. Run the main calculation ---
                self.on_calculate() 
                
                # --- C. Extract results for plotting ---
                # As requested, only plot if CalculatedOk is True
                if self.CalculatedOk:
                    y_val = None # Reset y_val for this step
                    
                    if y_param_name == "Lbp(m)": y_val = self.L1
                    elif y_param_name == "B(m)": y_val = self.B
                    elif y_param_name == "D(m)": y_val = self.D
                    elif y_param_name == "T(m)": y_val = self.T
                    elif y_param_name == "CB": y_val = self.C
                    elif y_param_name == "Displacement(t)": y_val = self.M
                    elif y_param_name == "CargoDW(t)": y_val = self.W1
                    elif y_param_name == "TotalDW(t)": y_val = self.W5
                    elif y_param_name == "ServicePower(kW)": y_val = 0.7457 * self.P1
                    elif y_param_name == "InstalledPower(kW)": y_val = 0.7457 * self.P2
                    elif y_param_name == "BuildCost(M$)" and is_econom_on: 
                        y_val = self.S
                    elif y_param_name == "RFR($/tonne or $/TEU)" and is_econom_on:
                        if is_teu_mode: # Use the mode active at the *start* of the run
                            y_val = self.Rf * self.m_TEU_Avg_Weight
                        else:
                            y_val = self.Rf
                    
                    # Only add the point if we found a valid y_val
                    # (e.g., if user picks "BuildCost" but econom is off, y_val is None)
                    if y_val is not None:
                        x_data.append(value)
                        y_data.append(y_val)

            # --- D. Show the plot ---
            self.text_results.append(f"\r\n... Range analysis complete. Opening plot... ...")
            
            if not x_data or not y_data:
                self._show_error(
                    f"No valid data points were generated for Y-Axis '{y_param_name}'.\n\n"
                    "If you selected an economic output (e.g., BuildCost, RFR), "
                    "please ensure 'Economic analysis required' is checked."
                )
            else:
                x_label = param_name
                y_label = y_param_name
                title = f"{y_label} vs. {x_label}"
                
                # Create and show the graph window
                # We store it as a member to prevent it from being garbage-collected
                self.graph_window = GraphWindow(x_data, y_data, x_label, y_label, title)
                self.graph_window.show()

        except Exception as e:
            self._show_error(f"Failed during plot analysis: {e}")
        
        finally:
            # --- Restore original UI state ---
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
            
            # --- Restore error flag state ---
            self.ignspd = original_ui_state['ignspd']
            self.ignpth = original_ui_state['ignpth']
            
            # Reset the main results window
            self.m_Results = "Press the Calculate button\r\nto find ship dimensions ..."
            self.text_results.setText(self.m_Results)
            self.CalculatedOk = False
            self.Kcases = 0
            self._reset_dlg()
            # --- End restoring state ---
    # --- END: Plotting Function ---
    

    def _freeboard(self):
        """Port of Sub_freeboard"""
        # ... (UNCHANGED) ...
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
        
        if self.Kstype == 1: # Tanker
            F1_l = self._F1[l]
            F1_l1 = self._F1[l+1]
            self.F5 = F1_l + (self.L1 - L2_l) * (F1_l1 - F1_l) / (L2_l1 - L2_l)
        else: # Bulk carrier and cargo vessel
            F2_l = self._F2[l]
            F2_l1 = self._F2[l+1]
            self.F5 = F2_l + (self.L1 - L2_l) * (F2_l1 - F2_l) / (L2_l1 - L2_l)
            
        if self.Kstype != 1 and self.L1 < 100:
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
        # ... (UNCHANGED) ...
        if self.Kstype == 1: G3 = 0.63 * self.D
        elif self.Kstype == 2: G3 = 0.57 * self.D
        else: G3 = 0.62 * self.D
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
        
        # S8 = self._S1 * (self.M1 ** (2/3)) * (self.L1 ** (1/3)) / C_safe + self._S2 * self.M1
        S8 = self.m_S1_Steel1 * (self.M1 ** (2/3)) * (self.L1 ** (1/3)) / C_safe + self.m_S2_Steel2 * self.M1
        
        # S9 = self._S3 * (self.M2 ** (2/3)) + self._S4 * (self.M2 ** 0.95)
        S9 = self.m_S3_Outfit1 * (self.M2 ** (2/3)) + self.m_S4_Outfit2 * (self.M2 ** 0.95)
        
        # --- MODIFIED: Nuclear Capital Cost (v2, from $/kW) ---
        S0_nuclear = 0.0 # Will store the calculated nuclear cost
        if self.Ketype == 4: # Nuclear
            # Calculate total reactor cost from the $/kW rate
            installed_power_kw = self.P2 * 0.7457
            S0_nuclear = self.m_Reactor_Cost_per_kW * installed_power_kw
            S0 = S0_nuclear # This is the capital cost in $
        else: # Fossil
            # S0 = self._S5 * (self.P1 ** 0.82) + self._S6 * (self.P1 ** 0.82) # C++ check?!
            S0 = self.m_S5_Machinery1 * (self.P1 ** 0.82) + self.m_S6_Machinery2 * (self.P1 ** 0.82)
        
        self.S = S8 + S9 + S0
        
        I_rate = self.I * 0.01
        H0 = (1.0 + I_rate) ** self.N
        if (H0 - 1.0) == 0: H0 = 1e-9 # Avoid div by zero
        H0 = I_rate * H0 / (H0 - 1.0)
        
        self.H1 = H0 * self.S # Annual capital charges
        H3 = H3 * self.S #
        
        # --- MODIFIED: Nuclear "Fuel" Cost (v2, based on S0_nuclear) ---
        if self.Ketype == 4: # Nuclear
            # Nuclear "fuel" cost is annualized core + decommissioning
            core_life_safe = self.m_Core_Life if self.m_Core_Life > 0 else 1e-9
            
            # Use the calculated S0_nuclear (Option A)
            annual_core_cost = S0_nuclear / core_life_safe
            
            # Simple sinking fund for decommissioning
            repay_years_safe = self.N if self.N > 0 else 1e-9
            annual_decom_fund = (self.m_Decom_Cost * 1.0e6) / repay_years_safe 
            
            self.H7 = annual_core_cost + annual_decom_fund
        else: # Fossil
            if self.Ketype == 1: F7 = 0.15
            elif self.Ketype == 2: F7 = 0.15
            else: F7 = 0.28
            self.H7 = F7 * self.P1 * self.D1 * 24 * self.F8 * 1.0e-3
        
        # Rt = self.H1 + self._H2 + H3 + self._H4 + self._H5 + self._H6 + self.H7 + self._H8
        Rt = self.H1 + self.m_H2_Crew + H3 + self.m_H4_Port + self.m_H5_Stores + self.m_H6_Overhead + self.H7 + self.m_H8_Other
        
        self.S *= 1.0e-6 # Convert total build cost to M$ for output
        
        W1_safe = self.W1 if self.W1 != 0 else 1e-9
        W7 = self.V7 * W1_safe
        
        if W7 == 0: W7 = 1e-9 # Avoid division by zero
        self.Rf = Rt / W7
        
        return True # C++ version has no failure modes

    def _mass(self):
        """Port of Sub_mass"""
        E1 = self.L1 * (self.B + self.T) + 0.85 * self.L1 * (self.D - self.T) + 250
        
        T_safe = self.T if self.T != 0 else 1e-9
        C1 = self.C + (0.8 * self.D - self.T) / (10.0 * T_safe)
        
        if self.Kstype == 1:
            K1 = 0.032; K2 = 0.37 - self.L1 / 1765.0; K3 = 0.59
        elif self.Kstype == 2:
            K1 = 0.032; K2 = 0.32 - self.L1 / 1765.0; K3 = 0.56
        else:
            K1 = 0.034; K2 = 0.41; K3 = 0.56
            
        self.M1 = K1 * (E1 ** 1.36) * (1.0 + 0.5 * (C1 - 0.7)) # Steel
        self.M2 = K2 * self.L1 * self.B # Outfit
        
        N1_safe = self.N1 if self.N1 != 0 else 1e-9
        
        # --- MODIFIED: Nuclear Machinery Mass ---
        if self.Ketype == 4: # Nuclear
            # --- PLACEHOLDER: Nuclear Machinery Mass ---
            # This is a *total guess* and MUST be replaced.
            # A real formula would be complex, e.g., M3 = C_base + C_pwr * P2
            # It must account for reactor, shielding, steam plant, etc.
            # Using a very heavy placeholder: 4000 tonnes base + 0.2 t/kW
            self.M3 = 4000 + 0.2 * (self.P2 * 0.7457) # P2 is in BHP, convert to KW
        elif self.Ketype == 1:
            self.M3 = 9.38 * ((self.P2 / N1_safe) ** 0.84) + K3 * (self.P2 ** 0.7)
        elif self.Ketype == 2:
            self.M3 = 9.38 * ((self.P2 / N1_safe) ** 0.84) + K3 * (self.P2 ** 0.7)
        else: # Ketype == 3
            self.M3 = 0.16 * (self.P2 ** 0.89)
            
        M0 = (self.M1 + self.M2 + self.M3) * 1.02 # Lightship mass
        
        V_safe = self.V if self.V != 0 else 1e-9
        
        # --- MODIFIED: Nuclear Fuel Weight ---
        if self.Ketype == 4: # Nuclear
            W3 = 0.0 # Nuclear fuel is not a consumable
        elif self.Ketype == 3: # Steam turbines
            W3 = 0.0011 * (0.28 * self.P1 * self.R / V_safe)
        else: # Diesels
            W3 = 0.0011 * (0.15 * self.P1 * self.R / V_safe)
            
        W4 = 13.0 * (self.M ** 0.35) # Stores, water, etc.
        
        self.W1 = self.M - M0 - W3 - W4 # Cargo deadweight
        self.W5 = self.M - M0 # Total deadweight
        
        return True

    def _power(self):
        """Port of Sub_power"""
        # ... (UNCHANGED, except for F9 for nuclear) ...
        self.Kpwrerr = 1
        m0 = 0
        mm = self.maxit
        X0 = 20.0 * (self.C - 0.675)
        L1_safe = self.L1 if self.L1 > 0 else 1e-9
        V0 = self.V / math.sqrt(3.28 * L1_safe)
        W0 = (self.L1 * self.B * self.T * self.C) ** (1/3)
        if W0 == 0: W0 = 1e-9
        
        # ... (Debug and V0 range checks - UNCHANGED) ...
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
        
        # ... (Debug and P5 pitch range checks - UNCHANGED) ...
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
        
        if self.Ketype == 1: self.F9 = 0.98 # Direct
        elif self.Ketype == 2: self.F9 = 0.95 # Geared
        elif self.Ketype == 3: self.F9 = 0.95 # Steam
        elif self.Ketype == 4: self.F9 = 0.95 # Nuclear (same as steam)
            
        Q_safe = self.Q if self.Q != 0 else 1e-9
        F9_safe = self.F9 if self.F9 != 0 else 1e-9
        
        self.P1 = (self.P / Q_safe) * self.F0 / F9_safe
        F6 = 30.0 # Margin %
        self.P2 = self.P1 * (1.0 + 0.01 * F6)
        
        return True

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
        # ... (UNCHANGED) ...
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
        #
        self.Kstype = self.combo_ship.currentIndex() + 1
        self.MdfEnable[0] = (self.m_Lbratio or self.m_Bvalue)
        self.MdfEnable[1] = self.m_Cbvalue
        self.dlg_modify.set_enable(self.MdfEnable)
        
        # --- MODIFIED: Add cost parameters to data dict ---
        data = {
            'Lb01': self.Lb01, 'Lb02': self.Lb02, 'Lb03': self.Lb03, 'Lb04': self.Lb04, 'Lb05': self.Lb05,
            'Maxit': self.maxit, 'Ignspd': self.ignspd, 'Ignpth': self.ignpth, 'dbgmd': self.dbgmd,
            'Note': f"({self.combo_ship.currentText()} with {self.combo_engine.currentText()})",
            
            # New Cost Params
            'S1_Steel1': self.m_S1_Steel1,
            'S2_Steel2': self.m_S2_Steel2,
            'S3_Outfit1': self.m_S3_Outfit1,
            'S4_Outfit2': self.m_S4_Outfit2,
            'S5_Machinery1': self.m_S5_Machinery1,
            'S6_Machinery2': self.m_S6_Machinery2,
            'H3_Maint_Percent': self.m_H3_Maint_Percent,
            # Also adding the other fixed costs so user can modify them
            'H2_Crew': self.m_H2_Crew,
            'H4_Port': self.m_H4_Port,
            'H5_Stores': self.m_H5_Stores,
            'H6_Overhead': self.m_H6_Overhead,
        }
        # --- End of MODIFICATION ---
        
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
        """Port of reset_dlg - NOW THE MAIN UI CONTROLLER"""
        
        # Get UI state
        is_cargo_mode = self.radio_cargo.isChecked()
        is_ship_mode = self.radio_ship.isChecked()
        is_teu_mode = self.radio_teu.isChecked()
        is_design_mode = is_cargo_mode or is_teu_mode # Not ship mode
        
        is_econom_on = self.check_econom.isChecked()
        is_nuclear = (self.combo_engine.currentIndex() == 3) # 4th item
        
        is_lbratio_on = self.check_lbratio.isChecked()
        is_bvalue_on = self.check_bvalue.isChecked()
        is_btratio_on = self.check_btratio.isChecked()
        is_cbvalue_on = self.check_cbvalue.isChecked()
        is_pdtratio_on = self.check_pdtratio.isChecked()

        # Ship dim fields
        self.edit_length.setEnabled(is_ship_mode)
        self.edit_breadth.setEnabled(is_ship_mode)
        self.edit_depth.setEnabled(is_ship_mode)
        self.edit_draught.setEnabled(is_ship_mode)
        self.edit_block.setEnabled(is_ship_mode)
        
        # Cargo fields
        self.edit_weight.setEnabled(is_cargo_mode)
        self.edit_error.setEnabled(is_cargo_mode)
        
        # TEU fields
        self.edit_teu.setEnabled(is_teu_mode)
        self.edit_teu_weight.setEnabled(is_teu_mode)
        
        # Design constraint fields
        self.check_lbratio.setEnabled(is_design_mode)
        self.check_bvalue.setEnabled(is_design_mode)
        self.check_btratio.setEnabled(is_design_mode)
        self.check_cbvalue.setEnabled(is_design_mode)
        self.btn_modify.setEnabled(is_design_mode)
        
        self.edit_lbratio.setEnabled(is_design_mode and is_lbratio_on)
        self.edit_bvalue.setEnabled(is_design_mode and is_bvalue_on)
        self.edit_btratio.setEnabled(is_design_mode and is_btratio_on)
        self.edit_cbvalue.setEnabled(is_design_mode and is_cbvalue_on)
        
        self.edit_pdtratio.setEnabled(is_pdtratio_on)
        
        # Economic fields
        self.edit_voyages.setEnabled(is_econom_on)
        self.edit_seadays.setEnabled(is_econom_on)
        self.edit_interest.setEnabled(is_econom_on)
        self.edit_repay.setEnabled(is_econom_on)

        # Fuel vs Nuclear Fields
        self.label_fuel.setVisible(is_econom_on and not is_nuclear)
        self.edit_fuel.setVisible(is_econom_on and not is_nuclear)
        
        self.label_reactor_cost.setVisible(is_econom_on and is_nuclear)
        self.edit_reactor_cost.setVisible(is_econom_on and is_nuclear)
        self.label_core_life.setVisible(is_econom_on and is_nuclear)
        self.edit_core_life.setVisible(is_econom_on and is_nuclear)
        self.label_decom_cost.setVisible(is_econom_on and is_nuclear)
        self.edit_decom_cost.setVisible(is_econom_on and is_nuclear)
        
        # --- MODIFIED: Range - disabled/infinite for nuclear ---
        if is_nuclear:
            # Switching TO nuclear.
            # We only store the value if the box isn't already "Infinite".
            # This prevents storing 'inf' as the conventional range.
            current_range_text = self.edit_range.text()
            if current_range_text != "Infinite":
                try:
                    # Try to parse the current text as a float
                    self.m_conventional_Range = float(current_range_text)
                except ValueError:
                    # If text is bad (e.g., empty), fallback to the last good model value
                    # which might also be 'inf', so we check
                    if self.m_Range != float('inf'):
                        self.m_conventional_Range = self.m_Range
                    # If self.m_Range is *also* inf, we just keep the default (12000.0)
                    
            self.edit_range.setText("Infinite")
            self.edit_range.setEnabled(False) # Grayed out
        else:
            # Switching AWAY from nuclear.
            self.edit_range.setEnabled(True)
            # Restore the last conventional value
            if self.m_conventional_Range == float('inf'):
                # This could happen if started in nuclear mode, just use default
                self.m_conventional_Range = 12000.0 
            self.edit_range.setText(f"{self.m_conventional_Range:.6g}")
        
        # Save button
        self.btn_save.setEnabled(self.CalculatedOk and not self.Ksaved)

    def on_check_econom(self, checked):
        self.m_Econom = checked
        self._reset_dlg()

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
        """Port of Sub_outvdu"""
        #
        output_lines = []
        
        Stype = self.combo_ship.currentText() #
        Etype = self.combo_engine.currentText() #
        
        if self.m_Append and self.Kcases > 0: #
            self.Kcases += 1
            output_lines.append("\r\n" + "="*40 + "\r\n")
        else:
            self.Kcases = 1 #
            
        output_lines.append(f"Case {self.Kcases:3d}: {Stype} with {Etype} engine") #
        
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
                output_lines.append("  ------- Dimensions:") #
            
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
            
            if opt['ocb']: output_lines.append(f"   CB = {self.C:5.3f}") #
            if opt['odisp']: output_lines.append(f"   Disp. (tonnes) = {int(self.M + 0.5):7d}") #
            
            # --- MODIFIED: TEU Output ---
            if self.design_mode == 2: # If we were in TEU mode
                est_teu = self._estimate_teu_capacity(self.L1, self.B, self.D)
                output_lines.append(f"   Target TEU = {int(self.target_teu)}")
                output_lines.append(f"   Est. Capacity = {int(est_teu)} TEU")
                output_lines.append(f"   Avg. Weight = {self.m_TEU_Avg_Weight:5.2f} t/TEU")
                output_lines.append(f"   -> Target Cargo DW = {self.W:7.0f} tonnes")
            elif self.Kstype == 3 and (opt['ocdw'] or opt['otdw']): # Cargo ship
                est_teu = self._estimate_teu_capacity(self.L1, self.B, self.D)
                output_lines.append(f"   (Est. TEU Capacity = ~{int(est_teu)})")
                
            if opt['ocdw']: output_lines.append(f"   Cargo DW(tonnes) = {self.W1:7.0f}") #
            if opt['otdw']: output_lines.append(f"   Total DW(tonnes) = {self.W5:7.0f}") #
            if opt['opdt']: output_lines.append(f"   Prop.dia./T = {self.Pdt:7.2f}") #
            if opt['ospeed']: output_lines.append(f"   Speed (knots) = {self.V:7.2f}") #
            
            # --- MODIFIED: Show 'Infinite' for nuclear range ---
            if self.Ketype == 4: # Nuclear
                 if opt['orange']: output_lines.append("   Range(N.M.) = Infinite")
            else:
                if opt['orange']: output_lines.append(f"   Range(N.M.) = {self.R:8.1f}") #
            
            if opt['oerpm']: output_lines.append(f"   Engine RPM = {self.N1:6.1f}") #
            if opt['oprpm']: output_lines.append(f"   Propeller RPM = {self.N2:6.1f}") #
            if opt['ospower']: output_lines.append(f"   Service power = {int(self.P1 + 0.5):6d} BHP / {int(0.7457 * self.P1 + 0.5):6d} KW") #
            if opt['oipower']: output_lines.append(f"   Installed power = {int(self.P2 + 0.5):6d} BHP / {int(0.7457 * self.P2 + 0.5):6d} KW") #
            
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

            if opt['osmass']: output_lines.append(f"   Steel mass(tonnes) = {int(self.M1 + 0.5):5d}") #
            if opt['oomass']: output_lines.append(f"   Outfit mass(tonnes) = {int(self.M2 + 0.5):5d}") #
            if opt['ommass']: output_lines.append(f"   Machy mass(tonnes) = {int(self.M3 + 0.5):5d}") #
            if opt['ofbd']: output_lines.append(f"   Freeboard(m) = {self.F5:5.2f}") #
            if opt['oagm']: output_lines.append(f"   Approx. GM(m) = {self.G6:5.1f}") #
            
            if self.m_Econom and ob2:
                output_lines.append("  ------- Economic analysis:") #
                if opt['ovyear']: output_lines.append(f"   Voyages/year = {self.V7:6.3f}") #
                if opt['osdyear']: output_lines.append(f"   Sea days/year = {self.D1:6.2f}") #
                
                # --- MODIFIED: Economic Output (v2, $/kW) ---
                if self.Ketype == 4: # Nuclear
                    if opt['ofcost']: 
                        # Show the calculation: $/kW * kW -> M$
                        installed_power_kw = self.P2 * 0.7457
                        total_reactor_cost_M = (self.m_Reactor_Cost_per_kW * installed_power_kw) / 1.0e6
                        output_lines.append(f"   Reactor Cost Rate = {self.m_Reactor_Cost_per_kW:,.2f} ($/kW)")
                        output_lines.append(f"   @ {installed_power_kw:,.0f} kW (Installed)")
                        output_lines.append(f"   -> Reactor CAPEX = {total_reactor_cost_M:6.2f} (M$)")
                    
                    if opt['oirate']: output_lines.append(f"   Core Life (years) = {self.m_Core_Life:3.0f}")
                else: # Fossil
                    if opt['ofcost']: output_lines.append(f"   Fuel cost/tonne = {self.F8:6.2f}") #
                
                if opt['oirate']: output_lines.append(f"   Interest rate (%%) = {self.I:6.2f}") #
                if opt['oreyear']: output_lines.append(f"   Repayment years = {self.N:3d}") #
                if opt['obcost']: output_lines.append(f"   Build cost = {self.S:5.2f}(M)") #
                if opt['oacc']: output_lines.append(f"   Annual capital charges = {self.H1:5.2f}") #
                
                if self.Ketype == 4: # Nuclear
                    if opt['oafc']: output_lines.append(f"   Annual Core/Decom Cost = {self.H7:5.2f}") #
                else: # Fossil
                    if opt['oafc']: output_lines.append(f"   Annual fuel costs = {self.H7:5.2f}") #
                
                if opt['orfr']:
                    if self.design_mode == 2: # TEU
                        output_lines.append(f"   Required rate = {self.Rf * self.m_TEU_Avg_Weight:5.2f} ($/TEU)")
                    else: # Cargo
                        output_lines.append(f"   Required freight rate = {self.Rf:5.2f} ($/tonne)") #
        
        else:
             output_lines.append("  --- No output is selected!") #
             
        output_lines.append("------- End of output results.") #
        
        formatted_output = "\r\n".join(output_lines)
        
        if self.m_Append and self.Kcases > 1: #
            self.m_Results += "\r\n" + formatted_output
        else:
            self.m_Results = formatted_output #
            
        self.text_results.setText(self.m_Results)
        # Move scroll to the end
        self.text_results.verticalScrollBar().setValue(self.text_results.verticalScrollBar().maximum())
            
        return True