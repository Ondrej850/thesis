"""
COCO format annotation manager with YOLO export support
Path: src/annotation/coco_manager.py
"""

import json
import os
import sys
from datetime import datetime
from dataclasses import asdict
from typing import List

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

    def export_yolo(self, output_dir: str, image_filename: str) -> str:
        """Export annotations in YOLO format for a specific image.

        YOLO format per line:
            <class_id> <x_center_norm> <y_center_norm> <width_norm> <height_norm>

        All coordinates are normalised by the image dimensions.

        A ``classes.txt`` file listing category names is also written to
        *output_dir*.

        Args:
            output_dir: Directory where ``<image_basename>.txt`` is written.
            image_filename: The filename used when the image was registered.

        Returns:
            Path to the written YOLO annotation file.
        """
        # Find matching image record
        image_data = next(
            (img for img in self.images if img["file_name"] == image_filename), None
        )
        if image_data is None:
            raise ValueError(
                f"Image '{image_filename}' not found in COCO dataset. "
                "Register the image first with add_image()."
            )

        img_width = image_data["width"]
        img_height = image_data["height"]
        image_id = image_data["id"]

        lines: List[str] = []
        for ann in self.annotations:
            if ann["image_id"] != image_id:
                continue
            x, y, w, h = ann["bbox"]  # [x, y, width, height] in pixels
            if w <= 0 or h <= 0:
                continue
            x_center = (x + w / 2) / img_width
            y_center = (y + h / 2) / img_height
            w_norm = w / img_width
            h_norm = h / img_height
            class_id = ann["category_id"]
            lines.append(
                f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}"
            )

        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(image_filename))[0]
        yolo_txt_path = os.path.join(output_dir, f"{base_name}.txt")
        with open(yolo_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Write classes.txt
        classes_path = os.path.join(output_dir, "classes.txt")
        with open(classes_path, "w", encoding="utf-8") as f:
            for cat in self.categories:
                f.write(cat["name"] + "\n")

        print(f"✓ Exported YOLO annotations to: {yolo_txt_path}")
        print(f"  - Annotations: {len(lines)}")
        print(f"  - Classes file: {classes_path}")
        return yolo_txt_path

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