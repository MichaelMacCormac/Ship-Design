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
    "Fuel escalation (%/yr)":   "Fuel Price Escalation (%/yr)",
    "Carbon escalation (%/yr)": "Carbon Tax Escalation (%/yr)",
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
    "GMmin(m)":              "Minimum Fluid GM (m)",
    "WindHeel(deg)":         "Steady Wind Heel (deg)",
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


from ship_config import (
    FuelConfig, DEFAULT_FUEL_PRICE, ShipConfig, ResistanceMethodConfig, EmpiricalBasisConfig,
)
from ship_solver import ShipDesignSolver
from economics import PricePath


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

class PricePathDialog(QDialog):
    """
    Popup to set how the fuel price and carbon tax move over the ship's life.

    Each price is a path relative to its base value (the main Fuel price and
    Carbon tax fields): flat, a constant %/yr escalation, or calendar-year
    keyframes in % of base. On accept, result_fuel / result_carbon hold the
    PricePath objects and result_year the delivery year.
    """
    MODE_LABELS = {"flat": "Flat", "escalation": "Escalation (%/yr)", "keyframes": "Keyframes (% of base)"}

    def __init__(self, fuel_path, carbon_path, delivery_year, ship_life, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fuel & Carbon Price Paths")
        self.resize(720, 620)
        self.ship_life = max(int(ship_life), 1)
        self.result_fuel = fuel_path
        self.result_carbon = carbon_path
        self.result_year = int(delivery_year)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Paths scale the base Fuel price and Carbon tax entered on the main form.\n"
            "Escalation compounds from the delivery year; keyframes are calendar years,\n"
            "interpolated linearly and held flat before the first / after the last."
        ))

        top = QHBoxLayout()
        top.addWidget(QLabel("Delivery year (operating year 1):"))
        self.edit_year = QLineEdit(str(int(delivery_year)))
        self.edit_year.setFixedWidth(70)
        top.addWidget(self.edit_year)
        top.addWidget(QLabel(f"Ship life: {self.ship_life} years"))
        top.addStretch()
        layout.addLayout(top)

        groups = QHBoxLayout()
        self.fuel_ui = self._build_group("Fuel price", fuel_path)
        self.carbon_ui = self._build_group("Carbon tax", carbon_path)
        groups.addWidget(self.fuel_ui["box"])
        groups.addWidget(self.carbon_ui["box"])
        layout.addLayout(groups)

        self.canvas = None
        if FigureCanvas is not None:
            self.figure = Figure(figsize=(6, 2.4))
            self.canvas = FigureCanvas(self.figure)
            layout.addWidget(self.canvas)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Apply")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        self.edit_year.textChanged.connect(self._refresh_preview)
        for ui in (self.fuel_ui, self.carbon_ui):
            self._on_mode_changed(ui)
        self._refresh_preview()

    def _build_group(self, title, path):
        box = QGroupBox(title)
        grid = QGridLayout(box)
        combo = QComboBox()
        for mode in PricePath.MODES:
            combo.addItem(self.MODE_LABELS[mode], mode)
        combo.setCurrentIndex(PricePath.MODES.index(path.mode) if path.mode in PricePath.MODES else 0)
        grid.addWidget(QLabel("Mode:"), 0, 0)
        grid.addWidget(combo, 0, 1)

        label_esc = QLabel("Escalation (%/yr):")
        edit_esc = QLineEdit(f"{path.escalation_pct:g}")
        grid.addWidget(label_esc, 1, 0)
        grid.addWidget(edit_esc, 1, 1)

        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Year", "% of base"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for year, pct in path.keyframes:
            self._add_keyframe(table, f"{int(year)}", f"{pct:g}")
        grid.addWidget(table, 2, 0, 1, 2)

        row_btns = QHBoxLayout()
        btn_add = QPushButton("Add Year")
        btn_del = QPushButton("Remove Year")
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_del)
        row_btns.addStretch()
        grid.addLayout(row_btns, 3, 0, 1, 2)

        ui = {"box": box, "combo": combo, "label_esc": label_esc, "edit_esc": edit_esc,
              "table": table, "btn_add": btn_add, "btn_del": btn_del}
        combo.currentIndexChanged.connect(lambda _i, u=ui: self._on_mode_changed(u))
        edit_esc.textChanged.connect(self._refresh_preview)
        table.itemChanged.connect(self._refresh_preview)
        btn_add.clicked.connect(lambda _c=False, u=ui: self._on_add_keyframe(u))
        btn_del.clicked.connect(lambda _c=False, u=ui: self._on_remove_keyframe(u))
        return ui

    def _add_keyframe(self, table, year, pct):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(year))
        table.setItem(row, 1, QTableWidgetItem(pct))

    def _delivery_year(self):
        try:
            return int(float(self.edit_year.text()))
        except ValueError:
            return self.result_year

    def _on_add_keyframe(self, ui):
        table = ui["table"]
        last = self._delivery_year() - 5
        if table.rowCount() and table.item(table.rowCount() - 1, 0):
            try:
                last = int(float(table.item(table.rowCount() - 1, 0).text()))
            except ValueError:
                pass
        self._add_keyframe(table, str(last + 5), "100")
        self._refresh_preview()

    def _on_remove_keyframe(self, ui):
        row = ui["table"].currentRow()
        if row >= 0:
            ui["table"].removeRow(row)
            self._refresh_preview()

    def _on_mode_changed(self, ui):
        mode = ui["combo"].currentData()
        ui["label_esc"].setVisible(mode == "escalation")
        ui["edit_esc"].setVisible(mode == "escalation")
        for key in ("table", "btn_add", "btn_del"):
            ui[key].setVisible(mode == "keyframes")
        if mode == "keyframes" and ui["table"].rowCount() == 0:
            # Seed a flat start/end pair so the user edits rather than types.
            year = self._delivery_year()
            ui["table"].blockSignals(True)
            self._add_keyframe(ui["table"], str(year), "100")
            self._add_keyframe(ui["table"], str(year + self.ship_life - 1), "100")
            ui["table"].blockSignals(False)
        self._refresh_preview()

    def _read_path(self, ui):
        """Build a PricePath from one group's widgets; raises ValueError."""
        mode = ui["combo"].currentData()
        if mode == "escalation":
            path = PricePath("escalation", escalation_pct=float(ui["edit_esc"].text()))
        elif mode == "keyframes":
            frames = []
            table = ui["table"]
            for r in range(table.rowCount()):
                cells = [table.item(r, c).text().strip() if table.item(r, c) else "" for c in (0, 1)]
                if not any(cells):
                    continue
                frames.append((int(float(cells[0])), float(cells[1])))
            path = PricePath("keyframes", keyframes=tuple(frames))
        else:
            path = PricePath()
        path.validate()
        return path

    def _refresh_preview(self, *_):
        if self.canvas is None:
            return
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        year = self._delivery_year()
        years = [year + i for i in range(self.ship_life)]
        for name, ui in (("Fuel price", self.fuel_ui), ("Carbon tax", self.carbon_ui)):
            try:
                idx = self._read_path(ui).index(year, self.ship_life) * 100.0
                ax.plot(years, idx, marker=".", label=name)
            except (ValueError, TypeError, AttributeError):
                ax.plot([], [], label=f"{name} (invalid)")
        ax.set_ylabel(mpl_safe("% of base"))
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=8)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def accept(self):
        try:
            year = int(float(self.edit_year.text()))
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Delivery year must be a whole number.")
            return
        for name, ui in (("Fuel price", self.fuel_ui), ("Carbon tax", self.carbon_ui)):
            try:
                path = self._read_path(ui)
            except (ValueError, TypeError, AttributeError) as e:
                QMessageBox.critical(self, "Input Error", f"{name} path is invalid.\n{e}")
                return
            if ui is self.fuel_ui:
                self.result_fuel = path
            else:
                self.result_carbon = path
        self.result_year = year
        super().accept()

class ShipDesViewWidget(QWidget, ShipDesignSolver):
    """
    Replaces CShipDesView.
    The main form: builds the UI, copies widget values onto the
    ShipDesignSolver inputs, runs solve() and reports the results.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        ShipDesignSolver.__init__(self)

        self.graph_window = None # Holds reference to graph window
        self.Savefile = "SDout.txt" #
        self.MdfEnable = [False] * 10 #;]
        from dialog_outopt import OutoptDialog
        self.outopt_data = OutoptDialog().get_data() # Get defaults
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
        self.edit_ship_life = QLineEdit()
        self.edit_ship_life.setToolTip(
            "Operating years for the cash flow. Cargo is carried and OPEX paid for this\n"
            "many years; loan payments still run for the full repayment term.")
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

        # --- Propulsion: single vs twin screw ---
        prop_group = QGroupBox("Propulsion")
        prop_layout = QGridLayout()
        self.combo_props = QComboBox()
        self.combo_props.addItem("Single screw", 1)
        self.combo_props.addItem("Twin screw", 2)
        self.combo_props.setToolTip(
            "Twin screw: one engine per shaft, Holtrop & Mennen (1984) twin-screw\n"
            "wake, thrust deduction and relative rotative efficiency, twin appendages\n"
            "and an extra shaft line.")
        self.combo_props.currentIndexChanged.connect(self._reset_dlg)
        self.edit_twin_app = QLineEdit(f"{self.m_TwinAppAreaPct:g}")
        self.edit_twin_app.setToolTip("Twin appendage wetted area (shaft brackets, exposed shafts,\n"
                                      "twin rudders) as % of hull wetted surface. Placeholder - edit.")
        self.edit_twin_k2 = QLineEdit(f"{self.m_TwinK2:g}")
        self.edit_twin_k2.setToolTip("Equivalent appendage form factor (1+k2); Holtrop 1982 gives\n"
                                     "2.8 for twin-screw rudders, 3.0 for shaft brackets.")
        self.edit_shaft_mass = QLineEdit(f"{self.m_ShaftMassPerKW:g}")
        self.edit_shaft_mass.setToolTip("Mass of each additional shaft line per kW it carries. Placeholder - edit.")
        self.edit_shaft_cost = QLineEdit(f"{self.m_ShaftCostPerKW:g}")
        self.edit_shaft_cost.setToolTip("Cost of each additional shaft line per kW it carries. Placeholder - edit.")
        self.btn_compare_props = QPushButton("Compare single vs twin")
        self.btn_compare_props.clicked.connect(self.on_compare_props)
        prop_layout.addWidget(QLabel("Propellers:"), 0, 0)
        prop_layout.addWidget(self.combo_props, 0, 1)
        prop_layout.addWidget(self.btn_compare_props, 0, 2, 1, 2)
        prop_layout.addWidget(QLabel("Twin app. area (% S):"), 1, 0)
        prop_layout.addWidget(self.edit_twin_app, 1, 1)
        prop_layout.addWidget(QLabel("Twin app. (1+k2):"), 1, 2)
        prop_layout.addWidget(self.edit_twin_k2, 1, 3)
        prop_layout.addWidget(QLabel("Extra shaft (kg/kW):"), 2, 0)
        prop_layout.addWidget(self.edit_shaft_mass, 2, 1)
        prop_layout.addWidget(QLabel("Extra shaft ($/kW):"), 2, 2)
        prop_layout.addWidget(self.edit_shaft_cost, 2, 3)
        self.check_auto_rpm = QCheckBox("Auto-adjust propeller RPM if pitch out of range")
        self.check_auto_rpm.setToolTip(
            "Off (default): original behaviour - a propeller pitch outside 0.5-1.4 during sizing\n"
            "fails the design. On: the solver's existing RPM correction (x1.05 / x0.95, up to 15\n"
            "tries) is applied inside the sizing loop. Designs that solve with it off are unchanged.")
        prop_layout.addWidget(self.check_auto_rpm, 3, 0, 1, 4)
        prop_group.setLayout(prop_layout)
        left_col.addWidget(prop_group)

        # --- Stability checks ---
        stab_group = QGroupBox("Stability")
        stab_layout = QGridLayout()
        self.edit_gm_req = QLineEdit(f"{self.m_GMRequired:g}")
        self.edit_gm_req.setToolTip("Minimum fluid GM in departure and arrival (IMO IS Code 2008: 0.15 m).")
        self.edit_fsc = QLineEdit(f"{self.m_FSCAllowance:g}")
        self.edit_fsc.setToolTip("Free-surface allowance for below-deck tanks, m (placeholder).\n"
                                 "Deck LH2 tank free surface is computed from the tank layout.")
        self.check_auto_beam = QCheckBox("Widen beam to meet stability")
        self.check_auto_beam.setToolTip("If GM, the IS-2008 checks or the wind heel check fail, re-solve with\n"
                                        "the beam widened 3% per step (up to 30 steps) until they pass.")
        stab_layout.addWidget(QLabel("Required GM (m):"), 0, 0)
        stab_layout.addWidget(self.edit_gm_req, 0, 1)
        stab_layout.addWidget(QLabel("FSC allowance (m):"), 0, 2)
        stab_layout.addWidget(self.edit_fsc, 0, 3)
        stab_layout.addWidget(self.check_auto_beam, 1, 0, 1, 4)
        stab_group.setLayout(stab_layout)
        left_col.addWidget(stab_group)

        # --- Above-deck hydrogen ---
        self.group_deck_h2 = QGroupBox("Above-deck hydrogen (LH2 fuels only)")
        deck_layout = QGridLayout()
        self.check_deck_h2 = QCheckBox("Carry LH2 tanks above deck")
        self.check_deck_h2.setToolTip("Frees hull volume, but the tanks (about 7x the fuel mass) sit high:\n"
                                      "see the Stability block in the results.")
        self.check_deck_h2.toggled.connect(self._reset_dlg)
        self.edit_deck_pct = QLineEdit(f"{self.m_DeckH2Pct:g}")
        self.edit_deck_dia = QLineEdit(f"{self.m_DeckTankDia:g}")
        self.edit_deck_dia.setToolTip("Horizontal cylinder diameter (placeholder).")
        self.edit_deck_support = QLineEdit(f"{self.m_DeckTankSupport:g}")
        self.edit_deck_support.setToolTip("Saddle height of the tank bottom above deck (placeholder).")
        self.edit_deck_usable = QLineEdit(f"{self.m_DeckUsableFrac:g}")
        self.edit_deck_usable.setToolTip("Fraction of Lbp available for deck tanks (placeholder).")
        self.edit_deck_found = QLineEdit(f"{self.m_DeckFoundationPct:g}")
        self.edit_deck_found.setToolTip("Deck structure and tank foundations, % of deck tank + fuel weight\n"
                                        "(placeholder). Added to steel weight and cost.")
        self.edit_deck_tiers = QLineEdit(f"{self.m_DeckTEUTiers:g}")
        self.edit_deck_tiers.setToolTip("Container ships: container tiers lost above each deck slot the tanks\n"
                                        "occupy (placeholder).")
        deck_layout.addWidget(self.check_deck_h2, 0, 0, 1, 2)
        deck_layout.addWidget(QLabel("% of LH2 on deck:"), 0, 2)
        deck_layout.addWidget(self.edit_deck_pct, 0, 3)
        deck_layout.addWidget(QLabel("Tank diameter (m):"), 1, 0)
        deck_layout.addWidget(self.edit_deck_dia, 1, 1)
        deck_layout.addWidget(QLabel("Support height (m):"), 1, 2)
        deck_layout.addWidget(self.edit_deck_support, 1, 3)
        deck_layout.addWidget(QLabel("Usable deck (frac. L):"), 2, 0)
        deck_layout.addWidget(self.edit_deck_usable, 2, 1)
        deck_layout.addWidget(QLabel("Foundations (%):"), 2, 2)
        deck_layout.addWidget(self.edit_deck_found, 2, 3)
        deck_layout.addWidget(QLabel("TEU tiers lost:"), 3, 0)
        deck_layout.addWidget(self.edit_deck_tiers, 3, 1)
        self.group_deck_h2.setLayout(deck_layout)
        left_col.addWidget(self.group_deck_h2)

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
        eco_grid.addWidget(QLabel("Ship life (years):"), 5, 3)
        eco_grid.addWidget(self.edit_ship_life, 5, 4)

        self.btn_export_cashflow = QPushButton("Export Cash Flow CSV")
        self.btn_export_cashflow.setToolTip("Save the year-by-year cash flow behind the last RFR.")
        self.btn_export_cashflow.clicked.connect(self.on_export_cashflow_csv)
        eco_grid.addWidget(self.btn_export_cashflow, 6, 3, 1, 2)

        self.btn_price_paths = QPushButton("Price paths...")
        self.btn_price_paths.setToolTip("Set how the fuel price and carbon tax change over the ship's life.")
        self.btn_price_paths.clicked.connect(self.on_config_price_paths)
        self.label_price_paths = QLabel()
        eco_grid.addWidget(self.btn_price_paths, 6, 0)
        eco_grid.addWidget(self.label_price_paths, 6, 1, 1, 2)
        self._refresh_price_path_label()

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
            "Methane Slip (%)":    ("0", "4", "5"),        # LNG GWP sensitivity (sec 5.5)
            # -- Price paths (replace the current path with pure escalation) --
            "Fuel escalation (%/yr)":   ("-2", "6", "5"),
            "Carbon escalation (%/yr)": ("-2", "6", "5"),
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
            "VolMachinery(m3)", "VolStores(m3)", "VolUtilisation%",
            "GMmin(m)", "WindHeel(deg)"
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
            "VolMachinery(m3)", "VolStores(m3)", "VolUtilisation%",
            "GMmin(m)", "WindHeel(deg)"
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

        self.btn_monte_carlo = QPushButton("Monte Carlo Comparison...")
        self.btn_monte_carlo.setToolTip(
            "Compare two fuels under uncertain prices, carbon tax, finance and capex;\n"
            "win probability, break-even values and drivers.")
        self.btn_monte_carlo.clicked.connect(self.on_open_monte_carlo)
        self.mc_window = None
        comp_layout.addWidget(self.btn_monte_carlo, 6, 0, 1, 2)

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
            self.m_ShipLife = _safe_float(self.edit_ship_life)

            self.m_NumProps = self.combo_props.currentData()
            self.m_TwinAppAreaPct = _safe_float(self.edit_twin_app, default=6.0)
            self.m_TwinK2 = _safe_float(self.edit_twin_k2, default=2.8)
            self.m_ShaftMassPerKW = _safe_float(self.edit_shaft_mass, default=5.0)
            self.m_ShaftCostPerKW = _safe_float(self.edit_shaft_cost, default=150.0)

            self.m_AutoRPM = self.check_auto_rpm.isChecked()
            self.m_GMRequired = _safe_float(self.edit_gm_req, default=0.15)
            self.m_FSCAllowance = _safe_float(self.edit_fsc, default=0.10)
            self.m_AutoBeam = self.check_auto_beam.isChecked()
            self.m_DeckH2 = self.check_deck_h2.isChecked()
            self.m_DeckH2Pct = _safe_float(self.edit_deck_pct, default=100.0)
            self.m_DeckTankDia = _safe_float(self.edit_deck_dia, default=8.0)
            self.m_DeckTankSupport = _safe_float(self.edit_deck_support, default=1.5)
            self.m_DeckUsableFrac = _safe_float(self.edit_deck_usable, default=0.6)
            self.m_DeckFoundationPct = _safe_float(self.edit_deck_found, default=10.0)
            self.m_DeckTEUTiers = _safe_float(self.edit_deck_tiers, default=4.0)

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
            self.ship_name = self.combo_ship.currentText()
            self.engine_name = self.combo_engine.currentText()
            self.m_CarbonTaxOn = self.check_carbon_tax.isChecked()

            # Aux and ESD fields are handed over as raw text; the solver
            # float()s them at use and keeps its existing fallbacks.
            self.m_AuxEnabled = self.check_aux_enable.isChecked()
            self.m_AuxMode = self.combo_aux_mode.currentText()
            self.m_AuxBase = self.edit_aux_base.text()
            self.m_AuxP1 = self.edit_aux_p1.text()
            self.m_AuxP2 = self.edit_aux_p2.text()
            self.m_AuxPrem = self.edit_aux_prem.text()
            self.m_ALS = self.check_als.isChecked()
            self.m_ALSEff = self.edit_als_eff.text()
            self.m_Wind = self.check_wind.isChecked()
            self.m_WindSav = self.edit_wind_sav.text()

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
        self.edit_ship_life.setText(f"{self.m_ShipLife:.6g}")
        self.combo_props.setCurrentIndex(self.combo_props.findData(self.m_NumProps))
        self.edit_twin_app.setText(f"{self.m_TwinAppAreaPct:.6g}")
        self.edit_twin_k2.setText(f"{self.m_TwinK2:.6g}")
        self.edit_shaft_mass.setText(f"{self.m_ShaftMassPerKW:.6g}")
        self.edit_shaft_cost.setText(f"{self.m_ShaftCostPerKW:.6g}")
        self.check_auto_rpm.setChecked(self.m_AutoRPM)
        self.edit_gm_req.setText(f"{self.m_GMRequired:.6g}")
        self.edit_fsc.setText(f"{self.m_FSCAllowance:.6g}")
        self.check_auto_beam.setChecked(self.m_AutoBeam)
        self.check_deck_h2.setChecked(self.m_DeckH2)
        self.edit_deck_pct.setText(f"{self.m_DeckH2Pct:.6g}")
        self.edit_deck_dia.setText(f"{self.m_DeckTankDia:.6g}")
        self.edit_deck_support.setText(f"{self.m_DeckTankSupport:.6g}")
        self.edit_deck_usable.setText(f"{self.m_DeckUsableFrac:.6g}")
        self.edit_deck_found.setText(f"{self.m_DeckFoundationPct:.6g}")
        self.edit_deck_tiers.setText(f"{self.m_DeckTEUTiers:.6g}")

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

    # Qt implementations of the ShipDesignSolver reporting hooks.
    def _warn(self, message):
        QMessageBox.warning(self, "Warning", message)

    def _log(self, message):
        self.text_results.append(message)

    def _focus_field(self, widget_name):
        getattr(self, widget_name).setFocus()

    def _debug_info(self, message, title):
        QMessageBox.information(self, title, message)

    def _debug_stop(self, message):
        QMessageBox.critical(self, "Info. from OnButtonCal in debug mode", message)
        self.dbgmd = False; self.dlg_modify.data['dbgmd'] = False

    def _apply_range_defaults(self, combo, edit_start, edit_end, edit_steps):
        """Helper to auto-fill range fields based on selection."""
        param = combo.currentText()
        if param in self.RANGE_DEFAULTS:
            start, end, steps = self.RANGE_DEFAULTS[param]
            edit_start.setText(start)
            edit_end.setText(end)
            edit_steps.setText(steps)

    def on_calculate(self):
        """Port of OnButtonCal: read the form, run solve(), report."""
        if not self._update_ui_to_data():
            return
        self.btn_save.setEnabled(False)

        ok = self.solve()

        # solve() resolves the TEU target weight and the direct-drive RPM;
        # show them in the form even if the run then failed.
        if self.design_mode == 2:
            self.edit_weight.setText(str(self.W))
            self.edit_error.setText(str(self.m_Error))
        if self.Ketype == 1:
            self.edit_prpm.setText(str(self.m_Prpm))
        if not ok:
            return

        self.text_results.setEnabled(True)
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
            "GMmin(m)", "WindHeel(deg)", "StabilityOK", "DeckTEULost",
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
            'fuel_path': self.m_FuelPricePath,
            'carbon_path': self.m_CarbonPricePath,
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
                    elif self._set_price_path_param(param_name, value):
                        pass
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

                        # ----- Stability (departure/arrival checks) -----
                        row.extend([
                            f"{getattr(self, 'GM_min', float('nan')):.3f}",
                            f"{getattr(self, 'wind_heel_max', float('nan')):.2f}",
                            "YES" if getattr(self, 'stability_ok', False) else "NO",
                            f"{getattr(self, 'deck_teu_lost', 0)}",
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
            
            self.m_FuelPricePath = original_ui_state['fuel_path']
            self.m_CarbonPricePath = original_ui_state['carbon_path']
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
            'fuel_path': self.m_FuelPricePath,
            'carbon_path': self.m_CarbonPricePath,
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
                elif self._set_price_path_param(name, val):
                    pass
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
                elif name == "GMmin(m)":
                    return getattr(self, 'GM_min', np.nan)
                elif name == "WindHeel(deg)":
                    return getattr(self, 'wind_heel_max', np.nan)
                
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

            self.m_FuelPricePath = original_ui_state['fuel_path']
            self.m_CarbonPricePath = original_ui_state['carbon_path']
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
            'fuel_path': self.m_FuelPricePath,
            'carbon_path': self.m_CarbonPricePath,
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
            elif self._set_price_path_param(name, val):
                pass
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
            elif name == "GMmin(m)":
                return getattr(self, 'GM_min', np.nan)
            elif name == "WindHeel(deg)":
                return getattr(self, 'wind_heel_max', np.nan)
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

            self.m_FuelPricePath = original_ui_state['fuel_path']
            self.m_CarbonPricePath = original_ui_state['carbon_path']
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

    def _stability_report_lines(self):
        """Stability block for the results: deck-tank layout, KG build-up,
        per-condition checks and any failures."""
        conds = getattr(self, 'stab_conditions', None)
        if not conds:
            return []
        out = []
        if not self.stability_ok:
            out += ["", "   !!! STABILITY CHECK FAILED !!!"]
            out += [f"   - {f}" for f in self.stability_failures]
        if getattr(self, 'deck_fit_warning', ""):
            out += ["", f"   !!! {self.deck_fit_warning} !!!"]

        if self._deck_frac() > 0:
            out.append("  ------- Above-deck LH2 tanks:")
            out.append(f"   On deck: {self._deck_frac() * 100:.0f}% of LH2, {self.deck_mass:,.0f} t "
                       f"(fuel + tanks), {self.deck_tank_volume:,.0f} m3")
            out.append(f"   {self.deck_tank_rows} row(s) of {self.m_DeckTankDia:g} m cylinders, "
                       f"{self.deck_block_len:.1f} m long ({self.deck_len_avail:.1f} m usable): "
                       f"{'fits' if self.deck_tanks_fit else 'DOES NOT FIT'}")
            out.append(f"   Deck foundations = {self.M_deck_foundations:,.0f} t")
            if self.deck_teu_lost:
                out.append(f"   Deck TEU slots lost = {self.deck_teu_lost:,}")
        elif self.m_DeckH2:
            out.append("   (Above-deck LH2 is on but the engine is not a hydrogen fuel: ignored.)")

        out.append("  ------- Stability (departure KG build-up):")
        out.append(f"   {'Item':26s}{'Mass (t)':>11s}{'KG (m)':>9s}")
        for name, mass, kg in self.stab_groups:
            out.append(f"   {name:26s}{mass:11,.0f}{kg:9.2f}")
        for name, c in conds.items():
            out.append(f"   {name}: Disp {c['disp']:,.0f} t  T {c['T']:.2f} m")
            out.append(f"     KB {c['KB']:.2f}  BM {c['BM']:.2f}  KG {c['KG']:.2f}  FSC {c['FSC']:.2f}"
                       f"  GM {c['GM']:.2f} m")
            gz_at = lambda v: "n/a" if math.isnan(v) else f"{v:.2f} m"
            out.append(f"     Deck-edge immersion {c['phi_de']:.1f} deg (GZ {c['gz_de']:.2f} m); "
                       f"GZ 10 deg {gz_at(c['gz10'])}, 20 deg {gz_at(c['gz20'])}; "
                       f"area 0-{c['area_limit']:.0f} deg {c['area_to']:.3f} m.rad")
            out.append(f"     Wind heel {c['wind_heel']:.1f} deg (lever {c['wind_lever']:.3f} m, "
                       f"area {c['wind_area']:,.0f} m2)")
            for label, (passed, value) in c['criteria'].items():
                flag = "PASS" if passed else ("FAIL" if passed is False else "n/a ")
                out.append(f"     [{flag}] {label}: {value}")
        if getattr(self, 'auto_beam_steps', 0):
            out.append(f"   Auto-beam: B widened {self.B_original:.2f} -> {self.B:.2f} m "
                       f"in {self.auto_beam_steps} step(s)")
        out.append("   (Wall-sided GZ is valid only to deck-edge immersion; criteria beyond it are n/a.)")
        return out

    def on_compare_props(self):
        """Solve the current form with single and twin screw and show both."""
        if not self._update_ui_to_data():
            return
        snapshot = self.input_snapshot()
        runs = {}
        for n in (1, 2):
            s = ShipDesignSolver().set_inputs(**snapshot)
            s.m_NumProps = n
            # Like the sweeps: let the solver auto-correct RPM rather than
            # stopping on a transient pitch/speed range error.
            s.ignspd = s.ignpth = True
            s.dbgmd = False
            runs[n] = (s, s.solve())

        failed = [f"{'Single' if n == 1 else 'Twin'} screw: " + ("; ".join(s.solver_errors) or "no solution")
                  for n, (s, ok) in runs.items() if not ok]
        if failed:
            self._show_error("Comparison could not be completed.\n\n" + "\n".join(failed), "Single vs twin")
            if len(failed) == 2:
                return

        def val(s, ok, fn):
            try:
                return fn(s) if ok else float("nan")
            except (AttributeError, ZeroDivisionError):
                return float("nan")

        econ = self.m_Econom
        rows = [
            ("Length Lbp (m)", lambda s: s.L1, "{:,.2f}"),
            ("Breadth B (m)", lambda s: s.B, "{:,.2f}"),
            ("Draught T (m)", lambda s: s.T, "{:,.2f}"),
            ("Effective power Pe (kW)", lambda s: s.P * 0.7457, "{:,.0f}"),
            ("Propeller diameter (m)", lambda s: s.prop_D, "{:,.2f}"),
            ("Wake fraction w", lambda s: s.prop_w, "{:.3f}"),
            ("Thrust deduction t", lambda s: s.prop_t, "{:.3f}"),
            ("Hull efficiency nH", lambda s: s.prop_eta_h, "{:.3f}"),
            ("Open-water eff. nO", lambda s: s.prop_eta_o, "{:.3f}"),
            ("Rel. rotative eff. nR", lambda s: s.prop_eta_r, "{:.3f}"),
            ("QPC", lambda s: s.Q, "{:.3f}"),
            ("Service power (kW)", lambda s: s.P1 * 0.7457, "{:,.0f}"),
            ("Installed power (kW)", lambda s: s.P2 * 0.7457, "{:,.0f}"),
            ("Machinery mass (t)", lambda s: s.M3, "{:,.0f}"),
            ("Lightship (t)", lambda s: (s.M1 + s.M2 + s.M3) * 1.02, "{:,.0f}"),
            ("Cargo deadweight (t)", lambda s: s.W1, "{:,.0f}"),
        ]
        if econ:
            rows += [
                ("Build cost (M$)", lambda s: s.S, "{:,.2f}"),
                ("Machinery capex (M$)", lambda s: s.cost_machinery_M, "{:,.2f}"),
                ("RFR ($/t)", lambda s: s.Rf, "{:,.2f}"),
            ]

        (s1, ok1), (s2, ok2) = runs[1], runs[2]
        lines = [f"{self.combo_ship.currentText()} with {self.combo_engine.currentText()}",
                 f"{self.combo_resistance_method.currentText()}", "",
                 f"{'':26s}{'Single':>12s}{'Twin':>12s}{'Twin-Single':>13s}{'%':>8s}"]
        for label, fn, fmt in rows:
            a, b = val(s1, ok1, fn), val(s2, ok2, fn)
            d = b - a
            pct = (100.0 * d / a) if a not in (0.0,) and math.isfinite(a) and math.isfinite(b) else float("nan")
            cell = lambda v: fmt.format(v) if math.isfinite(v) else "-"
            lines.append(f"{label:26s}{cell(a):>12s}{cell(b):>12s}{cell(d):>13s}"
                         f"{(f'{pct:+.1f}' if math.isfinite(pct) else '-'):>8s}")
        lines += ["", "Single screw: legacy wake/thrust formulas, nR = 1.",
                  "Twin screw: Holtrop & Mennen (1984) twin-screw w, t, nR; one engine per",
                  "shaft; twin appendages and shaft-line allowances from the Propulsion inputs."]

        dlg = QDialog(self)
        dlg.setWindowTitle("Single vs Twin Screw")
        dlg.resize(640, 560)
        lay = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFontFamily("Courier New")
        text.setText("\n".join(lines))
        lay.addWidget(text)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn, alignment=Qt.AlignRight)
        self.last_props_comparison = "\n".join(lines)
        dlg.exec()

    def on_open_monte_carlo(self):
        """Opens (or raises) the Monte Carlo fuel comparison window."""
        from monte_carlo_window import MonteCarloWindow
        if self.mc_window is None:
            self.mc_window = MonteCarloWindow(self)
        self.mc_window.show()
        self.mc_window.raise_()
        self.mc_window.activateWindow()

    def on_config_price_paths(self):
        """Opens the fuel / carbon price path dialog."""
        try:
            ship_life = int(float(self.edit_ship_life.text()))
        except ValueError:
            ship_life = int(self.m_ShipLife)
        dlg = PricePathDialog(self.m_FuelPricePath, self.m_CarbonPricePath,
                              self.m_DeliveryYear, ship_life, self)
        if dlg.exec():
            self.m_FuelPricePath = dlg.result_fuel
            self.m_CarbonPricePath = dlg.result_carbon
            self.m_DeliveryYear = dlg.result_year
            self._refresh_price_path_label()

    def _refresh_price_path_label(self):
        self.label_price_paths.setText(
            f"Fuel: {self.m_FuelPricePath.describe()}  |  Carbon: {self.m_CarbonPricePath.describe()}"
            f"  (from {self.m_DeliveryYear})")

    def _set_price_path_param(self, name, val):
        """Sweep hook for the escalation parameters; True if `name` was one."""
        if name == "Fuel escalation (%/yr)":
            self.m_FuelPricePath = PricePath("escalation", escalation_pct=float(val))
        elif name == "Carbon escalation (%/yr)":
            self.m_CarbonPricePath = PricePath("escalation", escalation_pct=float(val))
            self.check_carbon_tax.setChecked(True)
        else:
            return False
        return True

    def on_export_cashflow_csv(self):
        """Exports the year-by-year cash flow of the last calculation."""
        cf = getattr(self, 'cash_flow', None)
        if not self.CalculatedOk or cf is None:
            self._show_error("Run a calculation with economics enabled first.")
            return

        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Cash Flow", "cash_flow.csv", "CSV Files (*.csv);;All Files (*)"
        )
        if not fileName:
            return

        try:
            with open(fileName, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([f"{self.combo_ship.currentText()} with {self.combo_engine.currentText()}"])
                writer.writerow(["Loan term (yrs)", self.N, "Ship life (yrs)", self.ship_life,
                                 "Discount rate (%)", self.I])
                writer.writerow(["PV net costs ($)", f"{cf.pv_costs:.2f}", "PV cargo (t)", f"{cf.pv_cargo:.2f}",
                                 "RFR ($/t)", f"{cf.rfr:.4f}"])
                writer.writerow(["Delivery year", self.m_DeliveryYear,
                                 "Fuel price path", self.m_FuelPricePath.describe(),
                                 "Carbon price path", self.m_CarbonPricePath.describe()])
                writer.writerow([])
                rows = cf.to_rows()
                writer.writerow(rows[0])
                for row in rows[1:]:
                    # Year columns as integers; money and cargo to the cent/kg;
                    # discount factor (last column) to 6 dp.
                    writer.writerow(row[:2] + [f"{v:.2f}" for v in row[2:-1]] + [f"{row[-1]:.6f}"])

            QMessageBox.information(self, "Export Complete", f"Successfully saved cash flow to:\n{fileName}")

        except Exception as e:
            self._show_error(f"Failed to write CSV file: {e}")

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
        self.edit_ship_life.setEnabled(is_econom_on)
        is_twin = self.combo_props.currentData() == 2
        for w in (self.edit_twin_app, self.edit_twin_k2, self.edit_shaft_mass):
            w.setEnabled(is_twin)
        self.edit_shaft_cost.setEnabled(is_twin and is_econom_on)

        is_h2 = "Hydrogen" in self.combo_engine.currentText()
        self.group_deck_h2.setEnabled(is_h2)
        deck_on = is_h2 and self.check_deck_h2.isChecked()
        for w in (self.edit_deck_pct, self.edit_deck_dia, self.edit_deck_support,
                  self.edit_deck_usable, self.edit_deck_found):
            w.setEnabled(deck_on)
        self.edit_deck_tiers.setEnabled(deck_on and ship_id == 4)
        self.btn_export_cashflow.setEnabled(
            is_econom_on and self.CalculatedOk and getattr(self, 'cash_flow', None) is not None)

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

            if getattr(self, 'n_props', None):
                # The factors the propeller solve actually used (single screw:
                # legacy wake/thrust formulas, etaR = 1; twin: Holtrop 1984).
                output_lines.append(f"  ------- Propulsion ({'twin' if self.n_props == 2 else 'single'} screw):")
                output_lines.append(f"   Propellers = {self.n_props}  D = {self.prop_D:.2f} m  P/D = {self.prop_PD:.3f}")
                if getattr(self, 'rpm_adjusted', False):
                    output_lines.append(f"   Auto-RPM: propeller RPM {self.rpm_initial:.1f} -> {self.rpm_final:.1f}"
                                        " to keep pitch in range")
                output_lines.append(f"   Thrust per propeller = {self.prop_thrust_each_kN:,.1f} kN")
                output_lines.append(f"   Wake w = {self.prop_w:.3f}  Thrust ded. t = {self.prop_t:.3f}")
                output_lines.append(f"   nH = {self.prop_eta_h:.3f}  nO = {self.prop_eta_o:.3f}  nR = {self.prop_eta_r:.3f}"
                                    f"  QPC = {self.Q:.3f}")
                if self.n_props == 2:
                    if getattr(self, 'twin_app_extra_kN', 0.0) > 0:
                        output_lines.append(f"   Twin appendage extra drag = {self.twin_app_extra_kN:,.1f} kN")
                    output_lines.append(f"   Extra shaft line: {getattr(self, 'M_shafting', 0.0):,.1f} t")

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
            output_lines.extend(self._stability_report_lines())

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

                    cf = getattr(self, 'cash_flow', None)
                    if cf is not None:
                        output_lines.append(f"   Ship life (years) = {self.ship_life:3d}")
                        output_lines.append(f"   PV of net costs = {cf.pv_costs / 1.0e6:,.2f} (M$)")
                        output_lines.append(f"   PV of cargo = {cf.pv_cargo:,.0f} (t)")
                        if not (self.m_FuelPricePath.is_flat() and self.m_CarbonPricePath.is_flat()):
                            output_lines.append(f"   Delivery year = {self.m_DeliveryYear}")
                            output_lines.append(f"   Fuel price path = {self.m_FuelPricePath.describe()}")
                            output_lines.append(f"   Carbon price path = {self.m_CarbonPricePath.describe()}")
                            if not math.isnan(cf.levelised_fuel_price):
                                output_lines.append(f"   Levelised fuel price = {cf.levelised_fuel_price:,.2f} ($/t)")
                            if not math.isnan(cf.levelised_carbon_price):
                                output_lines.append(f"   Levelised carbon tax = {cf.levelised_carbon_price:,.2f} ($/tCO2e)")
                        if self.ship_life != self.N or not (self.m_FuelPricePath.is_flat()
                                                            and self.m_CarbonPricePath.is_flat()):
                            annualised = self.Rf_annualised * conv_factor
                            output_lines.append(f"       (Single-year annualised RFR = {annualised:5.2f} {unit_label})")

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