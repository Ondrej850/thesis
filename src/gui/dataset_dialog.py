"""
Dataset generation dialog.
Lets the user configure randomisation ranges and generates a batch of images.
Path: src/gui/dataset_dialog.py
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from src.models.dataset_config import DatasetConfig
from src.generators.dataset_generator import DatasetGenerator
from src.database.database_manager import DatabaseManager
from src.database.font_manager import FontManager


# Reusable constants
ALL_DEFECTS = ["wrinkled_edges", "burns", "stains", "holes", "tears", "yellowing"]
ALL_CIPHER_TYPES = ["substitution", "bigram", "trigram", "dictionary", "nulls"]
ALL_KEY_TYPES = ["number", "special_character"]
ALL_VARIATION_LEVELS = ["none", "low", "medium", "high"]
ALL_COL_SEPARATORS = ["none", "line", "double_line"]
ALL_KEY_SEPARATORS = ["dots", "dashes", "none"]
ALL_TABLE_CONTENT = ["alphabet", "ngrams", "nulls"]
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
        row = self._section_font(row)
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
        return row

    def _section_column_pairs(self, row: int) -> int:
        row = self._add_section_label(row, "Column Pairs")
        self._cp_toggle, row = self._add_toggle(row, "Include:", "always")
        self._cipher_type_vars, row = self._add_checkboxes(row, "Cipher Types:", ALL_CIPHER_TYPES,
                                                            defaults=["substitution"])
        self._key_type_vars, row = self._add_checkboxes(row, "Key Types:", ALL_KEY_TYPES,
                                                         defaults=["number"])
        self._entries_lo, self._entries_hi, row = self._add_range(row, "Num Entries:", 5, 100, 10, 50)
        self._cp_fs_lo, self._cp_fs_hi, row = self._add_range(row, "Font Size:", 8, 36, 10, 20)
        return row

    def _section_font(self, row: int) -> int:
        row = self._add_section_label(row, "Font & Style")
        font_names = ["Random"] + self.font_manager.get_all_font_names()
        self._font_vars, row = self._add_checkboxes(row, "Fonts:", font_names, defaults=["Random"])
        self._var_level_vars, row = self._add_checkboxes(row, "Variation Levels:", ALL_VARIATION_LEVELS,
                                                          defaults=["low", "medium", "high"])
        self._col_sep_vars, row = self._add_checkboxes(row, "Column Separators:", ALL_COL_SEPARATORS,
                                                        defaults=["none", "line"])
        self._key_sep_vars, row = self._add_checkboxes(row, "Key Separators:", ALL_KEY_SEPARATORS,
                                                        defaults=["dots", "dashes"])
        self._dash_lo, self._dash_hi, row = self._add_range(row, "Dash Count:", 1, 10, 1, 5)
        self._spacing_lo, self._spacing_hi, row = self._add_range(row, "Line Spacing:", 5, 20, 5, 12)
        return row

    def _section_table_codes(self, row: int) -> int:
        row = self._add_section_label(row, "Table Codes")
        self._tc_toggle, row = self._add_toggle(row, "Include:", "random")
        self._tc_content_vars, row = self._add_checkboxes(row, "Content Types:", ALL_TABLE_CONTENT,
                                                           defaults=["alphabet"])
        self._tc_codes_lo, self._tc_codes_hi, row = self._add_range(row, "Codes/Symbol:", 1, 10, 1, 5)
        self._tc_boost_toggle, row = self._add_toggle(row, "Common Boost:", "random")
        self._tc_ccodes_lo, self._tc_ccodes_hi, row = self._add_range(row, "Common Codes:", 2, 20, 2, 8)
        self._tc_spacing_lo, self._tc_spacing_hi, row = self._add_range(row, "Col Spacing:", 2, 60, 5, 20)
        self._tc_vlines_toggle, row = self._add_toggle(row, "Vertical Lines:", "random")
        self._tc_fs_lo, self._tc_fs_hi, row = self._add_range(row, "Font Size:", 8, 36, 10, 20)
        return row

    def _section_layout(self, row: int) -> int:
        row = self._add_section_label(row, "Layout & Ink")
        self._sx_lo, self._sx_hi, row = self._add_range(row, "Start X:", 0, 400, 30, 80)
        self._sy_lo, self._sy_hi, row = self._add_range(row, "Start Y:", 0, 400, 30, 80)
        self._rm_lo, self._rm_hi, row = self._add_range(row, "Right Margin:", 0, 400, 30, 80)
        self._bm_lo, self._bm_hi, row = self._add_range(row, "Bottom Margin:", 0, 400, 30, 80)
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
        cfg = DatasetConfig(
            num_images=self.num_images_var.get(),
            output_dir=self.output_dir_var.get(),
            annotation_format=self.annotation_fmt_var.get(),
            # Paper
            aging_level_range=(self._aging_lo.get(), self._aging_hi.get()),
            paper_types=self._checked(self._paper_type_vars) or self.paper_types[:1],
            defects_mode=self._defects_toggle.get(),
            # Column pairs
            include_column_pairs=self._cp_toggle.get(),
            cipher_types=self._checked(self._cipher_type_vars) or ["substitution"],
            key_types=self._checked(self._key_type_vars) or ["number"],
            num_entries_range=(self._entries_lo.get(), self._entries_hi.get()),
            cp_font_size_range=(self._cp_fs_lo.get(), self._cp_fs_hi.get()),
            # Font
            fonts=self._checked(self._font_vars) or ["Random"],
            variation_levels=self._checked(self._var_level_vars) or ["medium"],
            col_separators=self._checked(self._col_sep_vars) or ["line"],
            key_separators=self._checked(self._key_sep_vars) or ["dashes"],
            dash_count_range=(self._dash_lo.get(), self._dash_hi.get()),
            spacing_range=(self._spacing_lo.get(), self._spacing_hi.get()),
            # Table codes
            include_table_codes=self._tc_toggle.get(),
            table_content_types=self._checked(self._tc_content_vars) or ["alphabet"],
            table_num_codes_range=(self._tc_codes_lo.get(), self._tc_codes_hi.get()),
            table_common_boost=self._tc_boost_toggle.get(),
            table_common_codes_range=(self._tc_ccodes_lo.get(), self._tc_ccodes_hi.get()),
            table_col_spacing_range=(self._tc_spacing_lo.get(), self._tc_spacing_hi.get()),
            table_vertical_lines=self._tc_vlines_toggle.get(),
            table_font_size_range=(self._tc_fs_lo.get(), self._tc_fs_hi.get()),
            # Layout
            start_x_range=(self._sx_lo.get(), self._sx_hi.get()),
            start_y_range=(self._sy_lo.get(), self._sy_hi.get()),
            right_margin_range=(self._rm_lo.get(), self._rm_hi.get()),
            bottom_margin_range=(self._bm_lo.get(), self._bm_hi.get()),
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
