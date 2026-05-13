"""
COCO format annotation manager with YOLO export support.
"""

import json
import os
from datetime import datetime
from dataclasses import asdict
from typing import List

from src.models.coco_annotation import COCOAnnotation


class COCOAnnotationManager:
    """Manages COCO format annotations for a generated dataset."""

    CATEGORY_ELEMENT = 0  # Individual cipher text or key
    CATEGORY_PAIR = 1     # One cipher text + its key
    CATEGORY_SECTION = 2  # Group of pairs (column or table block)

    def __init__(self):
        self.images: List[dict] = []
        self.annotations: List[dict] = []
        self.categories = [
            {"id": 0, "name": "element",  "supercategory": "cipher",
             "description": "Individual cipher text or key value"},
            {"id": 1, "name": "pair",     "supercategory": "cipher",
             "description": "Cipher text paired with its key value"},
            {"id": 2, "name": "section",  "supercategory": "cipher",
             "description": "Group of related pairs (column/table)"},
        ]
        self.image_id_counter = 1
        self.annotation_id_counter = 1

    def add_image(self, file_name: str, width: int, height: int) -> int:
        image_id = self.image_id_counter
        self.images.append({
            "id": image_id,
            "file_name": file_name,
            "width": width,
            "height": height,
            "date_captured": datetime.now().isoformat(),
        })
        self.image_id_counter += 1
        return image_id

    def add_annotation(self, annotation: COCOAnnotation):
        annotation.id = self.annotation_id_counter
        self.annotations.append(asdict(annotation))
        self.annotation_id_counter += 1

    def add_annotations(self, image_id: int, annotations: List[COCOAnnotation]):
        for ann in annotations:
            ann.image_id = image_id
            self.add_annotation(ann)

    def export_coco(self, output_path: str):
        coco_data = {
            "images": self.images,
            "annotations": self.annotations,
            "categories": self.categories,
            "info": {
                "description": "Historical Cipher Document Dataset",
                "version": "1.0",
                "year": 2025,
                "contributor": "Cipher Generator",
                "date_created": datetime.now().isoformat(),
            },
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, indent=2, ensure_ascii=False)
        print(f"Exported COCO: {len(self.images)} images, {len(self.annotations)} annotations → {output_path}")

    def export_yolo(self, output_dir: str, image_filename: str) -> str:
        """Export YOLO annotations for one image.

        Format per line: <class_id> <x_center_norm> <y_center_norm> <w_norm> <h_norm>
        Also writes classes.txt.

        Returns path to the written .txt file.
        """
        image_data = next(
            (img for img in self.images if img["file_name"] == image_filename), None
        )
        if image_data is None:
            raise ValueError(
                f"Image '{image_filename}' not found. Register it first with add_image()."
            )

        img_w = image_data["width"]
        img_h = image_data["height"]
        image_id = image_data["id"]

        lines: List[str] = []
        for ann in self.annotations:
            if ann["image_id"] != image_id:
                continue
            x, y, w, h = ann["bbox"]
            if w <= 0 or h <= 0:
                continue
            lines.append(
                f"{ann['category_id']} "
                f"{(x + w / 2) / img_w:.6f} "
                f"{(y + h / 2) / img_h:.6f} "
                f"{w / img_w:.6f} "
                f"{h / img_h:.6f}"
            )

        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_filename))[0]
        yolo_path = os.path.join(output_dir, f"{base}.txt")
        with open(yolo_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        classes_path = os.path.join(output_dir, "classes.txt")
        with open(classes_path, "w", encoding="utf-8") as f:
            for cat in self.categories:
                f.write(cat["name"] + "\n")

        return yolo_path

    def get_stats(self) -> dict:
        counts: dict = {}
        for ann in self.annotations:
            name = self.categories[ann['category_id']]['name']
            counts[name] = counts.get(name, 0) + 1
        return {
            "total_images": len(self.images),
            "total_annotations": len(self.annotations),
            "categories": len(self.categories),
            "annotations_per_category": counts,
        }

    def reset(self):
        self.images = []
        self.annotations = []
        self.image_id_counter = 1
        self.annotation_id_counter = 1
