from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag

class LibraryWidget(QTreeWidget):
    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        self.setHeaderLabel("Library")
        self.setDragEnabled(True)
        self.populate()

    def populate(self):
        self.clear()
        # Sort categories
        for category in sorted(self.registry.keys()):
            cat_item = QTreeWidgetItem(self)
            cat_item.setText(0, category)
            cat_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            
            # Sort types
            types = sorted([obj['name'] for obj in self.registry[category]])
            # Deduplicate
            types = sorted(list(set(types)))
            
            for type_name in types:
                type_item = QTreeWidgetItem(cat_item)
                type_item.setText(0, type_name)
                type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item or item.childCount() > 0: # Only drag leaf nodes (types)
            return
            
        type_name = item.text(0)
        category = item.parent().text(0)
        
        mime_data = QMimeData()
        mime_data.setText(f"{category}|{type_name}")
        
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction)
