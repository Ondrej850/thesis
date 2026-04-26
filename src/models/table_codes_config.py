"""
Table codes configuration data model
Path: src/models/table_codes_config.py
"""

from dataclasses import dataclass, field
from typing import List, Optional


# Most frequent English letters as specified by user: E, T, A, O, I, N, S, H, R
COMMON_ENGLISH_LETTERS = frozenset('ETAOINSHRD')

# Common English bigrams ordered by frequency
COMMON_BIGRAMS = [
    'TH', 'HE', 'IN', 'ER', 'AN', 'RE', 'ON', 'EN',
    'AT', 'ES', 'ED', 'IS', 'IT', 'AL', 'AR', 'ST',
    'TO', 'NT', 'NG', 'SE', 'HA', 'AS', 'OU', 'IO',
    'LE', 'VE', 'CO', 'ME', 'DE', 'HI', 'RI', 'RO',
]

# Common English trigrams ordered by frequency
COMMON_TRIGRAMS = [
    'THE', 'AND', 'ING', 'ENT', 'ION', 'HER', 'FOR', 'THA',
    'NTH', 'INT', 'ERE', 'TIO', 'TER', 'EST', 'ERS', 'HAT',
    'HIS', 'ITH', 'VER', 'ATE', 'ALL', 'NOT', 'ARE', 'WAS',
    'ONE', 'OUT', 'MAN', 'BUT', 'OFT', 'ETH', 'STH', 'OUR',
]

# Common short words used in historical cipher codebooks
COMMON_WORDS = [
    'THE', 'AND', 'FOR', 'NOT', 'BUT', 'YOU', 'ALL', 'CAN',
    'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS',
    'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD',
    'SEE', 'TWO', 'WAY', 'WHO', 'DID', 'LET', 'MAN', 'OWN',
    'SAY', 'SHE', 'TOO', 'USE', 'WAR', 'GOD', 'MEN', 'END',
    'KING', 'SAID', 'COME', 'SEND', 'GIVE', 'HAVE', 'KNOW',
    'ARMY', 'LORD', 'THAT', 'WILL', 'WITH', 'THIS', 'FROM',
]

# Null symbols used as decorative placeholders.
# All characters are from Basic Latin (U+0020-U+007E) or Latin-1 Supplement
# (U+00A1-U+00FF) — ranges covered by virtually every TTF font, so they
# always render correctly regardless of which custom handwriting font is active.
NULL_SYMBOLS = [
    # ASCII special characters (Basic Latin — render in every font)
    '!', '#', '$', '%', '&', '*', '+', '=', '?', '@',
    '^', '~', '{', '}', '[', ']', '|', '/', '<', '>',
    # Latin-1 Supplement — render in virtually every TTF font
    '¡', '¢', '£', '¤', '¥', '¦', '§', '©', '®', '°',
    '±', '²', '³', 'µ', '¶', '·', '¼', '½', '¾', '¿',
    '×', '÷',
]


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
            # Use pre-fetched DB words; fall back to built-in list if not provided
            if self.words:
                return list(self.words)
            symbols = [s.lower() for s in COMMON_WORDS]
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
