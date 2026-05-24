"""
Table codes configuration data model
Path: src/models/table_codes_config.py
"""

from dataclasses import dataclass, field
from typing import List, Optional

from src.database.database_manager import COMMON_BIGRAMS, COMMON_TRIGRAMS, NULL_SYMBOLS

# Most frequent English letters — used only for common-boost logic in this module
COMMON_ENGLISH_LETTERS = frozenset('ETAOINSHRD')


@dataclass
class TableCodesConfig:
    """Configuration for table-style homophonic cipher code tables"""

    content_type: str = 'alphabet'      # 'alphabet', 'bigrams', 'nulls'
    num_codes: int = 3                  # Default codes per symbol
    use_common_boost: bool = True       # Give extra codes to common English letters
    common_codes: int = 5               # Codes for common letters (E,T,A,O,I,N,S,H,R)
    draw_vertical_lines: bool = True    # Draw vertical separator lines between columns
    column_spacing: int = 10            # Extra px added to each column beyond widest text
    row_spacing: int = 0                # Extra px between rows (0 = tight grid)
    use_pair_grid: bool = False         # Arrange codes 2-per-row in a 2-column sub-grid
                                        # Only valid when use_common_boost=False
    draw_header_line: bool = True       # Draw separator line under header and after last code row
    num_symbols: int = 0                # How many symbols to render (0 = use full list; ignored for alphabet)
    words: Optional[List[str]] = field(default=None)  # Pre-fetched word list for 'words' content type

    def get_symbols(self) -> List[str]:
        """Return the ordered list of symbols for the selected content type.

        For all types except 'alphabet', num_symbols caps the list length
        (0 means use the full list).
        """
        if self.content_type == 'alphabet':
            return list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        elif self.content_type == 'bigrams':
            symbols = [s.lower() for s in COMMON_BIGRAMS]
        elif self.content_type == 'trigrams':
            symbols = [s.lower() for s in COMMON_TRIGRAMS]
        elif self.content_type == 'words':
            symbols = [s.lower() for s in self.words] if self.words else []
        elif self.content_type == 'nulls':
            symbols = list(NULL_SYMBOLS)
        else:
            return list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

        if self.num_symbols > 0:
            symbols = symbols[:self.num_symbols]
        return symbols

    def get_num_codes_for_symbol(self, symbol: str) -> int:
        """Return how many code numbers this symbol should receive."""
        if self.use_common_boost and self.content_type == 'alphabet':
            if symbol.upper() in COMMON_ENGLISH_LETTERS:
                return self.common_codes
        return self.num_codes

    def total_codes_needed(self) -> int:
        """Return the total number of unique code numbers required."""
        return sum(self.get_num_codes_for_symbol(s) for s in self.get_symbols())
