"""
Post-generation augmentation to simulate photographed/scanned document appearance.
Path: src/generators/augmentation.py
"""

import random

import numpy as np
from PIL import Image
import albumentations as A


def add_book_edges(image: np.ndarray) -> np.ndarray:
    """Add gradient edges to mimic a book/scanner capture.

    Randomly picks black or white for the whole image — never mixes both.
    Each of the four edges independently decides whether to apply.
    """
    h, w = image.shape[:2]
    arr = image.astype(np.float32)

    # Choose edge colour once for this image: black (0) or white (255)
    edge_fill = 0.0 if random.random() < 0.5 else 255.0

    def _apply(region, grad_1d, axis):
        # grad_1d goes 0→1 meaning "how much of the original to keep"
        # at 0: pure edge_fill; at 1: pure original
        shape = (1, len(grad_1d), 1) if axis == 1 else (len(grad_1d), 1, 1)
        g = grad_1d.reshape(shape)
        return (region * g + edge_fill * (1.0 - g)).astype(np.uint8)

    if random.random() < 0.3:
        ew = min(random.randint(20, 80), w)
        arr[:, :ew] = _apply(arr[:, :ew], np.linspace(0.0, 1.0, ew), axis=1)

    if random.random() < 0.15:
        ew = min(random.randint(20, 80), w)
        arr[:, -ew:] = _apply(arr[:, -ew:], np.linspace(1.0, 0.0, ew), axis=1)

    if random.random() < 0.2:
        ew = min(random.randint(20, 80), h)
        arr[:ew, :] = _apply(arr[:ew, :], np.linspace(0.0, 1.0, ew), axis=0)

    if random.random() < 0.15:
        ew = min(random.randint(20, 80), h)
        arr[-ew:, :] = _apply(arr[-ew:, :], np.linspace(1.0, 0.0, ew), axis=0)

    return arr.astype(np.uint8)


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


_PIPELINE = [
    A.ToSepia(p=0.40),
    A.ColorJitter(
        brightness=(0.75, 1.25),
        contrast=(0.75, 1.25),
        saturation=(0.83, 1.17),
        hue=(-0.04, 0.04),
        p=0.65,
    ),
    A.GaussNoise(std_range=(0.03, 0.12), p=0.65),
    A.ISONoise(color_shift=(0.01, 0.04), intensity=(0.08, 0.33), p=0.40),
    A.RandomShadow(
        shadow_roi=(0.0, 0.0, 1.0, 1.0),
        num_shadows_limit=(1, 2),
        shadow_intensity_range=(0.08, 0.25),
        p=0.20,
    ),
    A.Perspective(scale=(0.016, 0.04), p=0.50),
    A.OneOf([
        A.GaussianBlur(blur_limit=(3, 3)),
        A.MotionBlur(blur_limit=3),
    ], p=0.16),
    A.ImageCompression(quality_range=(68, 96), p=0.40),
]

# Bbox-aware transform: clips bboxes to image bounds, drops any that
# end up smaller than 4 px² or with <30 % of their area still visible.
_TRANSFORM = A.Compose(
    _PIPELINE,
    bbox_params=A.BboxParams(
        format="coco",
        label_fields=["labels"],
        clip=True,
        filter_invalid_bboxes=True,
        min_area=4.0,
        min_visibility=0.3,
    ),
)


def apply_photo_augmentation(
    pil_img: Image.Image,
    bboxes=None,
    labels=None,
):
    """Apply photo-realistic augmentation to a generated document PIL image.

    Pipeline:
      1. Dark gradient edges (book / scanner shadow)
      2. Optional vignette
      3. Albumentations transforms (aging, noise, blur, perspective, compression)

    If *bboxes* is provided (list of [x, y, w, h] in COCO format) the
    spatial transforms (Perspective) are applied to the bboxes too.
    *labels* must be a parallel list of identifiers so the caller can map
    surviving bboxes back to their annotations after some are dropped.

    Returns:
        Image.Image                       — when bboxes is None
        (Image.Image, bboxes, labels)     — otherwise
    """
    img = np.array(pil_img.convert("RGB"))

    img = add_book_edges(img)

    if random.random() < 0.40:
        strength = random.uniform(0.16, 0.50)
        img = _add_vignette(img, strength)

    bboxes_in = list(bboxes) if bboxes is not None else []
    labels_in = list(labels) if labels is not None else []

    result = _TRANSFORM(image=img, bboxes=bboxes_in, labels=labels_in)
    out_img = Image.fromarray(result["image"])

    if bboxes is None:
        return out_img
    return out_img, result["bboxes"], result["labels"]
