"""Small Unicode-aware lexical tokenization shared by Hami matching paths."""
from __future__ import annotations

import unicodedata

MATCH_STOP_WORDS = frozenset({
    "about", "after", "against", "also", "among", "because", "before", "being",
    "between", "could", "does", "during", "from", "have", "into", "more",
    "most", "other", "should", "some", "than", "that", "their", "there",
    "these", "they", "this", "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would", "your",
    "and", "are", "but", "can", "for", "not", "the", "you", "in", "to", "on", "of",
    "at", "an", "it", "is", "or", "as", "be", "by", "we", "he", "me", "my", "do",
    "if", "up", "no", "so", "us", "per", "need", "someone",
    "ko", "ka", "ki", "ke", "ma", "le", "lai", "bat", "ra", "cha", "chha", "ho",
    "yo", "tyo", "pani", "tatha", "ek", "kun", "kasari", "kina", "kaha", "kahile",
    "kati", "garne", "garna",
    "को", "की", "का", "के", "मा", "ले", "लाई", "बाट", "र", "छ", "छन्", "हो", "हुन्छ",
    "यो", "त्यो", "पनि", "तथा", "एक", "कुन", "कसरी", "किन", "कहाँ", "कहिले", "कति",
    "गर्ने", "गर्न", "भएको", "थियो",
    "में", "से", "और", "है", "हैं", "यह", "वह", "भी", "कैसे", "क्यों", "कब", "क्या",
})


def tokenize_match_terms(text: str) -> set[str]:
    """Unicode-aware lexical terms. Overlap is not semantic relevance or proof."""
    normalized = unicodedata.normalize("NFC", (text or "")).casefold()
    tokens: set[str] = set()
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        token = "".join(current)
        current.clear()
        if not token or token in MATCH_STOP_WORDS:
            return
        no_space_script = any(
            unicodedata.name(char, "").startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL"))
            for char in token
        )
        if no_space_script:
            if len(token) > 1:
                tokens.update(token[index:index + 2] for index in range(len(token) - 1))
        elif len(token) >= 2:
            tokens.add(token)

    for char in normalized:
        if unicodedata.category(char)[0] in {"L", "M", "N"}:
            current.append(char)
        else:
            flush()
    flush()
    return tokens
