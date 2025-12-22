# palette/extract.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from .color import (
    rgb8_to_oklab,
    oklab_to_rgb8,
    rgb8_to_hex,
    relative_luminance_from_rgb8,
    oklab_delta_e,
    oklab_to_oklch,
    hue_distance_deg,
)


@dataclass
class Cluster:
    lab: np.ndarray           # (3,)
    rgb8: np.ndarray          # (3,)
    hex: str
    weight: float             # weighted coverage
    raw_count: int            # pixel count
    L: float
    C: float
    h: float


def _load_pixels(image_bytes: bytes, downscale_max: int) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = min(1.0, downscale_max / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype=np.uint8)
    pixels = arr.reshape(-1, 3)
    return pixels


def _sample_pixels(pixels: np.ndarray, sample_max: int, seed: int = 1) -> np.ndarray:
    n = pixels.shape[0]
    if n <= sample_max:
        return pixels
    rng = np.random.default_rng(seed)
    idx = rng.choice(n, size=sample_max, replace=False)
    return pixels[idx]


def _weighted_kmeans_oklab(pixels_rgb8: np.ndarray, k: int, stevens_exp: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    returns: centers_oklab (k,3), labels (N,), sample_weights (N,)
    """
    lab = rgb8_to_oklab(pixels_rgb8)  # (N,3)
    Y = relative_luminance_from_rgb8(pixels_rgb8)
    # Stevens-style “power”: perceived ~ physical^exp
    weights = (Y + 1e-6) ** float(stevens_exp)

    km = KMeans(n_clusters=k, n_init="auto", random_state=1)
    km.fit(lab, sample_weight=weights)
    centers = km.cluster_centers_.astype(np.float32)
    labels = km.labels_.astype(np.int32)
    return centers, labels, weights.astype(np.float32)


def _build_clusters(
    centers_lab: np.ndarray,
    labels: np.ndarray,
    pixels_rgb8: np.ndarray,
    sample_weights: np.ndarray,
) -> List[Cluster]:
    k = centers_lab.shape[0]
    clusters: List[Cluster] = []
    for i in range(k):
        mask = labels == i
        raw_count = int(np.sum(mask))
        if raw_count == 0:
            continue
        w = float(np.sum(sample_weights[mask]))
        lab = centers_lab[i]
        rgb8 = oklab_to_rgb8(lab.reshape(1, 3))[0]
        hx = rgb8_to_hex(rgb8)
        L, C, h = oklab_to_oklch(lab)
        clusters.append(Cluster(lab=lab, rgb8=rgb8, hex=hx, weight=w, raw_count=raw_count, L=L, C=C, h=h))
    clusters.sort(key=lambda c: c.weight, reverse=True)
    return clusters


def _merge_similar(clusters: List[Cluster], merge_delta_e: float) -> List[Cluster]:
    """
    Merge clusters that are too similar (OKLab distance < threshold).
    """
    remaining = clusters[:]
    merged: List[Cluster] = []

    while remaining:
        base = remaining.pop(0)
        to_merge = [base]
        keep = []
        for c in remaining:
            if oklab_delta_e(base.lab, c.lab) < merge_delta_e:
                to_merge.append(c)
            else:
                keep.append(c)
        remaining = keep

        total_w = sum(c.weight for c in to_merge)
        if total_w <= 0:
            continue
        lab = sum((c.lab * c.weight for c in to_merge)) / total_w
        rgb8 = oklab_to_rgb8(lab.reshape(1, 3))[0]
        hx = rgb8_to_hex(rgb8)
        raw_count = int(sum(c.raw_count for c in to_merge))
        L, C, h = oklab_to_oklch(lab)
        merged.append(Cluster(lab=lab, rgb8=rgb8, hex=hx, weight=float(total_w), raw_count=raw_count, L=L, C=C, h=h))

    merged.sort(key=lambda c: c.weight, reverse=True)
    return merged


def _distinctness_scores(clusters: List[Cluster]) -> List[float]:
    if len(clusters) <= 1:
        return [0.0 for _ in clusters]
    labs = [c.lab for c in clusters]
    scores = []
    for i, li in enumerate(labs):
        dmin = 1e9
        for j, lj in enumerate(labs):
            if i == j:
                continue
            d = oklab_delta_e(li, lj)
            if d < dmin:
                dmin = d
        scores.append(float(dmin))
    return scores


def _pick_primary(clusters: List[Cluster]) -> int:
    total = sum(c.weight for c in clusters) or 1.0
    distinct = _distinctness_scores(clusters)
    # Normalize distinctness for scoring
    dmax = max(distinct) or 1.0
    best_i = 0
    best_score = -1e9
    for i, c in enumerate(clusters):
        amount = c.weight / total
        d = distinct[i] / dmax
        score = 0.70 * amount + 0.30 * d
        if score > best_score:
            best_score = score
            best_i = i
    return best_i


def _scheme_anchors(primary_h: float) -> Dict[str, List[float]]:
    # 3-anchor schemes (primary + 2 others) so you always get primary/secondary/tertiary
    return {
        "analogous": [primary_h, (primary_h + 30) % 360, (primary_h - 30) % 360],
        "complementary+accent": [primary_h, (primary_h + 180) % 360, (primary_h + 30) % 360],
        "split-complementary": [primary_h, (primary_h + 150) % 360, (primary_h + 210) % 360],
        "triadic": [primary_h, (primary_h + 120) % 360, (primary_h + 240) % 360],
    }


def _best_harmony_scheme(primary: Cluster, clusters: List[Cluster]) -> Tuple[str, List[float]]:
    schemes = _scheme_anchors(primary.h)
    best_name = "analogous"
    best_cost = 1e18
    best_anchors = schemes[best_name]

    for name, anchors in schemes.items():
        cost = 0.0
        for c in clusters:
            d = min(hue_distance_deg(c.h, a) for a in anchors)
            cost += c.weight * (d ** 2)  # squared to punish off-hues more
        if cost < best_cost:
            best_cost = cost
            best_name = name
            best_anchors = anchors

    return best_name, best_anchors


def _assign_to_anchors(clusters: List[Cluster], anchors: List[float]) -> List[int]:
    """
    Returns index of anchor for each cluster.
    """
    assignments = []
    for c in clusters:
        idx = int(np.argmin([hue_distance_deg(c.h, a) for a in anchors]))
        assignments.append(idx)
    return assignments


def _pick_secondary_tertiary(
    clusters: List[Cluster],
    primary_idx: int,
    anchors: List[float],
    distinct_min_delta_e: float,
) -> Tuple[int, int]:
    primary = clusters[primary_idx]
    assigns = _assign_to_anchors(clusters, anchors)

    # prefer top-weight clusters assigned to *different* anchors than primary
    p_anchor = assigns[primary_idx]
    candidates = [i for i in range(len(clusters)) if i != primary_idx]
    candidates.sort(key=lambda i: clusters[i].weight, reverse=True)

    chosen: List[int] = []
    used_anchors = {p_anchor}

    for i in candidates:
        a = assigns[i]
        if a in used_anchors:
            continue
        if oklab_delta_e(primary.lab, clusters[i].lab) < distinct_min_delta_e:
            continue
        chosen.append(i)
        used_anchors.add(a)
        if len(chosen) == 2:
            break

    # fallback: just pick the most distinct + heavy
    if len(chosen) < 2:
        for i in candidates:
            if i in chosen:
                continue
            if oklab_delta_e(primary.lab, clusters[i].lab) < distinct_min_delta_e:
                continue
            ok = True
            for j in chosen:
                if oklab_delta_e(clusters[j].lab, clusters[i].lab) < distinct_min_delta_e:
                    ok = False
                    break
            if ok:
                chosen.append(i)
            if len(chosen) == 2:
                break

    # if still missing, allow close matches
    while len(chosen) < 2 and candidates:
        i = candidates.pop(0)
        if i not in chosen and i != primary_idx:
            chosen.append(i)

    return chosen[0], chosen[1]


def extract_palette(
    image_bytes: bytes,
    max_k: int = 10,
    support_max: int = 4,
    merge_delta_e: float = 0.06,
    distinct_min_delta_e: float = 0.09,
    stevens_exp: float = 0.33,
    sample_max: int = 60000,
    downscale_max: int = 512,
) -> dict:
    pixels = _load_pixels(image_bytes, downscale_max=downscale_max)
    pixels = _sample_pixels(pixels, sample_max=sample_max)

    centers, labels, weights = _weighted_kmeans_oklab(pixels, k=max_k, stevens_exp=stevens_exp)
    clusters = _build_clusters(centers, labels, pixels, weights)
    clusters = _merge_similar(clusters, merge_delta_e=merge_delta_e)

    if not clusters:
        return {"error": "No clusters extracted."}

    primary_idx = _pick_primary(clusters)
    primary = clusters[primary_idx]

    scheme_name, anchors = _best_harmony_scheme(primary, clusters)
    sec_idx, ter_idx = _pick_secondary_tertiary(
        clusters, primary_idx=primary_idx, anchors=anchors, distinct_min_delta_e=distinct_min_delta_e
    )

    # supporting colors: remaining, capped
    used = {primary_idx, sec_idx, ter_idx}
    support = [c for i, c in enumerate(clusters) if i not in used]
    support.sort(key=lambda c: c.weight, reverse=True)
    support = support[:support_max]

    total_w = sum(c.weight for c in clusters) or 1.0

    def pack(c: Cluster, role: str) -> dict:
        return {
            "role": role,
            "hex": c.hex,
            "coverage": c.weight / total_w,
            "oklch": {"L": c.L, "C": c.C, "h": c.h},
        }

    result = {
        "scheme": scheme_name,
        "primary": pack(primary, "primary"),
        "secondary": pack(clusters[sec_idx], "secondary"),
        "tertiary": pack(clusters[ter_idx], "tertiary"),
        "support": [pack(c, f"support-{i+1}") for i, c in enumerate(support)],
        "settings": {
            "max_k": max_k,
            "support_max": support_max,
            "merge_delta_e": merge_delta_e,
            "distinct_min_delta_e": distinct_min_delta_e,
            "stevens_exp": stevens_exp,
        },
    }
    return result
