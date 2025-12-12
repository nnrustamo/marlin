import os
import re
import json
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
print(f"Scanning {SRC_DIR}", file=sys.stderr)

DIR_MAPPING = {
    'tensor_computes': 'TensorComputes',
    'tensor_solver': 'TensorSolver',
    'tensor_outputs': 'TensorOutputs',
    'tensor_predictor': 'TensorPredictor',
    'tensor_buffers': 'TensorBuffers',
    'tensor_timeintegrators': 'TensorTimeIntegrators',
    'timesteppers': 'TimeStepper',
    'stencils': 'Stencils',
    'auxkernels': 'AuxKernels',
    'functions': 'Functions',
    'postprocessors': 'Postprocessors',
    'vectorpostprocessors': 'VectorPostprocessors',
    'meshgenerators': 'MeshGenerators',
    'partitioner': 'Partitioner',
    'problems': 'Problem',
    'mesh': 'Mesh',
    'actions': 'Actions',
    'base': 'Base'
}

def parse_params(content):
    params = []
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('//'): continue
        
        # params.addParam<Type>("name", default, "doc")
        # We need to handle cases where default is a string literal "val" or a number.
        # Regex: params.addParam(?:<Type>)?("name", default, "doc")
        
        # Try to match addParam
        match = re.search(r'params\.add(?:RangeChecked)?Param(?:<([^>]+)>)?\s*\(\s*"([^"]+)"\s*,\s*(.+?)\s*,\s*"([^"]+)"\s*\)', line)
        if match:
            dtype = match.group(1) or "Unknown"
            name = match.group(2)
            default_val = match.group(3)
            doc = match.group(4)
            
            # Clean up default value (remove quotes if string)
            if default_val.startswith('"') and default_val.endswith('"'):
                default_val = default_val[1:-1]
                
            params.append({
                "name": name,
                "type": dtype,
                "default": default_val,
                "description": doc,
                "required": False
            })
            continue

        # Try to match addRequiredParam
        match = re.search(r'params\.addRequired(?:RangeChecked)?Param(?:<([^>]+)>)?\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', line)
        if match:
            dtype = match.group(1) or "Unknown"
            name = match.group(2)
            doc = match.group(3)
            params.append({
                "name": name,
                "type": dtype,
                "default": None,
                "description": doc,
                "required": True
            })
            continue
            
    return params

def scan_repository():
    registry = {}
    
    for root, dirs, files in os.walk(SRC_DIR):
        rel_path = os.path.relpath(root, SRC_DIR)
        if rel_path == '.': continue
        
        category = DIR_MAPPING.get(rel_path, rel_path)
        
        for file in files:
            if file.endswith('.C'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                matches = re.findall(r'registerMooseObject\s*\(\s*"[^"]+"\s*,\s*(\w+)\s*\)', content)
                
                # Also find registerMooseAction for Domain
                action_matches = re.findall(r'registerMooseAction\s*\(\s*"[^"]+"\s*,\s*(\w+)\s*,\s*"[^"]+"\s*\)', content)

                if matches or action_matches:
                    params = parse_params(content)
                    
                    for obj_name in matches:
                        if category not in registry:
                            registry[category] = []
                        
                        registry[category].append({
                            "name": obj_name,
                            "params": params,
                            "file": rel_path + "/" + file
                        })
                    
                    for action_name in action_matches:
                        if action_name == "DomainAction":
                            cat = "Domain"
                            name = "Domain"
                            if cat not in registry:
                                registry[cat] = []
                            registry[cat].append({
                                "name": name,
                                "params": params,
                                "file": rel_path + "/" + file
                            })
                        
    return registry

if __name__ == "__main__":
    data = scan_repository()
    with open(os.path.join(os.path.dirname(__file__), 'registry.json'), 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Registry saved to {os.path.join(os.path.dirname(__file__), 'registry.json')}")
