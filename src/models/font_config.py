"""
Font configuration data model
"""

from dataclasses import dataclass


@dataclass
class FontConfig:
    """Configuration for text rendering"""
    font_name: str
    font_size: int
    column_separator: str  # none, line, double_line
    key_separator: str  # dots, dashes, none
    dash_count: int
    spacing: int
    language: str

    def __post_init__(self):
        """Validate configuration"""
        if self.font_size <= 0:
            raise ValueError("Font size must be positive")
        if self.dash_count <= 0:
            raise ValueError("Dash count must be positive")
        if self.spacing < 0:
            raise ValueError("Spacing must be non-negative")