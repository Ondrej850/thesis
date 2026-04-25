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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS table_codes_words
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

        # Re-seed nulls_words if it only has the old exotic Unicode symbols (≤8 rows)
        cursor.execute("SELECT COUNT(*) FROM nulls_words")
        if cursor.fetchone()[0] <= 8:
            cursor.execute("DELETE FROM nulls_words")
            self._insert_nulls_words(cursor)
            conn.commit()

        # Seed table_codes_words independently (may be absent on existing installs)
        cursor.execute("SELECT COUNT(*) FROM table_codes_words")
        if cursor.fetchone()[0] == 0:
            self._insert_table_codes_words(cursor)
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

        self._insert_nulls_words(cursor)
        self._insert_table_codes_words(cursor)

    def _insert_nulls_words(self, cursor):
        """Populate nulls_words with Basic Latin + Latin-1 Supplement symbols."""
        nulls_words = [
            # Basic Latin — render in every font
            '!', '#', '$', '%', '&', '*', '+', '=', '?', '@',
            '^', '~', '{', '}', '[', ']', '|', '/', '<', '>',
            # Latin-1 Supplement — render in virtually every TTF font
            '¡', '¢', '£', '¤', '¥', '¦', '§', '©', '®', '°',
            '±', '²', '³', 'µ', '¶', '·', '¼', '½', '¾', '¿',
            '×', '÷',
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO nulls_words (word) VALUES (?)",
            [(word,) for word in nulls_words]
        )

    def _insert_table_codes_words(self, cursor):
        """Populate table_codes_words with a diverse wordlist."""
        # Words for table-codes "words" content type — varied length, historical/general
        table_codes_words = [
            # 3-4 letters
            "age", "air", "arm", "art", "bay", "bed", "bow", "box",
            "boy", "cap", "cat", "cup", "cut", "day", "dog", "ear",
            "end", "eye", "far", "fat", "few", "fly", "fog", "fun",
            "gap", "god", "gun", "hat", "hay", "hit", "ice", "ink",
            "joy", "key", "law", "leg", "lip", "log", "lot", "map",
            "men", "mud", "net", "oak", "oil", "old", "orb", "ore",
            "pan", "pen", "pig", "pin", "pit", "pot", "raw", "ray",
            "red", "rod", "row", "run", "sea", "sin", "sky", "sod",
            "sun", "tax", "tin", "tip", "top", "war", "web", "wet",
            "win", "wit", "woe", "wax", "zeal",
            # 5-6 letters
            "abbey", "acorn", "angel", "anger", "arrow", "ashes",
            "bacon", "badge", "beard", "bells", "bench", "birds",
            "blade", "blame", "blood", "bloom", "board", "bones",
            "books", "boots", "brand", "brave", "bread", "bride",
            "bride", "brook", "brown", "brush", "burden", "cable",
            "canal", "chain", "chair", "chalk", "charm", "chase",
            "chest", "chief", "child", "claim", "cloak", "cloth",
            "cloud", "coach", "coast", "comet", "coral", "corps",
            "court", "cover", "crane", "creek", "cross", "crowd",
            "crown", "crush", "curve", "dagger", "dance", "death",
            "delay", "devil", "diary", "digger", "draft", "drain",
            "drama", "dream", "dress", "drift", "drink", "drive",
            "drops", "drums", "dungeon", "dwarf", "eagle", "earth",
            "enemy", "error", "essay", "event", "exile", "faith",
            "famine", "feast", "fence", "fever", "field", "fight",
            "flame", "flank", "fleet", "flesh", "flood", "floor",
            "flour", "flute", "forge", "forum", "fraud", "front",
            "frost", "fruit", "funds", "ghost", "giant", "glass",
            "globe", "glory", "glove", "goods", "grace", "grain",
            "grand", "grant", "grape", "grass", "grave", "great",
            "greed", "green", "grief", "grove", "guard", "guide",
            "guild", "guilt", "heart", "heavy", "herbs", "hills",
            "horse", "house", "human", "humor", "image", "index",
            "irony", "ivory", "jewel", "joint", "judge", "juice",
            "keeps", "kings", "knife", "labor", "lance", "lands",
            "large", "laser", "layer", "legal", "light", "limit",
            "linen", "links", "lions", "lodge", "logic", "lorry",
            "march", "marks", "mercy", "medal", "might", "mills",
            "mists", "money", "monks", "month", "moral", "mouse",
            "mouth", "music", "night", "noble", "noise", "north",
            "notes", "novel", "nurse", "ocean", "offer", "order",
            "organ", "other", "ounce", "outlet", "paint", "paper",
            "peace", "pearl", "pedal", "plain", "plane", "plant",
            "plate", "plaza", "plead", "plume", "point", "poison",
            "polar", "pound", "power", "press", "price", "pride",
            "prize", "proof", "prose", "proud", "psalm", "queen",
            "quest", "queue", "quote", "radar", "range", "ranks",
            "rates", "reach", "realm", "rebel", "reign", "reply",
            "rider", "rifle", "river", "roads", "rocks", "Roman",
            "roots", "rouge", "round", "route", "ruler", "rumor",
            "rural", "saint", "sauce", "scale", "scene", "scope",
            "score", "scorn", "scout", "seals", "seeds", "sense",
            "serif", "serve", "shade", "shaft", "share", "sheep",
            "shelf", "shell", "ships", "shore", "sight", "siege",
            "signs", "skill", "slave", "sleep", "slope", "smoke",
            "snake", "snare", "snow", "songs", "space", "spark",
            "spear", "speed", "spell", "spend", "spine", "spoke",
            "squad", "staff", "stain", "stake", "stamp", "stars",
            "state", "stays", "steam", "steel", "storm", "story",
            "straw", "sword", "table", "taxes", "terms", "theft",
            "theme", "thorn", "tides", "tiger", "tiles", "title",
            "token", "tones", "torch", "total", "tower", "towns",
            "trace", "track", "trade", "trail", "train", "traps",
            "trend", "trial", "tribe", "trick", "troop", "truce",
            "trust", "truth", "tutor", "tyrant", "union", "unity",
            "urban", "usage", "value", "vault", "verse", "vigor",
            "viper", "visit", "visor", "voice", "voter", "vow",
            "wages", "walls", "waste", "watch", "waves", "weeds",
            "wells", "wheat", "wheel", "where", "white", "widow",
            "winds", "witch", "wolves", "woods", "words", "works",
            "world", "worry", "wound", "wrath", "yield", "youth",
            # 7-10 letters
            "absence", "account", "advance", "adviser", "ancient",
            "annals", "archive", "arsenal", "assault", "balance",
            "barrier", "battery", "captain", "capture", "cavalry",
            "chamber", "chapter", "charter", "citadel", "command",
            "compact", "compass", "conduct", "counsel", "counter",
            "courier", "crusade", "custody", "customs", "danger",
            "daybook", "dealing", "defence", "descent", "despair",
            "destiny", "dialect", "discord", "disgrace", "dismiss",
            "dispute", "distant", "divided", "draught", "embassy",
            "emperor", "engines", "enlarge", "emperor", "episode",
            "evasion", "faction", "failure", "feature", "fiction",
            "finance", "flanking", "foreign", "fortune", "freedom",
            "frontier", "galleon", "gallows", "general", "harbour",
            "harvest", "honesty", "hostile", "hostage", "humility",
            "infantry", "justice", "kingdom", "kinship", "knights",
            "lantern", "liberty", "lineage", "lookout", "manoeuvre",
            "marquis", "marshal", "martyr", "measure", "meeting",
            "message", "militia", "mission", "monarch", "morning",
            "network", "neutral", "outpost", "passage", "pattern",
            "payment", "pension", "pilgrim", "plotters", "portage",
            "portion", "prestige", "prisoner", "private", "process",
            "prodigy", "prophet", "protect", "protest", "proverb",
            "quarter", "ransom", "reaches", "reasons", "recruit",
            "records", "redoubt", "refusal", "regency", "reserve",
            "retreat", "revenue", "revolt", "rivalry", "robbery",
            "rulings", "sanction", "scholar", "scandal", "secrets",
            "seizure", "senator", "servant", "service", "setting",
            "shelter", "sheriff", "silence", "soldier", "sortie",
            "speaker", "spirits", "station", "storage", "subject",
            "summons", "support", "tactics", "tartars", "tenants",
            "terrace", "thought", "threats", "tidings", "torture",
            "trading", "travels", "treason", "tribune", "tribute",
            "triumph", "trouble", "trustee", "turncoat", "tyranny",
            "uncover", "uniform", "unknown", "upkeep", "urgency",
            "varlets", "vessels", "veteran", "village", "village",
            "warrant", "warlord", "weapons", "worship", "writers",
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO table_codes_words (word) VALUES (?)",
            [(word,) for word in table_codes_words]
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

    def get_table_words(self, n: int) -> List[str]:
        """Return *n* randomly sampled words from the table_codes_words pool."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT word FROM table_codes_words ORDER BY RANDOM() LIMIT ?", (n,)
        )
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