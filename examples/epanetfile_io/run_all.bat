@echo off
REM Run all epanetfile_io examples in series
REM Supported on: Windows (7 and later)
REM Usage: run_all.bat

echo.
echo ==========================================
echo Running HydroForge epanetfile_io Examples
echo ==========================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Run each example in order
echo [1/1] Running ex1.py...
echo ------------------------------------------
python "%SCRIPT_DIR%ex1.py"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: ex1.py failed!
    exit /b %errorlevel%
)
echo.

echo ==========================================
echo All examples completed successfully!
echo ==========================================
pause
