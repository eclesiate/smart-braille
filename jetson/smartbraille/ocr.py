"""Text extraction with Tesseract."""

import re

import cv2
import pytesseract

# Below this resolution Tesseract's accuracy drops, so the page is enlarged
# first. To be tuned on the real rig.
MIN_DPI = 200
UPSCALE_TO_DPI = 300


def clean_text(raw):
    """Turn Tesseract's line-oriented output into reading text.

    Joins words hyphenated across a line break, joins the lines of a
    paragraph with spaces, and keeps blank lines as paragraph breaks.
    """
    text = raw.replace("\r", "").replace("\x0c", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    paragraphs = re.split(r"\n\s*\n", text)
    joined = [" ".join(p.split()) for p in paragraphs]
    return "\n".join(p for p in joined if p)


def recognize(image, dpi=None, lang="eng", psm=3):
    """Run OCR on a preprocessed grayscale page and return cleaned text."""
    if dpi is not None and dpi < MIN_DPI:
        factor = UPSCALE_TO_DPI / dpi
        image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        dpi = UPSCALE_TO_DPI
    config = f"--oem 1 --psm {psm}"
    if dpi is not None:
        config += f" --dpi {int(round(dpi))}"
    return clean_text(pytesseract.image_to_string(image, lang=lang, config=config))
