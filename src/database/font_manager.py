"""
Font Manager
Path: src/database/font_manager.py
"""

import os
import random
from typing import List, Optional


class FontManager:
    """Manages handwritten fonts for cipher generation"""

    def __init__(self, fonts_dir: str = "fonts/handwritten"):
        self.fonts_dir = fonts_dir
        self.available_fonts = []
        self._scan_fonts()

    def _scan_fonts(self):
        """Scan fonts directory for available font files"""
        if not os.path.exists(self.fonts_dir):
            os.makedirs(self.fonts_dir, exist_ok=True)
            print(f"Created fonts directory: {self.fonts_dir}")
            print("Please add .ttf or .otf font files to this directory")
            return

        # Supported font extensions
        font_extensions = ('.ttf', '.otf', '.TTF', '.OTF')

        # Scan directory
        for filename in os.listdir(self.fonts_dir):
            if filename.endswith(font_extensions):
                font_path = os.path.join(self.fonts_dir, filename)
                self.available_fonts.append({
                    'name': os.path.splitext(filename)[0],
                    'path': font_path,
                    'filename': filename
                })

        if self.available_fonts:
            print(f"Found {len(self.available_fonts)} fonts:")
            for font in self.available_fonts:
                print(f"  - {font['name']}")
        else:
            print(f"No fonts found in {self.fonts_dir}")
            print("Add .ttf or .otf files to use custom fonts")

    def get_random_font(self) -> Optional[str]:
        """Get a random font path from available fonts"""
        if not self.available_fonts:
            print("Warning: No custom fonts available, using system default")
            return None

        font = random.choice(self.available_fonts)
        print(f"Selected font: {font['name']}")
        return font['path']

    def get_font_by_name(self, name: str) -> Optional[str]:
        """Get specific font by name"""
        for font in self.available_fonts:
            if font['name'].lower() == name.lower():
                return font['path']
        return None

    def get_all_font_names(self) -> List[str]:
        """Get list of all available font names"""
        return [font['name'] for font in self.available_fonts]

    def has_fonts(self) -> bool:
        """Check if any fonts are available"""
        return len(self.available_fonts) > 0

