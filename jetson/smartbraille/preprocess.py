"""Image preprocessing: find the page, rectify it, even out the lighting.

Follows section 3.5.1 of the 498A detailed design: grayscale, page contour
with approxPolyDP, four-point homography, then illumination normalisation
by fitting a quadratic surface to the brightest pixels of each tile.

One change from the design doc: the page is found from an Otsu threshold
instead of an edge map. The base is matte black, so the page is the one
large bright region and a threshold is more robust than edges.
"""

from dataclasses import dataclass

import cv2
import numpy as np

LETTER_SHORT_IN = 8.5
LETTER_LONG_IN = 11.0


@dataclass
class PageResult:
    image: np.ndarray  # rectified, normalised, grayscale uint8
    corners: np.ndarray | None  # 4x2 (tl, tr, br, bl) in the input frame
    dpi: float  # effective resolution of `image`, assuming a letter page
    found_page: bool


def to_gray(image):
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def order_corners(points):
    """Order four points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = pts[:, 0] - pts[:, 1]
    return np.array(
        [pts[np.argmin(s)], pts[np.argmax(d)], pts[np.argmax(s)], pts[np.argmin(d)]],
        dtype=np.float32,
    )


def find_page(gray, min_area_fraction=0.15):
    """Return the page's four corners (tl, tr, br, bl), or None if not found."""
    h, w = gray.shape
    scale = 1000.0 / max(h, w) if max(h, w) > 1000 else 1.0
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (5, 5), 0)
    _, mask = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < min_area_fraction * mask.size:
        return None
    # A page that fills the whole frame is not a detected page.
    x, y, cw, ch = cv2.boundingRect(contour)
    if cw >= mask.shape[1] - 2 and ch >= mask.shape[0] - 2:
        return None
    hull = cv2.convexHull(contour)
    quad = None
    for eps in (0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
        if len(approx) == 4:
            quad = approx.reshape(4, 2)
            break
    if quad is None:
        quad = cv2.boxPoints(cv2.minAreaRect(hull))
    return order_corners(quad / scale)


def rectify(gray, corners):
    """Warp the page to an upright letter-proportioned rectangle.

    Keeps the camera's native resolution: the output's short side matches
    the page's short side in the frame. Returns (image, dpi).
    """
    tl, tr, br, bl = corners
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    if width <= height:  # portrait
        out_w = int(round(width))
        out_h = int(round(out_w * LETTER_LONG_IN / LETTER_SHORT_IN))
        dpi = out_w / LETTER_SHORT_IN
    else:  # landscape
        out_h = int(round(height))
        out_w = int(round(out_h * LETTER_LONG_IN / LETTER_SHORT_IN))
        dpi = out_h / LETTER_SHORT_IN
    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    warped = cv2.warpPerspective(gray, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC)
    return warped, dpi


def trim_border(gray, fraction=0.01):
    """Cut a thin margin so the dark base at the page edge is not read as text."""
    h, w = gray.shape
    m = int(round(min(h, w) * fraction))
    return gray[m : h - m, m : w - m] if m > 0 else gray


def estimate_illumination(gray, tiles=12, percentile=90):
    """Fit a quadratic surface to the paper brightness. Returns a float32 field."""
    h, w = gray.shape
    ys = np.linspace(0, h, tiles + 1, dtype=int)
    xs = np.linspace(0, w, tiles + 1, dtype=int)
    samples = []
    for i in range(tiles):
        for j in range(tiles):
            tile = gray[ys[i] : ys[i + 1], xs[j] : xs[j + 1]]
            if tile.size == 0:
                continue
            cx = (xs[j] + xs[j + 1]) / 2 / w * 2 - 1
            cy = (ys[i] + ys[i + 1]) / 2 / h * 2 - 1
            samples.append((cx, cy, np.percentile(tile, percentile)))
    samples = np.array(samples, dtype=np.float64)
    # Tiles with no paper in them (a photo, a solid block) would pull the fit
    # down, so drop the ones well below the typical paper level.
    keep = samples[:, 2] >= 0.6 * np.median(samples[:, 2])
    x, y, z = samples[keep].T
    design = np.column_stack([np.ones_like(x), x, y, x * x, x * y, y * y])
    coeffs, *_ = np.linalg.lstsq(design, z, rcond=None)
    gx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    gy = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    c = coeffs.astype(np.float32)
    return c[0] + c[1] * gx + c[2] * gy + c[3] * gx * gx + c[4] * gx * gy + c[5] * gy * gy


def normalize_illumination(gray, target=245.0, max_gain=3.0, tiles=12):
    """Scale each pixel so the paper comes out near white. Gain is capped."""
    field = np.maximum(estimate_illumination(gray, tiles=tiles), 1.0)
    gain = np.minimum(target / field, max_gain)
    return np.clip(gray.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def preprocess(image):
    """Full pipeline on a camera frame (BGR or grayscale)."""
    gray = to_gray(image)
    corners = find_page(gray)
    if corners is None:
        page, dpi, found = gray, min(gray.shape) / LETTER_SHORT_IN, False
    else:
        page, dpi = rectify(gray, corners)
        page, found = trim_border(page), True
    return PageResult(normalize_illumination(page), corners, dpi, found)
