"""
Table codes configuration data model
Path: src/models/table_codes_config.py
"""

from dataclasses import dataclass, field
from typing import List


# Most frequent English letters as specified by user: E, T, A, O, I, N, S, H, R
COMMON_ENGLISH_LETTERS = frozenset('ETAOINSHRD')

# Common English bigrams ordered by frequency
COMMON_BIGRAMS = [
    'TH', 'HE', 'IN', 'ER', 'AN', 'RE', 'ON', 'EN',
    'AT', 'ES', 'ED', 'IS', 'IT', 'AL', 'AR', 'ST',
    'TO', 'NT', 'NG', 'SE', 'HA', 'AS', 'OU', 'IO',
    'LE', 'VE', 'CO', 'ME', 'DE', 'HI', 'RI', 'RO',
]

# Null symbols used as decorative placeholders
NULL_SYMBOLS = list('⁂※⸎◊✠☙❧⁕†‡§¶*+×÷=~^')


@dataclass
class TableCodesConfig:
    """Configuration for table-style homophonic cipher code tables"""

    content_type: str = 'alphabet'      # 'alphabet', 'ngrams', 'nulls'
    num_codes: int = 3                  # Default codes per symbol
    use_common_boost: bool = True       # Give extra codes to common English letters
    common_codes: int = 5               # Codes for common letters (E,T,A,O,I,N,S,H,R)
    draw_vertical_lines: bool = True    # Draw vertical separator lines between columns
    column_spacing: int = 10            # Extra px added to each column beyond widest text
    row_spacing: int = 0                # Extra px between rows (0 = tight grid)
    use_pair_grid: bool = False         # Arrange codes 2-per-row in a 2-column sub-grid
                                        # Only valid when use_common_boost=False

    def get_symbols(self) -> List[str]:
        """Return the ordered list of symbols for the selected content type."""
        if self.content_type == 'alphabet':
            return list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        elif self.content_type == 'ngrams':
            return list(COMMON_BIGRAMS)
        elif self.content_type == 'nulls':
            return list(NULL_SYMBOLS)
        return list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    def get_num_codes_for_symbol(self, symbol: str) -> int:
        """Return how many code numbers this symbol should receive."""
        if self.use_common_boost and self.content_type == 'alphabet':
            if symbol.upper() in COMMON_ENGLISH_LETTERS:
                return self.common_codes
        return self.num_codes

    def total_codes_needed(self) -> int:
        """Return the total number of unique code numbers required."""
        return sum(self.get_num_codes_for_symbol(s) for s in self.get_symbols())
