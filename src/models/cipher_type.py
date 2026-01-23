"""
Cipher type configuration data model
"""

from dataclasses import dataclass


@dataclass
class CipherType:
    """Configuration for cipher types"""
    cipher_type: str  # substitution, bigram, trigram, dictionary, nulls
    key_type: str  # number, special_character

    def __post_init__(self):
        """Validate configuration"""
        valid_cipher_types = ['substitution', 'bigram', 'trigram', 'dictionary', 'nulls']
        valid_key_types = ['number', 'special_character']

        if self.cipher_type not in valid_cipher_types:
            raise ValueError(f"Cipher type must be one of {valid_cipher_types}")
        if self.key_type not in valid_key_types:
            raise ValueError(f"Key type must be one of {valid_key_types}")