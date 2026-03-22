"""
Main GUI window for cipher generator application
Path: src/gui/main_window.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import random
import os
import threading
from typing import List, Tuple
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.models.paper_config import PaperConfig
from src.models.font_config import FontConfig
from src.models.cipher_type import CipherType
from src.models.table_codes_config import TableCodesConfig
from src.database.database_manager import DatabaseManager
from src.generators.image_generator import CipherImageGenerator
from src.annotations.coco_manager import COCOAnnotationManager
from src.database.font_manager import FontManager


class CollapsibleSection(ttk.Frame):
    """A LabelFrame-like section with a clickable header to collapse/expand."""

    def __init__(self, parent, title: str, expanded: bool = True, **kwargs):
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)

        self._expanded = tk.BooleanVar(value=expanded)

        # Header row: toggle button + label
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky=(tk.W, tk.E))
        header.columnconfigure(1, weight=1)

        self._toggle_btn = ttk.Button(
            header, text="▼" if expanded else "▶", width=2,
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=0, padx=(0, 4))

        self._title_label = ttk.Label(header, text=title, font=("TkDefaultFont", 9, "bold"))
        self._title_label.grid(row=0, column=1, sticky=tk.W)
        self._title_label.bind("<Button-1>", lambda _e: self._toggle())

        # Content frame (this is what callers populate)
        self.content = ttk.LabelFrame(self, text="", padding="5")
        self.content.columnconfigure(1, weight=1)
        if expanded:
            self.content.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))

    def _toggle(self):
        if self._expanded.get():
            self.content.grid_forget()
            self._expanded.set(False)
            self._toggle_btn.config(text="▶")
        else:
            self.content.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
            self._expanded.set(True)
            self._toggle_btn.config(text="▼")
        # Notify scrollable canvas to recalculate scroll region
        self.event_generate("<<SectionToggled>>")


class CipherGeneratorGUI:
    """Main GUI application"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Historical Cipher Generator - 15th Century")
        self.root.geometry("1400x900")

        # Initialize components
        self.db = DatabaseManager()
        self.font_manager = FontManager()

        # Initialize font database
        if self.font_manager.has_fonts():
            self.font_manager.add_font_to_database(self.db)

        self.preview_image = None
        self.current_generator = None  # Store generator instance

        # Only auto-regenerate after the user has clicked "Generate Preview" once
        self._preview_generated_once = False

        # Real-time preview: debounce timer for config changes
        self._debounce_timer = None
        self._debounce_delay = 0.3  # 300ms delay before regenerating
        self._is_generating = False  # Prevent concurrent generations

        # Cached cipher entries for consistent preview during visual changes
        self._cached_cipher_entries = None
        self._cached_cipher_type = None
        self._cached_num_entries = None
        self._cached_key_type = None

        # Cached paper image for consistent preview
        self._cached_paper_image = None
        self._cached_paper_aging = None
        self._cached_paper_type = None
        self._cached_paper_defects = None

        # Cached table codes: the symbol→codes assignment (not the rendered image).
        # Invalidated only when content-defining settings change (content_type,
        # num_codes, use_common_boost, common_codes).  Visual settings such as
        # font_size or symbols_per_row do NOT invalidate this cache.
        self._cached_code_table = None        # Dict[str, List[int]] or None
        self._cached_code_table_key = None    # tuple key identifying the content

        self.setup_gui()

        # Bind change listeners after GUI is set up
        self._bind_config_change_listeners()

    def setup_gui(self):
        """Setup GUI elements"""
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(0, weight=1)

        # Create main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        # Left panel - Scrollable configuration
        config_outer = ttk.LabelFrame(main_frame, text="Configuration", padding="5")
        config_outer.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        config_outer.rowconfigure(0, weight=1)
        config_outer.columnconfigure(0, weight=1)

        self._config_canvas = tk.Canvas(config_outer, highlightthickness=0, width=420)
        self._config_canvas.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))

        config_scrollbar = ttk.Scrollbar(config_outer, orient=tk.VERTICAL,
                                         command=self._config_canvas.yview)
        config_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self._config_canvas.configure(yscrollcommand=config_scrollbar.set)

        # Inner frame that holds all sections — lives inside the canvas
        config_frame = ttk.Frame(self._config_canvas)
        self._config_canvas_window = self._config_canvas.create_window(
            (0, 0), window=config_frame, anchor=tk.NW,
        )

        # Keep canvas scroll region and inner-frame width in sync
        def _on_config_frame_configure(_event=None):
            self._config_canvas.configure(scrollregion=self._config_canvas.bbox("all"))

        def _on_canvas_configure(event):
            self._config_canvas.itemconfigure(self._config_canvas_window, width=event.width)

        config_frame.bind("<Configure>", _on_config_frame_configure)
        self._config_canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            self._config_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                self._config_canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                self._config_canvas.yview_scroll(3, "units")

        self._config_canvas.bind_all("<MouseWheel>", _on_mousewheel)       # Windows / macOS
        self._config_canvas.bind_all("<Button-4>", _on_mousewheel_linux)   # Linux scroll up
        self._config_canvas.bind_all("<Button-5>", _on_mousewheel_linux)   # Linux scroll down

        # React to section collapse/expand
        config_frame.bind_all("<<SectionToggled>>", _on_config_frame_configure)

        # Right panel - Preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)

        # Setup sections
        self.setup_paper_config(config_frame)
        self.setup_cipher_config(config_frame)
        self.setup_font_config(config_frame)
        self.setup_table_codes_config(config_frame)
        self.setup_layout_config(config_frame)
        self.setup_preview(preview_frame)
        self.setup_buttons(main_frame)

    def setup_paper_config(self, parent):
        """Setup paper configuration section"""
        section = CollapsibleSection(parent, "1. Paper Configuration")
        section.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        frame = section.content

        # Aging level
        ttk.Label(frame, text="Aging Level:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.aging_var = tk.IntVar(value=50)
        aging_scale = ttk.Scale(frame, from_=0, to=100, variable=self.aging_var,
                               orient=tk.HORIZONTAL, length=200)
        aging_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(frame, textvariable=self.aging_var).grid(row=0, column=2, padx=5)

        # Paper type
        ttk.Label(frame, text="Paper Type:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.paper_type_var = tk.StringVar()
        paper_types = [pt[1] for pt in self.db.get_paper_types()]
        paper_combo = ttk.Combobox(frame, textvariable=self.paper_type_var,
                                  values=paper_types, state='readonly', width=25)
        paper_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        if paper_types:
            paper_combo.current(0)

        # Defects checklist
        ttk.Label(frame, text="Defects:").grid(row=2, column=0, sticky=tk.W, pady=2)
        defects_frame = ttk.Frame(frame)
        defects_frame.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=2)

        self.defect_vars = {}
        defects = ['wrinkled_edges', 'burns', 'stains', 'holes', 'tears', 'yellowing']
        for i, defect in enumerate(defects):
            var = tk.BooleanVar(value=True)
            self.defect_vars[defect] = var
            ttk.Checkbutton(defects_frame, text=defect.replace('_', ' ').title(),
                           variable=var).grid(row=i//2, column=i%2, sticky=tk.W, padx=5)

    def setup_cipher_config(self, parent):
        """Setup column-pairs cipher configuration section."""
        section = CollapsibleSection(parent, "2. Column Pairs")
        section.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        frame = section.content

        # Enable / disable checkbox
        self.include_column_pairs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Include column pairs in document",
            variable=self.include_column_pairs_var,
            command=self._on_column_pairs_toggle,
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=2)

        # Cipher type
        self._cp_label_type = ttk.Label(frame, text="Cipher Type:")
        self._cp_label_type.grid(row=1, column=0, sticky=tk.W, pady=2)
        self.cipher_type_var = tk.StringVar(value="substitution")
        cipher_types = ['substitution', 'bigram', 'trigram', 'dictionary', 'nulls']
        self._cp_cipher_combo = ttk.Combobox(
            frame, textvariable=self.cipher_type_var,
            values=cipher_types, state='readonly', width=25,
        )
        self._cp_cipher_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        # Key type
        self._cp_label_key = ttk.Label(frame, text="Key Type:")
        self._cp_label_key.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.key_type_var = tk.StringVar(value="number")
        key_types = ['number', 'special_character']
        self._cp_key_combo = ttk.Combobox(
            frame, textvariable=self.key_type_var,
            values=key_types, state='readonly', width=25,
        )
        self._cp_key_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)

        # Number of entries
        self._cp_label_entries = ttk.Label(frame, text="Number of Entries:")
        self._cp_label_entries.grid(row=3, column=0, sticky=tk.W, pady=2)
        self.num_entries_var = tk.IntVar(value=30)
        self._cp_entries_spinbox = ttk.Spinbox(
            frame, from_=5, to=100, textvariable=self.num_entries_var, width=10,
        )
        self._cp_entries_spinbox.grid(row=3, column=1, sticky=tk.W, pady=2)

        # Font size (local to column pairs)
        self._cp_label_font_size = ttk.Label(frame, text="Font Size:")
        self._cp_label_font_size.grid(row=4, column=0, sticky=tk.W, pady=2)
        self.cp_font_size_var = tk.IntVar(value=14)
        self._cp_font_size_spinbox = ttk.Spinbox(
            frame, from_=8, to=36, textvariable=self.cp_font_size_var, width=10,
        )
        self._cp_font_size_spinbox.grid(row=4, column=1, sticky=tk.W, pady=2)

    def _on_column_pairs_toggle(self):
        """Enable/disable column-pairs sub-controls based on checkbox."""
        state = "readonly" if self.include_column_pairs_var.get() else "disabled"
        spin_state = "normal" if self.include_column_pairs_var.get() else "disabled"
        self._cp_cipher_combo.configure(state=state)
        self._cp_key_combo.configure(state=state)
        self._cp_entries_spinbox.configure(state=spin_state)
        self._cp_font_size_spinbox.configure(state=spin_state)

    def setup_font_config(self, parent):
        """Setup font configuration section"""
        section = CollapsibleSection(parent, "3. Font Configuration")
        section.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        frame = section.content

        # Font selection
        ttk.Label(frame, text="Font:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.font_selection_var = tk.StringVar(value="Random")

        font_choices = ["Random"] + self.font_manager.get_all_font_names()
        if not self.font_manager.has_fonts():
            font_choices = ["System Default (No custom fonts found)"]

        font_combo = ttk.Combobox(frame, textvariable=self.font_selection_var,
                                  values=font_choices, state='readonly', width=25)
        font_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)

        # Variation Level
        ttk.Label(frame, text="Variation Level:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.variation_level_var = tk.StringVar(value="medium")
        variation_combo = ttk.Combobox(frame, textvariable=self.variation_level_var,
                                       values=['none', 'low', 'medium', 'high'],
                                       state='readonly', width=25)
        variation_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        # Add tooltip/help
        help_label = ttk.Label(frame, text="(Controls character size, position, rotation)",
                               font=('TkDefaultFont', 8), foreground='gray')
        help_label.grid(row=1, column=2, sticky=tk.W, padx=5)

        # Column separator
        ttk.Label(frame, text="Column Separator:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.col_sep_var = tk.StringVar(value="line")
        col_seps = ['none', 'line', 'double_line']
        ttk.Combobox(frame, textvariable=self.col_sep_var, values=col_seps,
                     state='readonly', width=25).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)

        # Key separator
        ttk.Label(frame, text="Key Separator:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.key_sep_var = tk.StringVar(value="dashes")
        key_seps = ['dots', 'dashes', 'none']
        ttk.Combobox(frame, textvariable=self.key_sep_var, values=key_seps,
                     state='readonly', width=25).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2)

        # Dash count
        ttk.Label(frame, text="Dash Count:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.dash_count_var = tk.IntVar(value=3)
        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.dash_count_var,
                    width=10).grid(row=4, column=1, sticky=tk.W, pady=2)

        # Spacing
        ttk.Label(frame, text="Line Spacing:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.spacing_var = tk.IntVar(value=8)
        ttk.Spinbox(frame, from_=5, to=20, textvariable=self.spacing_var,
                    width=10).grid(row=5, column=1, sticky=tk.W, pady=2)

    def setup_table_codes_config(self, parent):
        """Setup table codes configuration section (section 4)."""
        section = CollapsibleSection(parent, "4. Table Codes")
        section.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        frame = section.content

        # Enable / disable checkbox (off by default — opt-in feature)
        self.include_table_codes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Include table codes in document",
            variable=self.include_table_codes_var,
            command=self._on_table_codes_toggle,
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=2)

        ttk.Label(
            frame,
            text="Table appears above column pairs when both are enabled.",
            font=("TkDefaultFont", 8), foreground="gray",
        ).grid(row=0, column=3, sticky=tk.W, padx=5)

        # Table content type
        self._tc_label_content = ttk.Label(frame, text="Table Content:")
        self._tc_label_content.grid(row=1, column=0, sticky=tk.W, pady=2)
        self.table_content_var = tk.StringVar(value="alphabet")
        self._tc_content_combo = ttk.Combobox(
            frame, textvariable=self.table_content_var,
            values=["alphabet", "ngrams", "nulls"],
            state="readonly", width=25,
        )
        self._tc_content_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        # Codes per symbol
        self._tc_label_codes = ttk.Label(frame, text="Codes per Symbol:")
        self._tc_label_codes.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.table_num_codes_var = tk.IntVar(value=3)
        self._tc_codes_spinbox = ttk.Spinbox(
            frame, from_=1, to=10, textvariable=self.table_num_codes_var, width=10,
        )
        self._tc_codes_spinbox.grid(row=2, column=1, sticky=tk.W, pady=2)

        # Common letters boost
        self.table_common_boost_var = tk.BooleanVar(value=True)
        self._tc_boost_check = ttk.Checkbutton(
            frame,
            text="More codes for common letters (E,T,A,O,I,N,S,H,R)",
            variable=self.table_common_boost_var,
            command=self._on_table_boost_toggle,
        )
        self._tc_boost_check.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=2)

        # Common letter code count
        self._tc_label_common = ttk.Label(frame, text="Common Letter Codes:")
        self._tc_label_common.grid(row=4, column=0, sticky=tk.W, pady=2)
        self.table_common_codes_var = tk.IntVar(value=5)
        self._common_codes_spinbox = ttk.Spinbox(
            frame, from_=2, to=20, textvariable=self.table_common_codes_var, width=10,
        )
        self._common_codes_spinbox.grid(row=4, column=1, sticky=tk.W, pady=2)

        # Column spacing
        self._tc_label_spacing = ttk.Label(frame, text="Column Spacing:")
        self._tc_label_spacing.grid(row=5, column=0, sticky=tk.W, pady=2)
        self.table_col_spacing_var = tk.IntVar(value=10)
        self._tc_col_spacing_spinbox = ttk.Spinbox(
            frame, from_=2, to=60, textvariable=self.table_col_spacing_var, width=10,
        )
        self._tc_col_spacing_spinbox.grid(row=5, column=1, sticky=tk.W, pady=2)
        ttk.Label(
            frame,
            text="px extra per column (lower = tighter)",
            font=("TkDefaultFont", 8), foreground="gray",
        ).grid(row=5, column=3, sticky=tk.W, padx=5)

        # Vertical column lines
        self.table_vertical_lines_var = tk.BooleanVar(value=True)
        self._tc_vlines_check = ttk.Checkbutton(
            frame,
            text="Draw vertical lines between columns",
            variable=self.table_vertical_lines_var,
        )
        self._tc_vlines_check.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=2)

        # Font size (local to table codes)
        self._tc_label_font_size = ttk.Label(frame, text="Font Size:")
        self._tc_label_font_size.grid(row=7, column=0, sticky=tk.W, pady=2)
        self.table_font_size_var = tk.IntVar(value=14)
        self._tc_font_size_spinbox = ttk.Spinbox(
            frame, from_=8, to=36, textvariable=self.table_font_size_var, width=10,
        )
        self._tc_font_size_spinbox.grid(row=7, column=1, sticky=tk.W, pady=2)

        # Sync enabled/disabled states on startup
        self._on_table_codes_toggle()

    def _on_table_codes_toggle(self):
        """Enable/disable table-codes sub-controls based on the Include checkbox."""
        enabled = self.include_table_codes_var.get()
        combo_state = "readonly" if enabled else "disabled"
        spin_state = "normal" if enabled else "disabled"
        self._tc_content_combo.configure(state=combo_state)
        self._tc_codes_spinbox.configure(state=spin_state)
        self._tc_boost_check.configure(state="normal" if enabled else "disabled")
        self._tc_col_spacing_spinbox.configure(state=spin_state)
        self._tc_vlines_check.configure(state="normal" if enabled else "disabled")
        self._tc_font_size_spinbox.configure(state=spin_state)
        # Also honour the boost-spinbox state within the enabled section
        if enabled:
            self._on_table_boost_toggle()
        else:
            self._common_codes_spinbox.configure(state="disabled")

    def _on_table_boost_toggle(self):
        """Show or hide the common-codes spinbox depending on the boost checkbox."""
        state = "normal" if self.table_common_boost_var.get() else "disabled"
        self._common_codes_spinbox.configure(state=state)

    # ------------------------------------------------------------------
    # Pixel ↔ centimetre helpers  (96 DPI assumed)
    # ------------------------------------------------------------------
    PX_PER_CM = 37.795275591  # 96 DPI

    @staticmethod
    def _px_to_cm(px: int) -> float:
        """Convert pixels to centimetres (96 DPI)."""
        return px / CipherGeneratorGUI.PX_PER_CM

    @staticmethod
    def _cm_to_px(cm: float) -> int:
        """Convert centimetres to pixels (96 DPI)."""
        return int(round(cm * CipherGeneratorGUI.PX_PER_CM))

    def setup_layout_config(self, parent):
        """Setup layout & ink configuration section (section 5)."""
        section = CollapsibleSection(parent, "5. Layout & Ink")
        section.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)
        frame = section.content

        # ── Start position X ──────────────────────────────────────────
        ttk.Label(frame, text="Start X (px):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.start_x_var = tk.IntVar(value=50)
        self._start_x_spinbox = ttk.Spinbox(
            frame, from_=0, to=400, textvariable=self.start_x_var, width=10,
        )
        self._start_x_spinbox.grid(row=0, column=1, sticky=tk.W, pady=2)
        self._start_x_cm_label = ttk.Label(frame, text="≈ 1.32 cm from left",
                                           font=("TkDefaultFont", 8), foreground="gray")
        self._start_x_cm_label.grid(row=0, column=2, sticky=tk.W, padx=5)

        # ── Start position Y ──────────────────────────────────────────
        ttk.Label(frame, text="Start Y (px):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.start_y_var = tk.IntVar(value=50)
        self._start_y_spinbox = ttk.Spinbox(
            frame, from_=0, to=400, textvariable=self.start_y_var, width=10,
        )
        self._start_y_spinbox.grid(row=1, column=1, sticky=tk.W, pady=2)
        self._start_y_cm_label = ttk.Label(frame, text="≈ 1.32 cm from top",
                                           font=("TkDefaultFont", 8), foreground="gray")
        self._start_y_cm_label.grid(row=1, column=2, sticky=tk.W, padx=5)

        # ── Right margin ──────────────────────────────────────────────
        ttk.Label(frame, text="Right Margin (px):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.right_margin_var = tk.IntVar(value=50)
        self._right_margin_spinbox = ttk.Spinbox(
            frame, from_=0, to=400, textvariable=self.right_margin_var, width=10,
        )
        self._right_margin_spinbox.grid(row=2, column=1, sticky=tk.W, pady=2)
        self._right_margin_cm_label = ttk.Label(frame, text="≈ 1.32 cm from right",
                                                font=("TkDefaultFont", 8), foreground="gray")
        self._right_margin_cm_label.grid(row=2, column=2, sticky=tk.W, padx=5)

        # ── Bottom margin ─────────────────────────────────────────────
        ttk.Label(frame, text="Bottom Margin (px):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.bottom_margin_var = tk.IntVar(value=50)
        self._bottom_margin_spinbox = ttk.Spinbox(
            frame, from_=0, to=400, textvariable=self.bottom_margin_var, width=10,
        )
        self._bottom_margin_spinbox.grid(row=3, column=1, sticky=tk.W, pady=2)
        self._bottom_margin_cm_label = ttk.Label(frame, text="≈ 1.32 cm from bottom",
                                                 font=("TkDefaultFont", 8), foreground="gray")
        self._bottom_margin_cm_label.grid(row=3, column=2, sticky=tk.W, padx=5)

        # ── Ink color ─────────────────────────────────────────────────
        ttk.Label(frame, text="Ink Color:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.ink_color_var = tk.StringVar(value="dark_brown")
        ink_colors = [
            "dark_brown",      # (44, 36, 22)  – original
            "black",           # (15, 10, 10)
            "faded_brown",     # (80, 65, 45)
            "iron_gall",       # (35, 30, 50)  – blueish-black
            "sepia",           # (90, 60, 30)
            "charcoal",        # (50, 48, 46)
        ]
        self._ink_color_combo = ttk.Combobox(
            frame, textvariable=self.ink_color_var,
            values=ink_colors, state="readonly", width=25,
        )
        self._ink_color_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2)

        # Ink color swatch label (preview)
        self._ink_swatch_label = ttk.Label(frame, text="■ (44, 36, 22)",
                                           font=("TkDefaultFont", 8), foreground="gray")
        self._ink_swatch_label.grid(row=4, column=2, sticky=tk.W, padx=5)

    # ------------------------------------------------------------------
    # Ink colour mapping
    # ------------------------------------------------------------------
    INK_COLOR_MAP = {
        "dark_brown":  (44, 36, 22),
        "black":       (15, 10, 10),
        "faded_brown": (80, 65, 45),
        "iron_gall":   (35, 30, 50),
        "sepia":       (90, 60, 30),
        "charcoal":    (50, 48, 46),
    }

    def _get_ink_color_rgb(self) -> tuple:
        """Return the (R, G, B) tuple for the currently selected ink colour."""
        return self.INK_COLOR_MAP.get(self.ink_color_var.get(), (44, 36, 22))

    def _update_cm_labels(self, *_args):
        """Refresh the ≈ cm helper labels next to the spinboxes."""
        try:
            sx = self.start_x_var.get()
            self._start_x_cm_label.config(text=f"≈ {self._px_to_cm(sx):.2f} cm from left")
        except tk.TclError:
            pass
        try:
            sy = self.start_y_var.get()
            self._start_y_cm_label.config(text=f"≈ {self._px_to_cm(sy):.2f} cm from top")
        except tk.TclError:
            pass
        try:
            rm = self.right_margin_var.get()
            self._right_margin_cm_label.config(text=f"≈ {self._px_to_cm(rm):.2f} cm from right")
        except tk.TclError:
            pass
        try:
            bm = self.bottom_margin_var.get()
            self._bottom_margin_cm_label.config(text=f"≈ {self._px_to_cm(bm):.2f} cm from bottom")
        except tk.TclError:
            pass
        try:
            rgb = self._get_ink_color_rgb()
            self._ink_swatch_label.config(text=f"■ {rgb}")
        except tk.TclError:
            pass

    def setup_preview(self, parent):
        """Setup preview area - fits entire A4 page without scrolling"""
        # Create canvas frame
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas sized to fit A4 ratio (800x1100) scaled down to fit in window
        # Height ~750px to leave room for buttons, width proportional
        self.preview_canvas = tk.Canvas(canvas_frame, width=550, height=750, bg='#e0e0e0')
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)

    def setup_buttons(self, parent):
        """Setup action buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Generate Preview",
                  command=self.generate_preview, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Image",
                  command=self.save_image, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export COCO",
                  command=self.export_annotations, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export YOLO",
                  command=self.export_yolo_annotations, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stats",
                  command=self.show_stats, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fonts",
                  command=self.show_font_stats, width=15).pack(side=tk.LEFT, padx=5)

    def _bind_config_change_listeners(self):
        """Bind change listeners to all config widgets for real-time preview"""
        # Paper config listeners (invalidate paper cache, keep cipher cache)
        self.aging_var.trace_add('write', self._on_paper_config_change)
        self.paper_type_var.trace_add('write', self._on_paper_config_change)
        for var in self.defect_vars.values():
            var.trace_add('write', self._on_paper_config_change)

        # Cipher config listeners (content change - invalidate cache)
        self.cipher_type_var.trace_add('write', self._on_cipher_config_change)
        self.key_type_var.trace_add('write', self._on_cipher_config_change)
        # num_entries uses visual change - smart caching handles add/remove entries
        self.num_entries_var.trace_add('write', self._on_visual_config_change)

        # Font config listeners (visual only - use cached entries)
        self.font_selection_var.trace_add('write', self._on_visual_config_change)
        self.variation_level_var.trace_add('write', self._on_visual_config_change)
        self.col_sep_var.trace_add('write', self._on_visual_config_change)
        # Per-section font sizes (visual only)
        self.cp_font_size_var.trace_add('write', self._on_visual_config_change)
        self.table_font_size_var.trace_add('write', self._on_visual_config_change)
        self.key_sep_var.trace_add('write', self._on_visual_config_change)
        self.dash_count_var.trace_add('write', self._on_visual_config_change)
        self.spacing_var.trace_add('write', self._on_visual_config_change)

        # Include-section toggles (visual — just re-render, caches are fine)
        self.include_column_pairs_var.trace_add('write', self._on_visual_config_change)
        self.include_table_codes_var.trace_add('write', self._on_visual_config_change)

        # Table codes: content-changing settings invalidate the code-table cache
        self.table_content_var.trace_add('write', self._on_table_content_change)
        self.table_num_codes_var.trace_add('write', self._on_table_content_change)
        self.table_common_boost_var.trace_add('write', self._on_table_content_change)
        self.table_common_codes_var.trace_add('write', self._on_table_content_change)
        # Column spacing and vertical lines only affect layout/visuals
        self.table_col_spacing_var.trace_add('write', self._on_visual_config_change)
        self.table_vertical_lines_var.trace_add('write', self._on_visual_config_change)

        # Layout & ink listeners (visual only)
        self.start_x_var.trace_add('write', self._on_layout_config_change)
        self.start_y_var.trace_add('write', self._on_layout_config_change)
        self.right_margin_var.trace_add('write', self._on_layout_config_change)
        self.bottom_margin_var.trace_add('write', self._on_layout_config_change)
        self.ink_color_var.trace_add('write', self._on_layout_config_change)

    def _on_visual_config_change(self, *args):
        """Called when visual config changes - uses all cached data"""
        self._schedule_debounced_regenerate()

    def _on_layout_config_change(self, *args):
        """Called when layout/ink config changes - update cm labels and re-render."""
        self._update_cm_labels()
        self._schedule_debounced_regenerate()

    def _on_paper_config_change(self, *args):
        """Called when paper config changes - invalidates paper cache only"""
        self._invalidate_paper_cache()
        self._schedule_debounced_regenerate()

    def _on_cipher_config_change(self, *args):
        """Called when cipher config changes - invalidates cipher cache and regenerates"""
        self._invalidate_cipher_cache()
        self._schedule_debounced_regenerate()

    def _invalidate_cipher_cache(self):
        """Invalidate the cached cipher entries"""
        self._cached_cipher_entries = None

    def _invalidate_paper_cache(self):
        """Invalidate the cached paper image"""
        self._cached_paper_image = None

    def _on_table_content_change(self, *args):
        """Called when table content settings change — invalidates code-table cache."""
        self._invalidate_code_table_cache()
        self._schedule_debounced_regenerate()

    def _invalidate_code_table_cache(self):
        """Clear the cached symbol→codes assignment."""
        self._cached_code_table = None
        self._cached_code_table_key = None

    def _schedule_debounced_regenerate(self):
        """Schedule a debounced regeneration (only if user has generated at least once)"""
        if not self._preview_generated_once:
            return

        # Cancel any pending regeneration
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        # Schedule new regeneration after delay
        self._debounce_timer = threading.Timer(
            self._debounce_delay,
            self._debounced_regenerate
        )
        self._debounce_timer.start()

    def _debounced_regenerate(self):
        """Called after debounce delay - schedules regeneration on main thread"""
        # Schedule on main thread (tkinter requirement)
        self.root.after(0, self._regenerate_preview_silent)

    def _regenerate_preview_silent(self):
        """Regenerate preview without showing success message box"""
        if self._is_generating:
            return  # Skip if already generating

        try:
            self._do_generate(show_message=False)
        except Exception as e:
            # Silent fail for real-time updates - just print to console
            print(f"[Preview] Generation error: {e}")

    def generate_preview(self):
        """Generate preview of cipher document (manual button click)

        This regenerates everything fresh: new paper defects and new cipher entries.
        """
        try:
            # Invalidate all caches to get completely fresh document
            self._invalidate_cipher_cache()
            self._invalidate_paper_cache()
            self._invalidate_code_table_cache()
            self._do_generate(show_message=True)
            # Enable auto-regeneration on future config changes
            self._preview_generated_once = True
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"Failed to generate preview:\n{str(e)}\n\n{traceback.format_exc()}")

    def _do_generate(self, show_message: bool = True):
        """Core generation logic - reusable for both manual and auto-regeneration"""
        self._is_generating = True

        try:
            # Get selected font
            font_selection = self.font_selection_var.get()
            if font_selection == "Random":
                selected_font_path = self.font_manager.get_random_font()
            elif font_selection == "System Default (No custom fonts found)":
                selected_font_path = None
            else:
                selected_font_path = self.font_manager.get_font_by_name(font_selection)

            # Get variation level
            variation_level = self.variation_level_var.get()
            use_variations = variation_level != 'none'

            # Create configurations
            paper_config = PaperConfig(
                aging_level=self.aging_var.get(),
                paper_type=self.paper_type_var.get(),
                defects=[k for k, v in self.defect_vars.items() if v.get()],
                width=800,
                height=1100
            )

            font_config = FontConfig(
                font_name="custom",
                font_size=self.cp_font_size_var.get(),
                column_separator=self.col_sep_var.get(),
                key_separator=self.key_sep_var.get(),
                dash_count=self.dash_count_var.get(),
                spacing=self.spacing_var.get(),
                language="latin"
            )

            # Create generator with variation level
            generator = CipherImageGenerator(paper_config, font_config, variation_level)

            # Store generator instance for later use
            self.current_generator = generator

            # Register the preview image
            filename = "preview.png"
            generator.register_image(filename)

            # Get current paper config state
            current_aging = self.aging_var.get()
            current_paper_type = self.paper_type_var.get()
            current_defects = frozenset(k for k, v in self.defect_vars.items() if v.get())

            # Check if we can use cached paper image
            if (self._cached_paper_image is not None
                and self._cached_paper_aging == current_aging
                and self._cached_paper_type == current_paper_type
                and self._cached_paper_defects == current_defects):
                # Use cached paper (make a copy so text rendering doesn't affect cache)
                img = self._cached_paper_image.copy()
            else:
                # Generate new paper and cache it
                img = generator.create_aged_paper()
                self._cached_paper_image = img.copy()
                self._cached_paper_aging = current_aging
                self._cached_paper_type = current_paper_type
                self._cached_paper_defects = current_defects

            include_table = self.include_table_codes_var.get()
            include_pairs = self.include_column_pairs_var.get()

            # Read layout settings
            start_x = self.start_x_var.get()
            start_y = self.start_y_var.get()
            right_margin = self.right_margin_var.get()
            bottom_margin = self.bottom_margin_var.get()
            ink_color = self._get_ink_color_rgb()

            # Track current Y so table and pairs stack vertically on same page
            current_y = start_y

            # ── Table codes (rendered first, at top of page) ─────────────
            if include_table:
                table_config = self._build_table_config()
                code_table = self._get_or_generate_code_table(table_config)
                current_y = generator.render_table_codes(
                    img, table_config, start_x, current_y,
                    font_path=selected_font_path,
                    use_variations=use_variations,
                    track_annotations=True,
                    code_table=code_table,
                    font_size=self.table_font_size_var.get(),
                    ink_color=ink_color,
                )
                # Add a gap between table and column pairs
                current_y += self.spacing_var.get() * 4

            # ── Column pairs (rendered below table, or from top if no table) ──
            if include_pairs:
                cipher_entries = self._get_cipher_entries()
                generator.render_cipher_text(
                    img, cipher_entries, start_x, current_y,
                    block_id=1,
                    font_path=selected_font_path,
                    use_variations=use_variations,
                    track_annotations=True,
                    right_margin=right_margin,
                    bottom_margin=bottom_margin,
                    ink_color=ink_color,
                )

            # Mark font as used (for statistics)
            if selected_font_path:
                self.font_manager.mark_font_used(selected_font_path, self.db)

            # Store for saving
            self.preview_image = img

            # Display preview
            self._display_preview(img)

            # Show success message only if requested (manual generation)
            if show_message:
                stats = generator.get_annotation_stats()
                variation_info = f" with {variation_level} variations" if use_variations else ""
                font_info = f" using {font_selection}" if selected_font_path else ""
                parts = []
                if include_table:
                    parts.append("table codes")
                if include_pairs:
                    parts.append("column pairs")
                layout_info = " [" + " + ".join(parts) + "]" if parts else " [nothing selected]"
                ann_info = (
                    f"\n\nAnnotations: {stats['total_annotations']} "
                    f"({stats.get('annotations_per_category', {}).get('element', 0)} elements, "
                    f"{stats.get('annotations_per_category', {}).get('pair', 0)} cells/pairs, "
                    f"{stats.get('annotations_per_category', {}).get('section', 0)} sections)"
                )
                messagebox.showinfo(
                    "Success",
                    f"Preview generated{font_info}{variation_info}{layout_info}!{ann_info}",
                )

        finally:
            self._is_generating = False

    def _get_cipher_entries(self) -> List[Tuple[str, str]]:
        """Get cipher entries from database (with smart caching for consistent preview)

        Caching behavior:
        - If cipher_type or key_type changes: regenerate all entries
        - If num_entries decreases: return first N from cache
        - If num_entries increases: keep existing, generate only the new ones
        """
        cipher_type = self.cipher_type_var.get()
        num_entries = self.num_entries_var.get()
        key_type = self.key_type_var.get()

        # Check if cipher type or key type changed (requires full regeneration)
        if (self._cached_cipher_entries is not None
            and self._cached_cipher_type == cipher_type
            and self._cached_key_type == key_type):

            cached_count = len(self._cached_cipher_entries)

            if num_entries <= cached_count:
                # Just return first N entries from cache
                return self._cached_cipher_entries[:num_entries]
            else:
                # Need more entries - keep existing and generate additional ones
                entries = list(self._cached_cipher_entries)  # Copy existing
                additional_needed = num_entries - cached_count

                words = self.db.get_cipher_keys(cipher_type)
                if words:
                    for i in range(additional_needed):
                        word = random.choice(words)
                        key_num = self._generate_key_number(cipher_type)
                        entries.append((word, str(key_num)))
                else:
                    # Fallback for empty database
                    for i in range(additional_needed):
                        entries.append((f"Sample{cached_count + i}", str(100 + cached_count + i)))

                # Update cache with extended entries
                self._cached_cipher_entries = entries
                self._cached_num_entries = num_entries
                return entries

        # Full regeneration needed (type changed or no cache)
        words = self.db.get_cipher_keys(cipher_type)

        if not words:
            # Generate sample entries if database is empty
            entries = [(f"Sample{i}", str(100 + i)) for i in range(num_entries)]
        else:
            # Create entries: word + random key number
            entries = []
            for i in range(num_entries):
                word = random.choice(words)
                key_num = self._generate_key_number(cipher_type)
                entries.append((word, str(key_num)))

        # Cache the entries and config state
        self._cached_cipher_entries = entries
        self._cached_cipher_type = cipher_type
        self._cached_num_entries = num_entries
        self._cached_key_type = key_type

        return entries

    def _build_table_config(self) -> TableCodesConfig:
        """Build a TableCodesConfig from the current GUI state."""
        return TableCodesConfig(
            content_type=self.table_content_var.get(),
            num_codes=self.table_num_codes_var.get(),
            use_common_boost=self.table_common_boost_var.get(),
            common_codes=self.table_common_codes_var.get(),
            draw_vertical_lines=self.table_vertical_lines_var.get(),
            column_spacing=self.table_col_spacing_var.get(),
        )

    def _get_or_generate_code_table(self, table_config: TableCodesConfig) -> dict:
        """Return a cached symbol→codes assignment, generating one if needed.

        The cache is keyed on (content_type, num_codes, use_common_boost,
        common_codes) — only content-defining settings.  Visual settings
        (font size, symbols per row, variation level, …) do NOT trigger
        regeneration, so changing font size won't reshuffle all the numbers.
        """
        from src.generators.table_codes_generator import TableCodesGenerator

        cache_key = (
            table_config.content_type,
            table_config.num_codes,
            table_config.use_common_boost,
            table_config.common_codes,
        )

        if self._cached_code_table is not None and self._cached_code_table_key == cache_key:
            return self._cached_code_table

        # Generate fresh code table
        gen = TableCodesGenerator(
            config=table_config,
            font_size=self.table_font_size_var.get(),
            spacing=self.spacing_var.get(),
        )
        code_table = gen.generate_code_table()

        self._cached_code_table = code_table
        self._cached_code_table_key = cache_key
        return code_table

    def _generate_key_number(self, cipher_type: str) -> int:
        """Generate a random key number based on cipher type"""
        if cipher_type == 'substitution':
            return random.randint(100, 250)
        elif cipher_type == 'bigram':
            return random.randint(70, 99)
        elif cipher_type == 'trigram':
            return random.randint(170, 199)
        elif cipher_type == 'dictionary':
            return random.randint(300, 350)
        elif cipher_type == 'nulls':
            return random.randint(900, 950)
        else:
            return random.randint(100, 200)

    def _display_preview(self, img: Image.Image):
        """Display preview image on canvas - scaled to fit entirely"""
        # Get canvas dimensions
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()

        # Fallback if canvas not yet rendered
        if canvas_width <= 1:
            canvas_width = 550
        if canvas_height <= 1:
            canvas_height = 750

        # Calculate scale to fit image within canvas (maintain aspect ratio)
        width_ratio = canvas_width / img.width
        height_ratio = canvas_height / img.height
        scale = min(width_ratio, height_ratio) * 0.95  # 95% to add small margin

        display_width = int(img.width * scale)
        display_height = int(img.height * scale)

        preview_img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(preview_img)

        # Clear canvas
        self.preview_canvas.delete("all")

        # Center image on canvas
        x_offset = (canvas_width - display_width) // 2
        y_offset = (canvas_height - display_height) // 2

        # Display image centered
        self.preview_canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=photo)
        self.preview_canvas.image = photo  # Keep reference

    def save_image(self):
        """Save generated image"""
        if self.preview_image is None:
            messagebox.showwarning("Warning", "Please generate a preview first!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            try:
                self.preview_image.save(file_path)
                messagebox.showinfo("Success", f"Image saved to:\n{file_path}\n\nYou can now export COCO annotations.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image:\n{str(e)}")

    def export_annotations(self):
        """Export COCO annotations"""
        if self.current_generator is None:
            messagebox.showwarning("Warning",
                                 "No annotations to export!\nGenerate a preview first.")
            return

        stats = self.current_generator.get_annotation_stats()
        if stats['total_annotations'] == 0:
            messagebox.showwarning("Warning",
                                 "No annotations collected!\nMake sure you generated a preview with variations enabled.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="annotations.json"
        )

        if file_path:
            try:
                self.current_generator.export_coco_annotations(file_path)

                # Show detailed stats
                ann_per_cat = stats.get('annotations_per_category', {})
                detail_msg = f"COCO annotations exported successfully!\n\n"
                detail_msg += f"Total images: {stats['total_images']}\n"
                detail_msg += f"Total annotations: {stats['total_annotations']}\n\n"
                detail_msg += "Breakdown:\n"
                detail_msg += f"  • Elements (characters): {ann_per_cat.get('element', 0)}\n"
                detail_msg += f"  • Pairs (bigrams): {ann_per_cat.get('pair', 0)}\n"
                detail_msg += f"  • Sections (lines): {ann_per_cat.get('section', 0)}\n"

                messagebox.showinfo("Success", detail_msg)
            except Exception as e:
                import traceback
                messagebox.showerror("Error",
                                   f"Failed to export annotations:\n{str(e)}\n\n{traceback.format_exc()}")

    def export_yolo_annotations(self):
        """Export YOLO format annotations to a directory."""
        if self.current_generator is None:
            messagebox.showwarning("Warning",
                                   "No annotations to export!\nGenerate a preview first.")
            return

        stats = self.current_generator.get_annotation_stats()
        if stats["total_annotations"] == 0:
            messagebox.showwarning("Warning",
                                   "No annotations collected!\n"
                                   "Make sure you generated a preview with variations enabled.")
            return

        output_dir = filedialog.askdirectory(title="Select output directory for YOLO annotations")
        if not output_dir:
            return

        try:
            yolo_path = self.current_generator.export_yolo_annotations(
                output_dir, "preview.png"
            )
            messagebox.showinfo(
                "Success",
                f"YOLO annotations exported!\n\n"
                f"Annotation file: {yolo_path}\n"
                f"Classes file: {os.path.join(output_dir, 'classes.txt')}\n\n"
                f"Total annotations: {stats['total_annotations']}",
            )
        except Exception as e:
            import traceback
            messagebox.showerror(
                "Error",
                f"Failed to export YOLO annotations:\n{str(e)}\n\n{traceback.format_exc()}",
            )

    def show_stats(self):
        """Show dataset statistics"""
        if self.current_generator is None:
            messagebox.showinfo("Statistics", "No data yet. Generate a preview first!")
            return

        stats = self.current_generator.get_annotation_stats()
        ann_per_cat = stats.get('annotations_per_category', {})

        message = f"""Dataset Statistics:
        
Total Images: {stats['total_images']}
Total Annotations: {stats['total_annotations']}
Categories: {stats['categories']}

Annotations by Category:
  • Elements (characters): {ann_per_cat.get('element', 0)}
  • Pairs (bigrams): {ann_per_cat.get('pair', 0)}
  • Sections (lines): {ann_per_cat.get('section', 0)}
"""
        messagebox.showinfo("Dataset Statistics", message)

    def show_font_stats(self):
        """Show font usage statistics"""
        if not self.font_manager.has_fonts():
            messagebox.showinfo("Font Statistics",
                              "No custom fonts loaded.\n\nAdd .ttf or .otf files to 'fonts/handwritten' directory.")
            return

        stats = self.font_manager.get_font_stats(self.db)

        if not stats:
            message = f"Available Fonts: {len(self.font_manager.available_fonts)}\n\n"
            message += "Fonts not yet used:\n"
            for font_name in self.font_manager.get_all_font_names():
                message += f"  • {font_name}\n"
        else:
            message = "Font Usage Statistics:\n\n"
            for stat in stats:
                last_used = stat['last_used'] if stat['last_used'] else 'Never'
                message += f"• {stat['name']}\n"
                message += f"  Times used: {stat['times_used']}\n"
                message += f"  Last used: {last_used}\n\n"

        messagebox.showinfo("Font Statistics", message)