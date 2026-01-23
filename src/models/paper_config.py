"""
Paper configuration data model
"""

from dataclasses import dataclass
from typing import List


@dataclass
class PaperConfig:
    """Configuration for paper appearance"""
    aging_level: int  # 0-100
    paper_type: str
    defects: List[str]
    width: int = 800
    height: int = 1100

    def __post_init__(self):
        """Validate configuration"""
        if not 0 <= self.aging_level <= 100:
            raise ValueError("Aging level must be between 0 and 100")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Width and height must be positive")