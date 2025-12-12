import re

class MarlinImporter:
    def __init__(self):
        self.current_id = 1
        self.SINGLETON_CATEGORIES = ['Domain', 'Problem', 'Executioner', 'Mesh', 'GlobalParams']

    def parse(self, content):
        print("Starting parse...")
        lines = content.splitlines()
        stack = []
        root_blocks = []
        
        # Simple stack-based parser
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Remove inline comments
            if '#' in line:
                line = line.split('#')[0].strip()
                
            if line.startswith('[') and line.endswith(']'):
                tag = line[1:-1].strip()
                # print(f"Line {line_num}: Tag found: '{tag}'")
                
                if tag == '../' or tag == '':
                    # Close block
                    if stack:
                        block = stack.pop()
                        # print(f"Closed block: {block['name']}")
                        if stack:
                            stack[-1]['children'].append(block)
                        else:
                            root_blocks.append(block)
                    else:
                        print(f"Warning: Unmatched closing bracket at line {line_num}")
                elif tag.startswith('./'):
                    # Subblock
                    name = tag[2:]
                    stack.append({'name': name, 'params': {}, 'children': []})
                else:
                    # New block
                    name = tag
                    stack.append({'name': name, 'params': {}, 'children': []})
            elif '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().strip("'\"")
                    if stack:
                        stack[-1]['params'][key] = val
        
        print(f"Found {len(root_blocks)} root blocks.")
        # Convert to NodeEditor format
        nodes = []
        connections = []
        
        x_pos = 0
        y_pos = 0
        
        for block in root_blocks:
            cat = block['name']
            print(f"Processing root block: {cat}")
            
            if cat in self.SINGLETON_CATEGORIES:
                # Singleton
                node = {
                    "id": self.current_id,
                    "name": cat,
                    "category": cat,
                    "type": block['params'].get('type', cat),
                    "params": block['params'],
                    "pos": [x_pos, y_pos]
                }
                nodes.append(node)
                self.current_id += 1
                x_pos += 250
            else:
                # Container
                # Flatten children
                flat_children = self.flatten_children(block)
                print(f"  Found {len(flat_children)} children in {cat}")
                
                # Reset Y for new category column
                y_pos = 0
                
                for child in flat_children:
                    # Determine type
                    # If type is not in params, use name or Unknown
                    obj_type = child['params'].get('type', 'Unknown')
                    
                    node = {
                        "id": self.current_id,
                        "name": child['name'],
                        "category": cat,
                        "type": obj_type,
                        "params": child['params'],
                        "pos": [x_pos, y_pos]
                    }
                    nodes.append(node)
                    self.current_id += 1
                    y_pos += 150
                
                if flat_children:
                    x_pos += 250
        
        print(f"Generated {len(nodes)} nodes.")
        return {"blocks": nodes, "connections": connections}

    def flatten_children(self, block):
        results = []
        for child in block['children']:
            # If child has 'type', it's definitely an object
            if 'type' in child['params']:
                 results.append(child)
            
            # If child has children, recurse
            if child['children']:
                results.extend(self.flatten_children(child))
            elif 'type' not in child['params']:
                # Leaf node without type. 
                # In some cases (like TensorBuffers), the name IS the object and type is inferred or not needed.
                # e.g. [c] inside [TensorBuffers]
                results.append(child)
                
        return results
