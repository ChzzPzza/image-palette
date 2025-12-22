# palette/region.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


def crop_region(image_bytes: bytes, rect: Rect) -> bytes:
    """
    rect is in *image pixel coordinates* (not canvas coords).
    Returns cropped image bytes (PNG).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    W, H = img.size

    x0 = int(max(0, min(W - 1, rect.x)))
    y0 = int(max(0, min(H - 1, rect.y)))
    x1 = int(max(0, min(W, rect.x + rect.w)))
    y1 = int(max(0, min(H, rect.y + rect.h)))

    # Ensure non-empty crop
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Empty crop rectangle.")

    cropped = img.crop((x0, y0, x1, y1))

    out = io.BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()
