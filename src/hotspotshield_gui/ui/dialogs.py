"""Modal dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.ui.theme import Theme


class CredentialsDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        *,
        initial: Credentials | None = None,
        title: str = "Sign in to Hotspot Shield",
    ) -> None:
        super().__init__(master)
        self.theme = theme
        self.result: Credentials | None = None
        self.title(title)
        self.configure(bg=theme.bg)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, style="App.TFrame", padding=20)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Account", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(
            frame,
            text="Enter your Hotspot Shield Premium credentials.",
            style="Muted.TLabel",
            wraplength=360,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))

        ttk.Label(frame, text="Email", style="App.TLabel").grid(row=2, column=0, sticky="w")
        self.username_var = tk.StringVar(value=initial.username if initial else "")
        user_entry = ttk.Entry(frame, textvariable=self.username_var, width=36, style="Search.TEntry")
        user_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        ttk.Label(frame, text="Password", style="App.TLabel").grid(row=4, column=0, sticky="w")
        self.password_var = tk.StringVar(value="")
        pass_entry = ttk.Entry(
            frame, textvariable=self.password_var, show="•", width=36, style="Search.TEntry"
        )
        pass_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 16))

        btns = ttk.Frame(frame, style="App.TFrame")
        btns.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Cancel", style="Ghost.TButton", command=self._cancel).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Button(btns, text="Save & Continue", style="Primary.TButton", command=self._ok).pack(
            side=tk.RIGHT
        )

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())
        user_entry.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_visibility()
        self.focus_force()

    def _ok(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            return
        self.result = Credentials(username=username, password=password)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ErrorDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        *,
        message: str,
        technical: str | None = None,
        title: str = "Something went wrong",
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.configure(bg=theme.bg)
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, style="App.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=message, style="App.TLabel", wraplength=420, justify=tk.LEFT).pack(
            anchor="w", pady=(12, 8)
        )
        if technical:
            details = tk.Text(
                frame,
                height=6,
                width=56,
                wrap=tk.WORD,
                bg=theme.surface_alt,
                fg=theme.muted,
                relief=tk.FLAT,
                padx=8,
                pady=8,
            )
            details.insert("1.0", technical)
            details.configure(state=tk.DISABLED)
            details.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        ttk.Button(frame, text="OK", style="Primary.TButton", command=self.destroy).pack(anchor="e")
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())
