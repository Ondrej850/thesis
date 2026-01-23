"""
COCO format annotation manager
Path: src/annotation/coco_manager.py
"""

import json
from datetime import datetime
from typing import List
from dataclasses import asdict
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.models.coco_annotation import COCOAnnotation


class COCOAnnotationManager:
    """Manages COCO format annotations"""

    # Category definitions
    CATEGORY_ELEMENT = 0  # Single word/phrase OR single key (individual text items)
    CATEGORY_PAIR = 1     # One cipher text + its corresponding key (complete entry)
    CATEGORY_SECTION = 2  # Group of pairs (column, table, or related entries)

    def __init__(self):
        self.images = []
        self.annotations = []
        self.categories = [
            {"id": 0, "name": "element", "supercategory": "cipher",
             "description": "Individual cipher text or key value"},
            {"id": 1, "name": "pair", "supercategory": "cipher",
             "description": "Cipher text paired with its key value"},
            {"id": 2, "name": "section", "supercategory": "cipher",
             "description": "Group of related pairs (column/table)"},
        ]
        self.image_id_counter = 1
        self.annotation_id_counter = 1

    def add_image(self, file_name: str, width: int, height: int) -> int:
        """Add image to COCO dataset"""
        image_id = self.image_id_counter
        self.images.append({
            "id": image_id,
            "file_name": file_name,
            "width": width,
            "height": height,
            "date_captured": datetime.now().isoformat()
        })
        self.image_id_counter += 1
        return image_id

    def add_annotation(self, annotation: COCOAnnotation):
        """Add single annotation"""
        annotation.id = self.annotation_id_counter
        ann_dict = asdict(annotation)
        self.annotations.append(ann_dict)
        self.annotation_id_counter += 1

    def add_annotations(self, image_id: int, annotations: List[COCOAnnotation]):
        """Add multiple annotations for an image"""
        for ann in annotations:
            ann.image_id = image_id
            self.add_annotation(ann)

    def export_coco(self, output_path: str):
        """Export annotations in COCO format"""
        coco_format = {
            "images": self.images,
            "annotations": self.annotations,
            "categories": self.categories,
            "info": {
                "description": "Historical Cipher Document Dataset",
                "version": "1.0",
                "year": 2025,
                "contributor": "Cipher Generator",
                "date_created": datetime.now().isoformat()
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(coco_format, f, indent=2, ensure_ascii=False)

        print(f"✓ Exported COCO annotations to: {output_path}")
        print(f"  - Images: {len(self.images)}")
        print(f"  - Annotations: {len(self.annotations)}")
        self._print_category_stats()

    def _print_category_stats(self):
        """Print statistics per category"""
        category_counts = {}
        for ann in self.annotations:
            cat_id = ann['category_id']
            cat_name = self.categories[cat_id]['name']
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        if category_counts:
            print("  - Annotations by category:")
            for cat_name, count in category_counts.items():
                print(f"    • {cat_name}: {count}")

    def get_stats(self) -> dict:
        """Get statistics about the dataset"""
        category_counts = {}
        for ann in self.annotations:
            cat_id = ann['category_id']
            cat_name = self.categories[cat_id]['name']
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        return {
            "total_images": len(self.images),
            "total_annotations": len(self.annotations),
            "categories": len(self.categories),
            "annotations_per_category": category_counts
        }

    def reset(self):
        """Reset all data"""
        self.images = []
        self.annotations = []
        self.image_id_counter = 1
        self.annotation_id_counter = 1

    def validate_annotations(self) -> List[str]:
        """
        Validate all annotations and return list of errors

        Returns:
            List of error messages (empty if all valid)
        """
        errors = []

        for i, ann in enumerate(self.annotations):
            # Check required fields
            required_fields = ['id', 'image_id', 'category_id', 'bbox', 'area', 'segmentation', 'iscrowd']
            for field in required_fields:
                if field not in ann:
                    errors.append(f"Annotation {i}: Missing required field '{field}'")

            # Validate bbox format
            if 'bbox' in ann:
                bbox = ann['bbox']
                if not isinstance(bbox, list) or len(bbox) != 4:
                    errors.append(f"Annotation {i}: Invalid bbox format (must be [x, y, width, height])")
                elif bbox[2] <= 0 or bbox[3] <= 0:
                    errors.append(f"Annotation {i}: Invalid bbox dimensions (width/height must be > 0)")

            # Validate area
            if 'area' in ann and ann['area'] <= 0:
                errors.append(f"Annotation {i}: Invalid area (must be > 0)")

            # Validate category_id
            if 'category_id' in ann:
                cat_id = ann['category_id']
                if cat_id not in [0, 1, 2]:
                    errors.append(f"Annotation {i}: Invalid category_id {cat_id} (must be 0, 1, or 2)")

        return errors