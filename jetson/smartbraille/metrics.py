"""Accuracy metrics for OCR."""

import numpy as np


def edit_distance(a, b):
    """Levenshtein distance between two strings."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    b_codes = np.array([ord(c) for c in b])
    offsets = np.arange(len(b) + 1)
    prev = offsets.copy()
    for i, ch in enumerate(a, start=1):
        cur = np.empty_like(prev)
        cur[0] = i
        substitute = prev[:-1] + (b_codes != ord(ch))
        cur[1:] = np.minimum(prev[1:] + 1, substitute)
        # Insertions depend on the cell to the left; a running minimum of
        # (value - column) applies them to the whole row at once.
        cur = np.minimum.accumulate(cur - offsets) + offsets
        prev = cur
    return int(prev[-1])


def normalize_for_cer(text):
    return " ".join(text.split())


def cer(reference, hypothesis):
    """Character error rate: edit distance over reference length.

    Whitespace runs are collapsed first, so line breaks do not count.
    """
    ref = normalize_for_cer(reference)
    hyp = normalize_for_cer(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)
