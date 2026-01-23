"""
COCO format annotation model
Path: src/models/coco_annotation.py
"""

from dataclasses import dataclass
from typing import List


@dataclass
class COCOAnnotation:
    """COCO format annotation"""
    id: int
    image_id: int
    category_id: int
    segmentation: List[List[float]]
    area: float
    bbox: List[float]  # [x, y, width, height]
    iscrowd: int
    text: str = ""  # The actual text content

    def __post_init__(self):
        """Validate annotation"""
        if len(self.bbox) != 4:
            raise ValueError("bbox must contain exactly 4 values [x, y, width, height]")
        if self.area <= 0:
            raise ValueError("Area must be positive")
        if self.iscrowd not in [0, 1]:
            raise ValueError("iscrowd must be 0 or 1")


class BoundingBox:
    """Helper class to track bounding boxes during rendering"""
    def __init__(self):
        self.min_x = float('inf')
        self.min_y = float('inf')
        self.max_x = float('-inf')
        self.max_y = float('-inf')
        self.text = ""

    def add_point(self, x: float, y: float):
        """Add a point to expand the bounding box"""
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)

    def add_char_bbox(self, x: float, y: float, width: float, height: float):
        """Add character bounding box"""
        self.add_point(x, y)
        self.add_point(x + width, y + height)

    def to_coco_bbox(self) -> List[float]:
        """Convert to COCO bbox format [x, y, width, height]"""
        if self.min_x == float('inf'):
            return [0, 0, 0, 0]

        width = self.max_x - self.min_x
        height = self.max_y - self.min_y
        return [float(self.min_x), float(self.min_y), float(width), float(height)]

    def get_area(self) -> float:
        """Calculate area"""
        bbox = self.to_coco_bbox()
        return bbox[2] * bbox[3]

    def to_segmentation(self) -> List[List[float]]:
        """Convert to segmentation format (polygon)"""
        if self.min_x == float('inf'):
            return [[]]

        # Simple rectangle polygon (4 corners, clockwise)
        return [[
            float(self.min_x), float(self.min_y),
            float(self.max_x), float(self.min_y),
            float(self.max_x), float(self.max_y),
            float(self.min_x), float(self.max_y)
        ]]

    def is_valid(self) -> bool:
        """Check if bounding box has valid data"""
        return self.min_x != float('inf') and self.get_area() > 0

    def __repr__(self):
        """String representation for debugging"""
        if not self.is_valid():
            return f"BoundingBox(invalid, text='{self.text}')"
        bbox = self.to_coco_bbox()
        return f"BoundingBox(x={bbox[0]:.1f}, y={bbox[1]:.1f}, w={bbox[2]:.1f}, h={bbox[3]:.1f}, text='{self.text}')"