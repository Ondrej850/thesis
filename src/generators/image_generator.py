import random
from typing import List, Optional, Tuple
import os

from src.models import PaperConfig, FontConfig
from src.models.table_codes_config import TableCodesConfig
from src.annotations.coco_manager import COCOAnnotationManager
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .text_variation import VariatedTextRenderer, CipherEntryRenderer
from .table_codes_generator import TableCodesGenerator


class CipherImageGenerator:
    """Generates aged cipher document images"""

    def __init__(self, paper_config: PaperConfig, font_config: FontConfig, variation_level: str = "medium"):
        self.paper_config = paper_config
        self.font_config = font_config
        # Create low-level renderer and wrap it in high-level cipher renderer
        text_renderer = VariatedTextRenderer(variation_level)
        self.cipher_renderer = CipherEntryRenderer(text_renderer)

        # Use new COCO manager
        self.coco_manager = COCOAnnotationManager()
        self.current_image_id = None

    def create_aged_paper(self) -> Image.Image:
        """Create aged paper background with a randomly chosen base color."""
        # Palette spanning clean white → warm cream → parchment → medium brown
        base_palette = [
            '#FAFAF7',  # clean white
            '#F7F2E8',  # very light cream
            '#F2EBD9',  # light cream
            '#EDE0C4',  # warm cream / parchment light
            '#E8D5B0',  # classic parchment
            '#DFCA9C',  # warm tan
            '#D4B88A',  # medium tan
            '#C8A878',  # golden brown (like aged document photo)
            '#BF9C6A',  # medium brown
            '#B89060',  # darker warm brown
        ]
        base_hex = random.choice(base_palette)
        img = Image.new('RGB', (self.paper_config.width, self.paper_config.height),
                        color=base_hex)
        draw = ImageDraw.Draw(img)

        # Apply aging effects based on aging_level
        aging = self.paper_config.aging_level / 100.0

        # Add yellowing/browning — draw all dots onto a single overlay.
        # Derive aging dot colors as slightly darkened/warmer shades of the base.
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
                overlay_draw.ellipse([x, y, x + size, y + size],
                                     fill=(*color, alpha))
            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

        # Add defects
        if 'stains' in self.paper_config.defects:
            self._add_stains(img, int(10 * aging))

        if 'burns' in self.paper_config.defects:
            self._add_burns(img, int(5 * aging))

        if 'holes' in self.paper_config.defects:
            self._add_holes(img, int(3 * aging))

        if 'tears' in self.paper_config.defects:
            self._add_tears(img, int(5 * aging))

        if 'wrinkled_edges' in self.paper_config.defects:
            self._add_wrinkled_edges(img)

        # Apply slight blur for texture
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

        return img

    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def _add_stains(self, img, count):
        """Add stains to paper"""
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(0, img.width)
            y = random.randint(0, img.height)
            size = random.randint(20, 80)
            color = random.choice(['#8B7355', '#A0826D', '#6B5D4F'])
            alpha = random.randint(30, 80)
            draw.ellipse([x, y, x + size, y + size],
                         fill=(*self._hex_to_rgb(color), alpha))

    def _add_burns(self, img, count):
        """Add burn marks"""
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(0, img.width)
            y = random.randint(0, img.height)
            size = random.randint(15, 40)
            draw.ellipse([x, y, x + size, y + size],
                         fill=(80, 60, 40, 120))

    def _add_holes(self, img, count):
        """Add holes from rodents/insects"""
        draw = ImageDraw.Draw(img, 'RGBA')
        for _ in range(count):
            x = random.randint(50, img.width - 50)
            y = random.randint(50, img.height - 50)
            size = random.randint(5, 15)
            draw.ellipse([x, y, x + size, y + size],
                         fill=(255, 255, 255, 255))

    def _add_tears(self, img, count):
        """Add tears on edges"""
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
            elif edge == 'bottom':
                x = random.randint(img.width - 20, img.width)
                y = random.randint(0, img.height)
                points = [(x, y), (x - random.randint(10, 30), y + random.randint(-20, 20))]
            draw.line(points, fill=(0, 0, 0, 255), width=2)

    def _add_wrinkled_edges(self, img):
        """Add wrinkled edges effect"""
        # Darken edges slightly
        draw = ImageDraw.Draw(img, 'RGBA')
        edge_width = 30

        # Top edge
        for i in range(edge_width):
            alpha = int(50 * (1 - i / edge_width))
            draw.line([(0, i), (img.width, i)], fill=(100, 80, 60, alpha))

        # Bottom edge
        for i in range(edge_width):
            alpha = int(50 * (1 - i / edge_width))
            draw.line([(0, img.height - 1 - i), (img.width, img.height - 1 - i)],
                      fill=(100, 80, 60, alpha))

    def register_image(self, filename: str) -> int:
        """Register a new image with COCO manager and return its ID"""
        image_id = self.coco_manager.add_image(
            filename,
            self.paper_config.width,
            self.paper_config.height
        )
        self.current_image_id = image_id
        return image_id


    def render_cipher_text(self, img: Image.Image, cipher_entries: List[Tuple[str, str]],
                           start_x: int, start_y: int, block_id: int = 0,
                           font_path: Optional[str] = None, use_variations: bool = True,
                           track_annotations: bool = True,
                           right_margin: int = 50, bottom_margin: int = 50,
                           ink_color: Optional[Tuple[int, int, int]] = None,
                           pair_format: str = "text_first",
                           line_spacing_variation: float = 0.0) -> int:
        """Render cipher text with keys on image using multi-column layout"""

        # Load font path
        if font_path is None:
            font_path = self._get_fallback_font_path()

        if use_variations and font_path:
            # Multi-column layout configuration
            left_margin = start_x
            top_margin = start_y
            column_spacing = 30  # Gap between columns

            # Calculate available space
            max_height = self.paper_config.height - bottom_margin

            # Initialize column tracking
            current_column_x = left_margin
            current_y = top_margin
            column_max_x = left_margin  # Track the widest point in current column
            column_number = 1  # Track which column we're in

            separator = self._get_separator()

            # Entry height is constant (same font/spacing for every entry)
            estimated_entry_height = self.font_config.font_size + self.font_config.spacing
            if self.font_config.column_separator != 'none':
                estimated_entry_height += self.font_config.font_size * 0.6

            # Bail out early if there is no room for even the first entry.
            # Without this check the first entry (idx == 0) bypasses the column-
            # transition guard and renders below the paper, producing phantom
            # annotations that don't correspond to visible content.
            if start_y + estimated_entry_height > max_height:
                print(f"[WARNING] render_cipher_text: start_y={start_y} leaves no room "
                      f"for entries (max_height={max_height}), skipping.")
                return int(start_y)

            print(f"[DEBUG] render_cipher_text: use_variations={use_variations}, track_annotations={track_annotations}")
            print(f"[DEBUG] Total entries to render: {len(cipher_entries)}")
            print(f"[DEBUG] Multi-column layout: max_height={max_height}, column_spacing={column_spacing}")

            # Start tracking this section (column 1)
            if track_annotations:
                self.cipher_renderer.start_section()

            for idx, (cipher_text, key_value) in enumerate(cipher_entries):
                print(f"[DEBUG] Rendering entry {idx + 1}: '{cipher_text}' - '{key_value}'")

                # Check if we need to move to next column
                if current_y + estimated_entry_height > max_height and idx > 0:
                    # End section for the column that just filled up
                    if track_annotations:
                        section_bbox = self.cipher_renderer.end_section(block_id * 100 + column_number)
                        if section_bbox:
                            print(f"[DEBUG] Created section bbox for Column {column_number}: {section_bbox.text}")

                    # Proposed start of next column
                    next_col_x = column_max_x + column_spacing

                    # Lookahead: find the longest entry that would fill the next column.
                    # If even the longest entry doesn't fit between next_col_x and the
                    # right margin, don't start the column.
                    col_height = max_height - top_margin
                    entries_per_col = max(1, int(col_height // estimated_entry_height))
                    next_col_entries = cipher_entries[idx: idx + entries_per_col]

                    # Measure with the actual font so proportional glyph widths are correct.
                    # Add 20 px for the two 10-px inter-part gaps and a 15 % margin for the
                    # character-size / position variations applied during rendering.
                    VARIATION_MARGIN = 1.15
                    INTER_PART_GAPS = 20
                    try:
                        measure_font = ImageFont.truetype(font_path, self.font_config.font_size)
                        max_entry_width = VARIATION_MARGIN * max(
                            measure_font.getlength(ct + separator + kv) + INTER_PART_GAPS
                            for ct, kv in next_col_entries
                        ) if next_col_entries else 0
                    except Exception:
                        char_w = self.font_config.font_size * 0.6
                        max_entry_width = max(
                            len(ct + separator + kv) * char_w + INTER_PART_GAPS
                            for ct, kv in next_col_entries
                        ) if next_col_entries else 0

                    available_for_next = self.paper_config.width - right_margin - next_col_x
                    if available_for_next < max_entry_width:
                        print(f"[WARNING] Not enough space for next column: "
                              f"longest entry ~{max_entry_width:.0f}px, have {available_for_next:.0f}px. Stopping.")
                        break

                    # Move to next column
                    current_column_x = next_col_x
                    current_y = top_margin
                    column_number += 1
                    print(f"[DEBUG] Moving to new column {column_number} at x={current_column_x}, resetting y to {top_margin}")

                    # Start tracking new section for this column
                    if track_annotations:
                        self.cipher_renderer.start_section()

                # Render with variations and annotation tracking.
                # Allow text to use all space up to the paper's right margin; x_limit inside
                # render_cipher_entry will clip anything that would spill past it.
                available_width = self.paper_config.width - current_column_x - right_margin

                elements_before = (
                    len(self.cipher_renderer._text_renderer.collected_element_bboxes)
                    if track_annotations else 0
                )

                next_y = self.cipher_renderer.render_cipher_entry(
                    img, cipher_text, key_value, current_column_x, current_y,
                    font_path, self.font_config.font_size, separator,
                    column_separator=self.font_config.column_separator,
                    paper_width=self.paper_config.width,
                    track_annotations=track_annotations,
                    max_column_width=available_width,
                    ink_color=ink_color,
                    pair_format=pair_format,
                )

                # Apply per-line spacing variation if configured
                if line_spacing_variation > 0:
                    extra = random.uniform(-line_spacing_variation, line_spacing_variation)
                    next_y += extra

                # Update column_max_x from the element bboxes added by this entry.
                # Element bboxes are always created for any rendered text (even a single
                # element), so this works correctly even when the right part is clipped.
                if track_annotations:
                    element_bboxes = self.cipher_renderer._text_renderer.collected_element_bboxes
                    new_elements = element_bboxes[elements_before:]
                    for elem in new_elements:
                        if elem.is_valid():
                            column_max_x = max(column_max_x, elem.max_x)
                    if not new_elements:
                        # Nothing was tracked; conservatively claim the full available width
                        column_max_x = max(column_max_x, current_column_x + available_width)
                else:
                    # Fallback estimate, capped at the paper edge
                    text_width = len(cipher_text + separator + key_value) * (self.font_config.font_size * 0.6)
                    column_max_x = max(column_max_x, min(current_column_x + text_width,
                                                         self.paper_config.width - right_margin))

                # Update current Y position
                current_y = next_y

            # End section for the last column
            if track_annotations:
                section_bbox = self.cipher_renderer.end_section(block_id * 100 + column_number)
                if section_bbox:
                    print(f"[DEBUG] Created section bbox for Column {column_number}: {section_bbox.text}")

            # Collect all annotations after rendering all entries
            if track_annotations and self.current_image_id is not None:
                annotations = self.cipher_renderer.get_annotations(self.current_image_id)
                print(f"[DEBUG] Exporting {len(annotations)} annotations to COCO manager")
                self.coco_manager.add_annotations(self.current_image_id, annotations)

            return int(current_y)

        else:
            # Fallback to original non-varied rendering
            return self._render_text_simple(img, cipher_entries, start_x, start_y,
                                            block_id, font_path)

    def _get_fallback_font_path(self) -> Optional[str]:
        """Get a fallback font path"""
        fallback_fonts = [
            "times.ttf",
            "georgia.ttf",
            "arial.ttf",
            "C:\\Windows\\Fonts\\times.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/System/Library/Fonts/Times.ttc",
        ]

        for font_path in fallback_fonts:
            if os.path.exists(font_path):
                return font_path
        return None

    def _render_text_simple(self, img: Image.Image, cipher_entries: List[Tuple[str, str]],
                            start_x: int, start_y: int, block_id: int,
                            font_path: Optional[str]) -> int:
        """Simple rendering without variations (fallback)"""
        draw = ImageDraw.Draw(img)

        # Load font
        font = self._load_font(font_path)

        y_offset = start_y
        line_height = self.font_config.font_size + self.font_config.spacing

        for cipher_text, key_value in cipher_entries:
            text_bbox = draw.textbbox((start_x, y_offset), cipher_text, font=font)
            draw.text((start_x, y_offset), cipher_text, fill='#2C2416', font=font)

            separator_x = text_bbox[2] + 10
            separator = self._get_separator()
            draw.text((separator_x, y_offset), separator, fill='#2C2416', font=font)

            key_x = separator_x + 50
            key_bbox = draw.textbbox((key_x, y_offset), key_value, font=font)
            draw.text((key_x, y_offset), key_value, fill='#2C2416', font=font)

            y_offset += line_height

            if self.font_config.column_separator != 'none':
                line_width = key_bbox[2] - start_x
                self._draw_column_separator(draw, start_x, y_offset, line_width)
                y_offset += 5

        return y_offset

    def _load_font(self, font_path: Optional[str] = None):
        """Load font with fallback options"""
        # If custom font path provided, try to load it
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, self.font_config.font_size)
            except Exception as e:
                print(f"Failed to load custom font {font_path}: {e}")

        # Try common handwritten/historical fonts
        fallback_fonts = [
            "times.ttf",
            "georgia.ttf",
            "arial.ttf",
            "calibri.ttf",
            "C:\\Windows\\Fonts\\times.ttf",
            "C:\\Windows\\Fonts\\georgia.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/System/Library/Fonts/Times.ttc",
        ]

        for font_name in fallback_fonts:
            try:
                return ImageFont.truetype(font_name, self.font_config.font_size)
            except:
                continue

        # Last resort: default font
        print("Warning: Using default font. Add custom fonts for better results.")
        return ImageFont.load_default()

    def _get_separator(self) -> str:
        """Get separator between cipher and key"""
        if self.font_config.key_separator == 'dots':
            return " . . . "
        elif self.font_config.key_separator == 'dashes':
            return " " + "—" * self.font_config.dash_count + " "
        else:
            return "    "

    def _draw_column_separator(self, draw, x, y, width):
        """Draw column separator line"""
        if self.font_config.column_separator == 'line':
            draw.line([(x, y), (x + width, y)], fill='#2C2416', width=1)
        elif self.font_config.column_separator == 'double_line':
            draw.line([(x, y), (x + width, y)], fill='#2C2416', width=1)
            draw.line([(x, y + 3), (x + width, y + 3)], fill='#2C2416', width=1)

    def export_coco_annotations(self, output_path: str):
        """Export COCO annotations to file"""
        self.coco_manager.export_coco(output_path)

    def get_annotation_stats(self):
        """Get statistics about collected annotations"""
        return self.coco_manager.get_stats()

    def reset_annotations(self):
        """Reset all annotations (useful when generating multiple batches)"""
        self.coco_manager.reset()
        self.cipher_renderer.reset_annotations()

    # ------------------------------------------------------------------
    # Title / header rendering
    # ------------------------------------------------------------------

    TITLE_TEMPLATES = [
        # Multi-word titles (render as section + elements)
        "Alphabetum Cifratum",
        "Cifra Nova",
        "Clavis Secreta",
        "Tabula Cifrarum",
        "Liber Secretus",
        "Cifra Generalis",
        "Alphabetum Secretum",
        "Cifra Diplomatica",
        "Clavis Alphabetica",
        "Cifra Regia",
        "Tabula Secretorum",
        "Clavis Cifrae",
        "Liber Cifrarum",
        "Tabula Nova",
        "Cifra Universalis",
        "Clavis Generalis",
        "Alphabetum Novum",
        "Liber Clausus",
        # Single-word titles (render as element only, no section)
        "Nomenclator",
        "Cifra",
        "Clavis",
        "Alphabetum",
        "Nomenclatura",
        "Sigillum",
        "Tabula",
        "Secretum",
        "Vocabularium",
        "Registrum",
    ]

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
    ) -> int:
        """Render a title / header line above the cipher content.

        Each word becomes a separate element annotation.  A section annotation
        wrapping the whole title is added only when the title contains more than
        one word — a single-word title is just an element, not a section.

        Args:
            title_text: Explicit title string; if None, one is picked at random.
            title_font_size: Font size for the title; defaults to 1.5x base font.

        Returns:
            Y position below the title (ready for next content).
        """
        if font_path is None:
            font_path = self._get_fallback_font_path()

        base_color = ink_color or (44, 36, 22)
        fs = title_font_size or int(self.font_config.font_size * 1.5)
        text = title_text or random.choice(self.TITLE_TEMPLATES)
        words = text.split()

        renderer = self.cipher_renderer._text_renderer

        # Track element bboxes added during title rendering
        elems_before = len(renderer.collected_element_bboxes)

        # Render each word as a separate tracked element
        current_x = float(start_x)
        for word in words:
            end_x, end_y = renderer.render_varied_text(
                img, word, current_x, start_y,
                font_path or "", fs, base_color,
                track_annotations=track_annotations,
            )
            # Use the actual end_x returned by the renderer (accounts for variations)
            current_x = end_x + fs * 0.4  # inter-word gap

        # Build a section bbox only for multi-word titles
        if track_annotations and len(words) > 1:
            elems_after = len(renderer.collected_element_bboxes)
            new_elems = renderer.collected_element_bboxes[elems_before:elems_after]
            if new_elems:
                from src.models.coco_annotation import BoundingBox
                section_bbox = BoundingBox()
                section_bbox.text = f"Title: {text}"
                for eb in new_elems:
                    if eb.is_valid():
                        section_bbox.min_x = min(section_bbox.min_x, eb.min_x)
                        section_bbox.min_y = min(section_bbox.min_y, eb.min_y)
                        section_bbox.max_x = max(section_bbox.max_x, eb.max_x)
                        section_bbox.max_y = max(section_bbox.max_y, eb.max_y)
                if section_bbox.is_valid():
                    renderer.collected_section_bboxes.append(section_bbox)

        # Feed annotations to COCO manager
        if track_annotations and self.current_image_id is not None:
            annotations = renderer.get_annotations(self.current_image_id)
            self.coco_manager.add_annotations(self.current_image_id, annotations)
            # Reset so they aren't double-counted by later render passes
            renderer.collected_element_bboxes = []
            renderer.collected_pair_bboxes = []
            renderer.collected_section_bboxes = []

        next_y = start_y + fs + self.font_config.spacing * 2
        return int(next_y)

    # ------------------------------------------------------------------
    # Table-codes rendering
    # ------------------------------------------------------------------

    def render_table_codes(
        self,
        img: Image.Image,
        table_config: TableCodesConfig,
        start_x: int,
        start_y: int,
        font_path: Optional[str] = None,
        use_variations: bool = True,
        track_annotations: bool = True,
        code_table: Optional[dict] = None,
        font_size: Optional[int] = None,
        ink_color: Optional[Tuple[int, int, int]] = None,
    ) -> int:
        """Render a homophonic code table on *img*.

        Args:
            img: The PIL image to draw on (modified in-place).
            table_config: Configuration for what to put in the table.
            start_x: Left margin in pixels.
            start_y: Top margin in pixels.
            font_path: Path to handwritten TTF font; None uses system fallback.
            use_variations: Whether to apply handwriting variation effects.
            track_annotations: Whether to record COCO bounding boxes.
            code_table: Pre-generated symbol→codes mapping for stable previews.
                If None, a fresh random assignment is generated.

        Returns:
            Y position below the last rendered row block.
        """
        if font_path is None:
            font_path = self._get_fallback_font_path()

        variation_level = "medium" if use_variations else "none"
        actual_font_size = font_size if font_size is not None else self.font_config.font_size
        table_gen = TableCodesGenerator(
            config=table_config,
            font_size=actual_font_size,
            spacing=self.font_config.spacing,
            variation_level=variation_level,
            ink_color=ink_color,
        )

        next_y = table_gen.render_table(
            img, start_x, start_y, font_path,
            code_table=code_table,
            paper_width=self.paper_config.width,
            paper_height=self.paper_config.height,
            track_annotations=track_annotations,
        )

        print(f"[DEBUG] render_table_codes: rendered table, next_y={next_y}")

        # Feed collected annotations into the shared COCO manager
        if track_annotations and self.current_image_id is not None:
            annotations = table_gen.get_annotations(self.current_image_id)
            print(f"[DEBUG] Table codes: exporting {len(annotations)} annotations")
            self.coco_manager.add_annotations(self.current_image_id, annotations)

        return int(next_y)

    def export_yolo_annotations(self, output_dir: str, image_filename: str) -> str:
        """Export YOLO format annotations for *image_filename*.

        Args:
            output_dir: Directory where the ``.txt`` and ``classes.txt`` are saved.
            image_filename: Filename used when the image was registered.

        Returns:
            Path to the written YOLO ``.txt`` file.
        """
        return self.coco_manager.export_yolo(output_dir, image_filename)