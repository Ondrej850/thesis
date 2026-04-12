"""
Dataset generation configuration data model.
Stores ranges and option sets for batch-generating varied cipher images.
Path: src/models/dataset_config.py
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any


@dataclass
class DatasetConfig:
    """Configuration specifying randomisation ranges for batch dataset generation."""

    num_images: int = 10
    output_dir: str = ""
    annotation_format: str = "both"  # "coco", "yolo", "both"

    # Paper
    aging_level_range: Tuple[int, int] = (20, 80)
    paper_types: List[str] = field(default_factory=list)
    defects_mode: str = "random"  # "random", "all", "none"
    defects_pool: List[str] = field(
        default_factory=lambda: ["wrinkled_edges", "burns", "stains", "holes", "tears", "yellowing"]
    )

    # Column Pairs
    include_column_pairs: str = "always"  # "always", "never", "random"
    cipher_types: List[str] = field(default_factory=lambda: ["substitution"])
    key_types: List[str] = field(default_factory=lambda: ["number"])
    num_entries_range: Tuple[int, int] = (10, 50)
    cp_font_size_range: Tuple[int, int] = (10, 20)

    # Font
    fonts: List[str] = field(default_factory=lambda: ["Random"])
    variation_levels: List[str] = field(default_factory=lambda: ["low", "medium", "high"])
    col_separators: List[str] = field(default_factory=lambda: ["none", "line"])
    key_separators: List[str] = field(default_factory=lambda: ["dots", "dashes"])
    dash_count_range: Tuple[int, int] = (1, 5)
    spacing_range: Tuple[int, int] = (5, 12)

    # Table Codes
    include_table_codes: str = "random"  # "always", "never", "random"
    table_content_types: List[str] = field(default_factory=lambda: ["alphabet"])
    table_num_codes_range: Tuple[int, int] = (1, 5)
    table_common_boost: str = "random"  # "always", "never", "random"
    table_common_codes_range: Tuple[int, int] = (2, 8)
    table_col_spacing_range: Tuple[int, int] = (5, 20)
    table_vertical_lines: str = "random"  # "always", "never", "random"
    table_font_size_range: Tuple[int, int] = (10, 20)

    # Layout
    start_x_range: Tuple[int, int] = (30, 80)
    start_y_range: Tuple[int, int] = (30, 80)
    right_margin_range: Tuple[int, int] = (30, 80)
    bottom_margin_range: Tuple[int, int] = (30, 80)
    ink_colors: List[str] = field(
        default_factory=lambda: ["dark_brown", "black", "faded_brown", "iron_gall", "sepia", "charcoal"]
    )

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    @staticmethod
    def _rand_bool() -> bool:
        return random.random() < 0.5

    @staticmethod
    def _resolve_toggle(mode: str) -> bool:
        if mode == "always":
            return True
        if mode == "never":
            return False
        return DatasetConfig._rand_bool()

    def sample(self) -> Dict[str, Any]:
        """Return a single concrete configuration sampled from the ranges."""
        include_pairs = self._resolve_toggle(self.include_column_pairs)
        include_table = self._resolve_toggle(self.include_table_codes)

        # Defects
        if self.defects_mode == "all":
            defects = list(self.defects_pool)
        elif self.defects_mode == "none":
            defects = []
        else:  # random
            defects = [d for d in self.defects_pool if self._rand_bool()]

        return {
            # Paper
            "aging_level": random.randint(*self.aging_level_range),
            "paper_type": random.choice(self.paper_types) if self.paper_types else "Parchment Medium",
            "defects": defects,

            # Column pairs
            "include_column_pairs": include_pairs,
            "cipher_type": random.choice(self.cipher_types),
            "key_type": random.choice(self.key_types),
            "num_entries": random.randint(*self.num_entries_range),
            "cp_font_size": random.randint(*self.cp_font_size_range),

            # Font
            "font_name": random.choice(self.fonts),
            "variation_level": random.choice(self.variation_levels),
            "col_separator": random.choice(self.col_separators),
            "key_separator": random.choice(self.key_separators),
            "dash_count": random.randint(*self.dash_count_range),
            "spacing": random.randint(*self.spacing_range),

            # Table codes
            "include_table_codes": include_table,
            "table_content_type": random.choice(self.table_content_types),
            "table_num_codes": random.randint(*self.table_num_codes_range),
            "table_common_boost": self._resolve_toggle(self.table_common_boost),
            "table_common_codes": random.randint(*self.table_common_codes_range),
            "table_col_spacing": random.randint(*self.table_col_spacing_range),
            "table_vertical_lines": self._resolve_toggle(self.table_vertical_lines),
            "table_font_size": random.randint(*self.table_font_size_range),

            # Layout
            "start_x": random.randint(*self.start_x_range),
            "start_y": random.randint(*self.start_y_range),
            "right_margin": random.randint(*self.right_margin_range),
            "bottom_margin": random.randint(*self.bottom_margin_range),
            "ink_color": random.choice(self.ink_colors),
        }
