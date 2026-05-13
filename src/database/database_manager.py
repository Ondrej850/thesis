"""
In-memory data store for cipher data.
"""

import random
from typing import List

from src.models.table_codes_config import NULL_SYMBOLS

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SUBSTITUTION_WORDS: List[str] = [
    "Imperator", "Cardinal", "General", "Italia", "Franche",
    "Hispania", "Deutschland", "England", "Regis", "Polen",
    "Behem", "Dux", "Rex", "Princeps", "Francesco",
    "Austria", "Bavaria", "Saxonia", "Prussia", "Venetia",
    "Milano", "Firenze", "Roma", "Napoli", "Genova",
]

_BIGRAM_WORDS: List[str] = [
    "ab", "in", "de", "et", "ad", "ex", "co", "on", "er", "an",
    "re", "te", "st", "en", "or", "ti", "ar", "se", "it", "al",
]

_TRIGRAM_WORDS: List[str] = [
    "rex", "dux", "qui", "est", "per", "con", "ent", "ter",
    "tio", "pro", "res", "rum", "tur", "unt", "and", "ati",
]

_DICTIONARY_WORDS: List[str] = [
    "His Majesty", "Your Excellency", "Most Serene",
    "Holy Roman Empire", "grace of God", "Imperial Diet",
    "Papal States", "Council of Trent", "Peace Treaty",
]

_TABLE_CODES_WORDS: List[str] = [
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
    "brook", "brown", "brush", "burden", "cable",
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
    "emperor", "engines", "enlarge", "episode",
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
    "varlets", "vessels", "veteran", "village",
    "warrant", "warlord", "weapons", "worship", "writers",
]

_WORD_LISTS = {
    "substitution": _SUBSTITUTION_WORDS,
    "bigram":       _BIGRAM_WORDS,
    "trigram":      _TRIGRAM_WORDS,
    "dictionary":   _DICTIONARY_WORDS,
    "nulls":        list(NULL_SYMBOLS),
    "table_codes":  _TABLE_CODES_WORDS,
}


class DatabaseManager:
    """In-memory data store for cipher word lists."""

    def __init__(self):
        self._data = {k: list(v) for k, v in _WORD_LISTS.items()}

    def get_cipher_keys(self, cipher_type: str) -> List[str]:
        """Return all words for the given cipher type."""
        return list(self._data.get(cipher_type, []))

    def get_table_words(self, n: int) -> List[str]:
        """Return n randomly sampled words from the table-codes word pool."""
        pool = self._data["table_codes"]
        return random.sample(pool, min(n, len(pool)))
