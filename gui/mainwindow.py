import os
import json
from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QDockWidget, 
                             QFileDialog, QMessageBox, QSplitter, QVBoxLayout, QWidget, QDialog, QTextEdit)
from PyQt5.QtCore import Qt, QProcess

from node_editor import NodeEditor
from property_editor import PropertyEditor
from library_widget import LibraryWidget
from importer import MarlinImporter

class RunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Running Marlin")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)

    def run(self, program, arguments):
        self.text_edit.append(f"Executing: {program} {' '.join(arguments)}\n")
        self.process.start(program, arguments)

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.text_edit.append(stdout)

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.text_edit.append(f"<span style='color:red'>{stderr}</span>")

    def handle_finished(self):
        self.text_edit.append("\nExecution Finished.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marlin GUI")
        self.resize(1200, 800)
        
        self.last_input_path = None
        
        # Load Registry
        registry_path = os.path.join(os.path.dirname(__file__), 'registry.json')
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                self.registry = json.load(f)
        else:
            self.registry = {}
            QMessageBox.warning(self, "Warning", "registry.json not found. Please run scanner.py")

        # Central Widget (Node Editor)
        self.node_editor = NodeEditor(self.registry)
        self.setCentralWidget(self.node_editor)
        
        # Left Dock (Library)
        self.library_dock = QDockWidget("Library", self)
        self.library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.library_widget = LibraryWidget(self.registry)
        self.library_dock.setWidget(self.library_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.library_dock)

        # Right Dock (Property Editor)
        self.property_dock = QDockWidget("Properties", self)
        self.property_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.property_editor = PropertyEditor(self.registry)
        self.property_dock.setWidget(self.property_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_dock)
        
        # Connect Signals
        self.node_editor.selectionChanged.connect(self.property_editor.set_block)
        
        self.property_editor.nameChanged.connect(self.node_editor.update_selected_block_name)
        self.property_editor.categoryChanged.connect(self.node_editor.update_selected_block_category)
        self.property_editor.typeChanged.connect(self.node_editor.update_selected_block_type)
        self.property_editor.paramChanged.connect(self.node_editor.update_selected_block_param)
        
        # Toolbar
        self.create_toolbar()
        
        # Menu Bar
        self.create_menubar()

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        add_action = QAction("Add Block", self)
        add_action.triggered.connect(self.node_editor.add_block)
        toolbar.addAction(add_action)
        
        remove_action = QAction("Remove Block", self)
        remove_action.triggered.connect(self.node_editor.remove_selected_blocks)
        toolbar.addAction(remove_action)
        
        toolbar.addSeparator()
        
        run_action = QAction("Run", self)
        run_action.triggered.connect(self.run_marlin)
        toolbar.addAction(run_action)

    def create_menubar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save Diagram...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_diagram)
        file_menu.addAction(save_action)
        
        load_action = QAction("Load Diagram...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_diagram)
        file_menu.addAction(load_action)
        
        import_action = QAction("Import Input File...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self.import_input)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        gen_action = QAction("Generate Input File...", self)
        gen_action.setShortcut("Ctrl+G")
        gen_action.triggered.connect(self.generate_input)
        file_menu.addAction(gen_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def save_diagram(self):
        print("Attempting to save diagram...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        # Use None as parent to avoid potential window modality issues
        path, _ = QFileDialog.getSaveFileName(None, "Save Diagram", os.getcwd(), "JSON Files (*.json)", options=options)
        if path:
            if not path.endswith('.json'):
                path += '.json'
            data = self.node_editor.serialize()
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Saved to {path}")
            self.node_editor.set_modified(False)

    def load_diagram(self):
        if not self.check_unsaved_changes():
            return
            
        print("Attempting to load diagram...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(None, "Load Diagram", os.getcwd(), "JSON Files (*.json)", options=options)
        if path:
            with open(path, 'r') as f:
                data = json.load(f)
            self.node_editor.deserialize(data)
            print(f"Loaded from {path}")

    def import_input(self):
        if not self.check_unsaved_changes():
            return
            
        print("Attempting to import input file...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(None, "Import Input File", os.getcwd(), "Marlin Input (*.i)", options=options)
        if path:
            with open(path, 'r') as f:
                content = f.read()
            
            importer = MarlinImporter()
            data = importer.parse(content)
            self.node_editor.deserialize(data)
            print(f"Imported from {path}")
            QMessageBox.information(self, "Import Successful", f"Imported {len(data['blocks'])} blocks from {os.path.basename(path)}")

    def generate_input(self, path=None, silent=False):
        if path is None or isinstance(path, bool):
            print("Attempting to generate input...")
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            path, _ = QFileDialog.getSaveFileName(None, "Generate Input File", os.getcwd(), "Marlin Input (*.i)", options=options)
        
        if path:
            if not path.endswith('.i'):
                path += '.i'
            content = self.node_editor.generate_input_content()
            with open(path, 'w') as f:
                f.write(content)
            if not silent:
                QMessageBox.information(self, "Success", f"Input file generated at {path}")
            return path
        return None

    def run_marlin(self):
        import tempfile
        # Create a temporary file for running
        with tempfile.NamedTemporaryFile(suffix='.i', delete=False, mode='w') as tmp:
            input_path = tmp.name
            
        # First generate input file
        input_path = self.generate_input(path=input_path, silent=True)
        if input_path:
            # Run marlin-opt
            # Assuming marlin-opt is in the root or build directory
            # Let's try to find it
            marlin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../marlin-opt'))
            if not os.path.exists(marlin_path):
                 marlin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../build/marlin-opt'))
            
            if not os.path.exists(marlin_path):
                QMessageBox.critical(self, "Error", "Could not find marlin-opt executable.")
                return

            print(f"Running command: {marlin_path} -i {input_path}")
            
            # Keep reference to prevent garbage collection
            self.run_dialog = RunDialog(self)
            self.run_dialog.show()
            self.run_dialog.run(marlin_path, ["-i", input_path])
            # Do not call exec_() to avoid blocking main loop

    def closeEvent(self, event):
        if self.node_editor.is_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save them before closing?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Save)

            if reply == QMessageBox.Save:
                self.save_diagram()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def check_unsaved_changes(self):
        if self.node_editor.is_modified:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Do you want to save them before continuing?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Save)

            if reply == QMessageBox.Save:
                self.save_diagram()
                return True
            elif reply == QMessageBox.Discard:
                return True
            else:
                return False
        return True
