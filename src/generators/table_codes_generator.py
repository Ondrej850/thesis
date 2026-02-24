"""
Table codes generator — renders homophonic cipher code tables with
realistic handwriting variations and full COCO + YOLO annotation support.

Layout produced (one "row block" for each chunk of symbols):

    A    B    C    D    E    ...
    ─────────────────────────────
    12    7   41   22    1
    35   19   84   63   14
    91        55        23
                        47

Each symbol gets `num_codes` code numbers; common English letters
(E, T, A, O, I, N, S, H, R) can optionally receive more codes.

Annotations tracked (using the existing COCO pipeline):
  element  (cat 0) – individual code number rendered on screen
  cell     (cat 1) – symbol header + all its code numbers (one column)
  row_block(cat 2) – a full multi-symbol row with all code rows

Path: src/generators/table_codes_generator.py
"""

from __future__ import annotations

import math
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.models.coco_annotation import BoundingBox, COCOAnnotation
from src.models.table_codes_config import TableCodesConfig
from src.generators.text_variation import VariatedTextRenderer


class TableCodesGenerator:
    """Generates and renders a homophonic code table on a PIL Image.

    Works alongside the existing ``CipherImageGenerator`` infrastructure:
    it reuses ``VariatedTextRenderer`` for realistic handwriting and feeds
    its bounding-box data back into the same ``COCOAnnotationManager``.
    """

    # Dark-brown ink colour matching the rest of the document
    BASE_COLOR: Tuple[int, int, int] = (44, 36, 22)

    def __init__(
        self,
        config: TableCodesConfig,
        font_size: int,
        spacing: int,
        variation_level: str = "medium",
    ) -> None:
        self.config = config
        self.font_size = font_size
        self.spacing = spacing
        self._text_renderer = VariatedTextRenderer(variation_level)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_code_table(self) -> Dict[str, List[int]]:
        """Assign unique, shuffled code numbers to every symbol.

        Returns:
            Mapping of symbol → sorted list of code numbers.
        """
        symbols = self.config.get_symbols()
        total = self.config.total_codes_needed()

        # Pool large enough to guarantee uniqueness with room to spare
        pool_max = max(total * 2, 100)
        pool = list(range(1, pool_max + 1))
        random.shuffle(pool)

        code_table: Dict[str, List[int]] = {}
        idx = 0
        for sym in symbols:
            n = self.config.get_num_codes_for_symbol(sym)
            code_table[sym] = sorted(pool[idx: idx + n])
            idx += n

        return code_table

    def render_table(
        self,
        img: Image.Image,
        x: int,
        y: int,
        font_path: Optional[str],
        track_annotations: bool = True,
    ) -> int:
        """Render the full code table onto *img* and return the next Y position.

        Args:
            img: The PIL image to draw on.
            x: Left margin of the table.
            y: Top Y position to start drawing.
            font_path: Path to the handwritten TTF font (may be None).
            track_annotations: Whether to accumulate COCO bounding boxes.

        Returns:
            Y position after the last rendered row block.
        """
        symbols = self.config.get_symbols()
        code_table = self.generate_code_table()

        # Split symbols into rows
        cols = self.config.max_cols_per_row if self.config.max_cols_per_row > 0 else 13
        row_chunks: List[List[str]] = [
            symbols[i: i + cols] for i in range(0, len(symbols), cols)
        ]

        current_y = y
        for chunk in row_chunks:
            current_y = self._render_row_block(
                img, chunk, code_table, x, current_y, font_path, track_annotations
            )
            current_y += self.spacing * 3  # Extra gap between row blocks

        return current_y

    def get_annotations(self, image_id: int = 0) -> List[COCOAnnotation]:
        """Return all collected COCO annotations (elements, cells, row blocks)."""
        return self._text_renderer.get_annotations(image_id)

    def reset_annotations(self) -> None:
        """Clear all collected annotation data."""
        self._text_renderer.collected_element_bboxes = []
        self._text_renderer.collected_pair_bboxes = []
        self._text_renderer.collected_section_bboxes = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_font(self, font_path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        """Load a font with graceful fallback."""
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        # Fallback candidates
        for fb in [
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "times.ttf",
            "georgia.ttf",
            "arial.ttf",
        ]:
            try:
                return ImageFont.truetype(fb, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _measure_text(
        self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
    ) -> Tuple[int, int]:
        """Return (width, height) of *text* rendered with *font*."""
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]

    def _compute_column_width(
        self,
        draw: ImageDraw.ImageDraw,
        symbols: List[str],
        code_table: Dict[str, List[int]],
        font: ImageFont.FreeTypeFont,
    ) -> int:
        """Calculate a uniform column width that fits every header and code."""
        max_w = self.font_size  # Minimum
        for sym in symbols:
            w, _ = self._measure_text(draw, sym, font)
            max_w = max(max_w, w)
            for code in code_table[sym]:
                w, _ = self._measure_text(draw, str(code), font)
                max_w = max(max_w, w)
        # Add comfortable padding (50 % extra)
        return int(max_w * 1.5)

    def _render_row_block(
        self,
        img: Image.Image,
        symbols: List[str],
        code_table: Dict[str, List[int]],
        x: int,
        y: int,
        font_path: Optional[str],
        track_annotations: bool,
    ) -> int:
        """Render one horizontal block: header row + separator + code rows.

        Returns the Y position below this block.
        """
        draw = ImageDraw.Draw(img)
        font = self._load_font(font_path, self.font_size)
        col_w = self._compute_column_width(draw, symbols, code_table, font)
        row_h = self.font_size + self.spacing

        # --- Track section (row block) start ---
        pairs_start_idx = len(self._text_renderer.collected_pair_bboxes)
        section_min_x = float("inf")
        section_min_y = float("inf")
        section_max_x = float("-inf")
        section_max_y = float("-inf")

        # ── 1. Header row ───────────────────────────────────────────────
        current_y = y
        for col_idx, sym in enumerate(symbols):
            col_x = x + col_idx * col_w
            # Render the symbol header (tracked as element so it appears in pair bbox)
            self._text_renderer.render_varied_text(
                img, sym, col_x, current_y,
                font_path or "", self.font_size, self.BASE_COLOR,
                track_annotations=track_annotations,
            )

        current_y += row_h

        # ── 2. Separator line below header ──────────────────────────────
        line_x_end = x + len(symbols) * col_w
        draw.line([(x, current_y), (line_x_end, current_y)], fill="#2C2416", width=1)
        current_y += 4

        # ── 3. Code rows ────────────────────────────────────────────────
        max_codes_in_row = max(len(code_table[sym]) for sym in symbols)

        for code_row_idx in range(max_codes_in_row):
            for col_idx, sym in enumerate(symbols):
                codes = code_table[sym]
                if code_row_idx >= len(codes):
                    continue

                col_x = x + col_idx * col_w
                code_str = str(codes[code_row_idx])

                # Track element bboxes for individual code numbers
                elem_start = len(self._text_renderer.collected_element_bboxes)
                self._text_renderer.render_varied_text(
                    img, code_str, col_x, current_y,
                    font_path or "", self.font_size, self.BASE_COLOR,
                    track_annotations=track_annotations,
                )

            current_y += row_h

        # ── 4. Build cell (pair) annotations per symbol ─────────────────
        if track_annotations:
            # We need to group element annotations by column.
            # Re-render to associate: walk collected elements since pairs_start.
            # Simpler approach: build cell bboxes from geometry directly.
            all_codes_count = [len(code_table[sym]) for sym in symbols]
            total_rows = max(all_codes_count) if all_codes_count else 0

            for col_idx, sym in enumerate(symbols):
                col_x = x + col_idx * col_w
                n_codes = len(code_table[sym])
                if n_codes == 0:
                    continue

                # Cell bbox: from header top → last code row bottom, across col_w
                cell_top = y
                cell_bottom = y + row_h + 4 + n_codes * row_h  # header + separator + codes
                cell_right = col_x + col_w - (col_w - self.font_size) // 2

                cell_bbox = BoundingBox()
                cell_bbox.text = f"{sym}:{','.join(str(c) for c in code_table[sym])}"
                cell_bbox.min_x = float(col_x)
                cell_bbox.min_y = float(cell_top)
                cell_bbox.max_x = float(col_x + col_w)
                cell_bbox.max_y = float(cell_bottom)

                if cell_bbox.is_valid():
                    self._text_renderer.collected_pair_bboxes.append(cell_bbox)

            # ── 5. Build row-block (section) annotation ──────────────────
            block_width = len(symbols) * col_w
            block_height = row_h + 4 + max_codes_in_row * row_h

            section_bbox = BoundingBox()
            section_bbox.text = (
                f"RowBlock({''.join(symbols)}) "
                f"{len(symbols)} symbols × up to {max_codes_in_row} codes"
            )
            section_bbox.min_x = float(x)
            section_bbox.min_y = float(y)
            section_bbox.max_x = float(x + block_width)
            section_bbox.max_y = float(y + block_height)

            if section_bbox.is_valid():
                self._text_renderer.collected_section_bboxes.append(section_bbox)

        # ── 6. Bottom separator line ─────────────────────────────────────
        draw.line(
            [(x, current_y), (line_x_end, current_y)],
            fill="#2C2416", width=1,
        )
        current_y += 2

        return current_y
