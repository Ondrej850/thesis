"""
Post-generation augmentation to simulate photographed/scanned document appearance.
Path: src/generators/augmentation.py
"""

import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import albumentations as A


def apply_bleed_through(
    pil_img: Image.Image,
    intensity: float = 1.0,
    blur_radius: float | None = None,
    opacity: float | None = None,
    back_image: Image.Image | None = None,
) -> Image.Image:
    """Simulate ink seen through translucent paper from the reverse side.

    For normal images (no back_image) the front page itself is flipped to
    produce the ghost.  Pass a pre-rendered, pre-flipped page as back_image
    to use real content instead (used by background image generation).
    """
    if blur_radius is None:
        blur_radius = random.uniform(1.5, 4.0)
    if opacity is None:
        opacity = random.uniform(0.40, 0.75)

    if back_image is not None:
        source = back_image.convert('RGB').resize(pil_img.size)
    else:
        source = pil_img.convert('RGB').transpose(Image.FLIP_LEFT_RIGHT)

    combined = source.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    alpha = max(0.0, min(1.0, opacity * intensity))
    return Image.blend(pil_img.convert('RGB'), combined, alpha=alpha)


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


_BG_PRESETS = [
    (252, 252, 250),  # near-white
    (240, 238, 235),  # off-white
    (210, 208, 205),  # light grey
    (160, 158, 155),  # mid grey
    (70,  68,  65),   # dark grey
    (25,  23,  20),   # near-black
    (8,   8,   8),    # black
]

# Magenta sentinel: fills areas exposed by the affine transform.
# Aged-paper documents never produce exact (255, 0, 255) so the mask is reliable.
_SENTINEL = np.array([255, 0, 255], dtype=np.uint8)

_SURFACE_AFFINE = A.Compose(
    [A.Affine(
        scale=(0.80, 0.93),
        rotate=(-2.0, 2.0),
        translate_percent={"x": (-0.03, 0.03), "y": (-0.03, 0.03)},
        fill=(255, 0, 255),
        fit_output=False,
        p=1.0,
    )],
    bbox_params=A.BboxParams(
        format="coco",
        label_fields=["labels"],
        clip=True,
        filter_invalid_bboxes=True,
        min_area=4.0,
        min_visibility=0.75,
    ),
)

_PIPELINE = [
    A.ToSepia(p=0.40),
    A.ColorJitter(
        brightness=(0.75, 1.25),
        contrast=(0.75, 1.25),
        saturation=(0.83, 1.17),
        hue=(-0.04, 0.04),
        p=0.65,
    ),
    A.GaussNoise(std_range=(0.01, 0.04), p=0.50),
    A.ISONoise(color_shift=(0.01, 0.03), intensity=(0.03, 0.10), p=0.30),
    A.RandomShadow(
        shadow_roi=(0.0, 0.0, 1.0, 1.0),
        num_shadows_limit=(1, 2),
        shadow_intensity_range=(0.05, 0.15),
        p=0.15,
    ),
    A.Perspective(scale=(0.004, 0.02), p=0.50),
    A.OneOf([
        A.GaussianBlur(blur_limit=(3, 3)),
        A.MotionBlur(blur_limit=3),
    ], p=0.04),
    A.ImageCompression(quality_range=(82, 97), p=0.40),
]

# Bbox-aware transform: clips bboxes to image bounds, drops any that
# end up smaller than 4 px² or with <75 % of their area still visible.
_TRANSFORM = A.Compose(
    _PIPELINE,
    bbox_params=A.BboxParams(
        format="coco",
        label_fields=["labels"],
        clip=True,
        filter_invalid_bboxes=True,
        min_area=4.0,
        min_visibility=0.75,
    ),
)


def add_surface_capture(image: np.ndarray, bboxes=None, labels=None):
    """Simulate a document photographed lying on a surface.

    Uses albumentations Affine (via _SURFACE_AFFINE) for all geometric
    transforms so bbox updating is handled consistently with _TRANSFORM.
    A magenta sentinel fills the exposed border; those pixels are then
    replaced with a plain background + soft drop shadow.
    """
    h, w = image.shape[:2]
    bg_color = random.choice(_BG_PRESETS)

    bboxes_in = list(bboxes) if bboxes is not None else []
    labels_in = list(labels) if labels is not None else []

    result = _SURFACE_AFFINE(image=image, bboxes=bboxes_in, labels=labels_in)
    transformed = result["image"].copy()

    # Pixels the affine filled with the sentinel → these are the background areas
    bg_mask = np.all(transformed == _SENTINEL, axis=2)

    # Build background canvas + drop shadow
    bg = np.full((h, w, 3), bg_color, dtype=np.uint8)
    doc_pix = ~bg_mask
    if doc_pix.any():
        rows = np.where(doc_pix.any(axis=1))[0]
        cols = np.where(doc_pix.any(axis=0))[0]
        x1, x2 = int(cols[0]), int(cols[-1])
        y1, y2 = int(rows[0]), int(rows[-1])

        shadow_off  = random.randint(6, 18)
        shadow_blur = random.randint(10, 24)
        shadow_a    = random.randint(60, 130)
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow_layer).rectangle(
            [x1 + shadow_off, y1 + shadow_off, x2 + shadow_off, y2 + shadow_off],
            fill=(0, 0, 0, shadow_a),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
        bg = np.array(
            Image.alpha_composite(
                Image.fromarray(bg).convert("RGBA"), shadow_layer
            ).convert("RGB")
        )

    # Replace sentinel pixels with background (shadow included where applicable)
    transformed[bg_mask] = bg[bg_mask]

    if bboxes is None:
        return transformed
    return transformed, list(result["bboxes"]), list(result["labels"])


def apply_photo_augmentation(
    pil_img: Image.Image,
    bboxes=None,
    labels=None,
    back_image: Image.Image | None = None,
    bleed_through: str = "random",   # "always", "never", "random"
    book_edges: str = "random",      # "always", "never", "random"
    other: str = "random",           # "always", "never", "random"
):
    """Apply photo-realistic augmentation to a generated document PIL image.

    bleed_through — "always": force bleed-through; "random": 50% chance; "never": skip
    book_edges    — "always"/"random": apply when surface capture does not trigger; "never": skip
    other         — gates surface capture, vignette, and albumentations pipeline
                    "always": vignette always + albumentations always + 40% surface
                    "random": 40% vignette + albumentations always + 40% surface
                    "never":  skip all three
    """
    # 1. Bleed-through
    if bleed_through == "always" or (bleed_through == "random" and random.random() < 0.50):
        pil_img = apply_bleed_through(pil_img, back_image=back_image)

    img = np.array(pil_img.convert("RGB"))
    bboxes_in = list(bboxes) if bboxes is not None else []
    labels_in = list(labels) if labels is not None else []

    # 2. Surface capture (part of "other") OR book edges — mutually exclusive
    if other != "never":
        use_surface = random.random() < 0.40
        if use_surface:
            if bboxes is not None:
                img, bboxes_in, labels_in = add_surface_capture(img, bboxes_in, labels_in)
            else:
                img = add_surface_capture(img)
        elif book_edges != "never":
            img = add_book_edges(img)
    elif book_edges != "never":
        img = add_book_edges(img)

    # 3. Vignette (part of "other")
    if other == "always" or (other == "random" and random.random() < 0.40):
        img = _add_vignette(img, random.uniform(0.08, 0.25))

    # 4. Albumentations pipeline (part of "other")
    if other != "never":
        result = _TRANSFORM(image=img, bboxes=bboxes_in, labels=labels_in)
        out_img = Image.fromarray(result["image"])
        out_bboxes = list(result["bboxes"])
        out_labels = list(result["labels"])
    else:
        out_img = Image.fromarray(img)
        out_bboxes = bboxes_in
        out_labels = labels_in

    if bboxes is None:
        return out_img
    return out_img, out_bboxes, out_labels
