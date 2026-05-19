import re
import unicodedata

WHITESPACE_RE = re.compile(r"\s+")


def normalize_unicode(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value or "")
    return WHITESPACE_RE.sub(" ", normalized).strip()


def fold_text(value: str) -> str:
    normalized = normalize_unicode(value)
    folded = unicodedata.normalize("NFD", normalized)
    without_marks = "".join(char for char in folded if unicodedata.category(char) != "Mn")
    without_marks = without_marks.replace("đ", "d").replace("Đ", "D")
    return WHITESPACE_RE.sub(" ", without_marks).strip().lower()

