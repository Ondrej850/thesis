"""
Dataset generation configuration data model.
Stores ranges and option sets for batch-generating varied cipher images.
Path: src/models/dataset_config.py
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any


@dataclass
class TableRangeConfig:
    """Randomisation ranges for one table block in a batch run."""
    include: str = "always"                          # "always", "never", "random"
    content_types: List[str] = field(default_factory=lambda: ["alphabet", "bigrams", "trigrams", "words", "nulls"])
    num_codes_range: Tuple[int, int] = (1, 5)
    num_symbols_range: Tuple[int, int] = (5, 20)   # used when content_type != alphabet
    common_boost: str = "random"
    common_codes_range: Tuple[int, int] = (2, 8)
    col_spacing_range: Tuple[int, int] = (5, 20)
    vertical_lines: str = "random"
    font_size_range: Tuple[int, int] = (10, 20)
    row_spacing_range: Tuple[int, int] = (0, 6)
    pair_grid: str = "never"
    draw_header_line: str = "always"   # "always", "never", "random"
    include_title: str = "never"


@dataclass
class DatasetConfig:
    """Configuration specifying randomisation ranges for batch dataset generation."""

    num_images: int = 10
    output_dir: str = ""
    annotation_format: str = "both"  # "coco", "yolo", "both"
    ignore_empty_papers: bool = False  # skip images where nothing cipher-related renders

    # Paper
    aging_level_range: Tuple[int, int] = (20, 80)
    defects_mode: str = "random"  # "random", "all", "none"
    defects_pool: List[str] = field(
        default_factory=lambda: ["wrinkled_edges", "burns", "stains", "holes", "tears", "yellowing"]
    )

    # Column Pairs
    include_column_pairs: str = "always"  # "always", "never", "random"
    cipher_types: List[str] = field(default_factory=lambda: ["alphabet", "substitution", "bigram", "trigram", "dictionary", "nulls"])
    key_types: List[str] = field(default_factory=lambda: ["number", "double_char"])
    pair_formats: List[str] = field(default_factory=lambda: ["text_first", "number_first"])
    num_entries_range: Tuple[int, int] = (10, 50)
    cp_font_size_range: Tuple[int, int] = (10, 20)

    # Font
    fonts: List[str] = field(default_factory=lambda: ["Random"])
    variation_levels: List[str] = field(default_factory=lambda: ["low", "medium", "high"])
    col_separators: List[str] = field(default_factory=lambda: ["none", "line"])
    key_separators: List[str] = field(default_factory=lambda: ["dots", "dashes"])
    dash_count_range: Tuple[int, int] = (1, 5)
    spacing_range: Tuple[int, int] = (5, 12)

    # Multiple table configs — one entry per table block (up to 3).
    # When non-empty, these drive generation; legacy flat fields below are ignored.
    table_configs: List[TableRangeConfig] = field(default_factory=list)

    # Legacy single-table fields (kept for backward compat; used only when
    # table_configs is empty).
    include_table_codes: str = "random"  # "always", "never", "random"
    table_content_types: List[str] = field(default_factory=lambda: ["alphabet", "bigrams", "trigrams", "words", "nulls"])
    table_num_codes_range: Tuple[int, int] = (1, 5)
    table_common_boost: str = "random"
    table_common_codes_range: Tuple[int, int] = (2, 8)
    table_col_spacing_range: Tuple[int, int] = (5, 20)
    table_vertical_lines: str = "random"
    table_font_size_range: Tuple[int, int] = (10, 20)
    table_row_spacing_range: Tuple[int, int] = (0, 6)
    table_pair_grid: str = "never"
    include_table_title: str = "never"

    # Column pairs section title
    include_cp_title: str = "never"      # "always", "never", "random"

    # Layout
    start_x_range: Tuple[int, int] = (0, 100)
    start_y_range: Tuple[int, int] = (0, 100)
    right_margin_range: Tuple[int, int] = (0, 80)
    bottom_margin_range: Tuple[int, int] = (0, 80)
    line_spacing_jitter_range: Tuple[int, int] = (0, 8)
    include_title: str = "random"  # "always", "never", "random"
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

    def _sample_table(self, tc: TableRangeConfig, used_content_types: set) -> dict:
        """Sample one table's params, avoiding duplicate content types."""
        # Prefer a content type not yet used; fall back to any if no unique option
        available = [ct for ct in tc.content_types if ct not in used_content_types]
        content_type = random.choice(available if available else tc.content_types)
        used_content_types.add(content_type)

        boost = self._resolve_toggle(tc.common_boost)
        pair_grid = self._resolve_toggle(tc.pair_grid) if not boost else False

        num_sym = 0 if content_type == "alphabet" else random.randint(*tc.num_symbols_range)
        return {
            "content_type": content_type,
            "num_symbols": num_sym,
            "num_codes": random.randint(*tc.num_codes_range),
            "common_boost": boost,
            "common_codes": random.randint(*tc.common_codes_range),
            "col_spacing": random.randint(*tc.col_spacing_range),
            "vertical_lines": self._resolve_toggle(tc.vertical_lines),
            "font_size": random.randint(*tc.font_size_range),
            "row_spacing": random.randint(*tc.row_spacing_range),
            "pair_grid": pair_grid,
            "draw_header_line": self._resolve_toggle(tc.draw_header_line),
            "include_title": self._resolve_toggle(tc.include_title),
        }

    def sample(self) -> Dict[str, Any]:
        """Return a single concrete configuration sampled from the ranges."""
        include_pairs = self._resolve_toggle(self.include_column_pairs)

        # Defects
        if self.defects_mode == "all":
            defects = list(self.defects_pool)
        elif self.defects_mode == "none":
            defects = []
        else:  # random
            defects = [d for d in self.defects_pool if self._rand_bool()]

        # Build the tables list -------------------------------------------------
        if self.table_configs:
            # New multi-table path: each TableRangeConfig drives one table block.
            # Content types are kept unique across tables on the same image.
            used_types: set = set()
            tables = []
            for tc in self.table_configs:
                if not self._resolve_toggle(tc.include):
                    continue
                tables.append(self._sample_table(tc, used_types))
        else:
            # Legacy single-table fallback
            include_table = self._resolve_toggle(self.include_table_codes)
            if include_table:
                boost = self._resolve_toggle(self.table_common_boost)
                pair_grid = self._resolve_toggle(self.table_pair_grid) if not boost else False
                _ct = random.choice(self.table_content_types)
                tables = [{
                    "content_type": _ct,
                    "num_symbols": 0 if _ct == "alphabet" else random.randint(5, 20),
                    "num_codes": random.randint(*self.table_num_codes_range),
                    "common_boost": boost,
                    "common_codes": random.randint(*self.table_common_codes_range),
                    "col_spacing": random.randint(*self.table_col_spacing_range),
                    "vertical_lines": self._resolve_toggle(self.table_vertical_lines),
                    "font_size": random.randint(*self.table_font_size_range),
                    "row_spacing": random.randint(*self.table_row_spacing_range),
                    "pair_grid": pair_grid,
                    "draw_header_line": True,
                    "include_title": self._resolve_toggle(self.include_table_title),
                }]
            else:
                tables = []

        return {
            # Paper
            "aging_level": random.randint(*self.aging_level_range),
            "defects": defects,

            # Column pairs
            "include_column_pairs": include_pairs,
            "cipher_type": random.choice(self.cipher_types),
            "key_type": random.choice(self.key_types),
            "pair_format": random.choice(self.pair_formats),
            "num_entries": random.randint(*self.num_entries_range),
            "cp_font_size": random.randint(*self.cp_font_size_range),
            "include_cp_title": self._resolve_toggle(self.include_cp_title),

            # Font
            "font_name": random.choice(self.fonts),
            "variation_level": random.choice(self.variation_levels),
            "col_separator": random.choice(self.col_separators),
            "key_separator": random.choice(self.key_separators),
            "dash_count": random.randint(*self.dash_count_range),
            "spacing": random.randint(*self.spacing_range),

            # Tables — list of per-table dicts (may be empty if all excluded)
            "tables": tables,

            # Layout
            "start_x": random.randint(*self.start_x_range),
            "start_y": random.randint(*self.start_y_range),
            "right_margin": random.randint(*self.right_margin_range),
            "bottom_margin": random.randint(*self.bottom_margin_range),
            "line_spacing_jitter": random.randint(*self.line_spacing_jitter_range),
            "include_title": self._resolve_toggle(self.include_title),
            "ink_color": random.choice(self.ink_colors),
        }
