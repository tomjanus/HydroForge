@echo off
REM Run all uncertainty examples in series
REM Supported on: Windows (7 and later)
REM Usage: run_all.bat

echo.
echo ==========================================
echo Running HydroForge Uncertainty Examples
echo ==========================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Run each example in order
echo [1/3] Running ex1_pdfs.py...
echo ------------------------------------------
python "%SCRIPT_DIR%ex1_pdfs.py"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: ex1_pdfs.py failed!
    exit /b %errorlevel%
)
echo.

echo [2/3] Running ex2_uncertainties.py...
echo ------------------------------------------
python "%SCRIPT_DIR%ex2_uncertainties.py"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: ex2_uncertainties.py failed!
    exit /b %errorlevel%
)
echo.

echo [3/3] Running ex3_parameters.py...
echo ------------------------------------------
python "%SCRIPT_DIR%ex3_parameters.py"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: ex3_parameters.py failed!
    exit /b %errorlevel%
)
echo.

echo ==========================================
echo All examples completed successfully!
echo ==========================================
pause
