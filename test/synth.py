"""Synthetic test pages: printed text photographed on a dark base.

Used by the tests and by ocr_accuracy.py --synthetic. A synthetic page has
perfect focus and no lens distortion, so it checks the software, not the
camera. Real accuracy has to be measured on the rig.
"""

import os
import textwrap

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog near the river bank. "
    "In 1829 Louis Braille published a system of raised dots that is still "
    "in use today. Each cell holds up to 6 dots, arranged in 2 columns of 3, "
    "which gives 63 patterns plus the blank cell.\n\n"
    "A refreshable display raises and lowers its pins as the reader moves "
    "through the text. Commercial displays often cost more than $2,000, so "
    "many people who would benefit from one never get to use it. Printed "
    "pages, such as letters, bills and school handouts, remain hard to reach.\n\n"
    "This device photographs a page, finds the words, and shows them 8 cells "
    "at a time. Press Next to move forward and Back to return. If the page is "
    "crooked or the light is uneven, the software corrects it before reading. "
    "Does it work on small print? That depends on the camera: at 300 dots per "
    "inch, 10-point type is easy; at 100, it is not."
)


def find_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def render_page(text=SAMPLE_TEXT, dpi=220, point_size=11, font_path=None):
    """Render text onto a white letter page. Returns a grayscale uint8 array."""
    font_path = font_path or find_font()
    if font_path is None:
        raise RuntimeError("no TrueType font found")
    width, height = int(8.5 * dpi), int(11 * dpi)
    font = ImageFont.truetype(font_path, int(round(point_size * dpi / 72)))
    page = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(page)
    margin = dpi  # one inch
    line_height = int(font.size * 1.35)
    chars_per_line = int((width - 2 * margin) / (font.size * 0.47))
    y = margin
    for paragraph in text.split("\n\n"):
        for line in textwrap.wrap(paragraph, chars_per_line):
            draw.text((margin, y), line, fill=20, font=font)
            y += line_height
        y += line_height
    return np.array(page)


def photograph(page, frame_size=None, skew=0.04, vignette=0.45, noise=3.0, seed=0):
    """Place a page on a dark base as a camera would see it.

    Returns (frame, corners) where corners are the true page corners
    (tl, tr, br, bl) in the frame.
    """
    rng = np.random.default_rng(seed)
    ph, pw = page.shape
    if frame_size is None:
        frame_size = (int(pw * 1.5), int(ph * 1.25))
    fw, fh = frame_size
    x0, y0 = (fw - pw) / 2, (fh - ph) / 2
    square = np.array([[0, 0], [pw, 0], [pw, ph], [0, ph]], dtype=np.float32)
    jitter = rng.uniform(-skew, skew, size=(4, 2)) * [pw, ph]
    corners = (square + [x0, y0] + jitter).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(square, corners)
    frame = np.full((fh, fw), 18, dtype=np.uint8)
    warped = cv2.warpPerspective(page, matrix, (fw, fh), flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(np.full_like(page, 255), matrix, (fw, fh))
    frame[mask > 127] = warped[mask > 127]
    # Bright centre, darker corners, plus a left-to-right gradient.
    yy, xx = np.mgrid[0:fh, 0:fw].astype(np.float32)
    r2 = ((xx - fw / 2) / (fw / 2)) ** 2 + ((yy - fh / 2) / (fh / 2)) ** 2
    light = (1 - vignette * r2 / 2) * (0.9 + 0.1 * xx / fw)
    lit = frame.astype(np.float32) * light + rng.normal(0, noise, frame.shape)
    return np.clip(lit, 0, 255).astype(np.uint8), corners
