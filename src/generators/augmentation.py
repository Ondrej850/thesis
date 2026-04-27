"""
Post-generation augmentation to simulate photographed/scanned document appearance.
Path: src/generators/augmentation.py
"""

import random

import numpy as np
from PIL import Image
import albumentations as A


def add_book_edges(image: np.ndarray) -> np.ndarray:
    """Darken random edges with a gradient to mimic a book/scanner capture.

    Each of the four edges independently decides whether to apply, so any
    combination of 0-4 darkened edges is possible.
    """
    h, w = image.shape[:2]
    result = image.copy()

    if random.random() < 0.3:
        ew = min(random.randint(20, 80), w)
        grad = np.linspace(0.0, 1.0, ew)
        result[:, :ew] = (result[:, :ew] * grad[None, :, None]).astype(np.uint8)

    if random.random() < 0.15:
        ew = min(random.randint(20, 80), w)
        grad = np.linspace(1.0, 0.0, ew)
        result[:, -ew:] = (result[:, -ew:] * grad[None, :, None]).astype(np.uint8)

    if random.random() < 0.2:
        ew = min(random.randint(20, 80), h)
        grad = np.linspace(0.0, 1.0, ew)
        result[:ew, :] = (result[:ew, :] * grad[:, None, None]).astype(np.uint8)

    if random.random() < 0.15:
        ew = min(random.randint(20, 80), h)
        grad = np.linspace(1.0, 0.0, ew)
        result[-ew:, :] = (result[-ew:, :] * grad[:, None, None]).astype(np.uint8)

    return result


def _add_vignette(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """Darken edges radially to simulate lens vignetting."""
    h, w = image.shape[:2]
    y = np.linspace(-1.0, 1.0, h)
    x = np.linspace(-1.0, 1.0, w)
    xv, yv = np.meshgrid(x, y)
    radius = np.sqrt(xv ** 2 + yv ** 2)
    # Map radius to attenuation: centre=1, corners<1
    attenuation = np.clip(1.0 - strength * (radius / radius.max()), 0.0, 1.0)
    return (image * attenuation[:, :, None]).astype(np.uint8)


_TRANSFORM = A.Compose([
    A.ToSepia(p=0.5),
    A.ColorJitter(
        brightness=(0.7, 1.3),
        contrast=(0.7, 1.3),
        saturation=(0.8, 1.2),
        hue=(-0.05, 0.05),
        p=0.8,
    ),
    A.GaussNoise(std_range=(0.04, 0.15), p=0.8),
    A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.4), p=0.5),
    A.RandomShadow(
        shadow_roi=(0.0, 0.0, 1.0, 1.0),
        num_shadows_limit=(1, 2),
        shadow_intensity_range=(0.1, 0.3),
        p=0.25,
    ),
    A.Perspective(scale=(0.02, 0.05), p=0.6),
    A.OneOf([
        A.GaussianBlur(blur_limit=(3, 3)),
        A.MotionBlur(blur_limit=3),
    ], p=0.2),
    A.ImageCompression(quality_range=(60, 95), p=0.5),
])


def apply_photo_augmentation(pil_img: Image.Image) -> Image.Image:
    """Apply photo-realistic augmentation to a generated document PIL image.

    Pipeline:
      1. Dark gradient edges (book / scanner shadow)
      2. Optional vignette
      3. Albumentations transforms (aging, noise, blur, compression)

    Returns a new RGB PIL Image.
    """
    img = np.array(pil_img.convert("RGB"))

    img = add_book_edges(img)

    if random.random() < 0.5:
        strength = random.uniform(0.2, 0.6)
        img = _add_vignette(img, strength)

    img = _TRANSFORM(image=img)["image"]

    return Image.fromarray(img)
