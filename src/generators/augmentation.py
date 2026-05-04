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

    Uses a freshly generated synthetic page as the back-side source so the
    ghost shows different content from the front.  Pass *back_image* to
    override with a specific pre-rendered page.
    """
    if blur_radius is None:
        blur_radius = random.uniform(1.5, 4.0)
    if opacity is None:
        opacity = random.uniform(0.40, 0.75)

    back = back_image if back_image is not None else _make_back_page(pil_img.size)
    back = back.convert('RGB').resize(pil_img.size)

    flipped_front = pil_img.convert('RGB').transpose(Image.FLIP_LEFT_RIGHT)
    combined = Image.blend(flipped_front, back, alpha=0.5)
    combined = combined.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    alpha = max(0.0, min(1.0, opacity * intensity))
    return Image.blend(pil_img.convert('RGB'), combined, alpha=alpha)


def _make_back_page(size: tuple) -> Image.Image:
    """Generate a synthetic cipher-like page to use as bleed-through source.

    Produces aged paper + horizontal strokes in real ink colours so the ghost
    looks like actual foreign content rather than a mirror of the front page.
    """
    w, h = size
    paper_palette = ['#FAFAF7', '#F7F2E8', '#F2EBD9', '#EDE0C4', '#E8D5B0', '#DFCA9C']
    img = Image.new('RGB', size, random.choice(paper_palette))

    # Paper grain
    arr = np.array(img, dtype=np.float32)
    arr += np.random.normal(0, 5, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    draw = ImageDraw.Draw(img)
    ink = random.choice([(44, 36, 22), (15, 10, 10), (80, 65, 45), (35, 30, 50)])

    x_start = random.randint(30, 60)
    y = random.randint(40, 70)
    line_h = random.randint(18, 28)

    while y < h - 50:
        if random.random() < 0.88:
            x = x_start
            while x < w - 40:
                seg = random.randint(6, 20)
                if random.random() < 0.82:
                    draw.line(
                        [(x, y), (x + seg, y + random.randint(-1, 1))],
                        fill=ink,
                        width=random.randint(1, 2),
                    )
                x += seg + random.randint(3, 8)
        y += line_h + random.randint(-2, 5)

    return img


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

    Shrinks and slightly rotates the document, adds a soft drop shadow,
    and composites it onto a plain background (white, grey, or dark).
    Bboxes are transformed to match the new geometry.
    """
    import math

    h, w = image.shape[:2]

    bg_presets = [
        (252, 252, 250),  # near-white
        (240, 238, 235),  # off-white
        (210, 208, 205),  # light grey
        (160, 158, 155),  # mid grey
        (70,  68,  65),   # dark grey
        (25,  23,  20),   # near-black
        (8,   8,   8),    # black
    ]
    bg_color = random.choice(bg_presets)

    scale = random.uniform(0.80, 0.93)
    new_w = int(w * scale)
    new_h = int(h * scale)

    pil_doc = Image.fromarray(image).resize((new_w, new_h), Image.LANCZOS)

    angle = random.uniform(-4.0, 4.0)
    # fillcolor fills the exposed corners of the expanded canvas with background
    pil_rot = pil_doc.rotate(angle, expand=True, resample=Image.BICUBIC,
                              fillcolor=bg_color)
    rw, rh = pil_rot.size

    bg = Image.new("RGB", (w, h), bg_color)

    max_ox = max(0, w - rw)
    max_oy = max(0, h - rh)
    ox = random.randint(0, max_ox) if max_ox > 0 else 0
    oy = random.randint(0, max_oy) if max_oy > 0 else 0

    # Soft drop shadow
    shadow_off = random.randint(6, 18)
    shadow_blur = random.randint(10, 24)
    shadow_alpha = random.randint(60, 130)
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).rectangle(
        [ox + shadow_off, oy + shadow_off,
         ox + rw + shadow_off - 1, oy + rh + shadow_off - 1],
        fill=(0, 0, 0, shadow_alpha),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
    bg = Image.alpha_composite(bg.convert("RGBA"), shadow_layer).convert("RGB")

    bg.paste(pil_rot, (ox, oy))
    result = np.array(bg)

    if bboxes is None:
        return result

    # Transform bboxes: scale → rotate (CCW by angle) → translate by (ox, oy)
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    cx, cy = new_w / 2.0, new_h / 2.0    # centre of scaled doc
    rcx, rcy = rw / 2.0, rh / 2.0        # centre of rotated canvas

    out_bboxes, out_labels = [], []
    for bbox, lbl in zip(bboxes, labels):
        bx, by, bw, bh = bbox
        bx_s, by_s, bw_s, bh_s = bx * scale, by * scale, bw * scale, bh * scale

        corners = [
            (bx_s,        by_s),
            (bx_s + bw_s, by_s),
            (bx_s + bw_s, by_s + bh_s),
            (bx_s,        by_s + bh_s),
        ]
        rotated = []
        for px, py in corners:
            dx, dy = px - cx, py - cy
            rotated.append((cos_a * dx - sin_a * dy + rcx + ox,
                             sin_a * dx + cos_a * dy + rcy + oy))

        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]
        nx = max(0.0, min(xs))
        ny = max(0.0, min(ys))
        nw = min(max(xs) - nx, w - nx)
        nh = min(max(ys) - ny, h - ny)

        if nw > 2 and nh > 2:
            out_bboxes.append([nx, ny, nw, nh])
            out_labels.append(lbl)

    return result, out_bboxes, out_labels


def apply_photo_augmentation(
    pil_img: Image.Image,
    bboxes=None,
    labels=None,
):
    """Apply photo-realistic augmentation to a generated document PIL image.

    Pipeline:
      1a. Book/scanner gradient edges  OR
      1b. Surface-capture (shrink + rotate onto plain background) — mutually exclusive, ~40% surface
      2. Optional vignette
      3. Albumentations transforms (aging, noise, blur, perspective, compression)
      4. Optional bleed-through (ink ghost from reverse side)

    If *bboxes* is provided (list of [x, y, w, h] in COCO format) spatial
    transforms are applied to the bboxes too.  *labels* is a parallel list
    of identifiers so the caller can map surviving bboxes back to annotations.

    Returns:
        Image.Image                       — when bboxes is None
        (Image.Image, bboxes, labels)     — otherwise
    """
    img = np.array(pil_img.convert("RGB"))

    use_surface = random.random() < 0.40

    if use_surface:
        bboxes_in = list(bboxes) if bboxes is not None else []
        labels_in = list(labels) if labels is not None else []
        if bboxes is not None:
            img, bboxes_in, labels_in = add_surface_capture(img, bboxes_in, labels_in)
        else:
            img = add_surface_capture(img)
    else:
        img = add_book_edges(img)
        bboxes_in = list(bboxes) if bboxes is not None else []
        labels_in = list(labels) if labels is not None else []

    if random.random() < 0.40:
        img = _add_vignette(img, random.uniform(0.16, 0.50))

    result = _TRANSFORM(image=img, bboxes=bboxes_in, labels=labels_in)
    out_img = Image.fromarray(result["image"])
    out_bboxes = list(result["bboxes"])
    out_labels = list(result["labels"])

    if random.random() < 0.50:
        out_img = apply_bleed_through(out_img)

    if bboxes is None:
        return out_img
    return out_img, out_bboxes, out_labels
