"""Measure OCR accuracy (character error rate) and scan time.

On real photos, put each image next to a text file of the same name
holding the true text (page01.jpg + page01.txt):

    python test/ocr_accuracy.py photos/

Without a camera, check the software on synthetic pages at several
resolutions:

    python test/ocr_accuracy.py --synthetic 116 150 220 285

Targets: accuracy over 95% (CER under 0.05, NFS2) and under 5 s per page
on the Jetson (FS2, NFS1). Times measured on another machine do not count.
"""

import argparse
import pathlib
import sys

import cv2

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jetson"))
sys.path.insert(0, str(ROOT / "test"))

import synth  # noqa: E402
from smartbraille import metrics, pipeline  # noqa: E402

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def report(name, truth, image):
    result = pipeline.scan(image)
    error = metrics.cer(truth, result.text)
    t = result.timings_s
    print(f"{name:<24} CER {error:6.3f}  accuracy {100 * (1 - error):5.1f}%  "
          f"page {'found' if result.page.found_page else 'NOT FOUND'}  "
          f"{result.page.dpi:4.0f} dpi  preprocess {t['preprocess']:.2f} s  ocr {t['ocr']:.2f} s")
    return error


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", nargs="?", help="folder of images with matching .txt files")
    parser.add_argument("--synthetic", nargs="+", type=int, metavar="DPI",
                        help="render the sample page at these resolutions instead")
    parser.add_argument("--point-size", type=float, default=11, help="synthetic text size")
    args = parser.parse_args()

    errors = []
    if args.synthetic:
        for dpi in args.synthetic:
            page = synth.render_page(dpi=dpi, point_size=args.point_size)
            frame, _ = synth.photograph(page)
            errors.append(report(f"synthetic {dpi} dpi", synth.SAMPLE_TEXT, frame))
    elif args.folder:
        for path in sorted(pathlib.Path(args.folder).iterdir()):
            truth_file = path.with_suffix(".txt")
            if path.suffix.lower() not in IMAGE_TYPES or not truth_file.exists():
                continue
            image = cv2.imread(str(path))
            errors.append(report(path.name, truth_file.read_text(), image))
    else:
        parser.error("give a folder or --synthetic")

    if not errors:
        print("no pages found")
        return 1
    mean = sum(errors) / len(errors)
    print(f"\n{len(errors)} pages, mean CER {mean:.3f}, mean accuracy {100 * (1 - mean):.1f}%")
    return 0 if mean < 0.05 else 1


if __name__ == "__main__":
    sys.exit(main())
