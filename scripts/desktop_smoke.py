"""Launch the real Tk workspace once, then close it without a user display."""

import tkinter as tk

from review_core.desktop import main


def _smoke_mainloop(root: tk.Tk, *args: object, **kwargs: object) -> None:
    root.update_idletasks()
    root.update()
    root.destroy()


def run() -> int:
    original = tk.Tk.mainloop
    tk.Tk.mainloop = _smoke_mainloop
    try:
        return main()
    finally:
        tk.Tk.mainloop = original


if __name__ == "__main__":
    raise SystemExit(run())
