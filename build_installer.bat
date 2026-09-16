@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\TailoringManagementSystem\TailoringManagementSystem.exe" (
    echo Build the application first with build.bat.
    exit /b 1
)

set "ISCC=%PROGRAMFILES(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%PROGRAMFILES%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 was not found.
    echo Install Inno Setup, then run this script again.
    exit /b 1
)

if not exist installer\output mkdir installer\output
"%ISCC%" installer\TailoringManagementSystem.iss

if not exist "installer\output\TailoringManagementSystem_Setup.exe" (
    echo Installer build failed.
    exit /b 1
)

echo.
echo Installer created:
echo %CD%\installer\output\TailoringManagementSystem_Setup.exe
endlocal