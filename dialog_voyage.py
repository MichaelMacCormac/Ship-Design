# dialog_voyage.py
# Voyage Configuration Dialog
# Allows user to configure voyage mode, routes, speed profiles, and port operations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QComboBox, QLineEdit, QLabel, QPushButton, QGridLayout, QFormLayout
)
from PySide6.QtCore import Qt


# Route database with pre-defined routes
ROUTE_DATABASE = {
    "Southampton → Singapore (Suez)": {
        "port_approach": 100,  # nm (50 each end)
        "canal": 120,  # nm (Suez Canal)
        "open_ocean": 7780,  # nm
        "total": 8000,  # nm
        "default_port_days_origin": 2,
        "default_port_days_dest": 2
    },
    "Rotterdam → Shanghai (Suez)": {
        "port_approach": 100,  # nm
        "canal": 120,  # nm (Suez Canal)
        "open_ocean": 9780,  # nm
        "total": 10000,  # nm
        "default_port_days_origin": 2,
        "default_port_days_dest": 2
    },
    "New York → Los Angeles (Panama)": {
        "port_approach": 100,  # nm
        "canal": 50,  # nm (Panama Canal)
        "open_ocean": 4850,  # nm
        "total": 5000,  # nm
        "default_port_days_origin": 2,
        "default_port_days_dest": 2
    },
    "Houston → Rotterdam (Atlantic)": {
        "port_approach": 100,  # nm
        "canal": 0,  # nm (no canal)
        "open_ocean": 4700,  # nm
        "total": 4800,  # nm
        "default_port_days_origin": 2,
        "default_port_days_dest": 2
    },
    "Custom": {
        "port_approach": 100,  # nm (default)
        "canal": 0,  # nm (default)
        "open_ocean": 8000,  # nm (default)
        "total": 8100,  # nm (calculated)
        "default_port_days_origin": 2,
        "default_port_days_dest": 2
    }
}


class VoyageDialog(QDialog):
    """
    Dialog for configuring voyage parameters.
    Allows switching between Annual Voyages mode and Port to Port mode.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voyage Configuration")
        self.setMinimumWidth(600)
        
        # Initialize data structure
        self.data = {
            'voyage_mode': 0,  # 0=Annual Voyages, 1=Port to Port
            'selected_route': "Southampton → Singapore (Suez)",
            'speed_profile_ocean': 100.0,
            'speed_profile_canal': 20.0,
            'speed_profile_port': 10.0,
            'port_days_origin': 2.0,
            'port_days_dest': 2.0,
            'custom_port_approach': 100.0,
            'custom_canal': 0.0,
            'custom_ocean': 8000.0,
        }
        
        self._create_ui()
        self._connect_signals()
        self._update_ui_state()
        
    def _create_ui(self):
        """Create the UI layout"""
        main_layout = QVBoxLayout(self)
        
        # Mode selection group
        mode_group = QGroupBox("Voyage Mode")
        mode_layout = QVBoxLayout()
        
        self.radio_annual = QRadioButton("Annual Voyages (manual entry)")
        self.radio_port_to_port = QRadioButton("Port to Port (calculated from route)")
        self.radio_annual.setChecked(True)
        
        mode_layout.addWidget(self.radio_annual)
        mode_layout.addWidget(self.radio_port_to_port)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)
        
        # Port to Port configuration group
        self.port_to_port_group = QGroupBox("Port to Port Configuration")
        ptp_layout = QVBoxLayout()
        
        # Route selection
        route_layout = QHBoxLayout()
        route_layout.addWidget(QLabel("Select Route:"))
        self.combo_route = QComboBox()
        self.combo_route.addItems(list(ROUTE_DATABASE.keys()))
        route_layout.addWidget(self.combo_route)
        route_layout.addStretch()
        ptp_layout.addLayout(route_layout)
        
        # Custom route distances (shown when Custom is selected)
        self.custom_group = QGroupBox("Custom Route Distances")
        custom_layout = QGridLayout()
        
        custom_layout.addWidget(QLabel("Port Approach/Departure (nm):"), 0, 0)
        self.edit_custom_port = QLineEdit()
        custom_layout.addWidget(self.edit_custom_port, 0, 1)
        
        custom_layout.addWidget(QLabel("Canal Transit (nm):"), 1, 0)
        self.edit_custom_canal = QLineEdit()
        custom_layout.addWidget(self.edit_custom_canal, 1, 1)
        
        custom_layout.addWidget(QLabel("Open Ocean (nm):"), 2, 0)
        self.edit_custom_ocean = QLineEdit()
        custom_layout.addWidget(self.edit_custom_ocean, 2, 1)
        
        self.custom_group.setLayout(custom_layout)
        ptp_layout.addWidget(self.custom_group)
        
        # Speed profile
        speed_group = QGroupBox("Speed Profile (% of Cruise Speed)")
        speed_layout = QGridLayout()
        
        speed_layout.addWidget(QLabel("Open Ocean:"), 0, 0)
        self.edit_speed_ocean = QLineEdit()
        speed_layout.addWidget(self.edit_speed_ocean, 0, 1)
        speed_layout.addWidget(QLabel("%"), 0, 2)
        
        speed_layout.addWidget(QLabel("Canal Transit:"), 1, 0)
        self.edit_speed_canal = QLineEdit()
        speed_layout.addWidget(self.edit_speed_canal, 1, 1)
        speed_layout.addWidget(QLabel("%"), 1, 2)
        
        speed_layout.addWidget(QLabel("Port Approach/Departure:"), 2, 0)
        self.edit_speed_port = QLineEdit()
        speed_layout.addWidget(self.edit_speed_port, 2, 1)
        speed_layout.addWidget(QLabel("%"), 2, 2)
        
        speed_group.setLayout(speed_layout)
        ptp_layout.addWidget(speed_group)
        
        # Port operations
        port_group = QGroupBox("Port Operations")
        port_layout = QGridLayout()
        
        port_layout.addWidget(QLabel("Days at Origin Port (loading):"), 0, 0)
        self.edit_port_days_origin = QLineEdit()
        port_layout.addWidget(self.edit_port_days_origin, 0, 1)
        
        port_layout.addWidget(QLabel("Days at Destination Port (unloading):"), 1, 0)
        self.edit_port_days_dest = QLineEdit()
        port_layout.addWidget(self.edit_port_days_dest, 1, 1)
        
        port_group.setLayout(port_layout)
        ptp_layout.addWidget(port_group)
        
        # Calculated values display
        calc_group = QGroupBox("Calculated Values")
        calc_layout = QFormLayout()
        
        self.label_total_distance = QLabel("-- nm")
        calc_layout.addRow("Total Voyage Distance (one-way):", self.label_total_distance)
        
        self.label_voyage_time = QLabel("-- days")
        calc_layout.addRow("Total Voyage Time (round trip + port):", self.label_voyage_time)
        
        self.label_annual_voyages = QLabel("-- voyages/year")
        calc_layout.addRow("Annual Voyages:", self.label_annual_voyages)
        
        calc_group.setLayout(calc_layout)
        ptp_layout.addWidget(calc_group)
        
        self.port_to_port_group.setLayout(ptp_layout)
        main_layout.addWidget(self.port_to_port_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        
        button_layout.addWidget(self.btn_ok)
        button_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(button_layout)
        
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        self.radio_annual.toggled.connect(self._update_ui_state)
        self.radio_port_to_port.toggled.connect(self._update_ui_state)
        self.combo_route.currentIndexChanged.connect(self._on_route_changed)
        
        # Connect calculation triggers
        self.edit_speed_ocean.textChanged.connect(self._update_calculations)
        self.edit_speed_canal.textChanged.connect(self._update_calculations)
        self.edit_speed_port.textChanged.connect(self._update_calculations)
        self.edit_port_days_origin.textChanged.connect(self._update_calculations)
        self.edit_port_days_dest.textChanged.connect(self._update_calculations)
        self.edit_custom_port.textChanged.connect(self._update_calculations)
        self.edit_custom_canal.textChanged.connect(self._update_calculations)
        self.edit_custom_ocean.textChanged.connect(self._update_calculations)
        
        # Buttons
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
    def _update_ui_state(self):
        """Update UI based on selected mode"""
        is_port_to_port = self.radio_port_to_port.isChecked()
        self.port_to_port_group.setEnabled(is_port_to_port)
        
        # Update custom route visibility
        is_custom = self.combo_route.currentText() == "Custom"
        self.custom_group.setVisible(is_custom and is_port_to_port)
        
        # Update calculations if in port to port mode
        if is_port_to_port:
            self._update_calculations()
            
    def _on_route_changed(self):
        """Handle route selection change"""
        route_name = self.combo_route.currentText()
        
        if route_name in ROUTE_DATABASE:
            route = ROUTE_DATABASE[route_name]
            
            # Update port days with defaults
            self.edit_port_days_origin.setText(str(route['default_port_days_origin']))
            self.edit_port_days_dest.setText(str(route['default_port_days_dest']))
            
            # If custom route, update custom fields
            if route_name == "Custom":
                self.edit_custom_port.setText(str(route['port_approach']))
                self.edit_custom_canal.setText(str(route['canal']))
                self.edit_custom_ocean.setText(str(route['open_ocean']))
        
        self._update_ui_state()
        
    def _update_calculations(self):
        """Update calculated voyage time and annual voyages"""
        if not self.radio_port_to_port.isChecked():
            return
            
        try:
            # Get cruise speed from parent widget
            cruise_speed = self.parent().m_Speed if hasattr(self.parent(), 'm_Speed') else 15.0
            
            # Get route distances
            route_name = self.combo_route.currentText()
            if route_name == "Custom":
                dist_port = float(self.edit_custom_port.text() or 0)
                dist_canal = float(self.edit_custom_canal.text() or 0)
                dist_ocean = float(self.edit_custom_ocean.text() or 0)
            else:
                route = ROUTE_DATABASE[route_name]
                dist_port = route['port_approach']
                dist_canal = route['canal']
                dist_ocean = route['open_ocean']
            
            total_distance = dist_port + dist_canal + dist_ocean
            self.label_total_distance.setText(f"{total_distance:.0f} nm")
            
            # Get speed profiles
            speed_ocean_pct = float(self.edit_speed_ocean.text() or 100) / 100.0
            speed_canal_pct = float(self.edit_speed_canal.text() or 20) / 100.0
            speed_port_pct = float(self.edit_speed_port.text() or 10) / 100.0
            
            # Calculate time for each segment
            # Time = Distance / Speed (in hours), then convert to days
            time_port_hours = dist_port / (cruise_speed * speed_port_pct) if speed_port_pct > 0 else 0
            time_canal_hours = dist_canal / (cruise_speed * speed_canal_pct) if speed_canal_pct > 0 else 0
            time_ocean_hours = dist_ocean / (cruise_speed * speed_ocean_pct) if speed_ocean_pct > 0 else 0
            
            # Convert to days
            time_port_days = time_port_hours / 24.0
            time_canal_days = time_canal_hours / 24.0
            time_ocean_days = time_ocean_hours / 24.0
            
            # One-way transit time
            one_way_time = time_port_days + time_canal_days + time_ocean_days
            
            # Round trip time
            round_trip_time = 2 * one_way_time
            
            # Add port operation time
            port_days_origin = float(self.edit_port_days_origin.text() or 0)
            port_days_dest = float(self.edit_port_days_dest.text() or 0)
            total_port_days = port_days_origin + port_days_dest
            
            # Total voyage time
            total_voyage_time = round_trip_time + total_port_days
            self.label_voyage_time.setText(f"{total_voyage_time:.2f} days")
            
            # Calculate annual voyages
            sea_days = self.parent().m_Seadays if hasattr(self.parent(), 'm_Seadays') else 340.0
            if total_voyage_time > 0:
                annual_voyages = sea_days / total_voyage_time
                self.label_annual_voyages.setText(f"{annual_voyages:.2f} voyages/year")
            else:
                self.label_annual_voyages.setText("-- voyages/year")
                
        except (ValueError, ZeroDivisionError):
            # If any field is invalid, show placeholders
            self.label_total_distance.setText("-- nm")
            self.label_voyage_time.setText("-- days")
            self.label_annual_voyages.setText("-- voyages/year")
    
    def set_data(self, data):
        """Load data into the dialog"""
        self.data = data.copy()
        
        # Set mode
        if data['voyage_mode'] == 0:
            self.radio_annual.setChecked(True)
        else:
            self.radio_port_to_port.setChecked(True)
        
        # Set route
        route_name = data['selected_route']
        index = self.combo_route.findText(route_name)
        if index >= 0:
            self.combo_route.setCurrentIndex(index)
        
        # Set speed profiles
        self.edit_speed_ocean.setText(f"{data['speed_profile_ocean']:.6g}")
        self.edit_speed_canal.setText(f"{data['speed_profile_canal']:.6g}")
        self.edit_speed_port.setText(f"{data['speed_profile_port']:.6g}")
        
        # Set port days
        self.edit_port_days_origin.setText(f"{data['port_days_origin']:.6g}")
        self.edit_port_days_dest.setText(f"{data['port_days_dest']:.6g}")
        
        # Set custom route distances
        self.edit_custom_port.setText(f"{data['custom_port_approach']:.6g}")
        self.edit_custom_canal.setText(f"{data['custom_canal']:.6g}")
        self.edit_custom_ocean.setText(f"{data['custom_ocean']:.6g}")
        
        self._update_ui_state()
        
    def get_data(self):
        """Get data from the dialog"""
        self.data['voyage_mode'] = 1 if self.radio_port_to_port.isChecked() else 0
        self.data['selected_route'] = self.combo_route.currentText()
        
        try:
            self.data['speed_profile_ocean'] = float(self.edit_speed_ocean.text())
            self.data['speed_profile_canal'] = float(self.edit_speed_canal.text())
            self.data['speed_profile_port'] = float(self.edit_speed_port.text())
            self.data['port_days_origin'] = float(self.edit_port_days_origin.text())
            self.data['port_days_dest'] = float(self.edit_port_days_dest.text())
            self.data['custom_port_approach'] = float(self.edit_custom_port.text())
            self.data['custom_canal'] = float(self.edit_custom_canal.text())
            self.data['custom_ocean'] = float(self.edit_custom_ocean.text())
        except ValueError:
            pass  # Keep previous values if conversion fails
        
        return self.data
