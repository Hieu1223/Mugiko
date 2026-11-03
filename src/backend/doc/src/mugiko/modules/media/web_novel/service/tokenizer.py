"""Janome tokenizer for web novel module."""
from typing import List, Dict, Any
from dataclasses import dataclass

try:
    from janome.tokenizer import Tokenizer as JanomeTokenizer
    JANOME_AVAILABLE = True
except ImportError:
    JANOME_AVAILABLE = False


@dataclass
class Token:
    surface: str
    dictionary_form: str
    reading: str
    pos: str


class JanomeTokenizerWrapper:
    """Wrapper for Janome Japanese tokenizer."""

    def __init__(self, mode: str = "C"):
        """
        Initialize tokenizer.
        
        Note: Janome doesn't have split modes like SudachiPy.
        The mode parameter is kept for API compatibility but ignored.
        
        Args:
            mode: Ignored (kept for compatibility)
        """
        if not JANOME_AVAILABLE:
            raise RuntimeError("Janome not installed. Install with: pip install janome")
        
        self._tokenizer = JanomeTokenizer()
    
    def tokenize(self, text: str) -> List[Token]:
        """Tokenize Japanese text."""
        if not text.strip():
            return []
        
        tokens = []
        for m in self._tokenizer.tokenize(text):
            # Janome token attributes: surface, part_of_speech, infl_type, infl_form, base_form, reading, phonetic
            tokens.append(Token(
                surface=m.surface,
                dictionary_form=m.base_form,
                reading=m.reading if m.reading != '*' else m.surface,
                pos=m.part_of_speech.split(',')[0] if m.part_of_speech else "UNKNOWN",
            ))
        return tokens
    
    def tokenize_to_dict(self, text: str) -> List[Dict[str, str]]:
        """Tokenize and return as list of dicts for JSON storage."""
        return [
            {
                "surface": t.surface,
                "dictionary_form": t.dictionary_form,
                "reading": t.reading,
                "pos": t.pos,
            }
            for t in self.tokenize(text)
        ]


# Singleton instance
_tokenizer: JanomeTokenizerWrapper = None


def get_tokenizer(mode: str = "C") -> JanomeTokenizerWrapper:
    """Get or create tokenizer singleton."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = JanomeTokenizerWrapper(mode)
    return _tokenizer