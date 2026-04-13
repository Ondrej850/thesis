"""
Batch dataset generator.
Produces N randomised cipher document images with merged annotations.
Path: src/generators/dataset_generator.py
"""

import os
import random
import time
from typing import Callable, Optional

from src.models.paper_config import PaperConfig
from src.models.font_config import FontConfig
from src.models.table_codes_config import TableCodesConfig
from src.models.dataset_config import DatasetConfig
from src.annotations.coco_manager import COCOAnnotationManager
from src.generators.image_generator import CipherImageGenerator
from src.generators.table_codes_generator import TableCodesGenerator
from src.database.database_manager import DatabaseManager
from src.database.font_manager import FontManager

# Ink colour lookup (same as main_window.py)
INK_COLOR_MAP = {
    "dark_brown":  (44, 36, 22),
    "black":       (15, 10, 10),
    "faded_brown": (80, 65, 45),
    "iron_gall":   (35, 30, 50),
    "sepia":       (90, 60, 30),
    "charcoal":    (50, 48, 46),
}


def _generate_key_number(cipher_type: str) -> int:
    """Generate a random key number matching the main window logic."""
    ranges = {
        "substitution": (100, 250),
        "bigram":       (70, 99),
        "trigram":       (170, 199),
        "dictionary":   (300, 350),
        "nulls":        (900, 950),
    }
    lo, hi = ranges.get(cipher_type, (100, 200))
    return random.randint(lo, hi)


class DatasetGenerator:
    """Generates a batch of randomised cipher document images with annotations."""

    def __init__(
        self,
        config: DatasetConfig,
        db_manager: DatabaseManager,
        font_manager: FontManager,
    ):
        self.config = config
        self.db = db_manager
        self.font_manager = font_manager
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def generate(
        self,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None,
    ) -> str:
        """Generate the full dataset.

        Args:
            progress_callback: Called with (current_index, total, elapsed_s, eta_s)
                after each image.

        Returns:
            Path to the output directory.
        """
        os.makedirs(self.config.output_dir, exist_ok=True)
        images_dir = os.path.join(self.config.output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        annotations_dir = os.path.join(self.config.output_dir, "annotations")
        os.makedirs(annotations_dir, exist_ok=True)

        fmt = self.config.annotation_format
        yolo_dir = None
        if fmt in ("yolo", "both"):
            yolo_dir = os.path.join(annotations_dir, "yolo")
            os.makedirs(yolo_dir, exist_ok=True)

        coco_manager = COCOAnnotationManager()
        t0 = time.monotonic()

        for i in range(self.config.num_images):
            if self._cancelled:
                break

            params = self.config.sample()
            filename = f"image_{i:04d}.png"
            self._generate_single(i, params, coco_manager, images_dir)

            # Export YOLO per-image immediately so data is saved incrementally
            if yolo_dir is not None:
                coco_manager.export_yolo(yolo_dir, filename)

            elapsed = time.monotonic() - t0
            per_image = elapsed / (i + 1)
            eta = per_image * (self.config.num_images - (i + 1))

            if progress_callback:
                progress_callback(i + 1, self.config.num_images, elapsed, eta)

        # Export COCO (single JSON for all images)
        if not self._cancelled and fmt in ("coco", "both"):
            coco_manager.export_coco(os.path.join(annotations_dir, "annotations.json"))

        return self.config.output_dir

    # ------------------------------------------------------------------

    def _generate_single(
        self,
        index: int,
        params: dict,
        coco_manager: COCOAnnotationManager,
        images_dir: str,
    ):
        """Generate a single image from sampled *params*."""
        paper_config = PaperConfig(
            aging_level=params["aging_level"],
            paper_type=params["paper_type"],
            defects=params["defects"],
        )
        font_config = FontConfig(
            font_name="custom",
            font_size=params["cp_font_size"],
            column_separator=params["col_separator"],
            key_separator=params["key_separator"],
            dash_count=params["dash_count"],
            spacing=params["spacing"],
            language="latin",
        )

        variation_level = params["variation_level"]
        use_variations = variation_level != "none"

        generator = CipherImageGenerator(paper_config, font_config, variation_level)

        # Register image with the *shared* COCO manager (not the generator's own)
        filename = f"image_{index:04d}.png"
        image_id = coco_manager.add_image(filename, paper_config.width, paper_config.height)

        # Also register in the generator so its internal rendering tracks annotations
        generator.current_image_id = image_id

        img = generator.create_aged_paper()

        # Resolve font path
        font_path = self._resolve_font(params["font_name"])
        ink_color = INK_COLOR_MAP.get(params["ink_color"], (44, 36, 22))

        current_y = params["start_y"]

        # Title / header
        if params.get("include_title", False):
            current_y = generator.render_title(
                img, params["start_x"], current_y,
                font_path=font_path,
                use_variations=use_variations,
                track_annotations=True,
                ink_color=ink_color,
            )
            # Transfer title annotations to shared manager
            for ann in generator.coco_manager.annotations:
                ann["image_id"] = image_id
                ann["id"] = coco_manager.annotation_id_counter
                coco_manager.annotations.append(ann)
                coco_manager.annotation_id_counter += 1
            generator.coco_manager.annotations.clear()

        # Table codes
        if params["include_table_codes"]:
            table_config = TableCodesConfig(
                content_type=params["table_content_type"],
                num_codes=params["table_num_codes"],
                use_common_boost=params["table_common_boost"],
                common_codes=params["table_common_codes"],
                draw_vertical_lines=params["table_vertical_lines"],
                column_spacing=params["table_col_spacing"],
                row_spacing=params.get("table_row_spacing", 0),
            )
            table_gen = TableCodesGenerator(
                config=table_config,
                font_size=params["table_font_size"],
                spacing=params["spacing"],
                variation_level=variation_level,
                ink_color=ink_color,
            )
            code_table = table_gen.generate_code_table()
            current_y = table_gen.render_table(
                img,
                params["start_x"],
                current_y,
                font_path,
                code_table=code_table,
                paper_width=paper_config.width,
                paper_height=paper_config.height,
                track_annotations=True,
            )
            # Collect table annotations into the shared manager
            table_anns = table_gen.get_annotations(image_id)
            coco_manager.add_annotations(image_id, table_anns)
            current_y += params["spacing"] * 4

        # Column pairs
        if params["include_column_pairs"]:
            entries = self._get_cipher_entries(
                params["cipher_type"], params["key_type"], params["num_entries"]
            )
            generator.render_cipher_text(
                img,
                entries,
                params["start_x"],
                current_y,
                block_id=1,
                font_path=font_path,
                use_variations=use_variations,
                track_annotations=True,
                right_margin=params["right_margin"],
                bottom_margin=params["bottom_margin"],
                ink_color=ink_color,
                pair_format=params.get("pair_format", "text_first"),
                line_spacing_variation=float(params.get("line_spacing_jitter", 0)),
            )
            # The generator stores pair/element annotations in its own coco_manager.
            # Transfer them to the shared one.
            for ann in generator.coco_manager.annotations:
                ann["image_id"] = image_id
                ann["id"] = coco_manager.annotation_id_counter
                coco_manager.annotations.append(ann)
                coco_manager.annotation_id_counter += 1

        img.save(os.path.join(images_dir, filename))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_font(self, font_name: str) -> Optional[str]:
        if font_name == "Random":
            return self.font_manager.get_random_font()
        path = self.font_manager.get_font_by_name(font_name)
        return path if path else self.font_manager.get_random_font()

    @staticmethod
    def _generate_unique_double_char_keys(count: int) -> list:
        """Generate *count* unique two-character keys."""
        chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        pool = [a + b for a in chars for b in chars]
        random.shuffle(pool)
        return pool[:count]

    def _get_cipher_entries(self, cipher_type: str, key_type: str, num_entries: int):
        words = self.db.get_cipher_keys(cipher_type)
        if not words:
            return [(f"Sample{i}", str(100 + i)) for i in range(num_entries)]
        if key_type == "double_char":
            unique_keys = self._generate_unique_double_char_keys(num_entries)
            return [(random.choice(words), unique_keys[i]) for i in range(num_entries)]
        entries = []
        for _ in range(num_entries):
            word = random.choice(words)
            key_val = str(_generate_key_number(cipher_type))
            entries.append((word, key_val))
        return entries
