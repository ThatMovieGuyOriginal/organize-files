# build_exe.py
import os
import sys

from cx_Freeze import Executable, setup

# Add any additional modules that may be needed
additional_modules = []

# Add any packages that need to be included
packages = ["organize", "organize_gui"]

# Build options
build_options = {
    "packages": packages,
    "excludes": [],
    "include_files": [
        "organize_gui/resources",
    ],
    "optimize": 2,
}

# Base for GUI applications
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# Create the executable
executables = [
    Executable(
        "organize_gui/main.py",
        base=base,
        target_name="OrganizeTool.exe",
        icon="organize_gui/resources/icons/app_icon.ico",
        shortcut_name="Organize Tool",
        shortcut_dir="ProgramMenuFolder",
    )
]

# Run setup
setup(
    name="organize-gui",
    version="3.5.0",
    description="GUI for the organize file management automation tool",
    options={"build_exe": build_options},
    executables=executables,
)