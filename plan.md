# Plan: "Generate Annotated Dataset" Feature

## Overview

Add a **"Generate Annotated Dataset"** button to the GUI that opens a new dialog window. In this dialog, the user configures **ranges** (min/max) or **option sets** for every existing setting. The generator then produces N images, each with randomly sampled parameters from those ranges, and exports all images + a single merged COCO/YOLO annotation file.

---

## Architecture

### New Files
1. **`src/models/dataset_config.py`** — Dataclass holding all range definitions for dataset generation
2. **`src/gui/dataset_dialog.py`** — Tkinter Toplevel dialog for configuring dataset ranges
3. **`src/generators/dataset_generator.py`** — Orchestrator that loops N times, samples random configs, calls existing generators, and merges annotations

### Modified Files
4. **`src/gui/main_window.py`** — Add "Generate Annotated Dataset" button (next to existing action buttons)

---

## Step-by-step Implementation

### Step 1: Create `DatasetConfig` model (`src/models/dataset_config.py`)

A dataclass that stores ranges/options for every parameter:

```python
@dataclass
class DatasetConfig:
    num_images: int = 10
    output_dir: str = ""          # User picks via folder dialog
    annotation_format: str = "both"  # "coco", "yolo", or "both"

    # Paper
    aging_level_range: Tuple[int, int] = (20, 80)       # min, max
    paper_types: List[str] = field(default_factory=list) # subset to pick from
    defects_mode: str = "random"   # "random" (each defect 50/50), "all", "none", "fixed"
    defects_fixed: List[str] = field(default_factory=list)

    # Column Pairs
    include_column_pairs: str = "random"  # "always", "never", "random"
    cipher_types: List[str] = field(default_factory=lambda: ["substitution"])
    key_types: List[str] = field(default_factory=lambda: ["number"])
    num_entries_range: Tuple[int, int] = (10, 50)
    cp_font_size_range: Tuple[int, int] = (10, 20)

    # Font
    fonts: List[str] = field(default_factory=lambda: ["Random"])
    variation_levels: List[str] = field(default_factory=lambda: ["low", "medium", "high"])
    col_separators: List[str] = field(default_factory=lambda: ["none", "line"])
    key_separators: List[str] = field(default_factory=lambda: ["dots", "dashes"])
    dash_count_range: Tuple[int, int] = (1, 5)
    spacing_range: Tuple[int, int] = (5, 12)

    # Table Codes
    include_table_codes: str = "random"  # "always", "never", "random"
    table_content_types: List[str] = field(default_factory=lambda: ["alphabet"])
    table_num_codes_range: Tuple[int, int] = (1, 5)
    table_common_boost: str = "random"   # "always", "never", "random"
    table_common_codes_range: Tuple[int, int] = (2, 8)
    table_col_spacing_range: Tuple[int, int] = (5, 20)
    table_vertical_lines: str = "random"
    table_font_size_range: Tuple[int, int] = (10, 20)

    # Layout
    start_x_range: Tuple[int, int] = (30, 80)
    start_y_range: Tuple[int, int] = (30, 80)
    right_margin_range: Tuple[int, int] = (30, 80)
    bottom_margin_range: Tuple[int, int] = (30, 80)
    ink_colors: List[str] = field(default_factory=lambda: ["dark_brown", "black", "faded_brown"])
```

Add a `sample()` method that returns a concrete set of parameters (one random pick from each range/list) as a dict or named tuple.

---

### Step 2: Create Dataset Dialog (`src/gui/dataset_dialog.py`)

A `tk.Toplevel` window with scrollable content, structured similarly to the main window's collapsible sections:

**Layout:**
- **Header**: "Dataset Generation Settings"
- **General section**: Number of images (spinbox), Output directory (browse button), Annotation format (dropdown)
- **Paper section**: Aging range (two sliders or two spinboxes for min/max), Paper type checkboxes (multi-select), Defect mode dropdown
- **Column Pairs section**: Include mode (always/never/random), Cipher type checkboxes, Key type checkboxes, Entry count range, Font size range
- **Font section**: Font checkboxes (multi-select from available), Variation levels checkboxes, Separator options checkboxes, Dash count range, Spacing range
- **Table Codes section**: Include mode, Content type checkboxes, Codes range, Boost mode, Column spacing range, Font size range
- **Layout & Ink section**: Start X/Y ranges, Margin ranges, Ink color checkboxes
- **Bottom buttons**: "Generate Dataset" (starts generation), "Cancel"

**UI pattern for ranges**: Two spinboxes side-by-side labeled "Min" and "Max"
**UI pattern for option sets**: Checkboxes for each option (at least one must be selected)
**UI pattern for toggle features**: Dropdown with "Always / Never / Random"

When "Generate Dataset" is clicked → build a `DatasetConfig`, pass to `DatasetGenerator`, show a progress dialog.

---

### Step 3: Create Dataset Generator (`src/generators/dataset_generator.py`)

```python
class DatasetGenerator:
    def __init__(self, dataset_config: DatasetConfig, db_manager, font_manager):
        ...

    def generate(self, progress_callback=None):
        """Generate all images. Calls progress_callback(current, total) for UI updates."""
        coco_manager = COCOAnnotationManager()

        for i in range(self.config.num_images):
            # 1. Sample random parameters from ranges
            params = self.config.sample()

            # 2. Build PaperConfig, FontConfig, TableCodesConfig from sampled params
            paper_config = PaperConfig(...)
            font_config = FontConfig(...)

            # 3. Create generator, generate paper background
            generator = CipherImageGenerator(paper_config, font_config, params.variation_level)
            img = generator.create_aged_paper()

            # 4. Get font path
            font_path = self._get_font_path(params.font_name)

            # 5. Register image in shared COCO manager
            filename = f"image_{i:04d}.png"
            image_id = coco_manager.add_image(filename, 800, 1100)

            # 6. Render table codes if included
            current_y = params.start_y
            if params.include_table_codes:
                table_config = TableCodesConfig(...)
                current_y = generator.render_table_codes(img, table_config, ...)

            # 7. Render column pairs if included
            if params.include_column_pairs:
                entries = self._get_cipher_entries(params.cipher_type, params.key_type, params.num_entries)
                current_y = generator.render_cipher_text(img, entries, ...)

            # 8. Collect annotations into shared manager
            # (use generator's internal annotation data)

            # 9. Save image
            img.save(os.path.join(self.config.output_dir, filename))

            # 10. Progress callback
            if progress_callback:
                progress_callback(i + 1, self.config.num_images)

        # 11. Export merged annotations
        if self.config.annotation_format in ("coco", "both"):
            coco_manager.export_coco(os.path.join(self.config.output_dir, "annotations.json"))
        if self.config.annotation_format in ("yolo", "both"):
            # Export YOLO for each image
            for image_info in coco_manager.images:
                coco_manager.export_yolo(self.config.output_dir, image_info["file_name"])
```

Key design decisions:
- **Fresh cipher entries per image** — each image gets new random entries from the database (no caching across images in the batch)
- **Fresh font per image** — if font list includes multiple fonts, pick randomly each time
- **Shared COCO manager** — one annotations.json covering all images (standard COCO format supports this)
- **YOLO per-image** — one .txt file per image (YOLO standard)
- **Threading** — run generation in a background thread, update progress bar via callback

---

### Step 4: Add button to Main Window (`src/gui/main_window.py`)

In the existing button area (bottom of the left panel), add:

```python
ttk.Button(button_frame, text="Generate Annotated Dataset", command=self.open_dataset_dialog)
```

The `open_dataset_dialog` method creates and shows the `DatasetDialog`.

---

### Step 5: Progress Dialog

Simple `tk.Toplevel` with:
- Progress bar (`ttk.Progressbar`)
- Label: "Generating image 3/100..."
- Cancel button (sets a flag checked by the generator loop)

This can live inside `dataset_dialog.py` as a small class or be part of the dialog itself.

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `src/models/dataset_config.py` | **NEW** | DatasetConfig dataclass with ranges + `sample()` method |
| `src/gui/dataset_dialog.py` | **NEW** | Tkinter dialog for configuring dataset ranges + progress |
| `src/generators/dataset_generator.py` | **NEW** | Orchestrator: loops, samples, generates, merges annotations |
| `src/gui/main_window.py` | **MODIFY** | Add "Generate Annotated Dataset" button + handler |

No changes to existing generator/model/annotation code — the new feature composes existing functionality.
