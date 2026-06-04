"""
Table codes generator — renders homophonic cipher code tables with
realistic handwriting variations and COCO annotation support.

Layout per "row block":

    A    B    C    D    E    ...
    ─────────────────────────────
    12    7   41   22    1
    35   19   84   63   14
    91        55        23

Overflow handling:
  - Horizontal: columns auto-capped to paper width.
  - Vertical: blocks that overflow the bottom margin are skipped.

COCO annotation categories:
  element  (0) – individual rendered code number
  cell     (1) – symbol header + all its code numbers
  row_block(2) – a full multi-symbol row
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.models.coco_annotation import BoundingBox, COCOAnnotation
from src.models.table_codes_config import TableCodesConfig
from src.generators.text_variation import VariatedTextRenderer
from src.constants import FALLBACK_FONTS


class TableCodesRenderer:
    """Generates and renders a homophonic code table on a PIL Image."""

    BASE_COLOR: Tuple[int, int, int] = (44, 36, 22)

    def __init__(
        self,
        config: TableCodesConfig,
        font_size: int,
        spacing: int,
        variation_level: str = "medium",
        ink_color: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        self.config = config
        self.font_size = font_size
        self.spacing = spacing
        self._text_renderer = VariatedTextRenderer(variation_level)
        if ink_color is not None:
            self.BASE_COLOR = ink_color

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_code_table(self) -> Dict[str, List[int]]:
        """Assign unique shuffled code numbers to every symbol. Returns symbol → sorted codes."""
        symbols = self.config.get_symbols()
        total = self.config.total_codes_needed()
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
        """Render the full code table onto *img*. Returns the Y position below the last row block."""
        if code_table is None:
            code_table = self.generate_code_table()

        symbols = self.config.get_symbols()
        draw = ImageDraw.Draw(img)
        font = self._load_font(font_path, self.font_size)
        col_w = self._compute_column_width(draw, symbols, code_table, font)

        available_width = paper_width - x - right_margin
        cols_per_row = max(1, available_width // col_w)
        row_chunks = [symbols[i: i + cols_per_row] for i in range(0, len(symbols), cols_per_row)]

        max_y = paper_height - bottom_margin
        current_y = y
        line_h = self._get_line_height(font)

        for chunk in row_chunks:
            max_codes = max((len(code_table[s]) for s in chunk), default=0)
            visual_rows = math.ceil(max_codes / 2) if self.config.use_pair_grid else max_codes
            block_h = line_h + 2 + visual_rows * line_h + 1

            if current_y + block_h > max_y:
                break

            current_y = self._render_row_block(
                img, chunk, code_table, x, current_y, col_w, font_path, font, track_annotations,
            )
            current_y += self.config.row_spacing

        return current_y

    def get_annotations(self, image_id: int = 0) -> List[COCOAnnotation]:
        return self._text_renderer.get_annotations(image_id)

    def reset_annotations(self) -> None:
        self._text_renderer.collected_element_bboxes = []
        self._text_renderer.collected_pair_bboxes = []
        self._text_renderer.collected_section_bboxes = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_line_height(self, font: ImageFont.FreeTypeFont) -> int:
        try:
            ascent, descent = font.getmetrics()
            return ascent + descent
        except Exception:
            return self.font_size

    def _load_font(self, font_path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
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

    def _measure_text(self, draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]

    def _draw_wavy_line(
        self,
        draw: ImageDraw.ImageDraw,
        x1: int, y1: int, x2: int, y2: int,
        color: Tuple[int, int, int],
        width: int = 1,
        amplitude: float = 1.2,
        segment_len: int = 8,
    ) -> None:
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 2:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
            return
        n_segments = max(2, int(length / segment_len))
        nx = -dy / length
        ny = dx / length
        points: List[Tuple[float, float]] = [(float(x1), float(y1))]
        for i in range(1, n_segments):
            t = i / n_segments
            off = random.uniform(-amplitude, amplitude)
            points.append((x1 + dx * t + nx * off, y1 + dy * t + ny * off))
        points.append((float(x2), float(y2)))
        for a, b in zip(points, points[1:]):
            draw.line(
                [(int(round(a[0])), int(round(a[1]))), (int(round(b[0])), int(round(b[1])))],
                fill=color, width=width,
            )

    def _compute_column_width(
        self,
        draw: ImageDraw.ImageDraw,
        symbols: List[str],
        code_table: Dict[str, List[int]],
        font,
    ) -> int:
        max_sym_w = self.font_size
        max_code_w = self.font_size
        for sym in symbols:
            w, _ = self._measure_text(draw, sym, font)
            max_sym_w = max(max_sym_w, w)
            for code in code_table[sym]:
                w, _ = self._measure_text(draw, str(code), font)
                max_code_w = max(max_code_w, w)

        if self.config.use_pair_grid:
            inter_gap = max(4, self.font_size // 4)
            min_w = max(max_sym_w, 2 * max_code_w + inter_gap)
        else:
            min_w = max(max_sym_w, max_code_w)
        return min_w + self.config.column_spacing

    def _render_row_block(
        self,
        img: Image.Image,
        symbols: List[str],
        code_table: Dict[str, List[int]],
        x: int,
        y: int,
        col_w: int,
        font_path: Optional[str],
        font,
        track_annotations: bool,
    ) -> int:
        """Render one horizontal row block (header + separator + code rows + closing line).

        Returns the Y position below this block.
        """
        draw = ImageDraw.Draw(img)
        row_h = self._get_line_height(font)
        line_x_end = x + len(symbols) * col_w

        elems = self._text_renderer.collected_element_bboxes
        # Per-column list of element indices so we can build tight cell bboxes afterwards.
        col_elem_indices: Dict[int, List[int]] = {i: [] for i in range(len(symbols))}

        # ── 1. Header row ────────────────────────────────────────────────
        current_y = y
        for col_idx, sym in enumerate(symbols):
            before = len(elems)
            col_x = x + col_idx * col_w
            text_w, _ = self._measure_text(draw, sym, font)
            self._text_renderer.render_varied_text(
                img, sym, col_x + (col_w - text_w) // 2, current_y,
                font_path or "", self.font_size, self.BASE_COLOR,
                track_annotations=track_annotations,
            )
            if track_annotations and len(elems) > before:
                col_elem_indices[col_idx].append(len(elems) - 1)
        current_y += row_h

        # ── 2. Separator line below header ───────────────────────────────
        if self.config.draw_header_line:
            self._draw_wavy_line(draw, x, current_y, line_x_end, current_y, self.BASE_COLOR)
        current_y += 2

        # ── 3. Code rows ─────────────────────────────────────────────────
        max_codes = max((len(code_table[sym]) for sym in symbols), default=0)

        if self.config.use_pair_grid:
            inter_gap = max(4, self.font_size // 4)
            half_w = (col_w - self.config.column_spacing - inter_gap) // 2
            for vrow in range(math.ceil(max_codes / 2)):
                for col_idx, sym in enumerate(symbols):
                    codes = code_table[sym]
                    col_x = x + col_idx * col_w
                    for sub, left_offset in enumerate((0, half_w + inter_gap)):
                        idx = 2 * vrow + sub
                        if idx >= len(codes):
                            continue
                        before = len(elems)
                        code_str = str(codes[idx])
                        text_w, _ = self._measure_text(draw, code_str, font)
                        self._text_renderer.render_varied_text(
                            img, code_str,
                            col_x + left_offset + (half_w - text_w) // 2, current_y,
                            font_path or "", self.font_size, self.BASE_COLOR,
                            track_annotations=track_annotations,
                        )
                        if track_annotations and len(elems) > before:
                            col_elem_indices[col_idx].append(len(elems) - 1)
                current_y += row_h
        else:
            for code_row in range(max_codes):
                for col_idx, sym in enumerate(symbols):
                    codes = code_table[sym]
                    if code_row >= len(codes):
                        continue
                    before = len(elems)
                    col_x = x + col_idx * col_w
                    code_str = str(codes[code_row])
                    text_w, _ = self._measure_text(draw, code_str, font)
                    self._text_renderer.render_varied_text(
                        img, code_str, col_x + (col_w - text_w) // 2, current_y,
                        font_path or "", self.font_size, self.BASE_COLOR,
                        track_annotations=track_annotations,
                    )
                    if track_annotations and len(elems) > before:
                        col_elem_indices[col_idx].append(len(elems) - 1)
                current_y += row_h

        # ── 4. Vertical separator lines ───────────────────────────────────
        if self.config.draw_vertical_lines:
            for col_idx in range(len(symbols) + 1):
                vx = x + col_idx * col_w
                self._draw_wavy_line(draw, vx, y, vx, current_y, self.BASE_COLOR)

        # ── 5. COCO annotations ───────────────────────────────────────────
        if track_annotations:
            cells_added = 0
            for col_idx, sym in enumerate(symbols):
                indices = col_elem_indices[col_idx]
                if not indices:
                    continue
                cell_bbox = BoundingBox()
                cell_bbox.text = f"{sym}:{','.join(str(c) for c in code_table[sym])}"
                for i in indices:
                    eb = elems[i]
                    if eb.is_valid():
                        cell_bbox.add_point(eb.min_x, eb.min_y)
                        cell_bbox.add_point(eb.max_x, eb.max_y)
                if cell_bbox.is_valid():
                    self._text_renderer.collected_pair_bboxes.append(cell_bbox)
                    cells_added += 1

            if cells_added > 0:
                block_bbox = BoundingBox()
                block_bbox.text = f"RowBlock({''.join(symbols)}) {len(symbols)} symbols × up to {max_codes} codes"
                for cell in self._text_renderer.collected_pair_bboxes[-cells_added:]:
                    if cell.is_valid():
                        block_bbox.add_point(cell.min_x, cell.min_y)
                        block_bbox.add_point(cell.max_x, cell.max_y)
                if block_bbox.is_valid():
                    self._text_renderer.collected_section_bboxes.append(block_bbox)

        # ── 6. Closing separator line ─────────────────────────────────────
        if self.config.draw_header_line:
            self._draw_wavy_line(draw, x, current_y, line_x_end, current_y, self.BASE_COLOR)
        current_y += 1

        return current_y
