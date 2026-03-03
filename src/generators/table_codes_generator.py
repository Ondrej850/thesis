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

Overflow handling:
  - Horizontal: columns-per-row is automatically capped so each row block
    fits within (paper_width - left_x - right_margin).
  - Vertical: row blocks that would extend below (paper_height - bottom_margin)
    are silently skipped so nothing is rendered outside the paper.

Annotations tracked (using the existing COCO pipeline):
  element  (cat 0) – individual code number rendered on screen
  cell     (cat 1) – symbol header + all its code numbers (one column)
  row_block(cat 2) – a full multi-symbol row with all code rows

Path: src/generators/table_codes_generator.py
"""

from __future__ import annotations

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

    BASE_COLOR: Tuple[int, int, int] = (44, 36, 22)  # Dark-brown ink

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
            The same call with the same config always produces a fresh random
            assignment; cache this result externally for stable previews.
        """
        symbols = self.config.get_symbols()
        total = self.config.total_codes_needed()

        # Pool large enough to guarantee uniqueness
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
        code_table: Optional[Dict[str, List[int]]] = None,
        paper_width: int = 800,
        paper_height: int = 1100,
        right_margin: int = 50,
        bottom_margin: int = 50,
        track_annotations: bool = True,
    ) -> int:
        """Render the full code table onto *img* and return the next Y position.

        Args:
            img: The PIL image to draw on.
            x: Left margin of the table.
            y: Top Y position to start drawing.
            font_path: Path to the handwritten TTF font (may be None).
            code_table: Pre-generated symbol→codes mapping. If None, a new
                one is generated (use the cached version from the GUI).
            paper_width: Total image width — used to cap columns per row.
            paper_height: Total image height — row blocks that would exceed
                (paper_height - bottom_margin) are skipped.
            right_margin: Horizontal right-side margin in pixels.
            bottom_margin: Vertical bottom margin in pixels.
            track_annotations: Whether to accumulate COCO bounding boxes.

        Returns:
            Y position after the last rendered row block.
        """
        if code_table is None:
            code_table = self.generate_code_table()

        symbols = self.config.get_symbols()

        # ── Compute a uniform column width across ALL symbols ────────────
        draw = ImageDraw.Draw(img)
        font = self._load_font(font_path, self.font_size)
        col_w = self._compute_column_width(draw, symbols, code_table, font)

        # ── Auto-fit columns to available paper width ────────────────────
        available_width = paper_width - x - right_margin
        cols = max(1, available_width // col_w)

        row_chunks: List[List[str]] = [
            symbols[i: i + cols] for i in range(0, len(symbols), cols)
        ]

        max_y = paper_height - bottom_margin
        current_y = y

        for chunk in row_chunks:
            max_codes = max((len(code_table[s]) for s in chunk), default=0)
            row_h = self.font_size + self.spacing
            # Estimate block height: header row + sep line + code rows + sep line
            block_h = row_h + 4 + max_codes * row_h + 4

            if current_y + block_h > max_y:
                # Would overflow — stop here, don't render partial blocks
                print(
                    f"[TableCodes] Stopping at chunk '{chunk[0]}…': "
                    f"would exceed bottom margin (y={current_y}, block_h={block_h}, max_y={max_y})"
                )
                break

            current_y = self._render_row_block(
                img, chunk, code_table, x, current_y, col_w, font_path, font, track_annotations
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
        """Calculate a uniform column width from the widest symbol and code across ALL columns."""
        max_w = self.font_size  # Minimum
        for sym in symbols:
            w, _ = self._measure_text(draw, sym, font)
            max_w = max(max_w, w)
            for code in code_table[sym]:
                w, _ = self._measure_text(draw, str(code), font)
                max_w = max(max_w, w)
        return max_w + self.config.column_spacing  # text width + user-controlled spacing

    def _render_row_block(
        self,
        img: Image.Image,
        symbols: List[str],
        code_table: Dict[str, List[int]],
        x: int,
        y: int,
        col_w: int,
        font_path: Optional[str],
        font: ImageFont.FreeTypeFont,
        track_annotations: bool,
    ) -> int:
        """Render one horizontal block: header row + separator + code rows + closing line.

        Returns the Y position below this block.
        """
        draw = ImageDraw.Draw(img)
        row_h = self.font_size + self.spacing
        line_x_end = x + len(symbols) * col_w

        # ── 1. Header row (symbol letters / n-grams / nulls) ────────────
        current_y = y
        for col_idx, sym in enumerate(symbols):
            col_x = x + col_idx * col_w
            text_w, _ = self._measure_text(draw, sym, font)
            centered_x = col_x + (col_w - text_w) // 2
            self._text_renderer.render_varied_text(
                img, sym, centered_x, current_y,
                font_path or "", self.font_size, self.BASE_COLOR,
                track_annotations=track_annotations,
            )
        current_y += row_h

        # ── 2. Separator line below header ──────────────────────────────
        draw.line([(x, current_y), (line_x_end, current_y)], fill="#2C2416", width=1)
        current_y += 4

        # ── 3. Code rows ─────────────────────────────────────────────────
        max_codes_in_row = max((len(code_table[sym]) for sym in symbols), default=0)
        for code_row_idx in range(max_codes_in_row):
            for col_idx, sym in enumerate(symbols):
                codes = code_table[sym]
                if code_row_idx >= len(codes):
                    continue
                col_x = x + col_idx * col_w
                code_str = str(codes[code_row_idx])
                text_w, _ = self._measure_text(draw, code_str, font)
                centered_x = col_x + (col_w - text_w) // 2
                self._text_renderer.render_varied_text(
                    img, code_str, centered_x, current_y,
                    font_path or "", self.font_size, self.BASE_COLOR,
                    track_annotations=track_annotations,
                )
            current_y += row_h

        # ── 4. Vertical column separator lines ───────────────────────────
        if self.config.draw_vertical_lines:
            block_top = y
            block_bottom = current_y  # just before the closing separator line
            for col_idx in range(len(symbols) + 1):
                vx = x + col_idx * col_w
                draw.line([(vx, block_top), (vx, block_bottom)], fill="#2C2416", width=1)

        # ── 5. Build geometry-based COCO annotations ─────────────────────
        if track_annotations:
            for col_idx, sym in enumerate(symbols):
                n_codes = len(code_table[sym])
                if n_codes == 0:
                    continue
                col_x = x + col_idx * col_w
                cell_bottom = y + row_h + 4 + n_codes * row_h
                cell_bbox = BoundingBox()
                cell_bbox.text = f"{sym}:{','.join(str(c) for c in code_table[sym])}"
                cell_bbox.min_x = float(col_x)
                cell_bbox.min_y = float(y)
                cell_bbox.max_x = float(col_x + col_w)
                cell_bbox.max_y = float(cell_bottom)
                if cell_bbox.is_valid():
                    self._text_renderer.collected_pair_bboxes.append(cell_bbox)

            block_bbox = BoundingBox()
            block_bbox.text = (
                f"RowBlock({''.join(symbols)}) "
                f"{len(symbols)} symbols × up to {max_codes_in_row} codes"
            )
            block_bbox.min_x = float(x)
            block_bbox.min_y = float(y)
            block_bbox.max_x = float(line_x_end)
            block_bbox.max_y = float(current_y)
            if block_bbox.is_valid():
                self._text_renderer.collected_section_bboxes.append(block_bbox)

        # ── 5. Closing separator line ────────────────────────────────────
        draw.line([(x, current_y), (line_x_end, current_y)], fill="#2C2416", width=1)
        current_y += 2

        return current_y
