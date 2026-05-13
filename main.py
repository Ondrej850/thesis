"""
Historical Cipher Generator
Main entry point for the application
"""

import sys
import tkinter as tk

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from src.gui.main_window import CipherGeneratorGUI


def main():
    root = tk.Tk()
    app = CipherGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
