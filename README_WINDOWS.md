# Tailoring Management System — Windows build

This folder contains the native Windows desktop build source. It uses PySide6 for the UI, SQLAlchemy with SQLite for local storage, and stores business data outside Program Files:

```text
%LOCALAPPDATA%\TailoringManagementSystem\
├── data\tailoring.db
├── backups\
├── documents\
├── images\
└── logs\
```

## Development login

```text
Username: admin
Password: admin123
```

Change the initial password before production use.

## Build the EXE on Windows

Install Python 3.12+ and run:

```bat
build.bat
```

Output:

```text
dist\TailoringManagementSystem\TailoringManagementSystem.exe
```

## Build the installer

Install Inno Setup 6, then run:

```bat
build_installer.bat
```

Output:

```text
installer\output\TailoringManagementSystem_Setup.exe
```

The installer keeps business data in `%LOCALAPPDATA%` so application updates do not delete the database.