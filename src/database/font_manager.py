"""
Font manager — discovers handwritten TTF/OTF fonts in a directory.
"""

import os
import random
from typing import List, Optional


class FontManager:
    """Manages handwritten fonts for cipher generation."""

    def __init__(self, fonts_dir: str = "fonts/handwritten"):
        self.fonts_dir = fonts_dir
        self.available_fonts: List[dict] = []
        self._scan_fonts()

    def _scan_fonts(self):
        if not os.path.exists(self.fonts_dir):
            os.makedirs(self.fonts_dir, exist_ok=True)
            return

        for filename in os.listdir(self.fonts_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                self.available_fonts.append({
                    'name': os.path.splitext(filename)[0],
                    'path': os.path.join(self.fonts_dir, filename),
                })

        print(f"FontManager: {len(self.available_fonts)} font(s) found in '{self.fonts_dir}'")

    def get_random_font(self) -> Optional[str]:
        if not self.available_fonts:
            return None
        return random.choice(self.available_fonts)['path']

    def get_font_by_name(self, name: str) -> Optional[str]:
        for font in self.available_fonts:
            if font['name'].lower() == name.lower():
                return font['path']
        return None

    def get_all_font_names(self) -> List[str]:
        return [font['name'] for font in self.available_fonts]

    def has_fonts(self) -> bool:
        return bool(self.available_fonts)
