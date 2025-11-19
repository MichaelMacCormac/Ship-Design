# dialog_modify.py
# Complete port of CModify
#
# MODIFIED to include detailed economic parameters
# MODIFIED again to improve layout (wider, stacked groups)
#

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QCheckBox, QDialogButtonBox, QGroupBox, QLabel,
    QHBoxLayout, QMessageBox
)

class ModifyDialog(QDialog):
    """
    Replaces the CModify dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        #
        self.setWindowTitle("Modify parameters")
        # --- NEW: Set a wider default size ---
        self.setMinimumWidth(600)
        
        # This dict will hold our data, replacing m_ member variables
        self.data = {
            'Lb01': 4.0,   #
            'Lb02': 0.025, #
            'Lb03': 30.0,  #
            'Lb04': 6.5,   #
            'Lb05': 130.0, #
            'Cb01': 0.0, 'Cb02': 0.0, 'Cb03': 0.0, 'Cb04': 0.0, 'Cb05': 0.0,
            'L11': 0.0, 'L12': 0.0, 'L13': 0.0,
            'Maxit': 0,    #
            'Ignpth': False, #
            'Ignspd': False, #
            'dbgmd': False,  #
            'Note': "More can be added later.", #
            
            # --- Economic params ---
            'S1_Steel1': 1600.0,
            'S2_Steel2': 242.0,
            'S3_Outfit1': 18000.0,
            'S4_Outfit2': 3500.0,
            'S5_Machinery1': 750.0,
            'S6_Machinery2': 1700.0,
            'H3_Maint_Percent': 0.05,
            'H2_Crew': 60000.0,
            'H4_Port': 500000.0,
            'H5_Stores': 30000.0,
            'H6_Overhead': 250000.0,
        }
        
        # --- Create UI Controls ---
        layout = QVBoxLayout()

        self.note_label = QLabel(self.data['Note']) #
        layout.addWidget(self.note_label)

        # L/B Ratio Group
        lb_group = QGroupBox("L/B ratio")
        lb_layout = QFormLayout()
        self.edit_Lb01 = QLineEdit()
        self.edit_Lb02 = QLineEdit()
        self.edit_Lb03 = QLineEdit()
        self.edit_Lb04 = QLineEdit()
        self.edit_Lb05 = QLineEdit()
        lb_layout.addRow("Lb01:", self.edit_Lb01) #
        lb_layout.addRow("Lb02:", self.edit_Lb02) #
        lb_layout.addRow("Lb03:", self.edit_Lb03) #
        lb_layout.addRow("Lb04:", self.edit_Lb04) #
        lb_layout.addRow("Lb05:", self.edit_Lb05) #
        lb_group.setLayout(lb_layout)
        layout.addWidget(lb_group)
        self.lb_widgets = [self.edit_Lb01, self.edit_Lb02, self.edit_Lb03, 
                           self.edit_Lb04, self.edit_Lb05]

        # CB value Group
        cb_group = QGroupBox("CB value")
        cb_layout = QFormLayout()
        self.edit_Cb01 = QLineEdit()
        self.edit_Cb02 = QLineEdit()
        self.edit_Cb03 = QLineEdit()
        self.edit_Cb04 = QLineEdit()
        self.edit_Cb05 = QLineEdit()
        cb_layout.addRow("Cb01:", self.edit_Cb01) #
        cb_layout.addRow("Cb02:", self.edit_Cb02) #
        cb_layout.addRow("Cb03:", self.edit_Cb03) #
        cb_layout.addRow("Cb04:", self.edit_Cb04) #
        cb_layout.addRow("Cb05:", self.edit_Cb05) #
        cb_group.setLayout(cb_layout)
        layout.addWidget(cb_group)
        self.cb_widgets = [self.edit_Cb01, self.edit_Cb02, self.edit_Cb03,
                           self.edit_Cb04, self.edit_Cb05]
        
        # Initial L value Group
        L_group = QGroupBox("Initial L value")
        L_layout = QFormLayout()
        self.edit_L11 = QLineEdit()
        self.edit_L12 = QLineEdit()
        self.edit_L13 = QLineEdit()
        L_layout.addRow("L11:", self.edit_L11) #
        L_layout.addRow("L12:", self.edit_L12) #
        L_layout.addRow("L13:", self.edit_L13) #
        L_group.setLayout(L_layout)
        layout.addWidget(L_group)
        self.L_widgets = [self.edit_L11, self.edit_L12, self.edit_L13]

        # --- NEW: Re-organized Economic Parameters Group ---
        eco_group = QGroupBox("Economic Parameters")
        
        # Main horizontal layout for this group
        eco_main_layout = QHBoxLayout()

        # --- Capital Costs Sub-Group ---
        capital_group = QGroupBox("Capital Costs")
        capital_layout = QFormLayout()
        
        self.edit_S1_Steel1 = QLineEdit()
        self.edit_S2_Steel2 = QLineEdit()
        self.edit_S3_Outfit1 = QLineEdit()
        self.edit_S4_Outfit2 = QLineEdit()
        self.edit_S5_Machinery1 = QLineEdit()
        self.edit_S6_Machinery2 = QLineEdit()
        capital_layout.addRow("Steel Cost Param 1:", self.edit_S1_Steel1)
        capital_layout.addRow("Steel Cost Param 2:", self.edit_S2_Steel2)
        capital_layout.addRow("Outfit Cost Param 1:", self.edit_S3_Outfit1)
        capital_layout.addRow("Outfit Cost Param 2:", self.edit_S4_Outfit2)
        capital_layout.addRow("Machinery Cost Param 1:", self.edit_S5_Machinery1)
        capital_layout.addRow("Machinery Cost Param 2:", self.edit_S6_Machinery2)
        capital_group.setLayout(capital_layout)
        
        # --- Annual Costs Sub-Group ---
        annual_group = QGroupBox("Annual Costs")
        annual_layout = QFormLayout()

        self.edit_H3_Maint_Percent = QLineEdit()
        self.edit_H2_Crew = QLineEdit()
        self.edit_H4_Port = QLineEdit()
        self.edit_H5_Stores = QLineEdit()
        self.edit_H6_Overhead = QLineEdit()
        annual_layout.addRow("Maint. (% of Build Cost):", self.edit_H3_Maint_Percent)
        annual_layout.addRow("Annual Crew Cost:", self.edit_H2_Crew)
        annual_layout.addRow("Annual Port/Admin Cost:", self.edit_H4_Port)
        annual_layout.addRow("Annual Stores Cost:", self.edit_H5_Stores)
        annual_layout.addRow("Annual Overhead Cost:", self.edit_H6_Overhead)
        annual_group.setLayout(annual_layout)

        # Add the two sub-groups to the main eco layout
        eco_main_layout.addWidget(capital_group)
        eco_main_layout.addWidget(annual_group)
        
        eco_group.setLayout(eco_main_layout)
        layout.addWidget(eco_group)
        # --- End of NEW ---

        # Options Group
        opt_group = QGroupBox("Iteration control (for power calculations)")
        opt_layout = QVBoxLayout()
        self.edit_Maxit = QLineEdit()
        maxit_layout = QHBoxLayout()
        maxit_layout.addWidget(QLabel("Maximum number of iterations:")) #
        maxit_layout.addWidget(self.edit_Maxit)
        opt_layout.addLayout(maxit_layout)
        
        self.check_Ignspd = QCheckBox("Ignore speed limits") #
        self.check_Ignpth = QCheckBox("Ignore pitch limits") #
        self.check_dbgmd = QCheckBox("Run in debug mode") #
        opt_layout.addWidget(self.check_Ignspd)
        opt_layout.addWidget(self.check_Ignpth)
        opt_layout.addWidget(self.check_dbgmd)
        opt_group.setLayout(opt_layout)
        layout.addWidget(opt_group)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)

    def set_data(self, data):
        """
        Loads data from the main view into the dialog.
        """
        # Update self.data with all values from main,
        # falling back to defaults for any new ones.
        self.data.update(data)
        
        # Populate fields from data
        self.edit_Lb01.setText(str(self.data['Lb01']))
        self.edit_Lb02.setText(str(self.data['Lb02']))
        self.edit_Lb03.setText(str(self.data['Lb03']))
        self.edit_Lb04.setText(str(self.data['Lb04']))
        self.edit_Lb05.setText(str(self.data['Lb05']))
        self.edit_Cb01.setText(str(self.data['Cb01']))
        self.edit_Cb02.setText(str(self.data['Cb02']))
        self.edit_Cb03.setText(str(self.data['Cb03']))
        self.edit_Cb04.setText(str(self.data['Cb04']))
        self.edit_Cb05.setText(str(self.data['Cb05']))
        self.edit_L11.setText(str(self.data['L11']))
        self.edit_L12.setText(str(self.data['L12']))
        self.edit_L13.setText(str(self.data['L13']))
        self.edit_Maxit.setText(str(self.data['Maxit']))
        
        self.note_label.setText(self.data['Note'])
        self.check_Ignspd.setChecked(self.data['Ignspd'])
        self.check_Ignpth.setChecked(self.data['Ignpth'])
        self.check_dbgmd.setChecked(self.data['dbgmd'])
        
        # --- NEW: Populate economic fields ---
        self.edit_S1_Steel1.setText(str(self.data.get('S1_Steel1', 1600.0)))
        self.edit_S2_Steel2.setText(str(self.data.get('S2_Steel2', 242.0)))
        self.edit_S3_Outfit1.setText(str(self.data.get('S3_Outfit1', 18000.0)))
        self.edit_S4_Outfit2.setText(str(self.data.get('S4_Outfit2', 3500.0)))
        self.edit_S5_Machinery1.setText(str(self.data.get('S5_Machinery1', 750.0)))
        self.edit_S6_Machinery2.setText(str(self.data.get('S6_Machinery2', 1700.0)))
        self.edit_H3_Maint_Percent.setText(str(self.data.get('H3_Maint_Percent', 0.05)))
        self.edit_H2_Crew.setText(str(self.data.get('H2_Crew', 60000.0)))
        self.edit_H4_Port.setText(str(self.data.get('H4_Port', 500000.0)))
        self.edit_H5_Stores.setText(str(self.data.get('H5_Stores', 30000.0)))
        self.edit_H6_Overhead.setText(str(self.data.get('H6_Overhead', 250000.0)))
        # --- End of NEW ---

    def set_enable(self, k_enable):
        """
        Port of CModify::SetEnable and OnInitDialog logic
        k_enable is expected to be a list/tuple of two bools.
        """
        #);]
        for widget in self.lb_widgets:
            widget.setEnabled(not k_enable[0])
            
        #);]
        for widget in self.cb_widgets:
            widget.setEnabled(not k_enable[1])

    def on_accept(self):
        """
        When OK is clicked, update the data dict from the UI
        before closing.
        """
        try:
            # Pull data from UI back into our data dict
            self.data['Lb01'] = float(self.edit_Lb01.text())
            self.data['Lb02'] = float(self.edit_Lb02.text())
            self.data['Lb03'] = float(self.edit_Lb03.text())
            self.data['Lb04'] = float(self.edit_Lb04.text())
            self.data['Lb05'] = float(self.edit_Lb05.text())
            self.data['Cb01'] = float(self.edit_Cb01.text())
            self.data['Cb02'] = float(self.edit_Cb02.text())
            self.data['Cb03'] = float(self.edit_Cb03.text())
            self.data['Cb04'] = float(self.edit_Cb04.text())
            self.data['Cb05'] = float(self.edit_Cb05.text())
            self.data['L11'] = float(self.edit_L11.text())
            self.data['L12'] = float(self.edit_L12.text())
            self.data['L13'] = float(self.edit_L13.text())
            self.data['Maxit'] = int(self.edit_Maxit.text())
            
            self.data['Ignspd'] = self.check_Ignspd.isChecked()
            self.data['Ignpth'] = self.check_Ignpth.isChecked()
            self.data['dbgmd'] = self.check_dbgmd.isChecked()
            
            # --- NEW: Pull economic data ---
            self.data['S1_Steel1'] = float(self.edit_S1_Steel1.text())
            self.data['S2_Steel2'] = float(self.edit_S2_Steel2.text())
            self.data['S3_Outfit1'] = float(self.edit_S3_Outfit1.text())
            self.data['S4_Outfit2'] = float(self.edit_S4_Outfit2.text())
            self.data['S5_Machinery1'] = float(self.edit_S5_Machinery1.text())
            self.data['S6_Machinery2'] = float(self.edit_S6_Machinery2.text())
            self.data['H3_Maint_Percent'] = float(self.edit_H3_Maint_Percent.text())
            self.data['H2_Crew'] = float(self.edit_H2_Crew.text())
            self.data['H4_Port'] = float(self.edit_H4_Port.text())
            self.data['H5_Stores'] = float(self.edit_H5_Stores.text())
            self.data['H6_Overhead'] = float(self.edit_H6_Overhead.text())
            # --- End of NEW ---
            
            # If all conversions are successful, accept the dialog
            self.accept()
            
        except ValueError:
            # Handle bad input
            QMessageBox.warning(self, "Input Error", 
                                "Invalid number in one of the fields.")

    def get_data(self):
        """
        Called by the main view to retrieve the data after
        the dialog is accepted.
        """
        return self.data