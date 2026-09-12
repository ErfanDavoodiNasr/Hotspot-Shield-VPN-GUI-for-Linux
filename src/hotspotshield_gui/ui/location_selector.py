"""Searchable location selector."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from hotspotshield_gui.models.location import Location
from hotspotshield_gui.ui.theme import Theme


class LocationSelector(ttk.Frame):
    """Modern searchable location list with keyboard navigation."""

    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        *,
        on_select: Callable[[Location], None] | None = None,
        on_activate: Callable[[Location], None] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(master, style="Card.TFrame", **kwargs)  # type: ignore[arg-type]
        self.theme = theme
        self.on_select = on_select
        self.on_activate = on_activate
        self._all: list[Location] = []
        self._filtered: list[Location] = []
        self._current_code: str | None = None
        self._loading = False

        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(header, text="Location", style="Card.TLabel").pack(side=tk.LEFT)
        self.count_label = ttk.Label(header, text="", style="CardMuted.TLabel")
        self.count_label.pack(side=tk.RIGHT)

        search_row = ttk.Frame(self, style="Card.TFrame")
        search_row.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, style="Search.TEntry")
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self._on_query)
        self.search_entry.bind("<Down>", self._focus_list)
        self.search_entry.bind("<Return>", self._activate_selected)
        self.search_entry.bind("<Escape>", self._clear_query)

        self.clear_btn = ttk.Button(search_row, text="Clear", style="Ghost.TButton", command=self._clear_query)
        self.clear_btn.pack(side=tk.LEFT, padx=(8, 0))

        list_frame = ttk.Frame(self, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.listbox = tk.Listbox(
            list_frame,
            activestyle="dotbox",
            exportselection=False,
            highlightthickness=1,
            highlightcolor=theme.focus,
            highlightbackground=theme.border,
            selectbackground=theme.accent,
            selectforeground=theme.accent_fg,
            bg=theme.input_bg,
            fg=theme.input_fg,
            font=("TkDefaultFont", 11),
            borderwidth=0,
            relief=tk.FLAT,
        )
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.listbox.bind("<Double-Button-1>", self._activate_selected)
        self.listbox.bind("<Return>", self._activate_selected)
        self.listbox.bind("<Escape>", lambda _e: self.search_entry.focus_set())

        self.empty_label = ttk.Label(
            self,
            text="",
            style="CardMuted.TLabel",
            wraplength=360,
            justify=tk.CENTER,
        )

        self.retry_btn = ttk.Button(self, text="Retry", style="Ghost.TButton")

    def set_locations(self, locations: list[Location], *, current_code: str | None = None) -> None:
        self._all = list(locations)
        self._current_code = current_code
        self._loading = False
        self._apply_filter(self.search_var.get())

    def set_loading(self, message: str = "Loading locations…") -> None:
        self._loading = True
        self.listbox.delete(0, tk.END)
        self.empty_label.configure(text=message)
        self.empty_label.pack(fill=tk.X, padx=12, pady=8)
        self.retry_btn.pack_forget()
        self.count_label.configure(text="")

    def set_error(self, message: str, *, on_retry: Callable[[], None] | None = None) -> None:
        self._loading = False
        self.listbox.delete(0, tk.END)
        self.empty_label.configure(text=message)
        self.empty_label.pack(fill=tk.X, padx=12, pady=8)
        if on_retry:
            self.retry_btn.configure(command=on_retry)
            self.retry_btn.pack(pady=(0, 12))
        self.count_label.configure(text="Unavailable")

    def selected_location(self) -> Location | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        idx = int(selection[0])
        if 0 <= idx < len(self._filtered):
            return self._filtered[idx]
        return None

    def select_code(self, code: str | None) -> None:
        if not code:
            return
        for idx, loc in enumerate(self._filtered):
            if loc.code == code:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(idx)
                self.listbox.see(idx)
                self.listbox.activate(idx)
                return

    def focus_search(self) -> None:
        self.search_entry.focus_set()

    def _clear_query(self, _event: object | None = None) -> str:
        self.search_var.set("")
        self._apply_filter("")
        return "break"

    def _on_query(self, _event: object | None = None) -> None:
        self._apply_filter(self.search_var.get())

    def _apply_filter(self, query: str) -> None:
        if self._loading:
            return
        self.empty_label.pack_forget()
        self.retry_btn.pack_forget()
        q = query.strip()
        self._filtered = [loc for loc in self._all if loc.matches_query(q)]
        self.listbox.delete(0, tk.END)
        for loc in self._filtered:
            marker = " ●" if self._current_code and loc.code == self._current_code else ""
            self.listbox.insert(tk.END, f"{loc.display}{marker}")
        self.count_label.configure(text=f"{len(self._filtered)} / {len(self._all)}")
        if not self._filtered:
            msg = "No locations match your search." if self._all else "No locations available."
            self.empty_label.configure(text=msg)
            self.empty_label.pack(fill=tk.X, padx=12, pady=8)
        elif self._current_code:
            self.select_code(self._current_code)

    def _on_list_select(self, _event: object | None = None) -> None:
        loc = self.selected_location()
        if loc and self.on_select:
            self.on_select(loc)

    def _focus_list(self, _event: object | None = None) -> str:
        if self._filtered:
            self.listbox.focus_set()
            if not self.listbox.curselection():
                self.listbox.selection_set(0)
                self.listbox.activate(0)
        return "break"

    def _activate_selected(self, _event: object | None = None) -> str:
        loc = self.selected_location()
        if loc is None and self._filtered:
            self.listbox.selection_set(0)
            loc = self.selected_location()
        if loc:
            if self.on_select:
                self.on_select(loc)
            if self.on_activate:
                self.on_activate(loc)
        return "break"
