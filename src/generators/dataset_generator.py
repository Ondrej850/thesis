"""
Batch dataset generator.
Produces N randomised cipher document images with merged annotations.
"""

import os
import random
import time
from typing import Callable, Optional, Tuple

from PIL import Image

from src.models.paper_config import PaperConfig
from src.models.font_config import FontConfig
from src.models.table_codes_config import TableCodesConfig, NULL_SYMBOLS
from src.models.dataset_config import DatasetConfig
from src.annotations.coco_manager import COCOAnnotationManager
from src.generators.image_generator import CipherImageGenerator
from src.generators.augmentation import apply_photo_augmentation
from src.database.database_manager import DatabaseManager
from src.database.font_manager import FontManager
from src.constants import INK_COLOR_MAP, PAIR_SPACING_PX, KEY_NUMBER_RANGES


def _generate_key_number(cipher_type: str) -> int:
    lo, hi = KEY_NUMBER_RANGES.get(cipher_type, (100, 200))
    return random.randint(lo, hi)


class DatasetGenerator:
    """Generates a batch of randomised cipher document images with annotations."""

    def __init__(self, config: DatasetConfig, db_manager: DatabaseManager, font_manager: FontManager):
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
        """Generate the full dataset. Returns the output directory path."""
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
        total = self.config.num_images + self.config.num_background_images
        saved = 0

        while saved < self.config.num_images:
            if self._cancelled:
                break
            params = self.config.sample()
            if self.config.ignore_empty_papers and self._is_empty(params):
                continue

            filename = f"image_{saved:04d}.png"
            self._generate_single(saved, params, coco_manager, images_dir)

            if yolo_dir is not None:
                coco_manager.export_yolo(yolo_dir, filename)

            saved += 1
            elapsed = time.monotonic() - t0
            eta = (elapsed / saved) * (total - saved)
            if progress_callback:
                progress_callback(saved, total, elapsed, eta)

        if not self._cancelled and fmt in ("coco", "both"):
            coco_manager.export_coco(os.path.join(annotations_dir, "annotations.json"))

        for bg_idx in range(self.config.num_background_images):
            if self._cancelled:
                break
            params = self.config.sample()
            self._generate_background(bg_idx, params, images_dir)
            overall = self.config.num_images + bg_idx + 1
            elapsed = time.monotonic() - t0
            eta = (elapsed / overall) * (total - overall)
            if progress_callback:
                progress_callback(overall, total, elapsed, eta)

        return self.config.output_dir

    # ------------------------------------------------------------------
    # Core image builders
    # ------------------------------------------------------------------

    def _generate_single(
        self,
        index: int,
        params: dict,
        coco_manager: COCOAnnotationManager,
        images_dir: str,
    ):
        """Generate one annotated image and save it to *images_dir*."""
        filename = f"image_{index:04d}.png"
        paper_config, font_config = self._make_configs(params)
        font_path = self._resolve_font(params["font_name"])
        ink_color = INK_COLOR_MAP.get(params["ink_color"], (44, 36, 22))
        variation_level = params["variation_level"]

        generator = CipherImageGenerator(paper_config, font_config, variation_level)
        image_id = coco_manager.add_image(filename, paper_config.width, paper_config.height)
        generator.current_image_id = image_id

        img = generator.create_aged_paper()
        use_variations = variation_level != "none"
        current_y = params["start_y"]
        bottom_limit = paper_config.height - params.get("bottom_margin", 50)
        right_margin = params.get("right_margin", 50)
        bottom_margin = params.get("bottom_margin", 50)

        # Title
        if params.get("include_title") and current_y < bottom_limit:
            current_y = generator.render_title(
                img, params["start_x"], current_y,
                font_path=font_path, use_variations=use_variations,
                track_annotations=True, ink_color=ink_color,
                right_margin=right_margin, bottom_margin=bottom_margin,
            )
            self._transfer_annotations(generator, coco_manager, image_id)

        # Table blocks
        any_table = False
        for table_params in params.get("tables", []):
            if current_y >= bottom_limit:
                break
            if table_params.get("include_title") and current_y < bottom_limit:
                current_y = generator.render_title(
                    img, params["start_x"], current_y,
                    font_path=font_path, use_variations=use_variations,
                    track_annotations=True, ink_color=ink_color,
                    right_margin=right_margin, bottom_margin=bottom_margin,
                )
                self._transfer_annotations(generator, coco_manager, image_id)
            if current_y >= bottom_limit:
                break
            table_config = self._make_table_config(table_params)
            current_y = generator.render_table_codes(
                img, table_config, params["start_x"], current_y,
                font_path=font_path,
                use_variations=use_variations,
                variation_level=variation_level,
                track_annotations=True,
                font_size=table_params["font_size"],
                ink_color=ink_color,
                right_margin=right_margin,
                bottom_margin=bottom_margin,
            )
            self._transfer_annotations(generator, coco_manager, image_id)
            current_y += params["spacing"] * 2
            any_table = True

        if any_table:
            current_y += params["spacing"] * 2

        # Column pairs
        if params["include_column_pairs"] and current_y < bottom_limit:
            if params.get("include_cp_title") and current_y < bottom_limit:
                current_y = generator.render_title(
                    img, params["start_x"], current_y,
                    font_path=font_path, use_variations=use_variations,
                    track_annotations=True, ink_color=ink_color,
                    right_margin=right_margin, bottom_margin=bottom_margin,
                )
                self._transfer_annotations(generator, coco_manager, image_id)
            if current_y < bottom_limit:
                entries = self._get_cipher_entries(
                    params["cipher_type"], params["key_type"], params["num_entries"]
                )
                generator.render_cipher_text(
                    img, entries, params["start_x"], current_y,
                    block_id=1, font_path=font_path, use_variations=use_variations,
                    track_annotations=True,
                    right_margin=params["right_margin"],
                    bottom_margin=params["bottom_margin"],
                    ink_color=ink_color,
                    pair_format=params.get("pair_format", "text_first"),
                    line_spacing_variation=float(params.get("line_spacing_jitter", 0)),
                    pair_spacing=PAIR_SPACING_PX.get(params.get("pair_spacing", "normal"), 6),
                    column_gap=params.get("column_gap", 30),
                    column_divider=params.get("column_divider", False),
                )
                self._transfer_annotations(generator, coco_manager, image_id)

        img = self._augment_and_update_annotations(
            img, image_id, coco_manager,
            bleed_through=params.get("bleed_through", "random"),
            book_edges=params.get("book_edges", "random"),
            other=params.get("other", "random"),
        )
        img.save(os.path.join(images_dir, filename))

    def _render_content_image(self, params: dict) -> Image.Image:
        """Render a full cipher image without annotation tracking (used as bleed-through source)."""
        paper_config, font_config = self._make_configs(params)
        font_path = self._resolve_font(params["font_name"])
        ink_color = INK_COLOR_MAP.get(params["ink_color"], (44, 36, 22))
        variation_level = params["variation_level"]
        use_variations = variation_level != "none"

        generator = CipherImageGenerator(paper_config, font_config, variation_level)
        img = generator.create_aged_paper()
        current_y = params["start_y"]
        bottom_limit = paper_config.height - params.get("bottom_margin", 50)
        right_margin = params.get("right_margin", 50)
        bottom_margin = params.get("bottom_margin", 50)

        if params.get("include_title") and current_y < bottom_limit:
            current_y = generator.render_title(
                img, params["start_x"], current_y,
                font_path=font_path, use_variations=use_variations,
                track_annotations=False, ink_color=ink_color,
                right_margin=right_margin, bottom_margin=bottom_margin,
            )

        for table_params in params.get("tables", []):
            if current_y >= bottom_limit:
                break
            table_config = self._make_table_config(table_params)
            current_y = generator.render_table_codes(
                img, table_config, params["start_x"], current_y,
                font_path=font_path,
                use_variations=use_variations,
                variation_level=variation_level,
                track_annotations=False,
                font_size=table_params["font_size"],
                ink_color=ink_color,
                right_margin=right_margin,
                bottom_margin=bottom_margin,
            )
            current_y += params["spacing"] * 2

        if params["include_column_pairs"] and current_y < bottom_limit:
            entries = self._get_cipher_entries(
                params["cipher_type"], params["key_type"], params["num_entries"]
            )
            generator.render_cipher_text(
                img, entries, params["start_x"], current_y,
                block_id=1, font_path=font_path, use_variations=use_variations,
                track_annotations=False,
                right_margin=params["right_margin"],
                bottom_margin=params["bottom_margin"],
                ink_color=ink_color,
                pair_format=params.get("pair_format", "text_first"),
                line_spacing_variation=float(params.get("line_spacing_jitter", 0)),
                pair_spacing=PAIR_SPACING_PX.get(params.get("pair_spacing", "normal"), 6),
                column_gap=params.get("column_gap", 30),
                column_divider=params.get("column_divider", False),
            )

        return img

    def _generate_background(self, index: int, params: dict, images_dir: str):
        """Generate a plain aged-paper background image with bleed-through augmentation."""
        paper_config = PaperConfig(aging_level=params["aging_level"], defects=params["defects"])
        font_config = FontConfig(
            font_name="custom", font_size=14, column_separator="none",
            key_separator="none", dash_count=1, spacing=0, language="latin",
        )
        generator = CipherImageGenerator(paper_config, font_config, "low")
        img = generator.create_aged_paper()

        back_image = self._render_content_image(self.config.sample())
        back_image = back_image.transpose(Image.FLIP_LEFT_RIGHT)

        img = apply_photo_augmentation(
            img, back_image=back_image,
            bleed_through=params.get("bleed_through", "random"),
            book_edges=params.get("book_edges", "random"),
            other=params.get("other", "random"),
        )
        img.save(os.path.join(images_dir, f"bg_{index:04d}.png"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_configs(params: dict) -> Tuple[PaperConfig, FontConfig]:
        return (
            PaperConfig(aging_level=params["aging_level"], defects=params["defects"]),
            FontConfig(
                font_name="custom",
                font_size=params["cp_font_size"],
                column_separator=params["col_separator"],
                key_separator=params["key_separator"],
                dash_count=params["dash_count"],
                spacing=params["spacing"],
                language="latin",
            ),
        )

    def _make_table_config(self, table_params: dict) -> TableCodesConfig:
        """Build a TableCodesConfig from sampled table parameters."""
        ct = table_params["content_type"]
        num_sym = table_params.get("num_symbols", 0)
        words = self.db.get_table_words(num_sym) if ct == "words" and num_sym > 0 else None

        return TableCodesConfig(
            content_type=ct,
            num_symbols=num_sym,
            words=words,
            num_codes=table_params["num_codes"],
            use_common_boost=table_params["common_boost"],
            common_codes=table_params["common_codes"],
            draw_vertical_lines=table_params["vertical_lines"],
            column_spacing=table_params["col_spacing"],
            row_spacing=table_params.get("row_spacing", 0),
            use_pair_grid=table_params.get("pair_grid", False),
            draw_header_line=table_params.get("draw_header_line", True),
        )

    @staticmethod
    def _transfer_annotations(
        generator: CipherImageGenerator,
        coco_manager: COCOAnnotationManager,
        image_id: int,
    ):
        """Copy annotations from generator's internal manager to the shared manager."""
        paper_w = generator.paper_config.width
        paper_h = generator.paper_config.height
        for ann in generator.coco_manager.annotations:
            if not DatasetGenerator._ann_within_paper(ann, paper_w, paper_h):
                continue
            ann["image_id"] = image_id
            ann["id"] = coco_manager.annotation_id_counter
            coco_manager.annotations.append(ann)
            coco_manager.annotation_id_counter += 1
        generator.coco_manager.annotations.clear()

    @staticmethod
    def _augment_and_update_annotations(
        img: Image.Image,
        image_id: int,
        coco_manager: COCOAnnotationManager,
        bleed_through: str = "random",
        book_edges: str = "random",
        other: str = "random",
    ) -> Image.Image:
        """Augment image and update COCO bboxes to match spatial transforms.

        Annotations warped fully off-canvas or below the visibility threshold are dropped.
        """
        owned = [(i, ann) for i, ann in enumerate(coco_manager.annotations)
                 if ann.get("image_id") == image_id]

        aug_kwargs = dict(
            bleed_through=bleed_through,
            book_edges=book_edges,
            other=other,
        )

        if not owned:
            return apply_photo_augmentation(img, **aug_kwargs)

        bboxes = [list(ann["bbox"]) for _, ann in owned]
        labels = [i for i, _ in owned]
        orig_dims = {i: (ann["bbox"][2], ann["bbox"][3]) for i, ann in owned}

        new_img, new_bboxes, surviving_labels = apply_photo_augmentation(
            img, bboxes=bboxes, labels=labels, **aug_kwargs,
        )

        _DIM_THRESHOLD = 0.70
        survived = {}
        for label, new_bbox in zip(surviving_labels, new_bboxes):
            idx = int(label)
            orig_w, orig_h = orig_dims[idx]
            nw, nh = new_bbox[2], new_bbox[3]
            if orig_w == 0 or orig_h == 0 or (nw / orig_w >= _DIM_THRESHOLD and nh / orig_h >= _DIM_THRESHOLD):
                survived[idx] = list(new_bbox)

        rebuilt = []
        for i, ann in enumerate(coco_manager.annotations):
            if ann.get("image_id") != image_id:
                rebuilt.append(ann)
                continue
            new_bbox = survived.get(i)
            if new_bbox is None:
                continue
            x, y, w, h = (float(v) for v in new_bbox)
            ann["bbox"] = [x, y, w, h]
            ann["area"] = w * h
            ann["segmentation"] = [[x, y, x + w, y, x + w, y + h, x, y + h]]
            rebuilt.append(ann)
        coco_manager.annotations = rebuilt
        return new_img

    @staticmethod
    def _is_empty(params: dict) -> bool:
        return not params.get("tables") and not params.get("include_column_pairs", False)

    @staticmethod
    def _ann_within_paper(ann: dict, paper_width: int, paper_height: int) -> bool:
        bbox = ann.get("bbox")
        if not bbox or len(bbox) < 4:
            return False
        x, y, w, h = bbox
        return w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= paper_width and y + h <= paper_height

    def _resolve_font(self, font_name: str) -> Optional[str]:
        if font_name == "Random":
            return self.font_manager.get_random_font()
        return self.font_manager.get_font_by_name(font_name) or self.font_manager.get_random_font()

    @staticmethod
    def _generate_unique_double_char_keys(count: int) -> list:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        pool = [a + b for a in chars for b in chars]
        random.shuffle(pool)
        return pool[:count]

    def _get_cipher_entries(self, cipher_type: str, key_type: str, num_entries: int):
        if cipher_type == "alphabet":
            letters = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')[:min(num_entries, 26)]
            if key_type == "double_char":
                keys = self._generate_unique_double_char_keys(len(letters))
                return list(zip(letters, keys))
            if key_type == "special_character":
                return [(l, random.choice(NULL_SYMBOLS)) for l in letters]
            return [(l, str(_generate_key_number(cipher_type))) for l in letters]

        words = self.db.get_cipher_keys(cipher_type)
        if not words:
            return [(f"Sample{i}", str(100 + i)) for i in range(num_entries)]
        if key_type == "double_char":
            keys = self._generate_unique_double_char_keys(num_entries)
            return [(random.choice(words), keys[i]) for i in range(num_entries)]
        if key_type == "special_character":
            return [(random.choice(words), random.choice(NULL_SYMBOLS)) for _ in range(num_entries)]
        return [(random.choice(words), str(_generate_key_number(cipher_type))) for _ in range(num_entries)]
