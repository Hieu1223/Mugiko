"""Janome tokenizer for Japanese text."""
from typing import List, Dict, Any
from janome.tokenizer import Tokenizer as JanomeTokenizer


class JapaneseTokenizer:
    """Tokenizes Japanese text using Janome, returning kanji and hiragana forms."""

    def __init__(self):
        self.tokenizer = JanomeTokenizer()
        # Note: Janome doesn't have split modes like SudachiPy

    def _katakana_to_hiragana(self, text: str) -> str:
        """Convert katakana to hiragana."""
        result = ''
        for ch in text:
            code = ord(ch)
            if 0x30A1 <= code <= 0x30F6:  # Katakana range
                result += chr(code - 0x60)
            else:
                result += ch
        return result

    def tokenize(self, text: str) -> List[Dict[str, Any]]:
        """
        Tokenize Japanese text into words.
        
        Returns list of dicts with:
        - surface: original text (kanji/kana mix)
        - reading: hiragana reading
        - dictionary_form: dictionary form (base form)
        - part_of_speech: POS tags
        """
        if not text or not text.strip():
            return []

        morphemes = self.tokenizer.tokenize(text)
        tokens = []

        for m in morphemes:
            # surface = original surface form (kanji + kana)
            surface = m.surface
            # reading = hiragana reading (convert from katakana)
            reading = self._katakana_to_hiragana(m.reading if m.reading != '*' else m.surface)
            # dictionary_form = base/dictionary form
            dictionary_form = m.base_form
            # part_of_speech = POS as list
            pos = m.part_of_speech.split(',')

            tokens.append({
                "surface": surface,
                "reading": reading,
                "dictionary_form": dictionary_form,
                "part_of_speech": pos,
            })

        return tokens

    def tokenize_to_hiragana(self, text: str) -> str:
        """Convert text to pure hiragana."""
        tokens = self.tokenize(text)
        return "".join(t["reading"] for t in tokens)


# Global instance
_tokenizer: JapaneseTokenizer | None = None


def get_tokenizer() -> JapaneseTokenizer:
    """Get or create the global tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = JapaneseTokenizer()
    return _tokenizer


def tokenize_text(text: str) -> List[Dict[str, Any]]:
    """Convenience function to tokenize text."""
    return get_tokenizer().tokenize(text)


def text_to_hiragana(text: str) -> str:
    """Convenience function to convert text to hiragana."""
    return get_tokenizer().tokenize_to_hiragana(text)