# setup.py
import os
import shutil
import sys
from pathlib import Path
from subprocess import run

from setuptools import find_packages, setup


# Convert SVG to PNG for app icon
def convert_svg_to_png():
    try:
        from cairosvg import svg2png

        # Convert app icon
        svg_path = "organize_gui/resources/icons/app_icon.svg"
        png_path = "organize_gui/resources/icons/app_icon.png"
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        
        # Convert SVG to PNG
        with open(svg_path, "rb") as svg_file:
            svg_data = svg_file.read()
            svg2png(bytestring=svg_data, write_to=png_path, output_width=256, output_height=256)
            
    except ImportError:
        print("cairosvg not found, skipping SVG to PNG conversion")
        
        # Copy placeholder icon if available
        placeholder = "organize_gui/resources/icons/placeholder.png"
        if os.path.isfile(placeholder):
            shutil.copy(placeholder, "organize_gui/resources/icons/app_icon.png")


# Additional data files to include
def get_data_files():
    data_files = []
    
    # Include resources
    resources_dir = Path("organize_gui/resources")
    if resources_dir.exists():
        for subdir, dirs, files in os.walk(resources_dir):
            for file in files:
                file_path = os.path.join(subdir, file)
                dir_path = os.path.dirname(file_path)
                data_files.append((dir_path, [file_path]))
                
    return data_files


# Entry points
entry_points = {
    'console_scripts': [
        'organize-gui=organize_gui.main:main',
    ],
    'gui_scripts': [
        'organize-gui=organize_gui.main:main',
    ],
}


# Run setup
if __name__ == "__main__":
    # Convert SVG to PNG
    convert_svg_to_png()
    
    setup(
        name="organize-gui",
        version="3.5.0",
        description="GUI for the organize file management automation tool",
        author="Your Name",
        author_email="your.email@example.com",
        packages=find_packages(),
        install_requires=[
            "organize-tool>=3.3.0",
            "PyQt6>=6.0.0",
            "cairosvg>=2.5.0",
        ],
        entry_points=entry_points,
        data_files=get_data_files(),
        python_requires=">=3.9",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: X11 Applications :: Qt",
            "Intended Audience :: End Users/Desktop",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Topic :: Utilities",
        ],
    )