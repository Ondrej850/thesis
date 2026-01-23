"""
SQLite database manager for cipher data
Path: src/database/database_manager.py
"""

import sqlite3
from typing import List, Tuple, Optional
import random


class DatabaseManager:
    """Manages local SQLite databases for texts and ciphers"""

    def __init__(self, db_path: str = "cipher_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple word lists for each cipher type
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS substitution_words
            (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bigram_words
            (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trigram_words
            (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dictionary_words
            (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nulls_words
            (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE
            )
        ''')

        # Paper types table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_types
            (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                base_color TEXT NOT NULL,
                texture_pattern TEXT
            )
        ''')

        conn.commit()

        # Insert sample data if empty
        cursor.execute("SELECT COUNT(*) FROM substitution_words")
        if cursor.fetchone()[0] == 0:
            self._insert_sample_data(cursor)
            conn.commit()

        conn.close()

    def _insert_sample_data(self, cursor):
        """Insert sample data for testing"""

        # Sample substitution words (countries, titles, names)
        substitution_words = [
            "Imperator", "Cardinal", "General", "Italia", "Franche",
            "Hispania", "Deutschland", "England", "Regis", "Polen",
            "Behem", "Dux", "Rex", "Princeps", "Francesco",
            "Austria", "Bavaria", "Saxonia", "Prussia", "Venetia",
            "Milano", "Firenze", "Roma", "Napoli", "Genova"
        ]
        cursor.executemany(
            "INSERT INTO substitution_words (word) VALUES (?)",
            [(word,) for word in substitution_words]
        )

        # Sample bigram words (2-letter combinations)
        bigram_words = [
            "ab", "in", "de", "et", "ad", "ex", "co", "on", "er", "an",
            "re", "te", "st", "en", "or", "ti", "ar", "se", "it", "al"
        ]
        cursor.executemany(
            "INSERT INTO bigram_words (word) VALUES (?)",
            [(word,) for word in bigram_words]
        )

        # Sample trigram words (3-letter combinations)
        trigram_words = [
            "rex", "dux", "qui", "est", "per", "con", "ent", "ter",
            "tio", "pro", "res", "rum", "tur", "unt", "and", "ati"
        ]
        cursor.executemany(
            "INSERT INTO trigram_words (word) VALUES (?)",
            [(word,) for word in trigram_words]
        )

        # Sample dictionary words (phrases)
        dictionary_words = [
            "His Majesty", "Your Excellency", "Most Serene",
            "Holy Roman Empire", "grace of God", "Imperial Diet",
            "Papal States", "Council of Trent", "Peace Treaty"
        ]
        cursor.executemany(
            "INSERT INTO dictionary_words (word) VALUES (?)",
            [(word,) for word in dictionary_words]
        )

        # Sample nulls words (meaningless symbols/characters)
        nulls_words = ["⁂", "※", "⸎", "◊", "✠", "☙", "❧", "⁕"]
        cursor.executemany(
            "INSERT INTO nulls_words (word) VALUES (?)",
            [(word,) for word in nulls_words]
        )

        # Sample paper types
        paper_types = [
            ("Parchment Light", "#F4E8D0", "fine"),
            ("Parchment Medium", "#E8D5B7", "medium"),
            ("Parchment Dark", "#D4C4A8", "coarse"),
            ("Aged Paper", "#E8DCC8", "aged"),
        ]
        cursor.executemany(
            "INSERT INTO paper_types (name, base_color, texture_pattern) VALUES (?, ?, ?)",
            paper_types
        )

    def get_cipher_keys(self, cipher_type: str) -> List[str]:
        """
        Get list of words for specified cipher type

        Args:
            cipher_type: 'substitution', 'bigram', 'trigram', 'dictionary', or 'nulls'

        Returns:
            List of words
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        table_map = {
            'substitution': 'substitution_words',
            'bigram': 'bigram_words',
            'trigram': 'trigram_words',
            'dictionary': 'dictionary_words',
            'nulls': 'nulls_words'
        }

        if cipher_type not in table_map:
            conn.close()
            return []

        table_name = table_map[cipher_type]
        cursor.execute(f"SELECT word FROM {table_name}")
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results

    def get_paper_types(self) -> List[Tuple]:
        """Retrieve paper types from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM paper_types")
        results = cursor.fetchall()
        conn.close()
        return results

    def add_word(self, cipher_type: str, word: str):
        """Add new word to appropriate table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        table_map = {
            'substitution': 'substitution_words',
            'bigram': 'bigram_words',
            'trigram': 'trigram_words',
            'dictionary': 'dictionary_words',
            'nulls': 'nulls_words'
        }

        if cipher_type not in table_map:
            conn.close()
            return

        table_name = table_map[cipher_type]
        try:
            cursor.execute(f"INSERT INTO {table_name} (word) VALUES (?)", (word,))
            conn.commit()
        except sqlite3.IntegrityError:
            # Word already exists
            pass
        conn.close()

    def remove_word(self, cipher_type: str, word: str):
        """Remove word from appropriate table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        table_map = {
            'substitution': 'substitution_words',
            'bigram': 'bigram_words',
            'trigram': 'trigram_words',
            'dictionary': 'dictionary_words',
            'nulls': 'nulls_words'
        }

        if cipher_type not in table_map:
            conn.close()
            return

        table_name = table_map[cipher_type]
        cursor.execute(f"DELETE FROM {table_name} WHERE word = ?", (word,))
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """Get statistics about database contents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}
        tables = {
            'substitution': 'substitution_words',
            'bigram': 'bigram_words',
            'trigram': 'trigram_words',
            'dictionary': 'dictionary_words',
            'nulls': 'nulls_words'
        }

        for name, table in tables.items():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[name] = cursor.fetchone()[0]

        conn.close()
        return stats