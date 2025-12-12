from PyQt5.QtWidgets import (QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem, 
                             QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, 
                             QGraphicsPathItem, QVBoxLayout, QMenu, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QLinearGradient, QFont, QPainterPath

class Block:
    def __init__(self, id, name, category, type_name):
        self.id = id
        self.name = name
        self.category = category
        self.type = type_name
        self.params = {}
        self.pos = (0, 0)
        self.connections = [] # list of dicts: {'target_id': id, 'start_port': idx, 'end_port': idx}

class PortItem(QGraphicsRectItem):
    def __init__(self, parent, x, y, index):
        super().__init__(0, 0, 10, 10, parent)
        self.setPos(x, y)
        self.index = index
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(Qt.black, 1))
        self.setAcceptHoverEvents(True)
        self.setOpacity(0.0) # Invisible by default
        self.is_hovered = False

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.setOpacity(1.0)
        self.setBrush(QBrush(QColor(0, 255, 0))) # Green when hovered
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        if not self.parentItem().is_hovered:
            self.setOpacity(0.0)
        else:
            self.setOpacity(0.5) # Dim when parent hovered
            self.setBrush(QBrush(QColor(255, 255, 255)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # Start connection
        self.scene().editor.start_connection(self)
        event.accept()

class BlockItem(QGraphicsPathItem):
    def __init__(self, block, editor):
        super().__init__()
        self.block = block
        self.editor = editor
        self.width = 160
        self.height = 80
        
        # Shape
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 10, 10)
        self.setPath(path)
        
        # Flags
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(3, 3)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)
        
        self.setPos(block.pos[0], block.pos[1])
        
        # Ports (Top, Right, Bottom, Left)
        self.ports = []
        # Top (0)
        self.ports.append(PortItem(self, self.width/2 - 5, -5, 0))
        # Right (1)
        self.ports.append(PortItem(self, self.width - 5, self.height/2 - 5, 1))
        # Bottom (2)
        self.ports.append(PortItem(self, self.width/2 - 5, self.height - 5, 2))
        # Left (3)
        self.ports.append(PortItem(self, -5, self.height/2 - 5, 3))
        
        self.is_hovered = False

    def paint(self, painter, option, widget):
        # Background Gradient
        grad = QLinearGradient(0, 0, 0, self.height)
        if self.isSelected():
            grad.setColorAt(0.0, QColor(60, 60, 60))
            grad.setColorAt(1.0, QColor(30, 30, 30))
            painter.setPen(QPen(QColor(255, 165, 0), 2)) # Orange border when selected
        else:
            grad.setColorAt(0.0, QColor(50, 50, 50))
            grad.setColorAt(1.0, QColor(20, 20, 20))
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            
        painter.setBrush(QBrush(grad))
        painter.drawPath(self.path())
        
        # Glossy highlight
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(1, 1, self.width-2, self.height/2, 10, 10)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawPath(highlight_path)
        
        # Text
        painter.setPen(Qt.white)
        font_title = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font_title)
        painter.drawText(QRectF(10, 10, self.width-20, 20), Qt.AlignLeft, f"[{self.block.name}]")
        
        font_cat = QFont("Segoe UI", 8)
        painter.setFont(font_cat)
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(QRectF(10, 35, self.width-20, 20), Qt.AlignLeft, self.block.category)
        
        font_type = QFont("Segoe UI", 8)
        font_type.setItalic(True)
        painter.setFont(font_type)
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(QRectF(10, 55, self.width-20, 20), Qt.AlignLeft, self.block.type)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        for port in self.ports:
            port.setOpacity(0.5)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        for port in self.ports:
            port.setOpacity(0.0)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.block.pos = (value.x(), value.y())
            self.editor.update_connections()
            self.editor.set_modified(True)
        return super().itemChange(change, value)

    def update_text(self):
        self.update()

class ConnectionItem(QGraphicsPathItem):
    def __init__(self, start_port, end_port):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.start_item = start_port.parentItem()
        self.end_item = end_port.parentItem()
        self.setPen(QPen(QColor(200, 200, 200), 2))
        self.setZValue(-1) # Behind blocks
        self.update_pos()

    def update_pos(self):
        # Calculate exact port positions
        start_pos = self.start_port.scenePos() + QPointF(5, 5) # Center of 10x10 port
        end_pos = self.end_port.scenePos() + QPointF(5, 5)
        
        path = QPainterPath()
        path.moveTo(start_pos)
        
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        
        # Control points depend on port orientation
        # 0: Top, 1: Right, 2: Bottom, 3: Left
        
        ctrl1 = QPointF(start_pos)
        ctrl2 = QPointF(end_pos)
        
        # Heuristic for control point distance
        # Base distance on Euclidean distance but clamp it
        import math
        euclidean_dist = math.sqrt(dx*dx + dy*dy)
        dist = min(euclidean_dist * 0.5, 150) # Clamp to 150 max
        dist = max(dist, 20) # Minimum 20
        
        if self.start_port.index == 0: # Top
            ctrl1 += QPointF(0, -dist)
        elif self.start_port.index == 1: # Right
            ctrl1 += QPointF(dist, 0)
        elif self.start_port.index == 2: # Bottom
            ctrl1 += QPointF(0, dist)
        elif self.start_port.index == 3: # Left
            ctrl1 += QPointF(-dist, 0)
            
        if self.end_port.index == 0: # Top
            ctrl2 += QPointF(0, -dist)
        elif self.end_port.index == 1: # Right
            ctrl2 += QPointF(dist, 0)
        elif self.end_port.index == 2: # Bottom
            ctrl2 += QPointF(0, dist)
        elif self.end_port.index == 3: # Left
            ctrl2 += QPointF(-dist, 0)
        
        path.cubicTo(ctrl1, ctrl2, end_pos)
        self.setPath(path)

class NodeScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = parent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.editor.remove_selected_blocks()
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        if self.editor.connecting_line:
            line = QLineF(self.editor.connecting_start_pos, event.scenePos())
            self.editor.connecting_line.setLine(line)
            
            # Manual hover logic
            items = self.items(event.scenePos())
            found_port = None
            for item in items:
                if isinstance(item, PortItem) and item != self.editor.connecting_source:
                    found_port = item
                    break
            
            if found_port:
                found_port.setOpacity(1.0)
                found_port.setBrush(QBrush(QColor(0, 255, 0)))
            
            if self.editor.hovered_port and self.editor.hovered_port != found_port:
                self.editor.hovered_port.setOpacity(0.5) # Back to dim
                self.editor.hovered_port.setBrush(QBrush(QColor(255, 255, 255)))
            
            self.editor.hovered_port = found_port
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.editor.connecting_line:
            if self.editor.hovered_port:
                self.editor.finish_connection(self.editor.hovered_port)
            else:
                self.editor.cancel_connection()
        super().mouseReleaseEvent(event)

class FlowView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self.editor = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if "|" in text:
                category, type_name = text.split("|")
                pos = self.mapToScene(event.pos())
                self.editor.add_block_at(category, type_name, pos.x(), pos.y())
            event.acceptProposedAction()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
            else:
                zoom_factor = zoom_out_factor
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

class NodeEditor(QWidget):
    selectionChanged = pyqtSignal(object)
    modified = pyqtSignal(bool)
    
    SINGLETON_CATEGORIES = ['Domain', 'Problem', 'Executioner', 'Mesh', 'GlobalParams']

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.blocks = {} # id -> Block
        self.items = {} # id -> BlockItem
        self.connections = [] # list of ConnectionItem
        self.next_id = 1
        self.is_modified = False
        
        self.scene = NodeScene(self)
        self.scene.setSceneRect(0, 0, 5000, 5000)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        
        self.view = FlowView(self.scene, self)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        
        # Connection creation state
        self.connecting_source = None
        self.connecting_line = None
        self.connecting_start_pos = None
        self.hovered_port = None

    def set_modified(self, value=True):
        if self.is_modified != value:
            self.is_modified = value
            self.modified.emit(value)

    def add_block_at(self, category, type_name, x, y):
        # If singleton, name it same as category
        name = f"Block_{self.next_id}"
        if category in self.SINGLETON_CATEGORIES:
            name = category
            
        block = Block(self.next_id, name, category, type_name)
        self.next_id += 1
        block.pos = (x, y)
        
        self.blocks[block.id] = block
        
        item = BlockItem(block, self)
        self.scene.addItem(item)
        self.items[block.id] = item
        
        # Select the new block
        self.scene.clearSelection()
        item.setSelected(True)
        self.set_modified(True)

    def remove_selected_blocks(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
            
        blocks_to_remove = []
        for item in selected_items:
            if isinstance(item, BlockItem):
                blocks_to_remove.append(item.block.id)
        
        if not blocks_to_remove:
            return
            
        for block_id in blocks_to_remove:
            self.remove_block(block_id)
            
        self.set_modified(True)
        self.selectionChanged.emit(None)

    def remove_block(self, block_id):
        if block_id not in self.blocks:
            return
            
        # Remove connections involving this block
        # 1. Connections where this block is source
        block = self.blocks[block_id]
        # We need to find connection items that have this block as source or target
        
        conns_to_remove = []
        for conn in self.connections:
            if conn.start_item.block.id == block_id or conn.end_item.block.id == block_id:
                conns_to_remove.append(conn)
        
        for conn in conns_to_remove:
            self.scene.removeItem(conn)
            self.connections.remove(conn)
            
            # Update data model
            source_id = conn.start_item.block.id
            target_id = conn.end_item.block.id
            
            if source_id in self.blocks:
                # Remove from connections list
                # Need to handle both legacy and new format
                new_conns = []
                for c in self.blocks[source_id].connections:
                    if isinstance(c, dict):
                        if c['target_id'] != target_id:
                            new_conns.append(c)
                    else:
                        if c != target_id:
                            new_conns.append(c)
                self.blocks[source_id].connections = new_conns

        # Remove block item
        item = self.items[block_id]
        self.scene.removeItem(item)
        del self.items[block_id]
        del self.blocks[block_id]


    def start_connection(self, source_port):
        self.connecting_source = source_port
        self.connecting_start_pos = source_port.scenePos() + QPointF(5, 5)
        
        self.connecting_line = QGraphicsLineItem(QLineF(self.connecting_start_pos, self.connecting_start_pos))
        self.connecting_line.setPen(QPen(Qt.white, 2, Qt.DashLine))
        self.scene.addItem(self.connecting_line)
        
        # Show all ports
        for item in self.items.values():
            for port in item.ports:
                port.setOpacity(0.5)

    def finish_connection(self, target_port):
        # Create permanent connection
        source_block = self.connecting_source.parentItem().block
        target_block = target_port.parentItem().block
        
        source_id = source_block.id
        target_id = target_block.id
        
        # Check if connection already exists
        exists = False
        for conn in source_block.connections:
            if isinstance(conn, dict):
                if conn['target_id'] == target_id and conn['start_port'] == self.connecting_source.index and conn['end_port'] == target_port.index:
                    exists = True
                    break
            else:
                # Legacy format
                if conn == target_id:
                    exists = True
                    break
        
        if not exists:
            # Store connection info
            conn_info = {
                'target_id': target_id,
                'start_port': self.connecting_source.index,
                'end_port': target_port.index
            }
            source_block.connections.append(conn_info)
            
            conn_item = ConnectionItem(self.connecting_source, target_port)
            self.scene.addItem(conn_item)
            self.connections.append(conn_item)
            self.set_modified(True)
            
        self.cancel_connection()

    def cancel_connection(self):
        if self.connecting_line:
            self.scene.removeItem(self.connecting_line)
            self.connecting_line = None
        self.connecting_source = None
        self.connecting_start_pos = None
        
        # Hide all ports
        for item in self.items.values():
            for port in item.ports:
                port.setOpacity(0.0)
                port.setBrush(QBrush(QColor(255, 255, 255)))
        self.hovered_port = None

    def add_block(self):
        # Default block
        category = list(self.registry.keys())[0] if self.registry else "Unknown"
        obj_type = self.registry[category][0]['name'] if self.registry and category in self.registry else "Unknown"
        
        # Place in center of view
        center = self.view.mapToScene(self.view.viewport().rect().center())
        self.add_block_at(category, obj_type, center.x(), center.y())

    def on_scene_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if selected_items and isinstance(selected_items[0], BlockItem):
            self.selectionChanged.emit(selected_items[0].block)
        else:
            self.selectionChanged.emit(None)

    def update_selected_block_name(self, name):
        selected = self.get_selected_block()
        if selected:
            selected.name = name
            self.items[selected.id].update_text()
            self.set_modified(True)

    def update_selected_block_category(self, category):
        selected = self.get_selected_block()
        if selected:
            selected.category = category
            self.items[selected.id].update_text()
            self.set_modified(True)

    def update_selected_block_type(self, type_name):
        selected = self.get_selected_block()
        if selected:
            selected.type = type_name
            self.set_modified(True)

    def update_selected_block_param(self, name, value):
        selected = self.get_selected_block()
        if selected:
            selected.params[name] = value
            self.set_modified(True)

    def get_selected_block(self):
        selected_items = self.scene.selectedItems()
        if selected_items and isinstance(selected_items[0], BlockItem):
            return selected_items[0].block
        return None

    def update_connections(self):
        for conn in self.connections:
            conn.update_pos()

    # Serialization
    def serialize(self):
        data = {
            "blocks": [],
            "connections": []
        }
        for block in self.blocks.values():
            data["blocks"].append({
                "id": block.id,
                "name": block.name,
                "category": block.category,
                "type": block.type,
                "params": block.params,
                "pos": block.pos
            })
            for conn in block.connections:
                if isinstance(conn, dict):
                    data["connections"].append(conn | {'source_id': block.id})
                else:
                    # Legacy
                    data["connections"].append({'source_id': block.id, 'target_id': conn, 'start_port': 1, 'end_port': 3})
        return data

    def deserialize(self, data):
        self.scene.clear()
        self.blocks.clear()
        self.items.clear()
        self.connections.clear()
        
        max_id = 0
        for b_data in data["blocks"]:
            block = Block(b_data["id"], b_data["name"], b_data["category"], b_data["type"])
            block.params = b_data["params"]
            block.pos = tuple(b_data["pos"])
            self.blocks[block.id] = block
            
            item = BlockItem(block, self)
            self.scene.addItem(item)
            self.items[block.id] = item
            
            if block.id > max_id:
                max_id = block.id
                
        self.next_id = max_id + 1
        
        for conn_data in data["connections"]:
            if isinstance(conn_data, list):
                # Legacy format [source, target]
                source_id, target_id = conn_data
                start_port_idx = 1 # Right
                end_port_idx = 3 # Left
            else:
                source_id = conn_data['source_id']
                target_id = conn_data['target_id']
                start_port_idx = conn_data.get('start_port', 1)
                end_port_idx = conn_data.get('end_port', 3)
            
            if source_id in self.blocks and target_id in self.blocks:
                conn_info = {
                    'target_id': target_id,
                    'start_port': start_port_idx,
                    'end_port': end_port_idx
                }
                self.blocks[source_id].connections.append(conn_info)
                
                # Create visual connection
                source_item = self.items[source_id]
                target_item = self.items[target_id]
                
                start_port = source_item.ports[start_port_idx]
                end_port = target_item.ports[end_port_idx]
                
                conn_item = ConnectionItem(start_port, end_port)
                self.scene.addItem(conn_item)
                self.connections.append(conn_item)
        
        self.reset_view()
        self.set_modified(False)

    def reset_view(self):
        # Center on the content
        if self.items:
            rect = self.scene.itemsBoundingRect()
            self.view.fitInView(rect, Qt.KeepAspectRatio)
            # Zoom out a bit if needed, or just ensure it's visible
            # fitInView might zoom too much if few items.
            # Let's just center on 0,0 or the first item
            self.view.centerOn(rect.center())
            self.view.resetTransform()
        else:
            self.view.centerOn(0, 0)

    def generate_input_content(self):
        lines = []
        
        # Group by category
        categories = {}
        for block in self.blocks.values():
            if block.category not in categories:
                categories[block.category] = []
            categories[block.category].append(block)
            
        for cat, blocks in categories.items():
            if cat in self.SINGLETON_CATEGORIES:
                # Singleton block: [Category] ... []
                # We assume only one block per singleton category, or we merge them?
                # Usually there is only one. If multiple, we might have issues.
                # Let's take the first one.
                if not blocks: continue
                block = blocks[0]
                
                lines.append(f"[{cat}]")
                # For Problem/Executioner/Mesh, we might need 'type = ...'
                # For Domain, we usually don't need 'type = ...' unless it's a specific action param?
                # DomainAction doesn't have a 'type' param in the input file usually.
                # But Problem does.
                
                if cat != "Domain":
                     lines.append(f"  type = {block.type}")
                     
                for pname, pval in block.params.items():
                    if pval:
                        lines.append(f"  {pname} = {pval}")
                lines.append(f"[]")
                lines.append("")
            else:
                # Container block: [Category] -> [Name] -> type=...
                lines.append(f"[{cat}]")
                for block in blocks:
                    lines.append(f"  [{block.name}]")
                    lines.append(f"    type = {block.type}")
                    for pname, pval in block.params.items():
                        if pval:
                            lines.append(f"    {pname} = {pval}")
                    lines.append(f"  []")
                lines.append(f"[]")
                lines.append("")
            
        return "\n".join(lines)
