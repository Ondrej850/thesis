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
from src.database.database_manager import DatabaseManager
from src.generators.image_generator import CipherImageGenerator
from src.annotations.coco_manager import COCOAnnotationManager
from src.database.font_manager import FontManager


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

        # Real-time preview: debounce timer for config changes
        self._debounce_timer = None
        self._debounce_delay = 0.3  # 300ms delay before regenerating
        self._is_generating = False  # Prevent concurrent generations

        # Cached cipher entries for consistent preview during visual changes
        self._cached_cipher_entries = None
        self._cached_cipher_type = None
        self._cached_num_entries = None
        self._cached_key_type = None

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

        # Left panel - Configuration
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)

        # Right panel - Preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)

        # Setup sections
        self.setup_paper_config(config_frame)
        self.setup_cipher_config(config_frame)
        self.setup_font_config(config_frame)
        self.setup_preview(preview_frame)
        self.setup_buttons(main_frame)

    def setup_paper_config(self, parent):
        """Setup paper configuration section"""
        frame = ttk.LabelFrame(parent, text="1. Paper Configuration", padding="5")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        frame.columnconfigure(1, weight=1)

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
        """Setup cipher configuration section"""
        frame = ttk.LabelFrame(parent, text="2. Cipher Configuration", padding="5")
        frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        frame.columnconfigure(1, weight=1)

        # Cipher type
        ttk.Label(frame, text="Cipher Type:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cipher_type_var = tk.StringVar(value="substitution")
        cipher_types = ['substitution', 'bigram', 'trigram', 'dictionary', 'nulls']
        cipher_combo = ttk.Combobox(frame, textvariable=self.cipher_type_var,
                                   values=cipher_types, state='readonly', width=25)
        cipher_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)

        # Key type
        ttk.Label(frame, text="Key Type:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.key_type_var = tk.StringVar(value="number")
        key_types = ['number', 'special_character']
        key_combo = ttk.Combobox(frame, textvariable=self.key_type_var,
                                values=key_types, state='readonly', width=25)
        key_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        # Number of entries
        ttk.Label(frame, text="Number of Entries:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.num_entries_var = tk.IntVar(value=30)
        ttk.Spinbox(frame, from_=5, to=100, textvariable=self.num_entries_var,
                   width=10).grid(row=2, column=1, sticky=tk.W, pady=2)

    def setup_font_config(self, parent):
        """Setup font configuration section"""
        frame = ttk.LabelFrame(parent, text="3. Font Configuration", padding="5")
        frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        frame.columnconfigure(1, weight=1)

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

        # Font size
        ttk.Label(frame, text="Font Size:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.font_size_var = tk.IntVar(value=14)
        ttk.Spinbox(frame, from_=10, to=24, textvariable=self.font_size_var,
                    width=10).grid(row=2, column=1, sticky=tk.W, pady=2)

        # Column separator
        ttk.Label(frame, text="Column Separator:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.col_sep_var = tk.StringVar(value="line")
        col_seps = ['none', 'line', 'double_line']
        ttk.Combobox(frame, textvariable=self.col_sep_var, values=col_seps,
                     state='readonly', width=25).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2)

        # Key separator
        ttk.Label(frame, text="Key Separator:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.key_sep_var = tk.StringVar(value="dashes")
        key_seps = ['dots', 'dashes', 'none']
        ttk.Combobox(frame, textvariable=self.key_sep_var, values=key_seps,
                     state='readonly', width=25).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2)

        # Dash count
        ttk.Label(frame, text="Dash Count:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.dash_count_var = tk.IntVar(value=3)
        ttk.Spinbox(frame, from_=1, to=10, textvariable=self.dash_count_var,
                    width=10).grid(row=5, column=1, sticky=tk.W, pady=2)

        # Spacing
        ttk.Label(frame, text="Line Spacing:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.spacing_var = tk.IntVar(value=8)
        ttk.Spinbox(frame, from_=5, to=20, textvariable=self.spacing_var,
                    width=10).grid(row=6, column=1, sticky=tk.W, pady=2)

    def setup_preview(self, parent):
        """Setup preview area"""
        # Create canvas with scrollbars
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.preview_canvas = tk.Canvas(canvas_frame, width=800, height=700, bg='white')

        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                   command=self.preview_canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL,
                                   command=self.preview_canvas.xview)

        self.preview_canvas.configure(yscrollcommand=v_scrollbar.set,
                                     xscrollcommand=h_scrollbar.set)

        # Pack scrollbars and canvas
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def setup_buttons(self, parent):
        """Setup action buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="🔄 Generate Preview",
                  command=self.generate_preview, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Save Image",
                  command=self.save_image, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📊 Export COCO",
                  command=self.export_annotations, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📈 Stats",
                  command=self.show_stats, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔤 Fonts",
                  command=self.show_font_stats, width=15).pack(side=tk.LEFT, padx=5)

    def _bind_config_change_listeners(self):
        """Bind change listeners to all config widgets for real-time preview"""
        # Paper config listeners (visual only - use cached entries)
        self.aging_var.trace_add('write', self._on_visual_config_change)
        self.paper_type_var.trace_add('write', self._on_visual_config_change)
        for var in self.defect_vars.values():
            var.trace_add('write', self._on_visual_config_change)

        # Cipher config listeners (content change - invalidate cache)
        self.cipher_type_var.trace_add('write', self._on_cipher_config_change)
        self.key_type_var.trace_add('write', self._on_cipher_config_change)
        # num_entries uses visual change - smart caching handles add/remove entries
        self.num_entries_var.trace_add('write', self._on_visual_config_change)

        # Font config listeners (visual only - use cached entries)
        self.font_selection_var.trace_add('write', self._on_visual_config_change)
        self.variation_level_var.trace_add('write', self._on_visual_config_change)
        self.font_size_var.trace_add('write', self._on_visual_config_change)
        self.col_sep_var.trace_add('write', self._on_visual_config_change)
        self.key_sep_var.trace_add('write', self._on_visual_config_change)
        self.dash_count_var.trace_add('write', self._on_visual_config_change)
        self.spacing_var.trace_add('write', self._on_visual_config_change)

    def _on_visual_config_change(self, *args):
        """Called when visual config changes - uses cached cipher entries"""
        self._schedule_debounced_regenerate()

    def _on_cipher_config_change(self, *args):
        """Called when cipher config changes - invalidates cache and regenerates"""
        self._invalidate_cipher_cache()
        self._schedule_debounced_regenerate()

    def _invalidate_cipher_cache(self):
        """Invalidate the cached cipher entries"""
        self._cached_cipher_entries = None

    def _schedule_debounced_regenerate(self):
        """Schedule a debounced regeneration"""
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

        This also regenerates cipher entries (new random words/keys).
        """
        try:
            # Invalidate cache to get fresh entries on manual generation
            self._invalidate_cipher_cache()
            self._do_generate(show_message=True)
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
                font_size=self.font_size_var.get(),
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

            # Generate base image
            img = generator.create_aged_paper()

            # Get cipher entries from database
            cipher_entries = self._get_cipher_entries()

            # Render cipher text with variations and annotation tracking
            generator.render_cipher_text(
                img, cipher_entries, 50, 50,
                block_id=1,
                font_path=selected_font_path,
                use_variations=use_variations,
                track_annotations=True  # Always track for COCO export
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
                ann_info = f"\n\nAnnotations: {stats['total_annotations']} " \
                          f"({stats.get('annotations_per_category', {}).get('element', 0)} elements, " \
                          f"{stats.get('annotations_per_category', {}).get('pair', 0)} pairs, " \
                          f"{stats.get('annotations_per_category', {}).get('section', 0)} sections)"

                messagebox.showinfo("Success", f"Preview generated{font_info}{variation_info}!{ann_info}")

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
        """Display preview image on canvas"""
        # Resize for preview if needed
        display_width = 800
        ratio = display_width / img.width
        display_height = int(img.height * ratio)

        preview_img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(preview_img)

        # Clear canvas
        self.preview_canvas.delete("all")

        # Display image
        self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.preview_canvas.image = photo  # Keep reference

        # Update scroll region
        self.preview_canvas.configure(scrollregion=(0, 0, display_width, display_height))

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