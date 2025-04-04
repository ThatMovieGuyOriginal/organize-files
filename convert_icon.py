import os

from PIL import Image

# Ensure directories exist
os.makedirs("organize_gui/resources/icons", exist_ok=True)

# Create a simple colored square as an icon
img = Image.new('RGB', (256, 256), color=(74, 134, 232))  # Blue color similar to the SVG
ico_path = "organize_gui/resources/icons/app_icon.ico"

# Save as ICO
print("Creating ICO file...")
img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

# Also save as PNG for other uses
png_path = "organize_gui/resources/icons/app_icon.png"
img.save(png_path, format='PNG')

print(f"Icon creation complete. Icon saved to {ico_path}")