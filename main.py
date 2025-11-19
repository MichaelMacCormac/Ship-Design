# main.py
# Replaces ShipDes.cpp
# This is the main entry point for your application.

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings #
from main_window import MainWindow

class ShipDesApp:
    """
    Replaces the global "theApp" object and CShipDesApp.
    """
    def __init__(self, argv):
        # Replaces CShipDesApp::CShipDesApp()
        self.app = QApplication(argv)
        
        # Set up registry/settings key
        QApplication.setOrganizationName("SesSoton")
        QApplication.setApplicationName("ShipDes")

        # Replaces CShipDesApp::InitInstance()
        self.main_window = MainWindow()
        
        # Parse command line (replaces ParseCommandLine)
        # TODO: Check sys.argv[1:] for a file to open
        
        # Show main window (replaces ShowWindow/UpdateWindow)
        #
        self.main_window.show()

    def run(self):
        """
        Starts the application's event loop.
        """
        return self.app.exec()

# --- The main entry point ---
if __name__ == "__main__":
    # The one and only ShipDesApp object
    theApp = ShipDesApp(sys.argv)
    
    # Run the app
    sys.exit(theApp.run())