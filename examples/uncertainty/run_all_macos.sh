#!/bin/bash

# Run all uncertainty examples in series
# Optimized for: Apple macOS (Intel and Apple Silicon)
# Also works on: Linux and other Unix-like systems
# Usage: ./run_all_macos.sh or chmod +x run_all_macos.sh && ./run_all_macos.sh

set -e  # Exit on first error

echo "=========================================="
echo "Running HydroForge Uncertainty Examples"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found!"
    echo "Please install Python 3.8 or later."
    exit 1
fi

# Track timing
START_TIME=$(date +%s)

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

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "=========================================="
echo "All examples completed successfully!"
echo "Execution time: ${ELAPSED}s"
echo "=========================================="

# Display macOS notification if available
if command -v osascript &> /dev/null; then
    osascript -e "display notification \"All HydroForge examples completed in ${ELAPSED}s\" with title \"HydroForge Examples\""
fi
