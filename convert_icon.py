import os
import sys
try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image

try:
    img_path = r"C:\Users\Abdulaziz\.gemini\antigravity\brain\d70e593d-f81c-4f55-b9f8-1dcc5419de96\audio_icon_1773921524821.png"
    ico_path = r"c:\Users\Abdulaziz\Desktop\Script\app_icon.ico"
    img = Image.open(img_path)
    # Ensure it's square and resized properly for an icon
    img = img.resize((256, 256), Image.Resampling.LANCZOS)
    img.save(ico_path, format="ICO", sizes=[(256, 256)])
    print("Conversion Successful")
except Exception as e:
    print(f"Error during conversion: {e}")
