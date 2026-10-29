"""Monte Carlo fuel comparison window.

A non-modal window, opened from the main form's comparison group, that
configures and runs monte_carlo.run_comparison() on the current design and
plots the results: RFR distributions, the RFR gap, a break-even map, the
break-even value distribution and a tornado of the drivers.
"""
import csv
import math

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

try:
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
        NavigationToolbar2QT as NavigationToolbar,
    )
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch
except ImportError:
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None

import monte_carlo as mc
from ship_config import FuelConfig

# Fuel A / fuel B identity colours (reference categorical slots 1 and 2),
# used for every plot so A is always blue and B always orange.
COLOR_A = "#2a78d6"
COLOR_B = "#eb6834"
INK_MUTED = "#52514e"
GRID = "#d9d8d4"


def _mpl_safe(s):
    """Escape '$' so matplotlib does not switch to mathtext."""
    return s.replace("$", r"\$")


class MonteCarloWindow(QWidget):
    COL_USE, COL_INPUT, COL_DIST, COL_P1, COL_P2, COL_P3 = range(6)

    def __init__(self, main_widget):
        super().__init__()
        self.setWindowTitle("Monte Carlo Fuel Comparison")
        self.resize(1250, 860)
        self.main = main_widget
        self.result = None
        self._cancel = False
        self._columns = mc.columns()

        root = QHBoxLayout(self)
        left_panel = QWidget()
        left_panel.setMaximumWidth(560)
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(0, 0, 0, 0)
        root.addWidget(left_panel, 0)
        right = QVBoxLayout()
        root.addLayout(right, 1)

        # --- Fuels & sampling ---------------------------------------------
        setup = QGroupBox("Fuels && sampling")
        form = QGridLayout(setup)
        fuels = list(FuelConfig.DATA.keys())
        self.combo_a = QComboBox(); self.combo_a.addItems(fuels)
        self.combo_b = QComboBox(); self.combo_b.addItems(fuels)
        current = self.main.combo_engine.currentText()
        self.combo_a.setCurrentText(current)
        self.combo_b.setCurrentText("Ammonia (Combustion)" if current != "Ammonia (Combustion)" else "Direct diesel")
        self.edit_n = QLineEdit("2000")
        self.edit_seed = QLineEdit("1")
        self.check_lhs = QCheckBox("Latin hypercube")
        self.check_lhs.setChecked(True)
        self.check_lhs.setToolTip("Stratified sampling: converges faster than plain random sampling.")
        self.edit_corr = QLineEdit("0.5")
        self.edit_corr.setToolTip("Correlation between the fuel A and fuel B price draws (-1 to 1).")
        # Propeller count per side; defaults to the main form's setting so a
        # plain fuel comparison keeps the hull/propulsion the user designed.
        self.combo_props_a = QComboBox(); self.combo_props_b = QComboBox()
        form_props = getattr(self.main, "m_NumProps", 1)
        for combo in (self.combo_props_a, self.combo_props_b):
            combo.addItem("Single screw", 1)
            combo.addItem("Twin screw", 2)
            combo.setCurrentIndex(combo.findData(form_props))
        form.addWidget(QLabel("Option A:"), 0, 0); form.addWidget(self.combo_a, 0, 1, 1, 2)
        form.addWidget(self.combo_props_a, 0, 3)
        form.addWidget(QLabel("Option B:"), 1, 0); form.addWidget(self.combo_b, 1, 1, 1, 2)
        form.addWidget(self.combo_props_b, 1, 3)
        form.addWidget(QLabel("Samples:"), 2, 0); form.addWidget(self.edit_n, 2, 1)
        form.addWidget(QLabel("Seed:"), 2, 2); form.addWidget(self.edit_seed, 2, 3)
        form.addWidget(self.check_lhs, 3, 0, 1, 2)
        form.addWidget(QLabel("Price corr. A-B:"), 3, 2); form.addWidget(self.edit_corr, 3, 3)
        left.addWidget(setup)

        # --- Uncertain inputs table -----------------------------------------
        unc = QGroupBox("Uncertain inputs (defaults are placeholders - edit them)")
        unc_layout = QVBoxLayout(unc)
        self.table = QTableWidget(len(self._columns), 6)
        self.table.setHorizontalHeaderLabels(["Use", "Input", "Distribution", "P1", "P2", "P3"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_INPUT, QHeaderView.Stretch)
        for c in (self.COL_USE, self.COL_DIST, self.COL_P1, self.COL_P2, self.COL_P3):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumWidth(480)
        unc_layout.addWidget(self.table)
        hint = QLabel("P1/P2/P3: triangular = low / mode / high, uniform = low / high,\n"
                      "normal & lognormal = mean / SD, fixed = value.")
        hint.setStyleSheet(f"color: {INK_MUTED};")
        unc_layout.addWidget(hint)
        btn_defaults = QPushButton("Reset to defaults")
        btn_defaults.clicked.connect(self._load_defaults)
        unc_layout.addWidget(btn_defaults, alignment=Qt.AlignLeft)
        left.addWidget(unc, 1)

        # --- Break-even & map ------------------------------------------------
        be = QGroupBox("Break-even && map")
        be_form = QGridLayout(be)
        self.combo_be = QComboBox()
        self.edit_be_lo = QLineEdit()
        self.edit_be_hi = QLineEdit()
        self.combo_map_x = QComboBox()
        self.combo_map_y = QComboBox()
        be_form.addWidget(QLabel("Break-even on:"), 0, 0); be_form.addWidget(self.combo_be, 0, 1, 1, 3)
        be_form.addWidget(QLabel("Search from:"), 1, 0); be_form.addWidget(self.edit_be_lo, 1, 1)
        be_form.addWidget(QLabel("to:"), 1, 2); be_form.addWidget(self.edit_be_hi, 1, 3)
        be_form.addWidget(QLabel("Map X:"), 2, 0); be_form.addWidget(self.combo_map_x, 2, 1, 1, 3)
        be_form.addWidget(QLabel("Map Y:"), 3, 0); be_form.addWidget(self.combo_map_y, 3, 1, 1, 3)
        left.addWidget(be)

        # --- Run controls ---------------------------------------------------
        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run Monte Carlo")
        self.btn_run.setStyleSheet("font-weight: bold; color: darkblue;")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_export = QPushButton("Export Samples CSV")
        self.btn_export.setEnabled(False)
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_cancel)
        run_row.addWidget(self.btn_export)
        left.addLayout(run_row)
        self.progress = QProgressBar()
        left.addWidget(self.progress)

        # --- Results ----------------------------------------------------------
        self.text_summary = QTextEdit()
        self.text_summary.setReadOnly(True)
        self.text_summary.setFontFamily("Courier New")
        self.text_summary.setMinimumHeight(220)
        self.text_summary.setText("Configure the inputs and press Run Monte Carlo.")
        right.addWidget(self.text_summary, 0)

        self.tabs = QTabWidget()
        self.figures = {}
        for key, title in (("rfr", "RFR distributions"), ("gap", "Gap B - A"),
                           ("map", "Break-even map"), ("be", "Break-even value"),
                           ("drivers", "Drivers")):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            if FigureCanvas is not None:
                fig = Figure(figsize=(7, 4.5), layout="constrained")
                canvas = FigureCanvas(fig)
                page_layout.addWidget(NavigationToolbar(canvas, page))
                page_layout.addWidget(canvas)
                self.figures[key] = (fig, canvas)
            else:
                page_layout.addWidget(QLabel("Matplotlib not installed - plots disabled."))
            self.tabs.addTab(page, title)
        right.addWidget(self.tabs, 1)

        # --- Signals ------------------------------------------------------------
        self.combo_a.currentTextChanged.connect(lambda _t: self._on_fuel_changed("A"))
        self.combo_b.currentTextChanged.connect(lambda _t: self._on_fuel_changed("B"))
        self.combo_props_a.currentIndexChanged.connect(lambda _i: self._relabel())
        self.combo_props_b.currentIndexChanged.connect(lambda _i: self._relabel())
        self.combo_be.currentIndexChanged.connect(self._on_breakeven_changed)
        self.combo_map_x.currentIndexChanged.connect(self._redraw_map)
        self.combo_map_y.currentIndexChanged.connect(self._redraw_map)
        self.btn_run.clicked.connect(self.on_run)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_export.clicked.connect(self.on_export_csv)

        self._load_defaults()

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    def _base_inputs(self, quiet=False):
        """Snapshot of the main form's inputs (None if the form is invalid)."""
        if quiet:
            return self.main.input_snapshot()
        if not self.main._update_ui_to_data():
            return None
        return self.main.input_snapshot()

    def _fuels(self):
        return self.combo_a.currentText(), self.combo_b.currentText()

    def _props(self):
        return self.combo_props_a.currentData(), self.combo_props_b.currentData()

    def _names(self):
        (fa, fb), (pa, pb) = self._fuels(), self._props()
        return mc.option_names(fa, pa, fb, pb)

    def _label(self, col):
        return mc.column_label(col, *self._names())

    def _relabel(self):
        for row, col in enumerate(self._columns):
            self.table.item(row, self.COL_INPUT).setText(self._label(col))
        self._refresh_choice_combos()

    def _short_label(self, col):
        """Label without units, with A/B instead of fuel names (for tight axes)."""
        var, side = mc.column_info(col)
        return var.label + (f" ({side})" if side else "")

    def _set_row(self, row, col, dist, use):
        use_item = QTableWidgetItem()
        use_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        use_item.setCheckState(Qt.Checked if use else Qt.Unchecked)
        use_item.setData(Qt.UserRole, col)
        self.table.setItem(row, self.COL_USE, use_item)
        name = QTableWidgetItem(self._label(col))
        name.setFlags(name.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.COL_INPUT, name)
        combo = QComboBox()
        combo.addItems(mc.Distribution.KINDS)
        combo.setCurrentText(dist.kind)
        self.table.setCellWidget(row, self.COL_DIST, combo)
        for c, v in zip((self.COL_P1, self.COL_P2, self.COL_P3), (dist.a, dist.b, dist.c)):
            self.table.setItem(row, c, QTableWidgetItem(f"{v:.4g}"))

    def _load_defaults(self):
        base = self._base_inputs(quiet=True)
        dists, use = mc.default_uncertainty(base, *self._fuels())
        for row, col in enumerate(self._columns):
            self._set_row(row, col, dists[col], use[col])
        self._refresh_choice_combos()

    def _on_fuel_changed(self, side):
        """Relabel rows; reset the price row of the fuel that changed."""
        base = self._base_inputs(quiet=True)
        dists, use = mc.default_uncertainty(base, *self._fuels())
        for row, col in enumerate(self._columns):
            self.table.item(row, self.COL_INPUT).setText(self._label(col))
            if col in (f"fuel_price_{side}", f"fuel_escalation_{side}", "reactor_cost"):
                self._set_row(row, col, dists[col], use[col])
        self._refresh_choice_combos()

    def _refresh_choice_combos(self):
        """Fill the break-even and map-axis combos (keeping the selection)."""
        for combo, default in ((self.combo_be, "carbon_tax"), (self.combo_map_x, "carbon_tax"),
                               (self.combo_map_y, "fuel_price_B")):
            keep = combo.currentData() or default
            combo.blockSignals(True)
            combo.clear()
            if combo is self.combo_be:
                combo.addItem("(none)", "")
            for col in self._columns:
                combo.addItem(self._label(col), col)
            idx = combo.findData(keep)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)
        self._on_breakeven_changed()

    def _on_breakeven_changed(self, *_):
        col = self.combo_be.currentData()
        enabled = bool(col)
        self.edit_be_lo.setEnabled(enabled)
        self.edit_be_hi.setEnabled(enabled)
        if enabled:
            lo, hi = mc.default_breakeven_bracket(col, self._base_inputs(quiet=True), *self._fuels())
            self.edit_be_lo.setText(f"{lo:g}")
            self.edit_be_hi.setText(f"{hi:g}")

    def _read_config(self):
        """Validated run arguments from the widgets; raises ValueError."""
        fuel_a, fuel_b = self._fuels()
        props_a, props_b = self._props()
        if (fuel_a, props_a) == (fuel_b, props_b):
            raise ValueError("Choose two different options (fuel or number of propellers).")
        n = int(self.edit_n.text())
        if not 1 <= n <= 200000:
            raise ValueError("Samples must be between 1 and 200,000.")
        seed_txt = self.edit_seed.text().strip()
        seed = int(seed_txt) if seed_txt else None
        corr = float(self.edit_corr.text() or 0.0)
        if not -0.99 <= corr <= 0.99:
            raise ValueError("Price correlation must be between -0.99 and 0.99.")

        uncertain = {}
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item.checkState() != Qt.Checked:
                continue
            col = use_item.data(Qt.UserRole)
            kind = self.table.cellWidget(row, self.COL_DIST).currentText()
            params = []
            for c in (self.COL_P1, self.COL_P2, self.COL_P3):
                txt = self.table.item(row, c).text().strip() if self.table.item(row, c) else ""
                params.append(float(txt) if txt else 0.0)
            dist = mc.Distribution(kind, *params)
            try:
                dist.validate()
            except ValueError as e:
                raise ValueError(f"{self._label(col)}: {e}")
            uncertain[col] = dist

        breakeven = None
        col = self.combo_be.currentData()
        if col:
            breakeven = mc.BreakEvenSpec(col, float(self.edit_be_lo.text()), float(self.edit_be_hi.text()))
            if not breakeven.lo < breakeven.hi:
                raise ValueError("Break-even search range needs 'from' < 'to'.")
        return dict(fuel_a=fuel_a, fuel_b=fuel_b, props_a=props_a, props_b=props_b,
                    uncertain=uncertain, n=n, seed=seed,
                    method="lhs" if self.check_lhs.isChecked() else "random",
                    correlations={("fuel_price_A", "fuel_price_B"): corr}, breakeven=breakeven)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def on_run(self):
        try:
            cfg = self._read_config()
        except ValueError as e:
            QMessageBox.critical(self, "Monte Carlo input error", str(e))
            return
        base = self._base_inputs()
        if base is None:
            return

        self._cancel = False
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.progress.setRange(0, cfg["n"])
        self.progress.setValue(0)
        self.text_summary.setText(f"Running {cfg['n']} samples...")
        step = max(cfg["n"] // 200, 1)

        def progress(i, n):
            if i % step == 0 or i == n:
                self.progress.setValue(i)
                QApplication.processEvents()

        try:
            self.result = mc.run_comparison(base, progress=progress, cancelled=lambda: self._cancel, **cfg)
        except Exception as e:
            QMessageBox.critical(self, "Monte Carlo error", str(e))
            self.text_summary.setText(f"Run failed: {e}")
            return
        finally:
            self.btn_run.setEnabled(True)
            self.btn_cancel.setEnabled(False)

        self.text_summary.setText(self.result.summary())
        self.btn_export.setEnabled(self.result.n > 0)
        self._redraw_all()

    def _on_cancel(self):
        self._cancel = True

    def on_export_csv(self):
        if self.result is None:
            return
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Monte Carlo Samples", "monte_carlo_samples.csv", "CSV Files (*.csv);;All Files (*)")
        if not fileName:
            return
        try:
            with open(fileName, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                rows = self.result.to_rows()
                writer.writerow(rows[0])
                for row in rows[1:]:
                    writer.writerow([v if isinstance(v, (int, str)) else f"{v:.6g}" for v in row])
            QMessageBox.information(self, "Export Complete", f"Successfully saved samples to:\n{fileName}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", f"Failed to write CSV file: {e}")

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------
    def _axes(self, key):
        fig, canvas = self.figures[key]
        fig.clear()
        ax = fig.add_subplot(111)
        ax.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        return fig, canvas, ax

    @staticmethod
    def _message(ax, text):
        ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color=INK_MUTED)
        ax.set_xticks([]); ax.set_yticks([])

    def _redraw_all(self):
        if not self.figures or self.result is None:
            return
        self._draw_rfr()
        self._draw_gap()
        self._redraw_map()
        self._draw_breakeven()
        self._draw_drivers()

    def _bins(self, *arrays):
        data = np.concatenate([a[np.isfinite(a)] for a in arrays])
        if data.size == 0 or np.ptp(data) == 0:
            return 10
        return np.linspace(data.min(), data.max(), 41)

    def _draw_rfr(self):
        r = self.result
        fig, canvas, ax = self._axes("rfr")
        a, b = r.rfr_a[r.ok], r.rfr_b[r.ok]
        if not a.size:
            self._message(ax, "No solved samples.")
        else:
            bins = self._bins(a, b)
            ax.hist(a, bins=bins, color=COLOR_A, alpha=0.55, edgecolor="white", linewidth=0.5,
                    label=f"A: {r.name_a}")
            ax.hist(b, bins=bins, color=COLOR_B, alpha=0.55, edgecolor="white", linewidth=0.5,
                    label=f"B: {r.name_b}")
            for v, c in ((r.base_rfr_a, COLOR_A), (r.base_rfr_b, COLOR_B)):
                if math.isfinite(v):
                    ax.axvline(v, color=c, linestyle="--", linewidth=1.5)
            ax.set_xlabel(_mpl_safe("Required freight rate ($/t)"))
            ax.set_ylabel("Samples")
            ax.set_title("RFR distributions (dashed = base case)", fontsize=10)
            ax.legend(frameon=False)
        canvas.draw_idle()

    def _draw_gap(self):
        r = self.result
        fig, canvas, ax = self._axes("gap")
        g = r.gap[r.ok]
        if not g.size:
            self._message(ax, "No solved samples.")
        else:
            bins = self._bins(g)
            edges = bins if isinstance(bins, np.ndarray) else np.histogram_bin_edges(g, bins)
            counts, edges = np.histogram(g, bins=edges)
            centres = 0.5 * (edges[:-1] + edges[1:])
            colors = [COLOR_B if c < 0 else COLOR_A for c in centres]
            ax.bar(centres, counts, width=np.diff(edges), color=colors, edgecolor="white", linewidth=0.5)
            ax.axvline(0.0, color="#0b0b0b", linewidth=1.0)
            ax.set_xlabel(_mpl_safe("RFR gap B - A ($/t)   (left of 0: B cheaper, right: A cheaper)"))
            ax.set_ylabel("Samples")
            ax.set_title(f"P({r.name_b} cheaper than {r.name_a}) = {100 * r.p_b_cheaper():.1f} %", fontsize=10)
        canvas.draw_idle()

    def _redraw_map(self, *_):
        if not self.figures or self.result is None:
            return
        r = self.result
        fig, canvas, ax = self._axes("map")
        cx, cy = self.combo_map_x.currentData(), self.combo_map_y.currentData()
        missing = [self._label(c) for c in (cx, cy) if c not in r.samples or np.ptp(r.samples[c]) == 0]
        if missing:
            self._message(ax, "Not sampled in this run:\n" + "\n".join(missing)
                          + "\n\nTick it in the table (non-fixed distribution) and re-run.")
        elif not r.ok.any():
            self._message(ax, "No solved samples.")
        else:
            x, y = r.samples[cx][r.ok], r.samples[cy][r.ok]
            b_wins = r.gap[r.ok] < 0
            ax.scatter(x[~b_wins], y[~b_wins], s=10, color=COLOR_A, alpha=0.6, linewidths=0,
                       label=f"A cheaper: {r.name_a}")
            ax.scatter(x[b_wins], y[b_wins], s=10, color=COLOR_B, alpha=0.6, linewidths=0,
                       label=f"B cheaper: {r.name_b}")
            ax.set_xlabel(_mpl_safe(self._label(cx)))
            ax.set_ylabel(_mpl_safe(self._label(cy)))
            ax.set_title("Which fuel is cheaper in each sampled future", fontsize=10)
            ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2,
                      markerscale=2, fontsize=8)
        canvas.draw_idle()

    def _draw_breakeven(self):
        r = self.result
        fig, canvas, ax = self._axes("be")
        if r.breakeven is None:
            self._message(ax, "No break-even variable selected.")
        else:
            vals = r.breakeven[r.ok & np.isfinite(r.breakeven)]
            var, _ = mc.column_info(r.breakeven_spec.column)
            counts = r.breakeven_counts()
            if not vals.size:
                self._message(ax, "No break-even inside the search range.\n"
                              f"A always cheaper: {counts.get('A_always', 0)}   "
                              f"B always cheaper: {counts.get('B_always', 0)}")
            else:
                ax.hist(vals, bins=40, color=INK_MUTED, alpha=0.75, edgecolor="white", linewidth=0.5)
                if math.isfinite(r.base_breakeven):
                    ax.axvline(r.base_breakeven, color="#0b0b0b", linestyle="--", linewidth=1.5,
                               label=f"base case {r.base_breakeven:,.1f}")
                    ax.legend(frameon=False)
                ax.set_xlabel(_mpl_safe(f"Break-even {self._label(r.breakeven_spec.column)}"))
                ax.set_ylabel("Samples")
                no_cross = counts.get("A_always", 0) + counts.get("B_always", 0)
                ax.set_title(f"Value where RFR A = RFR B  ({vals.size} crossings, "
                             f"{no_cross} with no crossing in range)", fontsize=10)
        canvas.draw_idle()

    def _draw_drivers(self):
        r = self.result
        fig, canvas, ax = self._axes("drivers")
        drv = r.drivers()
        if not drv:
            self._message(ax, "Not enough variation to rank drivers.")
        else:
            drv = drv[:10][::-1]
            labels = [self._short_label(c) for c, _ in drv]
            rhos = [rho for _, rho in drv]
            # + raises B's RFR relative to A (favours A), - favours B.
            colors = [COLOR_A if v > 0 else COLOR_B for v in rhos]
            ax.barh(range(len(rhos)), rhos, color=colors, height=0.6)
            ax.set_yticks(range(len(rhos)))
            ax.set_yticklabels([_mpl_safe(l) for l in labels], fontsize=8)
            ax.axvline(0.0, color="#0b0b0b", linewidth=1.0)
            ax.set_xlim(-1, 1)
            ax.set_xlabel("Spearman rank correlation with the RFR gap (B - A)")
            ax.set_title("What drives the gap", fontsize=10)
            ax.legend(handles=[Patch(color=COLOR_A, label=f"higher value favours A: {r.name_a}"),
                               Patch(color=COLOR_B, label=f"higher value favours B: {r.name_b}")],
                      frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8)
        canvas.draw_idle()
