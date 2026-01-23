"""
Font Manager - Add this to database_manager.py or create as separate module
Path: src/database/font_manager.py
"""

import os
import random
from typing import List, Optional


class FontManager:
    """Manages handwritten fonts for cipher generation"""

    def __init__(self, fonts_dir: str = "fonts/handwritten"):
        self.fonts_dir = fonts_dir
        self.available_fonts = []
        self._scan_fonts()

    def _scan_fonts(self):
        """Scan fonts directory for available font files"""
        if not os.path.exists(self.fonts_dir):
            os.makedirs(self.fonts_dir, exist_ok=True)
            print(f"Created fonts directory: {self.fonts_dir}")
            print("Please add .ttf or .otf font files to this directory")
            return

        # Supported font extensions
        font_extensions = ('.ttf', '.otf', '.TTF', '.OTF')

        # Scan directory
        for filename in os.listdir(self.fonts_dir):
            if filename.endswith(font_extensions):
                font_path = os.path.join(self.fonts_dir, filename)
                self.available_fonts.append({
                    'name': os.path.splitext(filename)[0],
                    'path': font_path,
                    'filename': filename
                })

        if self.available_fonts:
            print(f"Found {len(self.available_fonts)} fonts:")
            for font in self.available_fonts:
                print(f"  - {font['name']}")
        else:
            print(f"No fonts found in {self.fonts_dir}")
            print("Add .ttf or .otf files to use custom fonts")

    def get_random_font(self) -> Optional[str]:
        """Get a random font path from available fonts"""
        if not self.available_fonts:
            print("Warning: No custom fonts available, using system default")
            return None

        font = random.choice(self.available_fonts)
        print(f"Selected font: {font['name']}")
        return font['path']

    def get_font_by_name(self, name: str) -> Optional[str]:
        """Get specific font by name"""
        for font in self.available_fonts:
            if font['name'].lower() == name.lower():
                return font['path']
        return None

    def get_all_font_names(self) -> List[str]:
        """Get list of all available font names"""
        return [font['name'] for font in self.available_fonts]

    def has_fonts(self) -> bool:
        """Check if any fonts are available"""
        return len(self.available_fonts) > 0

    def add_font_to_database(self, db_manager):
        """Add fonts to database for tracking"""
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()

        # Create fonts table if it doesn't exist
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS fonts
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY,
                           name
                           TEXT
                           NOT
                           NULL
                           UNIQUE,
                           path
                           TEXT
                           NOT
                           NULL,
                           filename
                           TEXT
                           NOT
                           NULL,
                           times_used
                           INTEGER
                           DEFAULT
                           0,
                           last_used
                           TIMESTAMP
                       )
                       ''')

        # Insert or update fonts
        for font in self.available_fonts:
            cursor.execute('''
                           INSERT
                           OR IGNORE INTO fonts (name, path, filename)
                VALUES (?, ?, ?)
                           ''', (font['name'], font['path'], font['filename']))

        conn.commit()
        conn.close()

    def get_font_stats(self, db_manager) -> List[dict]:
        """Get usage statistics for fonts"""
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                           SELECT name, times_used, last_used
                           FROM fonts
                           ORDER BY times_used DESC
                           ''')
            stats = []
            for row in cursor.fetchall():
                stats.append({
                    'name': row[0],
                    'times_used': row[1],
                    'last_used': row[2]
                })
            return stats
        except:
            return []
        finally:
            conn.close()

    def mark_font_used(self, font_path: str, db_manager):
        """Mark a font as used (for statistics)"""
        import sqlite3
        from datetime import datetime

        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                           UPDATE fonts
                           SET times_used = times_used + 1,
                               last_used  = ?
                           WHERE path = ?
                           ''', (datetime.now().isoformat(), font_path))
            conn.commit()
        except:
            pass
        finally:
            conn.close()