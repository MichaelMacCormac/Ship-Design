# dialog_outopt.py
# Complete port of COutopt
#

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QCheckBox, 
    QDialogButtonBox, QGroupBox
)

class OutoptDialog(QDialog):
    """
    Replaces the COutopt dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        #
        self.setWindowTitle("Select Output")
        
        # This dict holds the state of all checkboxes, replacing m_o... vars
        #
        self.data = {
            'oall': True, 'oshipd': True, 'ol': True, 'ob': True, 'olb': True,
            'od': True, 'ot': True, 'obt': True, 'ocb': True,
            'odispetc': True, 'odisp': True, 'ocdw': True, 'otdw': True,
            'opdt': True, 'ospeed': True, 'orange': True, 'oerpm': True,
            'oprpm': True, 'opoweretc': True, 'ospower': True,
            'oipower': True, 'ope': True, 'ono': True, 'onh': True,
            'oqpc': True, 'oscf': True, 'ont': True, 'omargin': True,
            'omassetc': True, 'osmass': True, 'oomass': True, 'ommass': True,
            'ofbd': True, 'oagm': True, 'oinput': True, 'ovyear': True,
            'osdyear': True, 'ofcost': True, 'oirate': True,
            'oreyear': True, 'ooutput': True, 'obcost': True, 'oacc': True,
            'oafc': True, 'orfr': True
        }
        
        # --- Create UI Controls ---
        main_layout = QVBoxLayout()
        
        #
        self.check_all = QCheckBox("Select / De-select all")
        main_layout.addWidget(self.check_all)
        
        self.checks = {}

        # Ship Dimensions Group
        #
        shipd_group = QGroupBox("Ship &dimensions")
        shipd_group.setCheckable(True)
        shipd_layout = QGridLayout()
        self.checks.update({
            'ol': QCheckBox("L"), 'ob': QCheckBox("B"), 'olb': QCheckBox("L/B"),
            'od': QCheckBox("D"), 'ot': QCheckBox("T"), 'obt': QCheckBox("B/T"),
            'ocb': QCheckBox("CB")
        })
        shipd_layout.addWidget(self.checks['ol'], 0, 0) #
        shipd_layout.addWidget(self.checks['ob'], 0, 1) #
        shipd_layout.addWidget(self.checks['olb'], 0, 2) #
        shipd_layout.addWidget(self.checks['od'], 1, 0) #
        shipd_layout.addWidget(self.checks['ot'], 1, 1) #
        shipd_layout.addWidget(self.checks['obt'], 1, 2) #
        shipd_layout.addWidget(self.checks['ocb'], 2, 0) #
        shipd_group.setLayout(shipd_layout)
        main_layout.addWidget(shipd_group)
        self.shipd_group = shipd_group

        # Displacement Group
        #
        dispetc_group = QGroupBox("Di&splacement. etc")
        dispetc_group.setCheckable(True)
        dispetc_layout = QGridLayout()
        self.checks.update({
            'odisp': QCheckBox("Disp."), 'ocdw': QCheckBox("Cargo DW"),
            'otdw': QCheckBox("Total DW"), 'opdt': QCheckBox("PropDia/T"),
            'ospeed': QCheckBox("Speed"), 'orange': QCheckBox("Range"),
            'oerpm': QCheckBox("Engine Rpm"), 'oprpm': QCheckBox("Prop. Rpm")
        })
        dispetc_layout.addWidget(self.checks['odisp'], 0, 0) #
        dispetc_layout.addWidget(self.checks['ocdw'], 0, 1) #
        dispetc_layout.addWidget(self.checks['otdw'], 0, 2) #
        dispetc_layout.addWidget(self.checks['opdt'], 1, 0) #
        dispetc_layout.addWidget(self.checks['ospeed'], 1, 1) #
        dispetc_layout.addWidget(self.checks['orange'], 1, 2) #
        dispetc_layout.addWidget(self.checks['oerpm'], 2, 0) #
        dispetc_layout.addWidget(self.checks['oprpm'], 2, 1) #
        dispetc_group.setLayout(dispetc_layout)
        main_layout.addWidget(dispetc_group)
        self.dispetc_group = dispetc_group

        # Power Group
        #
        poweretc_group = QGroupBox("&Power etc")
        poweretc_group.setCheckable(True)
        poweretc_layout = QGridLayout()
        self.checks.update({
            'ospower': QCheckBox("Serv. power"), 'oipower': QCheckBox("Inst. power"),
            'ope': QCheckBox("PE"), 'ono': QCheckBox("NO"),
            'onh': QCheckBox("NH"), 'oqpc': QCheckBox("QPC"),
            'oscf': QCheckBox("SCF"), 'ont': QCheckBox("NT"), 'omargin': QCheckBox("Margin")
        })
        poweretc_layout.addWidget(self.checks['ospower'], 0, 0) #
        poweretc_layout.addWidget(self.checks['oipower'], 0, 1) #
        poweretc_layout.addWidget(self.checks['ope'], 0, 2) #
        poweretc_layout.addWidget(self.checks['ono'], 0, 3) #
        poweretc_layout.addWidget(self.checks['onh'], 1, 0) #
        poweretc_layout.addWidget(self.checks['oqpc'], 1, 1) #
        poweretc_layout.addWidget(self.checks['oscf'], 1, 2) #
        poweretc_layout.addWidget(self.checks['ont'], 1, 3) #
        poweretc_layout.addWidget(self.checks['omargin'], 2, 0) #
        poweretc_group.setLayout(poweretc_layout)
        main_layout.addWidget(poweretc_group)
        self.poweretc_group = poweretc_group

        # Mass Group
        #
        massetc_group = QGroupBox("&Mass etc")
        massetc_group.setCheckable(True)
        massetc_layout = QGridLayout()
        self.checks.update({
            'osmass': QCheckBox("Steel mass"), 'oomass': QCheckBox("Outfit mass"),
            'ommass': QCheckBox("Machy mass"), 'ofbd': QCheckBox("Free board"), 'oagm': QCheckBox("Appr. GM")
        })
        massetc_layout.addWidget(self.checks['osmass'], 0, 0) #
        massetc_layout.addWidget(self.checks['oomass'], 0, 1) #
        massetc_layout.addWidget(self.checks['ommass'], 0, 2) #
        massetc_layout.addWidget(self.checks['ofbd'], 1, 0) #
        massetc_layout.addWidget(self.checks['oagm'], 1, 1) #
        massetc_group.setLayout(massetc_layout)
        main_layout.addWidget(massetc_group)
        self.massetc_group = massetc_group

        # Economic Input Group
        #
        einput_group = QGroupBox("&Input for economic analysis")
        einput_group.setCheckable(True)
        einput_layout = QGridLayout()
        self.checks.update({
            'ovyear': QCheckBox("Voyages/year"), 'osdyear': QCheckBox("Seadays/year"),
            'ofcost': QCheckBox("Fuel cost"), 'oirate': QCheckBox("Int. rate"), 'oreyear': QCheckBox("Repay. years")
        })
        einput_layout.addWidget(self.checks['ovyear'], 0, 0) #
        einput_layout.addWidget(self.checks['osdyear'], 0, 1) #
        einput_layout.addWidget(self.checks['ofcost'], 0, 2) #
        einput_layout.addWidget(self.checks['oirate'], 1, 0) #
        einput_layout.addWidget(self.checks['oreyear'], 1, 1) #
        einput_group.setLayout(einput_layout)
        main_layout.addWidget(einput_group)
        self.einput_group = einput_group
        
        # Economic Output Group
        #
        eoutput_group = QGroupBox("&Output from economic analysis")
        eoutput_group.setCheckable(True)
        eoutput_layout = QGridLayout()
        self.checks.update({
            'obcost': QCheckBox("Build cost"), 'oacc': QCheckBox("Ann. cap. charges"),
            'oafc': QCheckBox("Annual fuel cost"), 'orfr': QCheckBox("Req. freight rate")
        })
        eoutput_layout.addWidget(self.checks['obcost'], 0, 0) #
        eoutput_layout.addWidget(self.checks['oacc'], 0, 1) #
        eoutput_layout.addWidget(self.checks['oafc'], 1, 0) #
        eoutput_layout.addWidget(self.checks['orfr'], 1, 1) #
        eoutput_group.setLayout(eoutput_layout)
        main_layout.addWidget(eoutput_group)
        self.eoutput_group = eoutput_group
        
        # OK and Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)
        
        self.setLayout(main_layout)
        
        # --- Connect signals ---
        #
        self.check_all.toggled.connect(self.on_check_all)
        #
        shipd_group.toggled.connect(self.on_check_shipdim)
        dispetc_group.toggled.connect(self.on_check_dispetc) #
        poweretc_group.toggled.connect(self.on_check_poweretc) #
        massetc_group.toggled.connect(self.on_check_massetc) #
        einput_group.toggled.connect(self.on_check_einput) #
        eoutput_group.toggled.connect(self.on_check_eoutput) #

        self.update_ui_from_data() # Set initial state

    def update_data_from_ui(self):
        """Pulls state from UI checkboxes into self.data dict"""
        self.data['oall'] = self.check_all.isChecked()
        self.data['oshipd'] = self.shipd_group.isChecked()
        self.data['odispetc'] = self.dispetc_group.isChecked()
        self.data['opoweretc'] = self.poweretc_group.isChecked()
        self.data['omassetc'] = self.massetc_group.isChecked()
        self.data['oinput'] = self.einput_group.isChecked()
        self.data['ooutput'] = self.eoutput_group.isChecked()
        for key, checkbox in self.checks.items():
            self.data[key] = checkbox.isChecked()
            
    def update_ui_from_data(self):
        """Pushes state from self.data dict to UI checkboxes"""
        # Block signals to prevent loops
        self.check_all.blockSignals(True)
        self.shipd_group.blockSignals(True)
        self.dispetc_group.blockSignals(True)
        self.poweretc_group.blockSignals(True)
        self.massetc_group.blockSignals(True)
        self.einput_group.blockSignals(True)
        self.eoutput_group.blockSignals(True)

        self.check_all.setChecked(self.data['oall'])
        self.shipd_group.setChecked(self.data['oshipd'])
        self.dispetc_group.setChecked(self.data['odispetc'])
        self.poweretc_group.setChecked(self.data['opoweretc'])
        self.massetc_group.setChecked(self.data['omassetc'])
        self.einput_group.setChecked(self.data['oinput'])
        self.eoutput_group.setChecked(self.data['ooutput'])
        for key, checkbox in self.checks.items():
            checkbox.setChecked(self.data[key])
            
        # Unblock signals
        self.check_all.blockSignals(False)
        self.shipd_group.blockSignals(False)
        self.dispetc_group.blockSignals(False)
        self.poweretc_group.blockSignals(False)
        self.massetc_group.blockSignals(False)
        self.einput_group.blockSignals(False)
        self.eoutput_group.blockSignals(False)
            
    def on_accept(self):
        self.update_data_from_ui()
        self.accept()
        
    def get_data(self):
        return self.data
        
    def set_data(self, data):
        self.data.update(data)
        self.update_ui_from_data()

    # --- Ported Logic from Outopt.cpp ---
    
    def on_check_all(self, checked):
        #
        self.data['oall'] = checked
        self.set_shipd(checked)
        self.set_dispetc(checked)
        self.set_poweretc(checked)
        self.set_massetc(checked)
        self.set_input(checked)
        self.set_output(checked)
        self.update_ui_from_data()

    def on_check_shipdim(self, checked):
        #
        self.set_shipd(checked)
        self.update_ui_from_data()
        
    def on_check_dispetc(self, checked):
        #
        self.set_dispetc(checked)
        self.update_ui_from_data()
        
    def on_check_poweretc(self, checked):
        #
        self.set_poweretc(checked)
        self.update_ui_from_data()
        
    def on_check_massetc(self, checked):
        #
        self.set_massetc(checked)
        self.update_ui_from_data()
        
    def on_check_einput(self, checked):
        #
        self.set_input(checked)
        self.update_ui_from_data()
        
    def on_check_eoutput(self, checked):
        #
        self.set_output(checked)
        self.update_ui_from_data()

    def set_shipd(self, k):
        #
        self.data['oshipd'] = k
        self.data['ol'] = k; self.data['ob'] = k; self.data['olb'] = k
        self.data['od'] = k; self.data['ot'] = k; self.data['obt'] = k
        self.data['ocb'] = k
        
    def set_dispetc(self, k):
        #
        self.data['odispetc'] = k
        self.data['odisp'] = k; self.data['ocdw'] = k; self.data['otdw'] = k
        self.data['opdt'] = k; self.data['ospeed'] = k; self.data['orange'] = k
        self.data['oerpm'] = k; self.data['oprpm'] = k
        
    def set_poweretc(self, k):
        #
        self.data['opoweretc'] = k
        self.data['ospower'] = k; self.data['oipower'] = k; self.data['ope'] = k
        self.data['ono'] = k; self.data['onh'] = k; self.data['oqpc'] = k
        self.data['oscf'] = k; self.data['ont'] = k; self.data['omargin'] = k
        
    def set_massetc(self, k):
        #
        self.data['omassetc'] = k
        self.data['osmass'] = k; self.data['oomass'] = k; self.data['ommass'] = k
        self.data['ofbd'] = k; self.data['oagm'] = k
        
    def set_input(self, k):
        #
        self.data['oinput'] = k
        self.data['ovyear'] = k; self.data['osdyear'] = k; self.data['ofcost'] = k
        self.data['oirate'] = k; self.data['oreyear'] = k
        
    def set_output(self, k):
        #
        self.data['ooutput'] = k
        self.data['obcost'] = k; self.data['oacc'] = k; self.data['oafc'] = k
        self.data['orfr'] = k