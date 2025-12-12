# Marlin GUI

This is a graphical user interface for generating input files for the Marlin optimization framework.

## Requirements

- Python 3
- PyQt5

To install PyQt5:
```bash
pip install PyQt5
```

## Usage

1. Run the GUI:
   ```bash
   python3 gui/main.py
   ```

2. **Add Block**: Click "Add Block" in the toolbar to create a new block.
3. **Select Category**: Use the "Category" dropdown in the Properties panel to select the block type (e.g., `TensorComputes`, `TensorSolver`).
4. **Select Type**: Use the "Type" dropdown to select the specific object (e.g., `RandomTensor`).
5. **Edit Parameters**: Fill in the parameters in the Properties panel.
6. **Connect Blocks**: Drag from the output port (black circle) of one block to another block to connect them.
7. **Generate Input**: Click "Generate Input" to save the `.i` file.
8. **Run**: Click "Run" to execute Marlin with the generated input.

## Updating the Registry

If you add new objects to the C++ source code, run the scanner to update the registry:
```bash
python3 gui/scanner.py
```
This will update `gui/registry.json` with the new objects and parameters.
