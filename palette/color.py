# palette/color.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class OKLab:
    L: float
    a: float
    b: float


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    # c in [0,1]
    a = 0.055
    return np.where(c <= 0.04045, c / 12.92, ((c + a) / (1 + a)) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(c <= 0.0031308, 12.92 * c, (1 + a) * (c ** (1 / 2.4)) - a)


def rgb8_to_oklab(rgb8: np.ndarray) -> np.ndarray:
    """
    rgb8: (N,3) uint8
    returns (N,3) float OKLab
    """
    rgb = rgb8.astype(np.float32) / 255.0
    lin = srgb_to_linear(rgb)

    # linear RGB -> LMS
    M1 = np.array([
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ], dtype=np.float32)

    lms = lin @ M1.T
    lms_cbrt = np.cbrt(lms)

    # LMS -> OKLab
    M2 = np.array([
        [0.2104542553, 0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050, 0.4505937099],
        [0.0259040371, 0.7827717662, -0.8086757660],
    ], dtype=np.float32)

    lab = lms_cbrt @ M2.T
    return lab.astype(np.float32)


def oklab_to_rgb8(lab: np.ndarray) -> np.ndarray:
    """
    lab: (N,3) float OKLab
    returns (N,3) uint8 sRGB
    """
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]

    # OKLab -> LMS'
    M2_inv = np.array([
        [1.0000000000, 0.3963377774, 0.2158037573],
        [1.0000000000, -0.1055613458, -0.0638541728],
        [1.0000000000, -0.0894841775, -1.2914855480],
    ], dtype=np.float32)

    lms_ = np.stack([L, a, b], axis=1) @ M2_inv.T
    lms = lms_ ** 3

    # LMS -> linear RGB
    M1_inv = np.array([
        [4.0767416621, -3.3077115913, 0.2309699292],
        [-1.2684380046, 2.6097574011, -0.3413193965],
        [-0.0041960863, -0.7034186147, 1.7076147010],
    ], dtype=np.float32)

    lin = lms @ M1_inv.T
    srgb = linear_to_srgb(np.clip(lin, 0.0, 1.0))
    rgb8 = (np.clip(srgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    return rgb8


def rgb8_to_hex(rgb8: np.ndarray) -> str:
    r, g, b = int(rgb8[0]), int(rgb8[1]), int(rgb8[2])
    return f"#{r:02X}{g:02X}{b:02X}"


def relative_luminance_from_rgb8(rgb8: np.ndarray) -> np.ndarray:
    """
    rgb8: (N,3) uint8
    returns Y in [0,1] using linear RGB coefficients.
    """
    rgb = rgb8.astype(np.float32) / 255.0
    lin = srgb_to_linear(rgb)
    # Rec. 709 / sRGB luminance
    Y = 0.2126 * lin[:, 0] + 0.7152 * lin[:, 1] + 0.0722 * lin[:, 2]
    return np.clip(Y, 0.0, 1.0)


def oklab_delta_e(lab1: np.ndarray, lab2: np.ndarray) -> float:
    d = lab1 - lab2
    return float(np.sqrt(np.sum(d * d)))


def oklab_to_oklch(lab: np.ndarray) -> Tuple[float, float, float]:
    L, a, b = float(lab[0]), float(lab[1]), float(lab[2])
    C = math.sqrt(a * a + b * b)
    h = math.degrees(math.atan2(b, a)) % 360.0
    return (L, C, h)


def hue_distance_deg(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360.0
    return min(d, 360.0 - d)
