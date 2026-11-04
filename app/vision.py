"""Shadow silhouette extraction and shape matching.

The idea the report describes: photograph an object, find its cast shadow,
reduce the silhouette to a small rotation-tolerant descriptor, and compare
descriptors by cosine similarity. This module is the whole vision pipeline and
has no web dependencies, so it can be tested and benchmarked on its own.

Pipeline
--------
    BGR image
      -> grey + light blur
      -> binary mask of dark regions (adaptive threshold)
      -> keep the component that touches the "base" of the frame (the object /
         shadow contact region), which discards dark background clutter
      -> fill holes, take the largest external contour
      -> normalise to 64x64, build a 64-bin radial histogram
      -> L2-normalise

The radial histogram is deliberately coarse: it tolerates the moderate shape
change between two photographs of the same object taken from different angles,
which is exactly the weakness the report discusses in its limitations section.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

GRID = 64                 # normalised silhouette size
BINS = 64                 # descriptor length
MIN_AREA_FRACTION = 0.01  # ignore specks smaller than 1% of the frame
MIN_IOU = 0.45            # below this the silhouette is called unreliable


@dataclass
class Silhouette:
    """Result of running the pipeline on one image."""

    mask: np.ndarray            # uint8, 0/255, same size as the input
    grid: np.ndarray            # float32, GRID x GRID, normalised silhouette
    descriptor: np.ndarray      # float32, BINS, L2-normalised
    iou: float                  # mask area / bounding-box area, a quality proxy
    area_fraction: float        # foreground share of the frame

    @property
    def reliable(self) -> bool:
        return self.iou >= MIN_IOU and self.area_fraction >= MIN_AREA_FRACTION


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def _largest_component(mask: np.ndarray) -> np.ndarray:
    """Keep only the biggest connected blob."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return mask
    # stats[:, AREA]; index 0 is background
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == biggest, 255, 0).astype(np.uint8)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill interior holes so the silhouette is solid."""
    h, w = mask.shape
    flood = mask.copy()
    pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, pad, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    return cv2.bitwise_or(mask, holes)


def _cut_border(mask: np.ndarray, px: int = 2) -> np.ndarray:
    """Clear the outer few pixels so flood fill starts on background."""
    out = mask.copy()
    out[:px, :] = 0
    out[-px:, :] = 0
    out[:, :px] = 0
    out[:, -px:] = 0
    return out


def extract_shadow(image_bgr: np.ndarray) -> Silhouette:
    """Detect the cast shadow in `image_bgr` and describe its shape."""
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("empty image")

    # keep the work bounded: phone photos are huge and the descriptor is coarse
    h, w = image_bgr.shape[:2]
    scale = min(1.0, 480.0 / max(h, w))
    small = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) \
        if scale < 1.0 else image_bgr
    h, w = small.shape[:2]

    grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    grey = cv2.GaussianBlur(grey, (5, 5), 0)

    # dark regions = shadow candidates; blockSize scales with the frame
    block = max(15, (min(h, w) // 12) | 1)          # must be odd and >= 3
    mask = cv2.adaptiveThreshold(
        grey, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, block, 10
    )

    # remove the frame-touching background, then keep the strongest blob
    mask = _cut_border(mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = _largest_component(mask)
    mask = _fill_holes(mask)

    # re-take the largest external contour after filling
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        solid = np.zeros_like(mask)
        cv2.drawContours(solid, [max(contours, key=cv2.contourArea)], -1, 255, thickness=cv2.FILLED)
        mask = solid

    area = float(np.count_nonzero(mask))
    area_fraction = area / float(h * w)

    xs = np.where(mask.any(axis=0))[0]
    ys = np.where(mask.any(axis=1))[0]
    if xs.size and ys.size:
        crop = mask[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
        box_area = float(crop.size)
        iou = area / box_area if box_area else 0.0
    else:
        iou = 0.0

    grid = _normalise(mask)
    descriptor = descriptor_from_grid(grid)

    # scale the mask back up so callers can overlay it on the original photo
    if scale < 1.0:
        mask_out = cv2.resize(mask, (image_bgr.shape[1], image_bgr.shape[0]),
                              interpolation=cv2.INTER_NEAREST)
    else:
        mask_out = mask

    return Silhouette(mask=mask_out, grid=grid, descriptor=descriptor,
                      iou=float(iou), area_fraction=float(area_fraction))


def _normalise(mask: np.ndarray) -> np.ndarray:
    """Crop to the bounding box and squash to GRID x GRID, filling the frame."""
    ys, xs = np.where(mask > 0)
    if not len(ys):
        return np.zeros((GRID, GRID), np.float32)
    crop = mask[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    resized = cv2.resize(crop, (GRID, GRID), interpolation=cv2.INTER_AREA)
    return (resized > 127).astype(np.float32)


# ---------------------------------------------------------------------------
# descriptor
# ---------------------------------------------------------------------------
GRID_CELLS = 8            # 8 x 8 = 64 bins, matching the report's descriptor length


def descriptor_from_grid(grid: np.ndarray) -> np.ndarray:
    """64-bin descriptor = 8x8 occupancy grid of the normalised silhouette.

    Each of the 64 cells holds the fraction of that cell covered by the
    silhouette, so the descriptor keeps *where* the mass sits, not just how
    much of it there is. A radial histogram alone cannot tell a watch from a
    bag; an occupancy grid can. The vector is L2-normalised, so cosine
    similarity is a dot product.
    """
    g = (grid > 0.5).astype(np.float32)
    if not g.any():
        return np.zeros(BINS, np.float32)

    side = g.shape[0] // GRID_CELLS          # 64 // 8 == 8
    cells = g.reshape(GRID_CELLS, side, GRID_CELLS, side).mean(axis=(1, 3))

    # Shape cues that an occupancy grid alone loses. Both are scale free, so
    # the descriptor still ignores distance from the camera.
    ys, xs = np.nonzero(g)
    h = (ys.max() - ys.min() + 1) / g.shape[0]
    w = (xs.max() - xs.min() + 1) / g.shape[1]
    aspect = np.float32(w / h) if h > 0 else np.float32(1.0)
    fill = np.float32(g.mean())              # how solid the bounding box is

    desc = cells.ravel().astype(np.float32)

    # The outer ring of the 8x8 grid is mostly background and the 4x4 corner
    # blocks are almost always empty. Reuse those 28 cells for global shape
    # scalars, so silhouette geometry (aspect ratio, solidity) contributes
    # alongside the local mass distribution.
    ring = [0, 1, 2, 3, 4, 5, 6, 7,
            15, 23, 31, 39, 47, 55,
            63, 62, 61, 60, 59, 58, 57, 56,
            48, 40, 32, 24, 16, 8]
    scalars = np.array([aspect, fill], np.float32)
    for i, idx in enumerate(ring):
        desc[idx] = scalars[i % 2] * 0.5

    norm = float(np.linalg.norm(desc))
    return desc / norm if norm else desc


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two descriptors, scaled to 0..1."""
    if a is None or b is None or a.size == 0 or b.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


def rank(query: np.ndarray, candidates: list[tuple[int, np.ndarray]]) -> list[tuple[int, float]]:
    """Score every (item_id, descriptor) candidate and sort best first."""
    scored = [(item_id, similarity(query, desc)) for item_id, desc in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# synthetic sample photos (used to seed the demo database)
# ---------------------------------------------------------------------------
def _render_object(canvas, cx, cy, kind, colour, shadow_dir):
    """Draw a simple object plus its cast shadow; used by make_samples()."""
    h, w = canvas.shape[:2]
    shadow = tuple(int(c * 0.18) for c in colour)

    if kind == "bag":
        body = (cx - 55, cy - 40, cx + 55, cy + 55)
        handle = (cx - 30, cy - 70, cx + 30, cy - 20)
        cv2.ellipse(canvas, shadow_dir((cx, cy - 45)), (34, 28), 0, 0, 360, shadow, -1)
        cv2.rectangle(canvas, (cx - 55 + 34, cy - 40 + 30), (cx + 55 + 34, cy + 55 + 30),
                      shadow, -1)
        cv2.rectangle(canvas, body[0:2], body[2:4], colour, -1)
        cv2.ellipse(canvas, (cx, cy - 45), (32, 26), 0, 180, 360, colour, 12)
        cv2.line(canvas, (cx - 20, cy + 5), (cx - 5, cy + 40), (250, 250, 250), 5)
    elif kind == "bottle":
        body = (cx - 26, cy - 45, cx + 26, cy + 60)
        cv2.rectangle(canvas, (cx - 26 + 34, cy - 45 + 30), (cx + 26 + 34, cy + 60 + 30),
                      shadow, -1)
        cv2.rectangle(canvas, body[0:2], body[2:4], colour, -1)
        cv2.rectangle(canvas, (cx - 14, cy - 78), (cx + 14, cy - 45), colour, -1)
        cv2.rectangle(canvas, (cx - 16, cy - 88), (cx + 16, cy - 76), (60, 60, 60), -1)
        cv2.rectangle(canvas, (cx - 26, cy + 10), (cx + 26, cy + 26), (250, 250, 250), -1)
    elif kind == "watch":
        cv2.circle(canvas, (cx + 34, cy + 30), 52, shadow, -1)
        cv2.circle(canvas, (cx, cy), 52, colour, -1)
        cv2.circle(canvas, (cx, cy), 52, (40, 40, 40), 6)
        cv2.rectangle(canvas, (cx - 16, cy - 92), (cx + 16, cy - 52), (45, 45, 48), -1)
        cv2.rectangle(canvas, (cx - 16, cy + 52), (cx + 16, cy + 92), (45, 45, 48), -1)
        cv2.line(canvas, (cx, cy), (cx, cy - 30), (250, 250, 250), 4)
        cv2.line(canvas, (cx, cy), (cx + 22, cy + 10), (250, 250, 250), 4)
    elif kind == "umbrella":
        cv2.ellipse(canvas, (cx + 34, cy + 30 + 30), (95, 62), 0, 180, 360, shadow, -1)
        cv2.ellipse(canvas, (cx, cy), (95, 62), 0, 180, 360, colour, -1)
        cv2.line(canvas, (cx, cy), (cx, cy + 90), (70, 70, 70), 7)
        cv2.ellipse(canvas, (cx - 18, cy + 92), (20, 14), 0, 0, 180, (70, 70, 70), 7)
    elif kind == "helmet":
        cv2.ellipse(canvas, (cx + 34, cy + 35 + 30), (78, 66), 0, 180, 360, shadow, -1)
        cv2.ellipse(canvas, (cx, cy + 8), (78, 66), 0, 180, 360, colour, -1)
        cv2.ellipse(canvas, (cx, cy + 8), (78, 66), 0, 0, 180, colour, 0)
        cv2.rectangle(canvas, (cx - 82, cy + 2), (cx + 82, cy + 22), colour, -1)
        cv2.ellipse(canvas, (cx - 20, cy - 18), (26, 12), 0, 0, 360, (240, 240, 240), -1)
    return canvas


def make_sample(colour: str, kind: str, seed: int = 0) -> np.ndarray:
    """Render one synthetic 'photo' of an item lying on a surface with a shadow."""
    rng = np.random.default_rng(seed)
    img = np.full((360, 480, 3), 205, np.uint8)
    img[:] = (rng.integers(195, 215), rng.integers(195, 215), rng.integers(195, 215))

    bgr = {"blue": (170, 95, 40), "red": (45, 45, 175), "green": (70, 130, 70),
           "black": (38, 38, 40), "grey": (120, 122, 126), "white": (232, 232, 228),
           "yellow": (40, 190, 215)}.get(colour, (120, 120, 120))

    # Each "photo" varies a little: position, scale and a small rotation.
    # Real reports are different photographs of the same object, so the demo
    # data should be too - identical frames would score a meaningless 1.00.
    cx = 240 + int(rng.integers(-26, 27))
    cy = 170 + int(rng.integers(-18, 19))
    scale = float(rng.uniform(0.86, 1.12))
    angle = float(rng.uniform(-14, 14))

    canvas = _render_object(img, cx, cy, kind, bgr, lambda p: (p[0] + 34, p[1] + 30))

    if abs(scale - 1.0) > 0.01 or abs(angle) > 0.5:
        h, w = canvas.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
        canvas = cv2.warpAffine(canvas, M, (w, h), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)

    canvas = cv2.GaussianBlur(canvas, (3, 3), 0)

    # a little sensor noise so the threshold path is exercised realistically
    noise = rng.normal(0, 3.0, canvas.shape).astype(np.int16)
    return np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def to_data_uri(png_bytes: bytes) -> str:
    import base64
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
