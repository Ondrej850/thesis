"""
Shared constants used across generators and GUI.
"""

import platform

INK_COLOR_MAP = {
    "dark_brown":  (44, 36, 22),
    "black":       (15, 10, 10),
    "faded_brown": (80, 65, 45),
    "iron_gall":   (35, 30, 50),
    "sepia":       (90, 60, 30),
    "charcoal":    (50, 48, 46),
}

PAIR_SPACING_PX = {"tight": 2, "normal": 6, "high": 15}

# Key number ranges per cipher type (used when key_type == "number")
KEY_NUMBER_RANGES = {
    "alphabet":     (1, 99),
    "substitution": (100, 250),
    "bigram":       (70, 99),
    "trigram":      (170, 199),
    "dictionary":   (300, 350),
    "nulls":        (900, 950),
}

def _get_fallback_fonts():
    common = ["times.ttf", "georgia.ttf", "arial.ttf"]
    if platform.system() == "Linux":
        return [
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ] + common
    elif platform.system() == "Darwin":
        return ["/System/Library/Fonts/Times.ttc"] + common
    else:  # Windows
        return common


FALLBACK_FONTS = _get_fallback_fonts()
