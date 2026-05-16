"""
Cipher image generator — creates aged paper and renders cipher content with annotations.
"""

import random
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.models.paper_config import PaperConfig
from src.models.font_config import FontConfig
from src.models.table_codes_config import TableCodesConfig
from src.annotations.coco_manager import COCOAnnotationManager
from src.constants import FALLBACK_FONTS
from .text_variation import VariatedTextRenderer, CipherEntryRenderer
from .table_codes_generator import TableCodesGenerator


def _load_font_obj(font_path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    """Load a PIL font, trying the given path then system fallbacks."""
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    for fb in FALLBACK_FONTS:
        try:
            return ImageFont.truetype(fb, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _get_fallback_font_path() -> Optional[str]:
    """Return the first available fallback font path, or None."""
    import os
    for fp in FALLBACK_FONTS:
        if os.path.exists(fp):
            return fp
    return None


class CipherImageGenerator:
    """Generates aged cipher document images with annotation tracking."""

    def __init__(self, paper_config: PaperConfig, font_config: FontConfig, variation_level: str = "medium"):
        self.paper_config = paper_config
        self.font_config = font_config
        text_renderer = VariatedTextRenderer(variation_level)
        self.cipher_renderer = CipherEntryRenderer(text_renderer)
        self.coco_manager = COCOAnnotationManager()
        self.current_image_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Paper generation
    # ------------------------------------------------------------------

    def create_aged_paper(self) -> Image.Image:
        """Create aged paper background with a random base colour."""
        base_palette = [
            '#FAFAF7', '#F7F2E8', '#F2EBD9', '#EDE0C4', '#E8D5B0',
            '#DFCA9C', '#D4B88A', '#C8A878', '#BF9C6A', '#B89060',
        ]
        base_hex = random.choice(base_palette)
        img = Image.new('RGB', (self.paper_config.width, self.paper_config.height), color=base_hex)
        img = self._add_paper_grain(img)

        aging = self.paper_config.aging_level / 100.0

        num_dots = int(500 * aging)
        if num_dots > 0:
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            base_rgb = self._hex_to_rgb(base_hex)
            aging_colors = [
                tuple(max(0, c - d) for c, d in zip(base_rgb, (20, 10, 5))),
                tuple(max(0, c - d) for c, d in zip(base_rgb, (35, 20, 10))),
                tuple(max(0, c - d) for c, d in zip(base_rgb, (50, 30, 15))),
            ]
            for _ in range(num_dots):
                x = random.randint(0, self.paper_config.width)
                y = random.randint(0, self.paper_config.height)
                size = random.randint(5, 30)
                color = random.choice(aging_colors)
                alpha = random.randint(10, 50)
                overlay_draw.ellipse([x, y, x + size, y + size], fill=(*color, alpha))
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

        if 'stains' in self.paper_config.defects:
            self._add_stains(img, int(15 * aging))
        if 'holes' in self.paper_config.defects:
            self._add_holes(img, int(10 * aging))
        if 'tears' in self.paper_config.defects:
            self._add_tears(img, int(5 * aging))
        if 'ink_drops' in self.paper_config.defects:
            self._add_ink_drops(img, int(8 * aging))

        return img.filter(ImageFilter.GaussianBlur(radius=0.5))

    def _add_paper_grain(self, img: Image.Image) -> Image.Image:
        arr = np.array(img, dtype=np.float32)
        h, w = arr.shape[:2]

        arr += np.random.normal(0, 6, arr.shape).astype(np.float32)

        tile = 12
        lf = np.random.normal(0, 10, (h // tile + 2, w // tile + 2)).astype(np.float32)
        lf_up = np.array(
            Image.fromarray(np.clip(lf + 128, 0, 255).astype(np.uint8), mode='L').resize(
                (w, h), Image.BILINEAR
            ),
            dtype=np.float32,
        ) - 128
        arr += lf_up[:, :, None] * 0.55

        fiber = np.random.normal(0, 3, (h, 1)).astype(np.float32)
        arr += np.repeat(fiber, w, axis=1)[:, :, None] * 0.4

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def _add_stains(self, img: Image.Image, count: int):
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(0, img.width)
            y = random.randint(0, img.height)
            size = random.randint(20, 80)
            color = random.choice(['#8B7355', '#A0826D', '#6B5D4F'])
            alpha = random.randint(30, 80)
            draw.ellipse([x, y, x + size, y + size], fill=(*self._hex_to_rgb(color), alpha))

    def _add_ink_drops(self, img: Image.Image, count: int):
        draw = ImageDraw.Draw(img, 'RGBA')
        ink_colors = [(15, 10, 10), (35, 30, 50), (44, 36, 22)]
        for _ in range(count):
            x = random.randint(0, img.width)
            y = random.randint(0, img.height)
            size = random.randint(4, 15)
            color = random.choice(ink_colors)
            alpha = random.randint(180, 240)
            draw.ellipse([x, y, x + size, y + size], fill=(*color, alpha))

    def _add_burns(self, img: Image.Image, count: int):
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(0, img.width)
            y = random.randint(0, img.height)
            size = random.randint(15, 40)
            draw.ellipse([x, y, x + size, y + size], fill=(80, 60, 40, 120))

    def _add_holes(self, img: Image.Image, count: int):
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(30, img.width - 30)
            y = random.randint(30, img.height - 30)
            size = random.randint(4, 15)
            # Shadow rim to make holes look physical
            draw.ellipse([x - 2, y - 2, x + size + 2, y + size + 2], fill=(160, 140, 110, 80))
            draw.ellipse([x, y, x + size, y + size], fill=(255, 255, 255, 255))

    def _add_tears(self, img: Image.Image, count: int):
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            edge = random.choice(['left', 'right', 'top', 'bottom'])
            if edge == 'left':
                x = random.randint(0, 20)
                y = random.randint(0, img.height)
                points = [(x, y), (x + random.randint(10, 30), y + random.randint(-20, 20))]
            elif edge == 'right':
                x = random.randint(img.width - 20, img.width)
                y = random.randint(0, img.height)
                points = [(x, y), (x - random.randint(10, 30), y + random.randint(-20, 20))]
            elif edge == 'top':
                x = random.randint(0, 20)
                y = random.randint(0, img.height)
                points = [(x, y), (x + random.randint(10, 30), y + random.randint(-20, 20))]
            else:  # bottom
                x = random.randint(img.width - 20, img.width)
                y = random.randint(0, img.height)
                points = [(x, y), (x - random.randint(10, 30), y + random.randint(-20, 20))]
            draw.line(points, fill=(0, 0, 0, 255), width=2)

    def _add_wrinkled_edges(self, img: Image.Image):
        draw = ImageDraw.Draw(img, 'RGBA')
        edge_width = 30
        for i in range(edge_width):
            alpha = int(50 * (1 - i / edge_width))
            draw.line([(0, i), (img.width, i)], fill=(100, 80, 60, alpha))
            draw.line(
                [(0, img.height - 1 - i), (img.width, img.height - 1 - i)],
                fill=(100, 80, 60, alpha),
            )

    # ------------------------------------------------------------------
    # COCO management
    # ------------------------------------------------------------------

    def register_image(self, filename: str) -> int:
        image_id = self.coco_manager.add_image(
            filename, self.paper_config.width, self.paper_config.height
        )
        self.current_image_id = image_id
        return image_id

    def get_annotation_stats(self) -> dict:
        return self.coco_manager.get_stats()

    def export_coco_annotations(self, output_path: str):
        self.coco_manager.export_coco(output_path)

    def export_yolo_annotations(self, output_dir: str, image_filename: str) -> str:
        return self.coco_manager.export_yolo(output_dir, image_filename)

    def reset_annotations(self):
        self.coco_manager.reset()
        self.cipher_renderer.reset_annotations()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _get_separator(self) -> str:
        if self.font_config.key_separator == 'dots':
            return " . . . "
        if self.font_config.key_separator == 'dashes':
            return " " + "—" * self.font_config.dash_count + " "
        return ""

    def render_cipher_text(
        self,
        img: Image.Image,
        cipher_entries: List[Tuple[str, str]],
        start_x: int,
        start_y: int,
        block_id: int = 0,
        font_path: Optional[str] = None,
        use_variations: bool = True,
        track_annotations: bool = True,
        right_margin: int = 50,
        bottom_margin: int = 50,
        ink_color: Optional[Tuple[int, int, int]] = None,
        pair_format: str = "text_first",
        line_spacing_variation: float = 0.0,
        pair_spacing: int = 10,
        column_gap: int = 30,
        column_divider: bool = False,
    ) -> int:
        """Render cipher pairs in a multi-column layout. Returns final Y position."""
        if font_path is None:
            font_path = _get_fallback_font_path()

        if not (use_variations and font_path):
            return self._render_text_simple(img, cipher_entries, start_x, start_y, font_path)

        max_height = self.paper_config.height - bottom_margin
        separator = self._get_separator()

        entry_h = self.font_config.font_size + self.font_config.spacing
        if self.font_config.column_separator != 'none':
            entry_h += self.font_config.font_size * 0.6

        if start_y + entry_h > max_height:
            print(f"[WARNING] render_cipher_text: no room for entries at start_y={start_y}")
            return int(start_y)

        current_x = start_x
        current_y = start_y
        col_max_x = start_x
        col_number = 1

        if track_annotations:
            self.cipher_renderer.start_section()

        for idx, (cipher_text, key_value) in enumerate(cipher_entries):
            if current_y + entry_h > max_height and idx > 0:
                if track_annotations:
                    self.cipher_renderer.end_section(block_id * 100 + col_number)

                next_col_x = col_max_x + column_gap
                col_h = max_height - start_y
                entries_per_col = max(1, int(col_h // entry_h))
                next_entries = cipher_entries[idx: idx + entries_per_col]

                VARIATION_MARGIN = 1.15
                INTER_PART_GAPS = pair_spacing * 2
                try:
                    mfont = ImageFont.truetype(font_path, self.font_config.font_size)
                    max_entry_w = VARIATION_MARGIN * max(
                        mfont.getlength(ct + separator + kv) + INTER_PART_GAPS
                        for ct, kv in next_entries
                    ) if next_entries else 0
                except Exception:
                    char_w = self.font_config.font_size * 0.6
                    max_entry_w = max(
                        len(ct + separator + kv) * char_w + INTER_PART_GAPS
                        for ct, kv in next_entries
                    ) if next_entries else 0

                available = self.paper_config.width - right_margin - next_col_x
                if available < max_entry_w:
                    print(f"[WARNING] No space for next column: need {max_entry_w:.0f}px, have {available:.0f}px")
                    break

                if column_divider:
                    draw = ImageDraw.Draw(img)
                    div_x = col_max_x + column_gap // 2
                    div_color = ink_color or (44, 36, 22)
                    draw.line([(div_x, start_y), (div_x, max_height)], fill=div_color, width=1)

                current_x = next_col_x
                current_y = start_y
                col_number += 1

                if track_annotations:
                    self.cipher_renderer.start_section()

            available_w = self.paper_config.width - current_x - right_margin
            elems_before = (
                len(self.cipher_renderer._text_renderer.collected_element_bboxes)
                if track_annotations else 0
            )

            next_y = self.cipher_renderer.render_cipher_entry(
                img, cipher_text, key_value, current_x, current_y,
                font_path, self.font_config.font_size, separator,
                column_separator=self.font_config.column_separator,
                paper_width=self.paper_config.width,
                track_annotations=track_annotations,
                max_column_width=available_w,
                ink_color=ink_color,
                pair_format=pair_format,
                spacing=self.font_config.spacing,
                pair_spacing=pair_spacing,
            )

            if line_spacing_variation > 0:
                next_y += random.uniform(-line_spacing_variation, line_spacing_variation)

            if track_annotations:
                new_elems = self.cipher_renderer._text_renderer.collected_element_bboxes[elems_before:]
                for elem in new_elems:
                    if elem.is_valid():
                        col_max_x = max(col_max_x, elem.max_x)
                if not new_elems:
                    col_max_x = max(col_max_x, current_x + available_w)
            else:
                text_w = len(cipher_text + separator + key_value) * (self.font_config.font_size * 0.6)
                col_max_x = max(col_max_x, min(current_x + text_w, self.paper_config.width - right_margin))

            current_y = next_y

        if track_annotations:
            self.cipher_renderer.end_section(block_id * 100 + col_number)
            if self.current_image_id is not None:
                anns = self.cipher_renderer.get_annotations(self.current_image_id)
                self.coco_manager.add_annotations(self.current_image_id, anns)

        return int(current_y)

    def _render_text_simple(
        self,
        img: Image.Image,
        cipher_entries: List[Tuple[str, str]],
        start_x: int,
        start_y: int,
        font_path: Optional[str],
    ) -> int:
        """Fallback plain-text renderer (no variations, no annotation tracking)."""
        draw = ImageDraw.Draw(img)
        font = _load_font_obj(font_path, self.font_config.font_size)
        y = start_y
        line_h = self.font_config.font_size + self.font_config.spacing
        separator = self._get_separator()

        for cipher_text, key_value in cipher_entries:
            draw.text((start_x, y), cipher_text, fill='#2C2416', font=font)
            sep_x = draw.textbbox((start_x, y), cipher_text, font=font)[2] + 10
            draw.text((sep_x, y), separator, fill='#2C2416', font=font)
            key_x = sep_x + 50
            key_bbox = draw.textbbox((key_x, y), key_value, font=font)
            draw.text((key_x, y), key_value, fill='#2C2416', font=font)
            y += line_h

            if self.font_config.column_separator == 'line':
                draw.line([(start_x, y), (key_bbox[2], y)], fill='#2C2416', width=1)
                y += 5
            elif self.font_config.column_separator == 'double_line':
                draw.line([(start_x, y), (key_bbox[2], y)], fill='#2C2416', width=1)
                draw.line([(start_x, y + 3), (key_bbox[2], y + 3)], fill='#2C2416', width=1)
                y += 5

        return y

    # ------------------------------------------------------------------
    # Title rendering
    # ------------------------------------------------------------------

    def render_title(
        self,
        img: Image.Image,
        start_x: int,
        start_y: int,
        font_path: Optional[str] = None,
        use_variations: bool = True,
        track_annotations: bool = True,
        ink_color: Optional[Tuple[int, int, int]] = None,
        title_text: Optional[str] = None,
        title_font_size: Optional[int] = None,
        right_margin: int = 50,
        bottom_margin: int = 50,
    ) -> int:
        """Render a title above content. Returns Y position below the title."""
        if font_path is None:
            font_path = _get_fallback_font_path()

        base_color = ink_color or (44, 36, 22)
        fs = title_font_size or int(self.font_config.font_size * 1.5)
        text = title_text or "Nomenclator"
        words = text.split()
        max_y = self.paper_config.height - bottom_margin
        x_limit = self.paper_config.width - right_margin

        if start_y + fs > max_y:
            return int(start_y)

        renderer = self.cipher_renderer._text_renderer
        elems_before = len(renderer.collected_element_bboxes)

        current_x = float(start_x)
        for word in words:
            if current_x >= x_limit:
                break
            end_x, _ = renderer.render_varied_text(
                img, word, current_x, start_y,
                font_path or "", fs, base_color,
                track_annotations=track_annotations,
                x_limit=x_limit,
            )
            current_x = end_x + fs * 0.4

        if track_annotations and len(words) > 1:
            new_elems = renderer.collected_element_bboxes[elems_before:]
            if new_elems:
                from src.models.coco_annotation import BoundingBox
                section_bbox = BoundingBox()
                section_bbox.text = f"Title: {text}"
                for eb in new_elems:
                    if eb.is_valid():
                        section_bbox.add_point(eb.min_x, eb.min_y)
                        section_bbox.add_point(eb.max_x, eb.max_y)
                if section_bbox.is_valid():
                    renderer.collected_section_bboxes.append(section_bbox)

        if track_annotations and self.current_image_id is not None:
            anns = renderer.get_annotations(self.current_image_id)
            self.coco_manager.add_annotations(self.current_image_id, anns)
            renderer.collected_element_bboxes = []
            renderer.collected_pair_bboxes = []
            renderer.collected_section_bboxes = []

        return int(start_y + fs + self.font_config.spacing * 2)

    # ------------------------------------------------------------------
    # Table codes rendering
    # ------------------------------------------------------------------

    def render_table_codes(
        self,
        img: Image.Image,
        table_config: TableCodesConfig,
        start_x: int,
        start_y: int,
        font_path: Optional[str] = None,
        use_variations: bool = True,
        variation_level: str = "medium",
        track_annotations: bool = True,
        code_table: Optional[dict] = None,
        font_size: Optional[int] = None,
        ink_color: Optional[Tuple[int, int, int]] = None,
        right_margin: int = 50,
        bottom_margin: int = 50,
    ) -> int:
        """Render a homophonic code table. Returns Y position below the table."""
        if font_path is None:
            font_path = _get_fallback_font_path()

        actual_font_size = font_size if font_size is not None else self.font_config.font_size
        table_gen = TableCodesGenerator(
            config=table_config,
            font_size=actual_font_size,
            spacing=self.font_config.spacing,
            variation_level=variation_level if use_variations else "none",
            ink_color=ink_color,
        )

        next_y = table_gen.render_table(
            img, start_x, start_y, font_path,
            code_table=code_table,
            paper_width=self.paper_config.width,
            paper_height=self.paper_config.height,
            right_margin=right_margin,
            bottom_margin=bottom_margin,
            track_annotations=track_annotations,
        )

        if track_annotations and self.current_image_id is not None:
            self.coco_manager.add_annotations(
                self.current_image_id, table_gen.get_annotations(self.current_image_id)
            )

        return int(next_y)
