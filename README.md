# Historical Cipher Generator

A Python desktop application for generating synthetic 15th-century cipher documents with automatic bounding-box annotations in COCO and YOLO formats. Designed for creating ML training datasets of historical cryptographic manuscripts.

## Requirements

- Python **3.10 or newer**
- No database or external service required — everything runs locally

## Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd thesis

# 2. Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
python main.py
```

The GUI opens immediately — no configuration needed.

## Features

### Document generation
- Aged paper with configurable defects: stains, ink drops, holes, tears, grain, wrinkles
- Six ink colour presets (dark brown, black, faded brown, iron gall, sepia, charcoal)
- Handwritten-style fonts from the `fonts/` directory (automatically discovered)
- Per-character visual variations: rotation, size jitter, position offset

### Cipher types
- **Substitution** — single-letter substitution table
- **Bigram / Trigram** — two- and three-letter group substitution
- **Dictionary** — word/phrase-level encoding
- **Nulls** — decorative null symbols mixed into the cipher

### Table codes
- Homophonic code tables with up to 3 independent tables per document
- Configurable symbol count, code count, column spacing, and row spacing
- Optional common-code boosting for realistic frequency distributions

### Photo-realistic augmentation
- Perspective distortion, sepia tone, colour jitter, Gaussian/ISO noise
- Bleed-through simulation (ink visible from the reverse side)
- Book-edge gradients, vignetting, motion blur, JPEG compression artefacts
- Surface-capture mode: simulates a document photographed on a desk

### Annotations
- Live bounding-box tracking through all augmentation transforms
- Export to **COCO JSON** (`annotations.json`)
- Export to **YOLO TXT** (one `.txt` per image)
- Annotation categories: `element`, `pair`, `section`

### Batch dataset generation
- Configure parameter *ranges* (min/max) for every setting
- Generate N images with randomly sampled configurations
- Single merged annotation file covering the entire dataset

## Project Structure

```
thesis/
├── main.py                   # Entry point
├── requirements.txt
├── fonts/handwritten/        # TTF font files (auto-discovered)
└── src/
    ├── constants.py
    ├── annotations/
    │   └── coco_manager.py   # COCO/YOLO annotation export
    ├── database/
    │   ├── database_manager.py   # In-memory cipher word lists
    │   └── font_manager.py       # Font discovery
    ├── generators/
    │   ├── image_generator.py    # Core document renderer
    │   ├── augmentation.py       # Photo-realistic augmentation pipeline
    │   ├── text_variation.py     # Per-character variation engine
    │   ├── table_codes_generator.py
    │   └── dataset_generator.py  # Batch generation orchestrator
    ├── gui/
    │   ├── main_window.py        # Main GUI window
    │   └── dataset_dialog.py     # Batch generation dialog
    └── models/
        ├── paper_config.py
        ├── font_config.py
        ├── table_codes_config.py
        ├── dataset_config.py
        └── coco_annotation.py
```

## Dependencies

| Package | Purpose |
|---|---|
| `Pillow` | Image generation and manipulation |
| `numpy` | Array operations for augmentation |
| `albumentations` | Augmentation pipeline with bbox tracking |
