"""
Text Variation Engine for realistic handwriting effects with COCO annotation support
Path: src/generators/text_variation.py
"""

from PIL import Image, ImageDraw, ImageFont
import random
from typing import Tuple, Optional, List
import math
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.models.coco_annotation import BoundingBox, COCOAnnotation


class VariatedTextRenderer:
    """Low-level text renderer that applies realistic variations for handwritten appearance"""

    def __init__(self, variation_level: str = "medium"):
        """
        Initialize variation engine

        Args:
            variation_level: "low", "medium", "high" - controls amount of variation
        """
        self.variation_level = variation_level
        self.variation_settings = self._get_variation_settings(variation_level)

        # Word-level variation tracking
        self.current_word_base_size = None
        self.current_word_base_color = None
        self.current_word_angle = 0.0  # Slight angle for entire word
        self.variation_positions = []  # Which letters in word get variation

        # Bounding box tracking for annotations
        self.collected_element_bboxes = []  # Individual characters
        self.collected_pair_bboxes = []     # Character pairs
        self.collected_section_bboxes = []  # Text sections

        # Much lower probability - only 1-2 letters per word
        self.char_variation_probability = {
            "low": 0.12,     # ~1 letter per 8-letter word
            "medium": 0.18,  # ~1-2 letters per 7-letter word
            "high": 0.22,    # ~1-2 letters per 7-letter word
        }.get(variation_level, 0.18)

    def _get_variation_settings(self, level: str) -> dict:
        """Get variation parameters based on level"""
        settings = {
            "low": {
                "size_variation": 0.03,      # ±3% (very subtle)
                "rotation_max": 0.8,         # ±0.8 degrees
                "position_x": 0.2,           # ±0.2 pixels
                "position_y": 0.15,          # ±0.15 pixels
                "width_scale": 0.003,        # ±0.3%
                "height_scale": 0.003,       # ±0.3%
                "spacing_variation": 0.02,   # ±2% spacing (rarely used)
                "ink_variation": 1,          # ±1 in RGB
                "word_size_var": 0.02,       # ±2% per word
                "word_ink_var": 1,           # ±1 RGB per word
                "word_angle_max": 0.5,       # ±0.5 degrees per word
            },
            "medium": {
                "size_variation": 0.05,      # ±5% (subtle)
                "rotation_max": 1.5,         # ±1.5 degrees
                "position_x": 0.35,          # ±0.35 pixels
                "position_y": 0.25,          # ±0.25 pixels
                "width_scale": 0.008,        # ±0.8%
                "height_scale": 0.008,       # ±0.8%
                "spacing_variation": 0.04,   # ±4% spacing (rarely used)
                "ink_variation": 2,          # ±2 in RGB
                "word_size_var": 0.03,       # ±3% per word
                "word_ink_var": 1,           # ±1 RGB per word
                "word_angle_max": 1.0,       # ±1 degree per word
            },
            "high": {
                "size_variation": 0.07,      # ±7%
                "rotation_max": 2.5,         # ±2.5 degrees
                "position_x": 0.6,           # ±0.6 pixels
                "position_y": 0.4,           # ±0.4 pixels
                "width_scale": 0.012,        # ±1.2%
                "height_scale": 0.012,       # ±1.2%
                "spacing_variation": 0.06,   # ±6% spacing (rarely used)
                "ink_variation": 3,          # ±3 in RGB
                "word_size_var": 0.04,       # ±4% per word
                "word_ink_var": 2,           # ±2 RGB per word
                "word_angle_max": 1.5,       # ±1.5 degrees per word
            }
        }
        return settings.get(level, settings["medium"])

    def start_new_word(self, base_size: int, base_color: Tuple[int, int, int], word_length: int):
        """Initialize variations for a new word"""
        # Set word-level base values (slight variation per word)
        size_var = self.variation_settings["word_size_var"]
        self.current_word_base_size = int(base_size * (1.0 + random.uniform(-size_var, size_var)))

        ink_var = self.variation_settings["word_ink_var"]
        self.current_word_base_color = (
            max(0, min(255, base_color[0] + random.randint(-ink_var, ink_var))),
            max(0, min(255, base_color[1] + random.randint(-ink_var, ink_var))),
            max(0, min(255, base_color[2] + random.randint(-ink_var, ink_var)))
        )

        # Set a slight angle for the entire word (not perfectly horizontal)
        angle_max = self.variation_settings["word_angle_max"]
        self.current_word_angle = random.uniform(-angle_max, angle_max)

        # Decide which 1-2 letters in this word will have variation
        self.variation_positions = []
        if word_length > 0:
            # For a 7-letter word, typically get 1-2 positions
            num_variations = max(0, int(word_length * self.char_variation_probability))
            if num_variations > 0:
                self.variation_positions = random.sample(range(word_length),
                                                        min(num_variations, word_length))

    def should_apply_variation(self, char_index: int) -> bool:
        """Check if this specific character position should get variation"""
        return char_index in self.variation_positions

    def get_varied_font_size(self, base_size: int, char_index: int = -1) -> int:
        """Get varied font size for this character"""
        # Use word-level base size
        word_size = self.current_word_base_size if self.current_word_base_size else base_size

        if char_index >= 0 and not self.should_apply_variation(char_index):
            return word_size

        variation = self.variation_settings["size_variation"]
        factor = 1.0 + random.uniform(-variation, variation)
        return max(int(word_size * factor), word_size - 2)

    def get_varied_position(self, char_index: int = -1) -> Tuple[float, float]:
        """Get position offset for this character"""
        if char_index >= 0 and not self.should_apply_variation(char_index):
            return 0.0, 0.0

        x_offset = random.uniform(
            -self.variation_settings["position_x"],
            self.variation_settings["position_x"]
        )
        y_offset = random.uniform(
            -self.variation_settings["position_y"],
            self.variation_settings["position_y"]
        )
        return x_offset, y_offset

    def get_varied_rotation(self, char_index: int = -1) -> float:
        """Get rotation angle for this character"""
        if char_index >= 0 and not self.should_apply_variation(char_index):
            return 0.0

        max_rotation = self.variation_settings["rotation_max"]
        return random.uniform(-max_rotation, max_rotation)

    def get_varied_scale(self, char_index: int = -1) -> Tuple[float, float]:
        """Get width and height scale factors"""
        if char_index >= 0 and not self.should_apply_variation(char_index):
            return 1.0, 1.0

        width_var = self.variation_settings["width_scale"]
        height_var = self.variation_settings["height_scale"]

        width_scale = 1.0 + random.uniform(-width_var, width_var)
        height_scale = 1.0 + random.uniform(-height_var, height_var)

        return width_scale, height_scale

    def get_varied_spacing(self, base_spacing: float, char_index: int = -1) -> float:
        """Get varied spacing between characters - minimal variation to keep letters together"""
        # Only vary spacing for characters that have other variations applied
        if char_index >= 0 and char_index in self.variation_positions:
            variation = self.variation_settings["spacing_variation"] * 0.15  # Very minimal
            factor = 1.0 + random.uniform(-variation, variation)
            return base_spacing * factor
        # No spacing variation for most characters - keep them flowing together
        return base_spacing

    def get_varied_ink_color(self, base_color: Tuple[int, int, int], char_index: int = -1) -> Tuple[int, int, int]:
        """Get slightly varied ink color"""
        # Use word-level base color
        word_color = self.current_word_base_color if self.current_word_base_color else base_color

        if char_index >= 0 and not self.should_apply_variation(char_index):
            return word_color

        variation = self.variation_settings["ink_variation"]
        r = max(0, min(255, word_color[0] + random.randint(-variation, variation)))
        g = max(0, min(255, word_color[1] + random.randint(-variation, variation)))
        b = max(0, min(255, word_color[2] + random.randint(-variation, variation)))
        return (r, g, b)

    def render_varied_character(self, draw: ImageDraw.Draw, char: str,
                               x: float, y: float, font_path: str,
                               base_size: int, base_color: Tuple[int, int, int],
                               temp_image: Image.Image, char_index: int = -1,
                               char_position_in_word: int = 0) -> float:
        """
        Render a single character with variations

        Returns: x position for next character
        """
        # Get variations for this character
        varied_size = self.get_varied_font_size(base_size, char_index)
        x_offset, y_offset = self.get_varied_position(char_index)
        rotation = self.get_varied_rotation(char_index)
        width_scale, height_scale = self.get_varied_scale(char_index)
        ink_color = self.get_varied_ink_color(base_color, char_index)

        # Apply word-level angle offset
        angle_y_offset = char_position_in_word * math.tan(math.radians(self.current_word_angle)) * 10
        y_offset += angle_y_offset

        # Load font
        try:
            font = ImageFont.truetype(font_path, varied_size)
        except:
            font = ImageFont.load_default()

        # Get character size
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]

        actual_x = x + x_offset
        actual_y = y + y_offset

        # Apply transformations if needed
        use_rotation = abs(rotation) > 0.01 and char_index in self.variation_positions
        use_scaling = (abs(width_scale - 1.0) > 0.01 or abs(height_scale - 1.0) > 0.01) and \
                      char_index in self.variation_positions

        if use_rotation or use_scaling:
            padding = max(char_width, char_height) // 2 + 10
            temp_size = max(char_width, char_height) + padding * 2
            char_img = Image.new('RGBA', (temp_size, temp_size), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)

            char_x = (temp_size - char_width) // 2
            char_y = (temp_size - char_height) // 2
            char_draw.text((char_x, char_y), char, font=font, fill=ink_color)

            if use_rotation:
                char_img = char_img.rotate(rotation, expand=False, resample=Image.BICUBIC)

            if use_scaling:
                new_width = int(temp_size * width_scale)
                new_height = int(temp_size * height_scale)
                if new_width > 0 and new_height > 0:
                    char_img = char_img.resize((new_width, new_height), Image.BICUBIC)
                    if new_width > temp_size or new_height > temp_size:
                        crop_x = max(0, (new_width - temp_size) // 2)
                        crop_y = max(0, (new_height - temp_size) // 2)
                        char_img = char_img.crop((crop_x, crop_y,
                                                 crop_x + temp_size,
                                                 crop_y + temp_size))

            paste_x = int(x + x_offset - temp_size // 2 + char_width // 2)
            paste_y = int(y + y_offset - temp_size // 2 + char_height // 2)

            if 0 <= paste_x < temp_image.width - temp_size and \
               0 <= paste_y < temp_image.height - temp_size:
                temp_image.paste(char_img, (paste_x, paste_y), char_img)
        else:
            draw.text((actual_x, actual_y), char, font=font, fill=ink_color)

        base_spacing = char_width * 0.95
        next_x = x + self.get_varied_spacing(base_spacing, char_index)

        return next_x

    def render_varied_text(self, img: Image.Image, text: str,
                           start_x: float, start_y: float,
                           font_path: str, base_size: int,
                           base_color: Tuple[int, int, int] = (44, 36, 22),
                           track_annotations: bool = False) -> Tuple[float, float]:
        """
        Render entire text with character variations

        Args:
            track_annotations: If True, collect bounding box for this text as an element

        Returns: (end_x, end_y)
        """
        draw = ImageDraw.Draw(img)
        x = start_x
        y = start_y

        # Track bounding box for this entire text if needed
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        BBOX_PADDING = 2

        words = text.split(' ')

        for word_idx, word in enumerate(words):
            if '\n' in word:
                parts = word.split('\n')
                for part_idx, part in enumerate(parts):
                    if part:
                        self.start_new_word(base_size, base_color, len(part))

                        for char_idx, char in enumerate(part):
                            char_x_start = x

                            # Get the variations that will be applied to this character
                            if track_annotations:
                                try:
                                    varied_size = self.get_varied_font_size(base_size, char_idx)
                                    x_offset, y_offset = self.get_varied_position(char_idx)

                                    # Apply word angle offset
                                    angle_y_offset = char_idx * math.tan(math.radians(self.current_word_angle)) * 10
                                    y_offset += angle_y_offset

                                    # Get actual bbox with the varied size at the actual position
                                    font = ImageFont.truetype(font_path, varied_size)
                                    actual_x = x + x_offset
                                    actual_y = y + y_offset
                                    char_bbox = draw.textbbox((actual_x, actual_y), char, font=font)

                                    # Track with actual offsets applied
                                    min_x = min(min_x, char_bbox[0])
                                    min_y = min(min_y, char_bbox[1])
                                    max_x = max(max_x, char_bbox[2])
                                    max_y = max(max_y, char_bbox[3])
                                except:
                                    pass

                            # render_varied_character returns only x now
                            x = self.render_varied_character(
                                draw, char, x, y, font_path, base_size, base_color, img, char_idx, char_idx
                            )

                    if part_idx < len(parts) - 1:
                        x = start_x
                        y += base_size + self.variation_settings["position_y"] * 2
            else:
                self.start_new_word(base_size, base_color, len(word))

                for char_idx, char in enumerate(word):
                    char_x_start = x

                    # Get the variations that will be applied to this character
                    if track_annotations:
                        try:
                            varied_size = self.get_varied_font_size(base_size, char_idx)
                            x_offset, y_offset = self.get_varied_position(char_idx)

                            # Apply word angle offset
                            angle_y_offset = char_idx * math.tan(math.radians(self.current_word_angle)) * 10
                            y_offset += angle_y_offset

                            # Get actual bbox with the varied size at the actual position
                            font = ImageFont.truetype(font_path, varied_size)
                            actual_x = x + x_offset
                            actual_y = y + y_offset
                            char_bbox = draw.textbbox((actual_x, actual_y), char, font=font)

                            # Track with actual offsets applied
                            min_x = min(min_x, char_bbox[0])
                            min_y = min(min_y, char_bbox[1])
                            max_x = max(max_x, char_bbox[2])
                            max_y = max(max_y, char_bbox[3])
                        except:
                            pass

                    # render_varied_character returns only x now
                    x = self.render_varied_character(
                        draw, char, x, y, font_path, base_size, base_color, img, char_idx, char_idx
                    )

            if word_idx < len(words) - 1:
                x += self.get_varied_spacing(base_size * 0.3)

        # Store element bbox if tracking
        if track_annotations and min_x != float('inf'):
            text_bbox = BoundingBox()
            text_bbox.text = text
            text_bbox.min_x = min_x - BBOX_PADDING
            text_bbox.min_y = min_y - BBOX_PADDING
            text_bbox.max_x = max_x + BBOX_PADDING
            text_bbox.max_y = max_y + BBOX_PADDING

            self.collected_element_bboxes.append(text_bbox)

        return x, y

    def get_annotations(self, image_id: int = 0) -> List[COCOAnnotation]:
        """
        Convert collected bounding boxes to COCO annotations

        Returns: List of COCO annotations for elements, pairs, and sections
        """
        annotations = []

        # Element annotations (category_id = 0) - individual cipher texts and keys
        for bbox in self.collected_element_bboxes:
            if bbox.is_valid():
                ann = COCOAnnotation(
                    id=0,  # Will be set by manager
                    image_id=image_id,
                    category_id=0,  # element
                    segmentation=bbox.to_segmentation(),
                    area=bbox.get_area(),
                    bbox=bbox.to_coco_bbox(),
                    iscrowd=0,
                    text=bbox.text
                )
                annotations.append(ann)

        # Pair annotations (category_id = 1) - cipher + key combinations
        for bbox in self.collected_pair_bboxes:
            if bbox.is_valid():
                ann = COCOAnnotation(
                    id=0,  # Will be set by manager
                    image_id=image_id,
                    category_id=1,  # pair
                    segmentation=bbox.to_segmentation(),
                    area=bbox.get_area(),
                    bbox=bbox.to_coco_bbox(),
                    iscrowd=0,
                    text=bbox.text
                )
                annotations.append(ann)

        # Section annotations (category_id = 2) - groups of pairs
        for bbox in self.collected_section_bboxes:
            if bbox.is_valid():
                ann = COCOAnnotation(
                    id=0,  # Will be set by manager
                    image_id=image_id,
                    category_id=2,  # section
                    segmentation=bbox.to_segmentation(),
                    area=bbox.get_area(),
                    bbox=bbox.to_coco_bbox(),
                    iscrowd=0,
                    text=bbox.text
                )
                annotations.append(ann)

        return annotations


class CipherEntryRenderer:
    """High-level renderer for cipher entries (cipher_text + separator + key_value)

    Encapsulates the low-level VariatedTextRenderer and provides domain-specific
    layout logic for rendering cipher entries with proper annotation tracking.
    """

    def __init__(self, text_renderer: VariatedTextRenderer):
        self._text_renderer = text_renderer
        self._section_start_idx = None

    def start_section(self):
        """Mark the start of a new section for annotation tracking"""
        self._section_start_idx = len(self._text_renderer.collected_pair_bboxes)

    def end_section(self, section_id: int = 0) -> Optional[BoundingBox]:
        """
        Create and store a section bounding box from all pairs since start_section()

        Args:
            section_id: Identifier for this section

        Returns:
            The created section bbox, or None if no pairs were added
        """
        if self._section_start_idx is None:
            return None

        section_end_idx = len(self._text_renderer.collected_pair_bboxes)
        section_pairs = self._text_renderer.collected_pair_bboxes[self._section_start_idx:section_end_idx]

        if len(section_pairs) == 0:
            return None

        # Create section bbox by combining all pair bboxes
        section_bbox = BoundingBox()
        section_bbox.text = f"Section {section_id} ({len(section_pairs)} entries)"

        for pair_bbox in section_pairs:
            if section_bbox.min_x == float('inf'):
                section_bbox.min_x = pair_bbox.min_x
                section_bbox.min_y = pair_bbox.min_y
                section_bbox.max_x = pair_bbox.max_x
                section_bbox.max_y = pair_bbox.max_y
            else:
                section_bbox.min_x = min(section_bbox.min_x, pair_bbox.min_x)
                section_bbox.min_y = min(section_bbox.min_y, pair_bbox.min_y)
                section_bbox.max_x = max(section_bbox.max_x, pair_bbox.max_x)
                section_bbox.max_y = max(section_bbox.max_y, pair_bbox.max_y)

        if section_bbox.is_valid():
            self._text_renderer.collected_section_bboxes.append(section_bbox)
            self._section_start_idx = None  # Reset for next section
            return section_bbox

        return None

    def get_annotations(self, image_id: int = 0) -> List[COCOAnnotation]:
        """
        Get all COCO annotations (elements, pairs, sections)

        Args:
            image_id: The image ID for the annotations

        Returns:
            List of COCO annotations
        """
        return self._text_renderer.get_annotations(image_id)

    def reset_annotations(self):
        """Reset all collected annotations"""
        self._text_renderer.collected_element_bboxes = []
        self._text_renderer.collected_pair_bboxes = []
        self._text_renderer.collected_section_bboxes = []
        self._section_start_idx = None

    def render_cipher_entry(self, img: Image.Image, cipher_text: str,
                            key_value: str, x: float, y: float,
                            font_path: str, base_size: int,
                            separator: str = " — — — ",
                            column_separator: str = "none",
                            paper_width: int = 800,
                            track_annotations: bool = False) -> float:
        """
        Render a cipher entry (text + separator + key) with variations

        Returns: y position for next line
        """
        base_color = (44, 36, 22)  # Dark brown ink

        # Track which elements belong to this entry
        elements_start_idx = len(self._text_renderer.collected_element_bboxes)

        # Render cipher text and track its bbox
        end_x, end_y = self._text_renderer.render_varied_text(
            img, cipher_text, x, y, font_path, base_size, base_color, track_annotations
        )

        # Render separator (don't track)
        sep_x = end_x + 10
        sep_end_x, _ = self._text_renderer.render_varied_text(
            img, separator, sep_x, y, font_path, base_size, base_color, False
        )

        # Render key value and track its bbox AS A SEPARATE ELEMENT
        key_x = sep_end_x + 10
        key_end_x, _ = self._text_renderer.render_varied_text(
            img, key_value, key_x, y, font_path, base_size, base_color, track_annotations  # CHANGED: now tracks!
        )

        # Create pair bbox from all elements added during this entry
        if track_annotations:
            elements_end_idx = len(self._text_renderer.collected_element_bboxes)

            # Get all elements that were added (cipher_text + key_value)
            entry_elements = self._text_renderer.collected_element_bboxes[elements_start_idx:elements_end_idx]

            if len(entry_elements) >= 2:  # Should have at least cipher + key
                # Create pair bbox combining all elements in this entry
                pair_bbox = BoundingBox()
                pair_bbox.text = f"{cipher_text} — {key_value}"

                for elem_bbox in entry_elements:
                    pair_bbox.min_x = min(pair_bbox.min_x, elem_bbox.min_x) if pair_bbox.min_x != float(
                        'inf') else elem_bbox.min_x
                    pair_bbox.min_y = min(pair_bbox.min_y, elem_bbox.min_y) if pair_bbox.min_y != float(
                        'inf') else elem_bbox.min_y
                    pair_bbox.max_x = max(pair_bbox.max_x, elem_bbox.max_x) if pair_bbox.max_x != float(
                        '-inf') else elem_bbox.max_x
                    pair_bbox.max_y = max(pair_bbox.max_y, elem_bbox.max_y) if pair_bbox.max_y != float(
                        '-inf') else elem_bbox.max_y

                if pair_bbox.is_valid():
                    self._text_renderer.collected_pair_bboxes.append(pair_bbox)

        # Calculate next line position
        line_height = base_size + self._text_renderer.variation_settings["position_y"] * 3
        next_y = y + self._text_renderer.get_varied_spacing(line_height)

        # Draw row separator if needed
        if column_separator != 'none':
            draw = ImageDraw.Draw(img)
            # Position separator halfway between this line and next line
            separator_gap = base_size * 0.3  # 30% of font size
            separator_y = int(next_y + separator_gap)
            line_width = paper_width - x - 50

            if column_separator == 'line':
                draw.line([(x, separator_y), (x + line_width, separator_y)],
                          fill='#2C2416', width=1)
            elif column_separator == 'double_line':
                draw.line([(x, separator_y), (x + line_width, separator_y)],
                          fill='#2C2416', width=1)
                spacing = max(2, int(base_size * 0.15))  # Space between lines scales with font
                draw.line([(x, separator_y + spacing), (x + line_width, separator_y + spacing)],
                          fill='#2C2416', width=1)

            # Add extra space after separator (scales with font size)
            next_y += separator_gap * 2

        return next_y