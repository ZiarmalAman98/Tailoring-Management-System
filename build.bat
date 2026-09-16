@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Install Python 3.12+ first.
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller TailoringManagementSystem.spec --noconfirm --clean

if not exist "dist\TailoringManagementSystem\TailoringManagementSystem.exe" (
    echo Build failed: EXE was not created.
    exit /b 1
)

echo.
echo Windows application created:
echo %CD%\dist\TailoringManagementSystem\TailoringManagementSystem.exe
endlocal