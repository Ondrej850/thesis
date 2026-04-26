
"""
Dataset generation dialog.
Lets the user configure randomisation ranges and generates a batch of images.
Path: src/gui/dataset_dialog.py
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from src.models.dataset_config import DatasetConfig, TableRangeConfig
from src.generators.dataset_generator import DatasetGenerator
from src.database.database_manager import DatabaseManager
from src.database.font_manager import FontManager


# Reusable constants
ALL_DEFECTS = ["wrinkled_edges", "burns", "stains", "holes", "tears", "yellowing"]
ALL_CIPHER_TYPES = ["alphabet", "substitution", "bigram", "trigram", "dictionary", "nulls"]
ALL_KEY_TYPES = ["number", "double_char", "special_character"]
ALL_VARIATION_LEVELS = ["none", "low", "medium", "high"]
ALL_COL_SEPARATORS = ["none", "line", "double_line"]
ALL_KEY_SEPARATORS = ["dots", "dashes", "none"]
ALL_TABLE_CONTENT = ["alphabet", "bigrams", "trigrams", "words", "nulls"]
ALL_PAIR_FORMATS = ["text_first", "number_first"]
ALL_INK_COLORS = ["dark_brown", "black", "faded_brown", "iron_gall", "sepia", "charcoal"]
TOGGLE_OPTIONS = ["always", "never", "random"]


class DatasetDialog(tk.Toplevel):
    """Dialog for configuring and running batch dataset generation."""

    def __init__(self, parent, db_manager: DatabaseManager, font_manager: FontManager,
                 paper_types: list):
        super().__init__(parent)
        self.title("Generate Annotated Dataset")
        self.geometry("620x700")
        self.resizable(True, True)
        self.transient(parent)

        self.db = db_manager
        self.font_manager = font_manager
        self.paper_types = paper_types
        self._generator = None

        self._build_ui()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self):
        # Scrollable area
        outer = ttk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner = ttk.Frame(canvas)
        canvas_win = canvas.create_window((0, 0), window=self._inner, anchor=tk.NW)

        def _on_frame_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(canvas_win, width=event.width)

        self._inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel
        def _on_wheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        def _bind_wheel(_e):
            canvas.bind_all("<Button-4>", _on_wheel_linux)
            canvas.bind_all("<Button-5>", _on_wheel_linux)
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        def _unbind_wheel(_e):
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            canvas.unbind_all("<MouseWheel>")

        outer.bind("<Enter>", _bind_wheel)
        outer.bind("<Leave>", _unbind_wheel)

        row = 0
        row = self._section_general(row)
        row = self._section_paper(row)
        row = self._section_column_pairs(row)
        row = self._section_table_codes(row)
        row = self._section_layout(row)

        # Bottom buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=10, padx=10)
        ttk.Button(btn_frame, text="Generate Dataset", command=self._on_generate).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    # ------------------------------------------------------------------
    # Helper widgets
    # ------------------------------------------------------------------

    def _add_section_label(self, row: int, text: str) -> int:
        ttk.Label(self._inner, text=text, font=("TkDefaultFont", 10, "bold")).grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=10, pady=(12, 4))
        ttk.Separator(self._inner, orient=tk.HORIZONTAL).grid(
            row=row + 1, column=0, columnspan=4, sticky=tk.EW, padx=10)
        return row + 2

    def _add_range(self, row: int, label: str, from_: int, to: int,
                   default_lo: int, default_hi: int):
        """Add a min/max spinbox pair. Returns (lo_var, hi_var, next_row)."""
        ttk.Label(self._inner, text=label).grid(row=row, column=0, sticky=tk.W, padx=(20, 5), pady=2)
        lo_var = tk.IntVar(value=default_lo)
        hi_var = tk.IntVar(value=default_hi)
        f = ttk.Frame(self._inner)
        f.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=2)
        ttk.Label(f, text="Min:").pack(side=tk.LEFT)
        ttk.Spinbox(f, from_=from_, to=to, textvariable=lo_var, width=6).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(f, text="Max:").pack(side=tk.LEFT)
        ttk.Spinbox(f, from_=from_, to=to, textvariable=hi_var, width=6).pack(side=tk.LEFT, padx=2)
        return lo_var, hi_var, row + 1

    def _add_toggle(self, row: int, label: str, default: str = "random"):
        """Add an always/never/random dropdown. Returns (var, next_row)."""
        ttk.Label(self._inner, text=label).grid(row=row, column=0, sticky=tk.W, padx=(20, 5), pady=2)
        var = tk.StringVar(value=default)
        ttk.Combobox(self._inner, textvariable=var, values=TOGGLE_OPTIONS,
                     state="readonly", width=12).grid(row=row, column=1, sticky=tk.W, pady=2)
        return var, row + 1

    def _add_checkboxes(self, row: int, label: str, options: list, defaults: list = None):
        """Add a multi-select checkbox group. Returns (dict[str, BooleanVar], next_row)."""
        ttk.Label(self._inner, text=label).grid(row=row, column=0, sticky=tk.NW, padx=(20, 5), pady=2)
        frame = ttk.Frame(self._inner)
        frame.grid(row=row, column=1, columnspan=3, sticky=tk.W, pady=2)
        if defaults is None:
            defaults = options
        vars_ = {}
        for i, opt in enumerate(options):
            var = tk.BooleanVar(value=(opt in defaults))
            vars_[opt] = var
            ttk.Checkbutton(frame, text=opt.replace("_", " ").title(), variable=var).grid(
                row=i // 3, column=i % 3, sticky=tk.W, padx=4)
        return vars_, row + 1

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _section_general(self, row: int) -> int:
        row = self._add_section_label(row, "General")

        ttk.Label(self._inner, text="Number of Images:").grid(row=row, column=0, sticky=tk.W, padx=(20, 5), pady=2)
        self.num_images_var = tk.IntVar(value=10)
        ttk.Spinbox(self._inner, from_=1, to=10000, textvariable=self.num_images_var, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        self.ignore_empty_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self._inner,
            text="Ignore empty papers (re-generate if nothing renders on a page)",
            variable=self.ignore_empty_var,
        ).grid(row=row, column=0, columnspan=4, sticky=tk.W, padx=(20, 5), pady=2)
        row += 1

        ttk.Label(self._inner, text="Output Directory:").grid(row=row, column=0, sticky=tk.W, padx=(20, 5), pady=2)
        self.output_dir_var = tk.StringVar(value="")
        dir_frame = ttk.Frame(self._inner)
        dir_frame.grid(row=row, column=1, columnspan=3, sticky=tk.EW, pady=2)
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=35).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(dir_frame, text="Browse...", command=self._browse_output).pack(side=tk.LEFT)
        row += 1

        ttk.Label(self._inner, text="Annotation Format:").grid(row=row, column=0, sticky=tk.W, padx=(20, 5), pady=2)
        self.annotation_fmt_var = tk.StringVar(value="both")
        ttk.Combobox(self._inner, textvariable=self.annotation_fmt_var,
                     values=["coco", "yolo", "both"], state="readonly", width=12).grid(
            row=row, column=1, sticky=tk.W, pady=2)
        row += 1
        return row

    def _section_paper(self, row: int) -> int:
        row = self._add_section_label(row, "Paper")
        self._aging_lo, self._aging_hi, row = self._add_range(row, "Aging Level:", 0, 100, 20, 80)
        self._paper_type_vars, row = self._add_checkboxes(row, "Paper Types:", self.paper_types)
        self._defects_toggle, row = self._add_toggle(row, "Defects:", "random")
        font_names = ["Random"] + self.font_manager.get_all_font_names()
        self._font_vars, row = self._add_checkboxes(row, "Fonts:", font_names, defaults=["Random"])
        self._var_level_vars, row = self._add_checkboxes(row, "Variation Levels:", ALL_VARIATION_LEVELS,
                                                          defaults=["low", "medium", "high"])
        return row

    def _section_column_pairs(self, row: int) -> int:
        row = self._add_section_label(row, "Column Pairs")
        self._cp_toggle, row = self._add_toggle(row, "Include:", "always")
        self._cipher_type_vars, row = self._add_checkboxes(row, "Cipher Types:", ALL_CIPHER_TYPES,
                                                            defaults=["substitution"])
        self._key_type_vars, row = self._add_checkboxes(row, "Key Types:", ALL_KEY_TYPES,
                                                         defaults=["number"])
        self._pair_fmt_vars, row = self._add_checkboxes(row, "Pair Formats:", ALL_PAIR_FORMATS,
                                                         defaults=["text_first", "number_first"])
        self._entries_lo, self._entries_hi, row = self._add_range(row, "Num Entries:", 5, 100, 10, 50)
        self._cp_fs_lo, self._cp_fs_hi, row = self._add_range(row, "Font Size:", 8, 36, 10, 20)
        self._col_sep_vars, row = self._add_checkboxes(row, "Row Separators:", ALL_COL_SEPARATORS,
                                                        defaults=["none", "line"])
        self._key_sep_vars, row = self._add_checkboxes(row, "Key Separators:", ALL_KEY_SEPARATORS,
                                                        defaults=["dots", "dashes"])
        self._dash_lo, self._dash_hi, row = self._add_range(row, "Dash Count:", 1, 10, 1, 5)
        self._spacing_lo, self._spacing_hi, row = self._add_range(row, "Line Spacing:", 5, 20, 5, 12)
        self._jitter_lo, self._jitter_hi, row = self._add_range(row, "Line Spacing Jitter:", 0, 20, 0, 8)
        self._cp_title_toggle, row = self._add_toggle(row, "Section Title:", "never")
        return row

    def _section_table_codes(self, row: int) -> int:
        row = self._add_section_label(row, "Table Codes")

        ttk.Label(self._inner, text="Up to 3 independent table blocks per image. Content types are kept unique.",
                  font=("TkDefaultFont", 8), foreground="gray").grid(
            row=row, column=0, columnspan=4, sticky=tk.W, padx=(20, 5), pady=(0, 4))
        row += 1

        # Container frame for all table config panels
        self._tc_panels_frame = ttk.Frame(self._inner)
        self._tc_panels_frame.columnconfigure(0, weight=1)
        self._tc_panels_frame.grid(row=row, column=0, columnspan=4,
                                   sticky=(tk.W, tk.E), padx=10)
        row += 1

        # "Add another table config" button
        self._tc_add_btn = ttk.Button(self._inner, text="+ Add another table config",
                                      command=self._add_dataset_table_panel)
        self._tc_add_btn.grid(row=row, column=0, columnspan=2, sticky=tk.W,
                              padx=20, pady=(4, 2))
        row += 1

        self._dataset_table_panels = []
        self._add_dataset_table_panel()   # create first panel automatically
        return row

    # ------------------------------------------------------------------
    # Dataset table panel helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _panel_range(parent: ttk.LabelFrame, row: int, label: str,
                     from_: int, to: int, lo: int, hi: int):
        """Add a Min/Max spinbox pair inside *parent*. Returns (lo_var, hi_var)."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=(5, 5), pady=2)
        lo_var = tk.IntVar(value=lo)
        hi_var = tk.IntVar(value=hi)
        f = ttk.Frame(parent)
        f.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Label(f, text="Min:").pack(side=tk.LEFT)
        ttk.Spinbox(f, from_=from_, to=to, textvariable=lo_var, width=5).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(f, text="Max:").pack(side=tk.LEFT)
        ttk.Spinbox(f, from_=from_, to=to, textvariable=hi_var, width=5).pack(side=tk.LEFT, padx=2)
        return lo_var, hi_var

    @staticmethod
    def _panel_toggle(parent: ttk.LabelFrame, row: int, label: str, default: str = "random"):
        """Add an always/never/random dropdown inside *parent*. Returns var."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=(5, 5), pady=2)
        var = tk.StringVar(value=default)
        ttk.Combobox(parent, textvariable=var, values=TOGGLE_OPTIONS,
                     state="readonly", width=12).grid(row=row, column=1, sticky=tk.W, pady=2)
        return var

    def _add_dataset_table_panel(self):
        """Add one table range config panel (max 3)."""
        if len(self._dataset_table_panels) >= 3:
            return

        index = len(self._dataset_table_panels)
        # Default content type: prefer a unique type per panel
        default_types = ["alphabet", "bigrams", "nulls"]
        default_content = default_types[index] if index < len(default_types) else "alphabet"

        outer = ttk.LabelFrame(self._tc_panels_frame, text=f"Table {index + 1}", padding="5")
        outer.columnconfigure(1, weight=1)
        outer.grid(row=index, column=0, sticky=(tk.W, tk.E), pady=(0, 6))

        r = 0

        # Include toggle
        include_var = self._panel_toggle(outer, r, "Include:", "always" if index == 0 else "random")
        r += 1

        # Content types checkboxes
        ttk.Label(outer, text="Content Types:").grid(row=r, column=0, sticky=tk.NW, padx=(5, 5), pady=2)
        content_frame = ttk.Frame(outer)
        content_frame.grid(row=r, column=1, columnspan=3, sticky=tk.W, pady=2)
        content_vars = {}
        for i, opt in enumerate(ALL_TABLE_CONTENT):
            var = tk.BooleanVar(value=(opt == default_content))
            content_vars[opt] = var
            ttk.Checkbutton(content_frame, text=opt.title(), variable=var).grid(
                row=0, column=i, sticky=tk.W, padx=4)
        r += 1

        nsym_lo, nsym_hi = self._panel_range(outer, r, "Num Entries:", 1, 200, 5, 20)
        ttk.Label(outer, text="(ignored for alphabet — always full)",
                  font=("TkDefaultFont", 8), foreground="gray").grid(
            row=r, column=2, sticky=tk.W, padx=5)
        r += 1
        codes_lo, codes_hi = self._panel_range(outer, r, "Codes/Symbol:", 1, 10, 1, 5)
        r += 1
        boost_var = self._panel_toggle(outer, r, "Common Boost:", "random")
        r += 1
        ccodes_lo, ccodes_hi = self._panel_range(outer, r, "Common Codes:", 2, 20, 2, 8)
        r += 1
        sp_lo, sp_hi = self._panel_range(outer, r, "Col Spacing:", 2, 60, 5, 20)
        r += 1
        vlines_var = self._panel_toggle(outer, r, "Vertical Lines:", "random")
        r += 1
        fs_lo, fs_hi = self._panel_range(outer, r, "Font Size:", 8, 36, 10, 20)
        r += 1
        rsp_lo, rsp_hi = self._panel_range(outer, r, "Row Spacing:", 0, 20, 0, 6)
        r += 1
        pair_grid_var = self._panel_toggle(outer, r, "2×2 Pair Grid:", "never")
        ttk.Label(outer, text="(ignored when Boost = always)",
                  font=("TkDefaultFont", 8), foreground="gray").grid(
            row=r, column=2, sticky=tk.W, padx=5)
        r += 1
        draw_sep_var = self._panel_toggle(outer, r, "Draw Sep. Lines:", "always")
        r += 1
        title_var = self._panel_toggle(outer, r, "Section Title:", "never")

        self._dataset_table_panels.append({
            "include": include_var,
            "content_types": content_vars,
            "nsym_lo": nsym_lo, "nsym_hi": nsym_hi,
            "codes_lo": codes_lo, "codes_hi": codes_hi,
            "common_boost": boost_var,
            "ccodes_lo": ccodes_lo, "ccodes_hi": ccodes_hi,
            "sp_lo": sp_lo, "sp_hi": sp_hi,
            "vertical_lines": vlines_var,
            "fs_lo": fs_lo, "fs_hi": fs_hi,
            "rsp_lo": rsp_lo, "rsp_hi": rsp_hi,
            "pair_grid": pair_grid_var,
            "draw_header_line": draw_sep_var,
            "include_title": title_var,
        })

        if len(self._dataset_table_panels) >= 3:
            self._tc_add_btn.configure(state="disabled")

    def _section_layout(self, row: int) -> int:
        row = self._add_section_label(row, "Layout & Ink")
        self._sx_lo, self._sx_hi, row = self._add_range(row, "Start X:", 0, 400, 0, 100)
        self._sy_lo, self._sy_hi, row = self._add_range(row, "Start Y:", 0, 400, 0, 100)
        self._rm_lo, self._rm_hi, row = self._add_range(row, "Right Margin:", 0, 400, 0, 80)
        self._bm_lo, self._bm_hi, row = self._add_range(row, "Bottom Margin:", 0, 400, 0, 80)
        self._title_toggle, row = self._add_toggle(row, "Include Title:", "random")
        self._ink_vars, row = self._add_checkboxes(row, "Ink Colors:", ALL_INK_COLORS)
        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.output_dir_var.set(path)

    @staticmethod
    def _checked(vars_dict: dict) -> list:
        """Return list of checked option names from a checkbox group."""
        return [k for k, v in vars_dict.items() if v.get()]

    def _build_config(self) -> DatasetConfig:
        """Build a DatasetConfig from the dialog state."""
        # Build per-table configs from the dynamic panels
        table_configs = []
        for p in self._dataset_table_panels:
            content_types = [k for k, v in p["content_types"].items() if v.get()] or ["alphabet"]
            table_configs.append(TableRangeConfig(
                include=p["include"].get(),
                content_types=content_types,
                num_symbols_range=(p["nsym_lo"].get(), p["nsym_hi"].get()),
                num_codes_range=(p["codes_lo"].get(), p["codes_hi"].get()),
                common_boost=p["common_boost"].get(),
                common_codes_range=(p["ccodes_lo"].get(), p["ccodes_hi"].get()),
                col_spacing_range=(p["sp_lo"].get(), p["sp_hi"].get()),
                vertical_lines=p["vertical_lines"].get(),
                font_size_range=(p["fs_lo"].get(), p["fs_hi"].get()),
                row_spacing_range=(p["rsp_lo"].get(), p["rsp_hi"].get()),
                pair_grid=p["pair_grid"].get(),
                draw_header_line=p["draw_header_line"].get(),
                include_title=p["include_title"].get(),
            ))

        cfg = DatasetConfig(
            num_images=self.num_images_var.get(),
            output_dir=self.output_dir_var.get(),
            annotation_format=self.annotation_fmt_var.get(),
            ignore_empty_papers=self.ignore_empty_var.get(),
            # Paper
            aging_level_range=(self._aging_lo.get(), self._aging_hi.get()),
            paper_types=self._checked(self._paper_type_vars) or self.paper_types[:1],
            defects_mode=self._defects_toggle.get(),
            # Column pairs
            include_column_pairs=self._cp_toggle.get(),
            cipher_types=self._checked(self._cipher_type_vars) or ["substitution"],
            key_types=self._checked(self._key_type_vars) or ["number"],
            pair_formats=self._checked(self._pair_fmt_vars) or ["text_first"],
            num_entries_range=(self._entries_lo.get(), self._entries_hi.get()),
            cp_font_size_range=(self._cp_fs_lo.get(), self._cp_fs_hi.get()),
            include_cp_title=self._cp_title_toggle.get(),
            # Font
            fonts=self._checked(self._font_vars) or ["Random"],
            variation_levels=self._checked(self._var_level_vars) or ["medium"],
            col_separators=self._checked(self._col_sep_vars) or ["line"],
            key_separators=self._checked(self._key_sep_vars) or ["dashes"],
            dash_count_range=(self._dash_lo.get(), self._dash_hi.get()),
            spacing_range=(self._spacing_lo.get(), self._spacing_hi.get()),
            # Multiple table configs
            table_configs=table_configs,
            # Layout
            start_x_range=(self._sx_lo.get(), self._sx_hi.get()),
            start_y_range=(self._sy_lo.get(), self._sy_hi.get()),
            right_margin_range=(self._rm_lo.get(), self._rm_hi.get()),
            bottom_margin_range=(self._bm_lo.get(), self._bm_hi.get()),
            line_spacing_jitter_range=(self._jitter_lo.get(), self._jitter_hi.get()),
            include_title=self._title_toggle.get(),
            ink_colors=self._checked(self._ink_vars) or ["dark_brown"],
        )
        return cfg

    def _on_generate(self):
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Missing field", "Please select an output directory.", parent=self)
            return

        config = self._build_config()

        # Swap the content area for a progress view
        for widget in self._inner.winfo_children():
            widget.destroy()

        ttk.Label(self._inner, text="Generating dataset...",
                  font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, columnspan=4, padx=20, pady=(20, 10))

        self._progress_var = tk.IntVar(value=0)
        self._progress_bar = ttk.Progressbar(self._inner, maximum=config.num_images,
                                              variable=self._progress_var, length=400)
        self._progress_bar.grid(row=1, column=0, columnspan=4, padx=20, pady=5)

        self._progress_label = ttk.Label(self._inner, text=f"0 / {config.num_images}")
        self._progress_label.grid(row=2, column=0, columnspan=4, padx=20, pady=5)

        self._cancel_btn = ttk.Button(self._inner, text="Cancel", command=self._on_cancel_generation)
        self._cancel_btn.grid(row=3, column=0, columnspan=4, pady=10)

        self._generator = DatasetGenerator(config, self.db, self.font_manager)

        def _run():
            try:
                self._generator.generate(progress_callback=self._on_progress)
                self.after(0, lambda: self._on_done(config))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e), parent=self))

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        return f"{m}m {s}s"

    def _on_progress(self, current: int, total: int, elapsed: float, eta: float):
        self.after(0, lambda: self._update_progress(current, total, elapsed, eta))

    def _update_progress(self, current: int, total: int, elapsed: float, eta: float):
        self._progress_var.set(current)
        elapsed_str = self._fmt_time(elapsed)
        eta_str = self._fmt_time(eta)
        self._progress_label.config(
            text=f"{current} / {total}   |   Elapsed: {elapsed_str}   |   ETA: {eta_str}"
        )

    def _on_cancel_generation(self):
        if self._generator:
            self._generator.cancel()
        self.destroy()

    def _on_done(self, config: DatasetConfig):
        messagebox.showinfo(
            "Dataset Complete",
            f"Generated {config.num_images} images.\n\nOutput: {config.output_dir}",
            parent=self,
        )
        self.destroy()
