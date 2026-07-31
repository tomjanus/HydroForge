#!/bin/bash

# Run all uncertainty examples in series
# Supported on: Linux, macOS, and other Unix-like systems
# Usage: ./run_all.sh

set -e  # Exit on first error

echo "=========================================="
echo "Running HydroForge Uncertainty Examples"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run each example in order
echo "[1/3] Running ex1_pdfs.py..."
echo "----------------------------------------------"
python3 "$SCRIPT_DIR/ex1_pdfs.py"
echo ""

echo "[2/3] Running ex2_uncertainties.py..."
echo "----------------------------------------------"
python3 "$SCRIPT_DIR/ex2_uncertainties.py"
echo ""

echo "[3/3] Running ex3_parameters.py..."
echo "----------------------------------------------"
python3 "$SCRIPT_DIR/ex3_parameters.py"
echo ""

echo "=========================================="
echo "All examples completed successfully!"
echo "=========================================="
