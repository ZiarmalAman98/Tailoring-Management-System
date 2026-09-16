#define MyAppName "Tailoring Management System"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Tailoring Management System"
#define MyAppExeName "TailoringManagementSystem.exe"

[Setup]
AppId={{A28D8A4B-4D11-4B6F-9D87-TAILORING0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Tailoring Management System
DefaultGroupName=Tailoring Management System
OutputDir=output
OutputBaseFilename=TailoringManagementSystem_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
Uninstallable=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\TailoringManagementSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tailoring Management System"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Tailoring Management System"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Tailoring Management System"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\TailoringManagementSystem\logs"