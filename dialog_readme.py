# dialog_readme.py
# Complete port of CReadme
#

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox

class ReadmeDialog(QDialog):
    """
    Replaces the CReadme dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        #
        self.setWindowTitle("A Quick Help")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout()
        
        #
        #
        self.text_readme = QTextEdit()
        self.text_readme.setReadOnly(True) #
        layout.addWidget(self.text_readme)

        # Add OK button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
        #
        # Call the function to populate the text
        self._add_readme_text()

    def _add_readme_text(self):
        """
        Port of CReadme::AddReadmeText
        """
        readme_text = " To run ShipDes, you can also use:\r\n"
        readme_text += " Tab key, Space bar, Arrow keys,"
        readme_text += " Alt+C etc.\r\n"
        readme_text += " \r\n Please report any bug information to"
        readme_text += " \r\n     Prof. AF Molland or Dr. M Tan.\r\n"
        readme_text += " \r\n--- Add some useful "
        readme_text += " Read-Me Text here later! ---\r\n"
        
        #
        self.text_readme.setText(readme_text)