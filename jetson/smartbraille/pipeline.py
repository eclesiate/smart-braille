"""One scan: camera frame in, text and braille cells out, with timings."""

import time
from dataclasses import dataclass, field

from . import braille, ocr, preprocess


@dataclass
class ScanResult:
    text: str
    translation: braille.Translation
    page: preprocess.PageResult
    timings_s: dict = field(default_factory=dict)

    @property
    def total_s(self):
        return sum(self.timings_s.values())


def scan(image, table=braille.UNCONTRACTED_UEB):
    timings = {}

    start = time.perf_counter()
    page = preprocess.preprocess(image)
    timings["preprocess"] = time.perf_counter() - start

    start = time.perf_counter()
    text = ocr.recognize(page.image, dpi=page.dpi)
    timings["ocr"] = time.perf_counter() - start

    start = time.perf_counter()
    translation = braille.translate(text, table)
    timings["braille"] = time.perf_counter() - start

    return ScanResult(text, translation, page, timings)
