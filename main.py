"""
Historical Cipher Generator
Main entry point for the application
"""

import os
import sys

if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    python_root = sys.base_prefix  # system Python
    os.environ['TCL_LIBRARY'] = r"C:\Users\palenond\AppData\Local\Programs\Python\Python311\tcl\tcl8.6"
    os.environ['TK_LIBRARY'] = r"C:\Users\palenond\AppData\Local\Programs\Python\Python311\tcl\tk8.6"

import tkinter as tk

from src.gui.main_window import CipherGeneratorGUI


def main():
    """Main application entry point"""
    root = tk.Tk()
    app = CipherGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()