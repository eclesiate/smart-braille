"""Preprocessing and end-to-end OCR tests on synthetic pages.

These check the software path only. A synthetic page is in perfect focus
with no lens distortion; accuracy on the real rig is measured with
ocr_accuracy.py.
"""

import shutil

import numpy as np
import pytest

import synth
from smartbraille import metrics, pipeline, preprocess
from smartbraille.__main__ import App
from smartbraille.display import VirtualDisplay
from smartbraille.paging import Button

needs_font = pytest.mark.skipif(synth.find_font() is None, reason="no TrueType font")
needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="no tesseract")


@pytest.fixture(scope="module")
def photo():
    page = synth.render_page(dpi=220)
    frame, corners = synth.photograph(page)
    return page, frame, corners


@needs_font
def test_find_page_locates_the_corners(photo):
    _, frame, truth = photo
    found = preprocess.find_page(frame)
    assert found is not None
    assert np.abs(found - truth).max() < 0.01 * max(frame.shape)


def test_find_page_returns_none_without_a_page():
    dark = np.full((600, 800), 15, dtype=np.uint8)
    assert preprocess.find_page(dark) is None
    full = np.full((600, 800), 230, dtype=np.uint8)
    assert preprocess.find_page(full) is None


@needs_font
def test_rectified_page_is_letter_shaped_and_keeps_resolution(photo):
    page, frame, _ = photo
    result = preprocess.preprocess(frame)
    assert result.found_page
    h, w = result.image.shape
    assert h / w == pytest.approx(11 / 8.5, rel=0.02)
    assert result.dpi == pytest.approx(220, rel=0.1)


def test_illumination_normalisation_flattens_a_shaded_page():
    h, w = 600, 460
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    shade = 230 * (1 - 0.4 * (((xx - w / 2) / w) ** 2 + ((yy - h / 2) / h) ** 2) * 2)
    page = shade.copy()
    page[100:110, 50:400] *= 0.1  # a line of "text"
    out = preprocess.normalize_illumination(page.astype(np.uint8))
    paper = np.delete(out, np.s_[95:115], axis=0)
    assert paper.min() > 225 and paper.std() < 5
    assert out[100:110, 50:400].mean() < 60


@needs_font
@needs_tesseract
def test_end_to_end_accuracy_on_a_synthetic_page(photo):
    _, frame, _ = photo
    result = pipeline.scan(frame)
    error = metrics.cer(synth.SAMPLE_TEXT, result.text)
    assert error < 0.02, f"CER {error:.3f}\n{result.text}"
    assert len(result.translation.cells) >= len(result.translation.text)


@needs_font
@needs_tesseract
def test_app_scans_and_pages_on_the_virtual_display(photo):
    _, frame, _ = photo

    class Camera:
        def capture(self):
            return frame

    lines = []
    virtual = VirtualDisplay(out=lines.append)
    app = App(Camera(), [virtual], log=lines.append)
    app.press(Button.SCAN, now=0.0)
    assert len(app.reader.windows) > 50
    first = list(virtual.shown)
    assert first == app.reader.windows[0].cells
    app.press(Button.NEXT, now=1.0)
    assert virtual.shown == app.reader.windows[1].cells
    app.press(Button.BACK, now=2.0)
    assert virtual.shown == first
    # "The" plus its capital sign fills 4 cells; "quick" does not fit after it.
    assert any("[1/" in str(line) and "'The'" in str(line) for line in lines)
