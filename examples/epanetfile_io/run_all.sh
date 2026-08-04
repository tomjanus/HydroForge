#!/bin/bash

# Run all epanetfile_io examples in series
# Supported on: Linux, macOS, and other Unix-like systems
# Usage: ./run_all.sh

set -e  # Exit on first error

echo "=========================================="
echo "Running HydroForge epanetfile_io Examples"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run each example in order
echo "[1/1] Running ex1.py..."
echo "----------------------------------------------"
python3 "$SCRIPT_DIR/ex1.py"
echo ""

echo "=========================================="
echo "All examples completed successfully!"
echo "=========================================="
