"""Primary application window."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from hotspotshield_gui.controllers.vpn_controller import UiEvent, VpnController
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import VpnState
from hotspotshield_gui.security.secret_store import Credentials
from hotspotshield_gui.ui.components import StatusBadge, configure_styles
from hotspotshield_gui.ui.dialogs import CredentialsDialog, ErrorDialog
from hotspotshield_gui.ui.location_selector import LocationSelector
from hotspotshield_gui.ui.theme import Theme, resolve_theme

logger = logging.getLogger("hotspotshield_gui.ui.main_window")

STATE_COLORS = {
    VpnState.INITIALIZING: "muted",
    VpnState.DISCONNECTED: "muted",
    VpnState.CONNECTING: "warning",
    VpnState.VERIFYING_CONNECTION: "warning",
    VpnState.CONNECTED: "success",
    VpnState.SWITCHING_LOCATION: "warning",
    VpnState.DISCONNECTING: "warning",
    VpnState.VERIFYING_DISCONNECTION: "warning",
    VpnState.UNKNOWN: "danger",
    VpnState.ERROR: "danger",
}


class MainWindow:
    def __init__(self, root: tk.Tk, controller: VpnController, theme: Theme | None = None) -> None:
        self.root = root
        self.controller = controller
        self.theme = theme or resolve_theme(controller.settings.theme, root)
        self._alive = True
        self._current_state = VpnState.INITIALIZING
        self._can_connect = False
        self._can_disconnect = False
        self._can_cancel = False
        self._cli_connected = False
        self._busy = True

        self.root.title("Hotspot Shield")
        self.root.minsize(720, 560)
        self.root.geometry(controller.settings.window_geometry or "900x640")
        self.root.configure(bg=self.theme.bg)
        configure_styles(self.root, self.theme)

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-l>", lambda _e: self.location_selector.focus_search())
        self.root.bind("<Control-r>", lambda _e: self._safe_refresh_status())
        self._poll_events()
        self.controller.initialize()

    def _build(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=20)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=2)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        ttk.Label(header, text="Hotspot Shield", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="for Linux", style="Muted.TLabel").pack(side=tk.LEFT, padx=(8, 0))

        left = ttk.Frame(outer, style="Card.TFrame", padding=20)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

        ttk.Label(left, text="VPN STATUS", style="CardMuted.TLabel").pack(anchor="w")
        self.badge = StatusBadge(left, self.theme)
        self.badge.pack(anchor="w", pady=(8, 16))
        self.badge.set_status("Checking status…", color=self.theme.muted)

        self.selected_var = tk.StringVar(value="—")
        self.connected_var = tk.StringVar(value="—")
        self.ip_var = tk.StringVar(value="—")

        self._kv(left, "Selected location", self.selected_var)
        self._kv(left, "Current VPN location", self.connected_var)
        self._kv(left, "Public IP", self.ip_var)

        self.progress_var = tk.StringVar(value="Starting…")
        ttk.Label(left, textvariable=self.progress_var, style="CardMuted.TLabel").pack(
            anchor="w", pady=(16, 8)
        )

        self.primary_btn = ttk.Button(
            left,
            text="Connect",
            style="Primary.TButton",
            command=self._on_primary,
        )
        self.primary_btn.pack(fill=tk.X, pady=(8, 8))

        tools = ttk.Frame(left, style="Card.TFrame")
        tools.pack(fill=tk.X, pady=(8, 0))
        self.refresh_btn = ttk.Button(
            tools, text="Refresh status", style="Ghost.TButton", command=self._safe_refresh_status
        )
        self.refresh_btn.pack(side=tk.LEFT)
        ttk.Button(tools, text="Account…", style="Ghost.TButton", command=self._edit_credentials).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(tools, text="Theme", style="Ghost.TButton", command=self._toggle_theme).pack(
            side=tk.RIGHT
        )

        note = ttk.Label(
            left,
            text="Closing this window leaves the VPN connected.",
            style="CardMuted.TLabel",
            wraplength=280,
        )
        note.pack(anchor="w", pady=(20, 0))

        right = ttk.Frame(outer, style="Card.TFrame")
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.location_selector = LocationSelector(
            right,
            self.theme,
            on_select=self._on_location_selected,
            on_activate=self._on_location_activated,
        )
        self.location_selector.grid(row=0, column=0, sticky="nsew")
        self.location_selector.set_loading()

    def _kv(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        block = ttk.Frame(parent, style="Card.TFrame")
        block.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(block, text=label, style="CardMuted.TLabel").pack(anchor="w")
        ttk.Label(block, textvariable=variable, style="Card.TLabel", wraplength=280).pack(anchor="w")

    def _color_for(self, state: VpnState) -> str:
        key = STATE_COLORS.get(state, "muted")
        return {
            "muted": self.theme.muted,
            "success": self.theme.success,
            "warning": self.theme.warning,
            "danger": self.theme.danger,
        }[key]

    def _poll_events(self) -> None:
        if not self._alive:
            return
        try:
            for event in self.controller.poll_events():
                self._handle_event(event)
        except tk.TclError:
            return
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: UiEvent) -> None:
        name = event.name
        payload = event.payload
        if name == "state_changed":
            state: VpnState = payload["state"]
            self._current_state = state
            self._can_connect = bool(payload.get("can_connect"))
            self._can_disconnect = bool(payload.get("can_disconnect"))
            self._can_cancel = bool(payload.get("can_cancel"))
            self._cli_connected = bool(payload.get("cli_connected"))
            self._busy = bool(payload.get("busy"))
            self.badge.set_status(payload["label"], color=self._color_for(state))
            self._update_primary_button()
            self._update_tool_buttons()
        elif name == "progress":
            self.progress_var.set(str(payload.get("message", "")))
        elif name == "locations":
            locations: list[Location] = payload["locations"]
            current = None
            if self.controller.status_info:
                current = self.controller.status_info.connected_location_code
            self.location_selector.set_locations(locations, current_code=current)
            if self.controller.selected:
                self.location_selector.select_code(self.controller.selected.code)
                self.selected_var.set(self.controller.selected.display)
        elif name == "locations_error":
            self.location_selector.set_error(
                str(payload.get("message", "Unable to retrieve VPN locations.")),
                on_retry=self._safe_refresh_locations,
            )
        elif name == "selection":
            loc: Location = payload["location"]
            self.selected_var.set(loc.display)
            self.location_selector.select_code(loc.code)
        elif name == "status":
            info = payload["info"]
            self._cli_connected = bool(info.is_connected)
            if info.connected_location_code:
                name_part = info.connected_location_name or ""
                text = (
                    f"{info.connected_location_code} — {name_part}".strip(" —")
                    if name_part
                    else info.connected_location_code
                )
                self.connected_var.set(text)
            elif info.state is VpnState.DISCONNECTED:
                self.connected_var.set("—")
            current = info.connected_location_code
            if self.controller.locations:
                self.location_selector.set_locations(
                    self.controller.locations, current_code=current
                )
            self._update_primary_button()
        elif name == "ip":
            info = payload.get("info")
            if info is None:
                self.ip_var.set("Unavailable")
            else:
                bits = [info.ip]
                if info.city or info.country:
                    bits.append(", ".join(x for x in (info.city, info.country) if x))
                self.ip_var.set(" · ".join(bits))
        elif name == "need_credentials":
            creds = self._prompt_credentials()
            if creds:
                self.controller.save_credentials(creds)
                self.controller.connect(creds)
        elif name == "error":
            ErrorDialog(
                self.root,
                self.theme,
                message=str(payload.get("message", "An error occurred.")),
                technical=payload.get("technical"),
            )
            self._update_primary_button()
        elif name == "notice":
            self.progress_var.set(str(payload.get("message", "")))

    def _update_primary_button(self) -> None:
        state = self._current_state
        if state is VpnState.INITIALIZING or state is VpnState.DISCONNECTING:
            self.primary_btn.configure(state=tk.DISABLED, text="Please wait…")
            return
        if self._can_cancel:
            self.primary_btn.configure(state=tk.NORMAL, text="Cancel", style="Danger.TButton")
            return
        if state is VpnState.CONNECTED or (
            self._cli_connected and state in {VpnState.ERROR, VpnState.UNKNOWN}
        ):
            self.primary_btn.configure(state=tk.NORMAL, text="Disconnect", style="Danger.TButton")
            return
        if state is VpnState.ERROR and self._can_disconnect and not self._cli_connected:
            # Offer Connect as recovery when tunnel is down.
            self.primary_btn.configure(state=tk.NORMAL, text="Connect", style="Primary.TButton")
            return
        if self._can_connect and not self._busy:
            self.primary_btn.configure(state=tk.NORMAL, text="Connect", style="Primary.TButton")
            return
        self.primary_btn.configure(state=tk.DISABLED, text="Please wait…")

    def _update_tool_buttons(self) -> None:
        enabled = not self._busy and self._current_state not in {
            VpnState.CONNECTING,
            VpnState.DISCONNECTING,
            VpnState.SWITCHING_LOCATION,
            VpnState.INITIALIZING,
        }
        self.refresh_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def _safe_refresh_status(self) -> None:
        if self._busy:
            self.progress_var.set("Please wait for the current operation to finish.")
            return
        self.controller.refresh_status()

    def _safe_refresh_locations(self) -> None:
        if self._busy:
            self.progress_var.set("Please wait for the current operation to finish.")
            return
        self.controller.refresh_locations()

    def _on_primary(self) -> None:
        if self._can_cancel:
            self.controller.disconnect()
            return
        if self._current_state is VpnState.CONNECTED or (
            self._cli_connected and self._current_state in {VpnState.ERROR, VpnState.UNKNOWN}
        ):
            self.controller.disconnect()
            return
        self.controller.connect()

    def _on_location_selected(self, location: Location) -> None:
        self.controller.select_location(location)

    def _on_location_activated(self, location: Location) -> None:
        if self._busy:
            self.progress_var.set("Please wait for the current operation to finish.")
            return
        self.controller.select_location(location)
        if self._current_state is VpnState.CONNECTED:
            current = (
                self.controller.status_info.connected_location_code
                if self.controller.status_info
                else None
            )
            if current == location.code:
                return
            self.controller.switch_location(location)
        else:
            self.controller.connect()

    def _prompt_credentials(self) -> Credentials | None:
        existing = self.controller.load_credentials()
        dialog = CredentialsDialog(self.root, self.theme, initial=existing)
        self.root.wait_window(dialog)
        return dialog.result

    def _edit_credentials(self) -> None:
        creds = self._prompt_credentials()
        if creds:
            self.controller.save_credentials(creds)
            self.progress_var.set("Account details saved.")

    def _toggle_theme(self) -> None:
        current = (self.controller.settings.theme or "system").lower()
        order = ("system", "light", "dark")
        try:
            nxt = order[(order.index(current) + 1) % len(order)]
        except ValueError:
            nxt = "dark"
        self.controller.settings.theme = nxt
        self.controller.settings_repo.save(self.controller.settings)
        self.apply_theme(resolve_theme(nxt, self.root))
        self.progress_var.set(f"Theme: {nxt}")

    def apply_theme(self, theme: Theme) -> None:
        """Apply a theme immediately without restarting the app."""
        self.theme = theme
        self.root.configure(bg=theme.bg)
        configure_styles(self.root, theme)
        self.badge.apply_theme(theme)
        self.badge.set_status(
            self.controller.machine.display_label,
            color=self._color_for(self._current_state),
        )
        self.location_selector.apply_theme(theme)

    def _on_close(self) -> None:
        try:
            self.controller.settings.window_geometry = self.root.geometry()
            self.controller.shutdown()
        finally:
            self._alive = False
            self.root.destroy()
