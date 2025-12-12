from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox, 
                             QLineEdit, QLabel, QScrollArea, QCheckBox)
from PyQt5.QtCore import pyqtSignal

class PropertyEditor(QWidget):
    categoryChanged = pyqtSignal(str)
    typeChanged = pyqtSignal(str)
    nameChanged = pyqtSignal(str)
    paramChanged = pyqtSignal(str, str) # param_name, value

    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        self.current_block = None
        
        self.layout = QVBoxLayout(self)
        
        # Name
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.on_name_changed)
        self.layout.addWidget(QLabel("Name (Block Name)"))
        self.layout.addWidget(self.name_edit)
        
        # Category
        self.category_combo = QComboBox()
        self.category_combo.addItems(sorted(self.registry.keys()))
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        self.layout.addWidget(QLabel("Category (KeyWordBlock)"))
        self.layout.addWidget(self.category_combo)
        
        # Type
        self.type_combo = QComboBox()
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        self.layout.addWidget(QLabel("Type"))
        self.layout.addWidget(self.type_combo)
        
        # Parameters Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.params_widget = QWidget()
        self.params_layout = QFormLayout(self.params_widget)
        self.scroll.setWidget(self.params_widget)
        self.layout.addWidget(QLabel("Parameters"))
        self.layout.addWidget(self.scroll)
        
        self.block_updating = False

    def set_block(self, block):
        self.block_updating = True
        self.current_block = block
        
        if block:
            self.name_edit.setText(block.name)
            self.category_combo.setCurrentText(block.category)
            self.update_type_combo(block.category)
            self.type_combo.setCurrentText(block.type)
            self.update_params_ui()
            self.setEnabled(True)
        else:
            self.name_edit.clear()
            self.category_combo.setCurrentIndex(-1)
            self.type_combo.clear()
            self.clear_params_ui()
            self.setEnabled(False)
            
        self.block_updating = False

    def update_type_combo(self, category):
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        if category in self.registry:
            types = [obj['name'] for obj in self.registry[category]]
            self.type_combo.addItems(sorted(types))
        self.type_combo.blockSignals(False)

    def clear_params_ui(self):
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def update_params_ui(self):
        self.clear_params_ui()
        if not self.current_block:
            return
            
        category = self.current_block.category
        obj_type = self.current_block.type
        
        # Find object definition
        obj_def = None
        if category in self.registry:
            for obj in self.registry[category]:
                if obj['name'] == obj_type:
                    obj_def = obj
                    break
        
        if not obj_def:
            return
            
        # Create widgets for parameters
        for param in obj_def['params']:
            name = param['name']
            desc = param['description']
            default = param['default']
            ptype = param['type']
            
            current_val = self.current_block.params.get(name, default)
            if current_val is None:
                current_val = ""
            
            label = QLabel(name)
            label.setToolTip(desc)
            
            if ptype == 'bool':
                widget = QCheckBox()
                widget.setChecked(str(current_val).lower() in ('true', '1', 'yes'))
                widget.stateChanged.connect(lambda state, n=name: self.on_param_changed(n, "true" if state else "false"))
            else:
                widget = QLineEdit(str(current_val))
                widget.textChanged.connect(lambda val, n=name: self.on_param_changed(n, val))
                
            self.params_layout.addRow(label, widget)

    def on_name_changed(self, text):
        if not self.block_updating and self.current_block:
            self.nameChanged.emit(text)

    def on_category_changed(self, text):
        if not self.block_updating and self.current_block:
            self.update_type_combo(text)
            # Select first type by default
            if self.type_combo.count() > 0:
                new_type = self.type_combo.itemText(0)
                self.typeChanged.emit(new_type)
            self.categoryChanged.emit(text)
            self.update_params_ui()

    def on_type_changed(self, text):
        if not self.block_updating and self.current_block:
            self.typeChanged.emit(text)
            self.update_params_ui()

    def on_param_changed(self, name, value):
        if not self.block_updating and self.current_block:
            self.paramChanged.emit(name, value)
