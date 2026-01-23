"""
Layout configuration data model
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class LayoutConfig:
    """Configuration for layout on paper"""
    blocks: List[Dict]  # List of {x, y, width, height, type}

    def __post_init__(self):
        """Validate configuration"""
        for block in self.blocks:
            required_keys = ['x', 'y', 'width', 'height', 'type']
            if not all(key in block for key in required_keys):
                raise ValueError(f"Block must contain {required_keys}")