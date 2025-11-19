# main_window.py
# Replaces CMainFrame

from PySide6.QtWidgets import QMainWindow, QDialog
from PySide6.QtGui import QAction

# Import our new Python-based view and dialogs
from ship_des_view_widget import ShipDesViewWidget
from dialog_about import AboutDialog 
from dialog_readme import ReadmeDialog

class MainWindow(QMainWindow):
    """
    Replaces CMainFrame. This is the main SDI window.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ShipDes") #
        self.setGeometry(100, 100, 1024, 768) # Default size

        # --- Create the Central Widget ---
        # This is the key change for SDI. The main form *is*
        # the central widget.
        self.view_widget = ShipDesViewWidget(self)
        self.setCentralWidget(self.view_widget)

        self._create_menus()

    def _create_menus(self):
        # File Menu
        file_menu = self.menuBar().addMenu("&File")

        #
        new_action = QAction("&New SD", self)
        # new_action.triggered.connect(self.view_widget.on_file_new)
        file_menu.addAction(new_action)

        #
        self.save_action = QAction("&Save data", self)
        self.save_action.triggered.connect(self.view_widget.on_button_save)
        file_menu.addAction(self.save_action)

        file_menu.addSeparator()
        
        #
        exit_action = QAction("E&xit Prog.", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = self.menuBar().addMenu("&Edit")
        mod_action = QAction("&Modify", self) #
        mod_action.triggered.connect(self.view_widget.on_dialog_modify)
        edit_menu.addAction(mod_action)
        
        out_action = QAction("&Select", self) #
        out_action.triggered.connect(self.view_widget.on_dialog_outopt)
        edit_menu.addAction(out_action)
        
        # Help Menu
        help_menu = self.menuBar().addMenu("&Help")

        #
        about_action = QAction("&About ShipDes...", self)
        about_action.triggered.connect(self.on_app_about)
        help_menu.addAction(about_action)

        #
        readme_action = QAction("&Readme file", self)
        readme_action.triggered.connect(self.view_widget.on_dialog_readme)
        help_menu.addAction(readme_action)

    def on_app_about(self):
        """
        Replaces CShipDesApp::OnAppAbout
        """
        dlg = AboutDialog(self)
        dlg.exec()