# dialog_about.py
# Port of CAboutDlg from ShipDes.cpp
# and IDD_ABOUTBOX from ShipDes.rc

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt

class AboutDialog(QDialog):
    """
    Replaces the CAboutDlg class.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        #
        self.setWindowTitle("About ShipDes")
        
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        #
        # (Icon is handled by the main window, we'll add a placeholder)
        left_layout.addWidget(QLabel("🚢")) 
        left_layout.addStretch()
        main_layout.addLayout(left_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("ShipDes Version 4.01")) #
        right_layout.addWidget(QLabel("Copyright (C) 2002")) #
        right_layout.addWidget(QLabel("SES, Ship Science , University of Southampton")) #
        right_layout.addWidget(QLabel("A. F. Molland")) #
        right_layout.addWidget(QLabel("(Re-programmed by M. Tan)")) #
        right_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok) #
        buttons.accepted.connect(self.accept)
        right_layout.addWidget(buttons)
        
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)