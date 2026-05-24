"""
Post-generation augmentation to simulate photographed/scanned document appearance.
Path: src/generators/augmentation.py
"""

import random
from dataclasses import dataclass
from typing import Optional, Dict

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import albumentations as A


@dataclass
class AugmentationState:
    """All random choices from one augmentation pass.

    Pass an existing AugmentationState to apply_photo_augmentation to replay
    identical effects on a new render. Reset to None only on explicit Generate
    Preview so that every auto-regenerate looks the same as the previous one.
    """
    # Bleed-through
    apply_bleed: bool = False
    bleed_blur: float = 2.0
    bleed_opacity: float = 0.5

    # Spatial effect: "surface" | "book_edges" | "none"
    spatial_mode: str = "none"

    # Surface-capture params (used when spatial_mode == "surface")
    surface_bg_color: tuple = (252, 252, 250)
    surface_shadow_off: int = 12
    surface_shadow_blur: int = 16
    surface_shadow_alpha: int = 90
    surface_replay: Optional[Dict] = None   # ReplayCompose replay data

    # Book-edge params (used when spatial_mode == "book_edges"; None = edge not applied)
    book_edge_fill: float = 0.0
    book_left_w: Optional[int] = None
    book_right_w: Optional[int] = None
    book_top_w: Optional[int] = None
    book_bottom_w: Optional[int] = None

    # Vignette
    apply_vignette: bool = False
    vignette_strength: float = 0.15

    # Albumentations pipeline replay data
    pipeline_replay: Optional[Dict] = None


# ---------------------------------------------------------------------------
# Bleed-through
# ---------------------------------------------------------------------------

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
        opacity = random.uniform(0.40, 0.60)

    if back_image is not None:
        source = back_image.convert('RGB').resize(pil_img.size)
    else:
        source = pil_img.convert('RGB').transpose(Image.FLIP_LEFT_RIGHT)

    combined = source.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    alpha = max(0.0, min(1.0, opacity * intensity))
    return Image.blend(pil_img.convert('RGB'), combined, alpha=alpha)


# ---------------------------------------------------------------------------
# Book edges
# ---------------------------------------------------------------------------

def _apply_book_edges(image: np.ndarray, state: AugmentationState) -> np.ndarray:
    """Apply book-edge gradients using parameters already stored in state."""
    h, w = image.shape[:2]
    arr = image.astype(np.float32)
    ef = state.book_edge_fill

    def _grad(region, grad_1d, axis):
        shape = (1, len(grad_1d), 1) if axis == 1 else (len(grad_1d), 1, 1)
        g = grad_1d.reshape(shape)
        return (region * g + ef * (1.0 - g)).astype(np.uint8)

    if state.book_left_w:
        ew = min(state.book_left_w, w)
        arr[:, :ew] = _grad(arr[:, :ew], np.linspace(0.0, 1.0, ew), axis=1)
    if state.book_right_w:
        ew = min(state.book_right_w, w)
        arr[:, -ew:] = _grad(arr[:, -ew:], np.linspace(1.0, 0.0, ew), axis=1)
    if state.book_top_w:
        ew = min(state.book_top_w, h)
        arr[:ew, :] = _grad(arr[:ew, :], np.linspace(0.0, 1.0, ew), axis=0)
    if state.book_bottom_w:
        ew = min(state.book_bottom_w, h)
        arr[-ew:, :] = _grad(arr[-ew:, :], np.linspace(1.0, 0.0, ew), axis=0)

    return arr.astype(np.uint8)


def add_book_edges(image: np.ndarray) -> np.ndarray:
    """Public backward-compatible wrapper: choose random params, apply, return image."""
    state = AugmentationState()
    state.spatial_mode = "book_edges"
    state.book_edge_fill = 0.0 if random.random() < 0.5 else 255.0
    h, w = image.shape[:2]
    state.book_left_w  = min(random.randint(20, 80), w) if random.random() < 0.30 else None
    state.book_right_w = min(random.randint(20, 80), w) if random.random() < 0.15 else None
    state.book_top_w   = min(random.randint(20, 80), h) if random.random() < 0.20 else None
    state.book_bottom_w= min(random.randint(20, 80), h) if random.random() < 0.15 else None
    return _apply_book_edges(image, state)


# ---------------------------------------------------------------------------
# Vignette
# ---------------------------------------------------------------------------

def _add_vignette(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """Darken edges radially to simulate lens vignetting."""
    h, w = image.shape[:2]
    y = np.linspace(-1.0, 1.0, h)
    x = np.linspace(-1.0, 1.0, w)
    xv, yv = np.meshgrid(x, y)
    radius = np.sqrt(xv ** 2 + yv ** 2)
    attenuation = np.clip(1.0 - strength * (radius / radius.max()), 0.0, 1.0)
    return (image * attenuation[:, :, None]).astype(np.uint8)


# ---------------------------------------------------------------------------
# Surface capture
# ---------------------------------------------------------------------------

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
_SENTINEL = np.array([255, 0, 255], dtype=np.uint8)

_BBOX_PARAMS = A.BboxParams(
    format="coco",
    label_fields=["labels"],
    clip=True,
    filter_invalid_bboxes=True,
    min_area=4.0,
    min_visibility=0.75,
)

_SURFACE_AFFINE = A.ReplayCompose(
    [A.Affine(
        scale=(0.80, 0.93),
        rotate=(-2.0, 2.0),
        translate_percent={"x": (-0.03, 0.03), "y": (-0.03, 0.03)},
        fill=(255, 0, 255),
        fit_output=False,
        p=1.0,
    )],
    bbox_params=_BBOX_PARAMS,
)


def _run_surface_capture(
    image: np.ndarray,
    bboxes_in: list,
    labels_in: list,
    state: AugmentationState,
):
    """Apply (or replay) the surface-capture affine transform using state."""
    h, w = image.shape[:2]

    if state.surface_replay is not None:
        result = _SURFACE_AFFINE.replay(
            state.surface_replay, image=image, bboxes=bboxes_in, labels=labels_in,
        )
    else:
        result = _SURFACE_AFFINE(image=image, bboxes=bboxes_in, labels=labels_in)
        state.surface_replay = result["replay"]

    transformed = result["image"].copy()
    bg_mask = np.all(transformed == _SENTINEL, axis=2)

    bg = np.full((h, w, 3), state.surface_bg_color, dtype=np.uint8)
    doc_pix = ~bg_mask
    if doc_pix.any():
        rows = np.where(doc_pix.any(axis=1))[0]
        cols = np.where(doc_pix.any(axis=0))[0]
        x1, x2 = int(cols[0]), int(cols[-1])
        y1, y2 = int(rows[0]), int(rows[-1])

        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow_layer).rectangle(
            [x1 + state.surface_shadow_off, y1 + state.surface_shadow_off,
             x2 + state.surface_shadow_off, y2 + state.surface_shadow_off],
            fill=(0, 0, 0, state.surface_shadow_alpha),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(state.surface_shadow_blur))
        bg = np.array(
            Image.alpha_composite(
                Image.fromarray(bg).convert("RGBA"), shadow_layer
            ).convert("RGB")
        )

    transformed[bg_mask] = bg[bg_mask]
    return transformed, list(result["bboxes"]), list(result["labels"])


def add_surface_capture(image: np.ndarray, bboxes=None, labels=None):
    """Public backward-compatible wrapper: choose random params and apply."""
    state = AugmentationState()
    state.spatial_mode = "surface"
    state.surface_bg_color = random.choice(_BG_PRESETS)
    state.surface_shadow_off = random.randint(6, 18)
    state.surface_shadow_blur = random.randint(10, 24)
    state.surface_shadow_alpha = random.randint(60, 130)

    bboxes_in = list(bboxes) if bboxes is not None else []
    labels_in = list(labels) if labels is not None else []
    img_out, bboxes_out, labels_out = _run_surface_capture(image, bboxes_in, labels_in, state)

    if bboxes is None:
        return img_out
    return img_out, bboxes_out, labels_out


# ---------------------------------------------------------------------------
# Albumentations pipeline
# ---------------------------------------------------------------------------

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

_TRANSFORM = A.ReplayCompose(
    _PIPELINE,
    bbox_params=_BBOX_PARAMS,
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_photo_augmentation(
    pil_img: Image.Image,
    bboxes=None,
    labels=None,
    back_image: Image.Image | None = None,
    bleed_through: str = "random",   # "always" | "never" | "random"
    book_edges: str = "random",      # "always" | "never" | "random"
    other: str = "random",           # "always" | "never" | "random"
    state: AugmentationState | None = None,
):
    """Apply photo-realistic augmentation to a generated document PIL image.

    Pass a previously returned AugmentationState as *state* to replay the
    same random choices (perspective angle, colour values, edge widths, etc.)
    on a freshly rendered document.  Omit (or pass None) for a fresh random
    augmentation.

    Returns
    -------
    When bboxes is None : (pil_image, AugmentationState)
    When bboxes given   : (pil_image, bboxes, labels, AugmentationState)
    """
    replay_mode = state is not None
    if not replay_mode:
        state = AugmentationState()

    # ── 1. Bleed-through ────────────────────────────────────────────────────
    if replay_mode:
        if state.apply_bleed and bleed_through != "never":
            pil_img = apply_bleed_through(
                pil_img,
                blur_radius=state.bleed_blur,
                opacity=state.bleed_opacity,
                back_image=back_image,
            )
    else:
        do_bleed = (
            bleed_through == "always"
            or (bleed_through == "random" and random.random() < 0.50)
        )
        if do_bleed:
            blur   = random.uniform(1.5, 4.0)
            opac   = random.uniform(0.40, 0.60)
            pil_img = apply_bleed_through(pil_img, blur_radius=blur, opacity=opac, back_image=back_image)
            state.apply_bleed    = True
            state.bleed_blur     = blur
            state.bleed_opacity  = opac

    img = np.array(pil_img.convert("RGB"))
    bboxes_in = list(bboxes) if bboxes is not None else []
    labels_in = list(labels) if labels is not None else []

    # ── 2. Surface capture OR book edges ────────────────────────────────────
    if replay_mode:
        if state.spatial_mode == "surface" and other != "never":
            img, bboxes_in, labels_in = _run_surface_capture(img, bboxes_in, labels_in, state)
        elif state.spatial_mode == "book_edges" and book_edges != "never":
            img = _apply_book_edges(img, state)
    else:
        if other != "never":
            use_surface = random.random() < 0.40
            if use_surface:
                state.spatial_mode         = "surface"
                state.surface_bg_color     = random.choice(_BG_PRESETS)
                state.surface_shadow_off   = random.randint(6, 18)
                state.surface_shadow_blur  = random.randint(10, 24)
                state.surface_shadow_alpha = random.randint(60, 130)
                img, bboxes_in, labels_in  = _run_surface_capture(img, bboxes_in, labels_in, state)
            elif book_edges != "never":
                state.spatial_mode   = "book_edges"
                h, w = img.shape[:2]
                state.book_edge_fill = 0.0 if random.random() < 0.5 else 255.0
                state.book_left_w    = min(random.randint(20, 80), w) if random.random() < 0.30 else None
                state.book_right_w   = min(random.randint(20, 80), w) if random.random() < 0.15 else None
                state.book_top_w     = min(random.randint(20, 80), h) if random.random() < 0.20 else None
                state.book_bottom_w  = min(random.randint(20, 80), h) if random.random() < 0.15 else None
                img = _apply_book_edges(img, state)
        elif book_edges != "never":
            state.spatial_mode   = "book_edges"
            h, w = img.shape[:2]
            state.book_edge_fill = 0.0 if random.random() < 0.5 else 255.0
            state.book_left_w    = min(random.randint(20, 80), w) if random.random() < 0.30 else None
            state.book_right_w   = min(random.randint(20, 80), w) if random.random() < 0.15 else None
            state.book_top_w     = min(random.randint(20, 80), h) if random.random() < 0.20 else None
            state.book_bottom_w  = min(random.randint(20, 80), h) if random.random() < 0.15 else None
            img = _apply_book_edges(img, state)

    # ── 3. Vignette ─────────────────────────────────────────────────────────
    if replay_mode:
        if state.apply_vignette and other != "never":
            img = _add_vignette(img, state.vignette_strength)
    else:
        do_vignette = other == "always" or (other == "random" and random.random() < 0.40)
        if do_vignette:
            strength = random.uniform(0.08, 0.25)
            img = _add_vignette(img, strength)
            state.apply_vignette    = True
            state.vignette_strength = strength

    # ── 4. Albumentations pipeline ───────────────────────────────────────────
    if other != "never":
        if replay_mode and state.pipeline_replay is not None:
            result = _TRANSFORM.replay(
                state.pipeline_replay, image=img, bboxes=bboxes_in, labels=labels_in,
            )
        else:
            result = _TRANSFORM(image=img, bboxes=bboxes_in, labels=labels_in)
            state.pipeline_replay = result["replay"]
        out_img    = Image.fromarray(result["image"])
        out_bboxes = list(result["bboxes"])
        out_labels = list(result["labels"])
    else:
        out_img    = Image.fromarray(img)
        out_bboxes = bboxes_in
        out_labels = labels_in

    if bboxes is None:
        return out_img, state
    return out_img, out_bboxes, out_labels, state
