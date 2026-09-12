"""VPN controller: bridges services to the UI thread safely."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hotspotshield_gui.config.settings import SettingsRepository
from hotspotshield_gui.models.location import Location
from hotspotshield_gui.models.vpn_state import StateMachine, VpnState, VpnStatusInfo
from hotspotshield_gui.security.secret_store import Credentials, SecretStore
from hotspotshield_gui.services.ip_service import PublicIpInfo
from hotspotshield_gui.services.vpn_service import VpnService
from hotspotshield_gui.utils.errors import AppError

logger = logging.getLogger("hotspotshield_gui.controllers.vpn_controller")


@dataclass
class UiEvent:
    name: str
    payload: dict[str, Any]


class VpnController:
    """Owns state machine + background workers; emits UI events via a queue."""

    def __init__(
        self,
        service: VpnService | None = None,
        secret_store: SecretStore | None = None,
        settings_repo: SettingsRepository | None = None,
    ) -> None:
        self.service = service or VpnService()
        self.secret_store = secret_store or SecretStore()
        self.settings_repo = settings_repo or SettingsRepository(self.secret_store)
        self.settings = self.settings_repo.load()
        self.machine = StateMachine()
        self.events: queue.Queue[UiEvent] = queue.Queue()
        self.locations: list[Location] = []
        self.selected: Location | None = None
        self.status_info: VpnStatusInfo | None = None
        self.public_ip: PublicIpInfo | None = None
        self.progress_message = "Starting…"
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._cancel_requested = threading.Event()
        self._closed = False

    def _emit(self, name: str, **payload: Any) -> None:
        if self._closed:
            return
        self.events.put(UiEvent(name=name, payload=payload))

    def poll_events(self) -> list[UiEvent]:
        items: list[UiEvent] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                break
        return items

    def _emit_state(self) -> None:
        self._emit(
            "state_changed",
            state=self.machine.state,
            label=self.machine.display_label,
            error=self.machine.last_error,
            busy=self.machine.busy,
            can_connect=self.machine.can_connect,
            can_disconnect=self.machine.can_disconnect,
            can_cancel=self.machine.can_cancel,
            cli_connected=bool(self.status_info and self.status_info.is_connected),
        )

    def _set_state(self, state: VpnState, *, error: str | None = None, force: bool = False) -> None:
        with self._lock:
            if force:
                self.machine.force(state, error=error)
            else:
                try:
                    self.machine.transition(state, error=error)
                except Exception as exc:  # noqa: BLE001
                    logger.error("State transition failed: %s", exc)
                    self.machine.force(VpnState.ERROR, error=str(exc))
        self._emit_state()

    def _set_progress(self, message: str) -> None:
        self.progress_message = message
        self._emit("progress", message=message)

    def _reconcile_after_error(self, fallback_message: str, technical: str | None = None) -> None:
        """Map UI to real CLI state after a failure so we never strand Connecting."""
        try:
            info = self.service.refresh_status()
            self.status_info = info
            self._set_state(info.state, force=True)
            self._emit("status", info=info)
            self._emit(
                "error",
                message=fallback_message,
                technical=technical,
            )
            self._set_progress(self.machine.display_label)
        except AppError:
            self._set_state(VpnState.ERROR, error=fallback_message, force=True)
            self._emit("error", message=fallback_message, technical=technical)

    def _run_bg(self, target: Callable[[], None], *, name: str) -> bool:
        """Start a worker. Caller must only enter busy states AFTER this returns True."""
        with self._lock:
            if self._worker and self._worker.is_alive():
                self._emit("notice", message="Please wait for the current operation to finish.")
                return False
            self._cancel_requested.clear()

            def wrapper() -> None:
                try:
                    target()
                except AppError as exc:
                    logger.warning("%s failed: %s", name, exc.technical)
                    self._reconcile_after_error(exc.user_message, exc.technical)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Unexpected error in %s", name)
                    self._reconcile_after_error(
                        "Something went wrong.\n\nTry again. If it keeps happening, restart the app.",
                        str(exc),
                    )
                finally:
                    with self._lock:
                        self._worker = None

            self._worker = threading.Thread(target=wrapper, name=name, daemon=True)
            self._worker.start()
            return True

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._worker and self._worker.is_alive()) or self.machine.busy

    # --- public API ----------------------------------------------------
    def initialize(self) -> None:
        self._set_state(VpnState.INITIALIZING, force=True)
        self._set_progress("Checking status…")

        def work() -> None:
            if not self.service.cli_available():
                self._set_state(
                    VpnState.ERROR,
                    error="Hotspot Shield CLI is not installed.",
                    force=True,
                )
                self._emit(
                    "error",
                    message=(
                        "Hotspot Shield is not installed on this computer.\n\n"
                        "Install the official Hotspot Shield Linux package, then reopen this app."
                    ),
                    technical="hotspotshield not found on PATH",
                )
                return

            try:
                info = self.service.refresh_status()
                self.status_info = info
                self._set_state(info.state, force=True)
                self._emit("status", info=info)
            except AppError as exc:
                self._set_state(VpnState.DISCONNECTED, force=True)
                self._emit("notice", message=exc.user_message)

            self._set_progress("Loading locations…")
            try:
                self.locations = self.service.list_locations()
                self._emit("locations", locations=list(self.locations))
                self._select_default_location()
            except AppError as exc:
                self._emit("locations_error", message=exc.user_message, technical=exc.technical)

            self._refresh_ip_silent()
            self._set_progress(self.machine.display_label)

        if not self._run_bg(work, name="initialize"):
            self._set_state(VpnState.DISCONNECTED, force=True)

    def _select_default_location(self) -> None:
        if not self.locations:
            return
        code = self.settings.last_location_code
        chosen = None
        if code:
            chosen = next((loc for loc in self.locations if loc.code == code), None)
        if chosen is None and self.status_info and self.status_info.connected_location_code:
            code2 = self.status_info.connected_location_code
            chosen = next((loc for loc in self.locations if loc.code == code2), None)
        if chosen is None:
            chosen = self.locations[0]
        self.selected = chosen
        self._emit("selection", location=chosen)

    def select_location(self, location: Location) -> None:
        self.selected = location
        self.settings.remember_location(location.code)
        self.settings_repo.save(self.settings)
        self._emit("selection", location=location)

    def connect(self, credentials: Credentials | None = None) -> None:
        if self.selected is None:
            self._emit(
                "error",
                message="Select a location first.\n\nChoose a country or city from the list on the right.",
                technical="no selection",
            )
            return
        if self.machine.state is VpnState.CONNECTED:
            self._emit("notice", message="Already connected.")
            return
        if self.machine.busy or self.is_busy():
            self._emit("notice", message="Please wait for the current operation to finish.")
            return
        if not self.machine.can_connect:
            self._emit("notice", message="Cannot connect in the current state.")
            return

        creds = credentials or self.secret_store.load()
        if creds is None or not creds.is_complete():
            self._emit("need_credentials")
            return

        location = self.selected

        def work() -> None:
            if self._cancel_requested.is_set():
                self._set_state(VpnState.DISCONNECTED, force=True)
                self._set_progress("Cancelled")
                return
            info = self.service.connect(location, creds, progress=self._set_progress)
            if self._cancel_requested.is_set():
                try:
                    info = self.service.disconnect(progress=self._set_progress, settle_seconds=0.5)
                except AppError:
                    info = self.service.refresh_status()
                self.status_info = info
                self._set_state(info.state, force=True)
                self._emit("status", info=info)
                self._set_progress("Cancelled")
                return
            self.status_info = info
            self.settings.remember_location(location.code)
            self.settings_repo.save(self.settings)
            try:
                self.secret_store.save(creds)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not persist credentials: %s", exc)
            self._set_state(VpnState.CONNECTED, force=True)
            self._emit("status", info=info)
            self._refresh_ip_silent()
            self._set_progress("Connected")

        if not self._run_bg(work, name="connect"):
            return
        self._set_state(VpnState.CONNECTING)
        self._set_progress("Connecting…")

    def disconnect(self) -> None:
        # Allow cancel while connecting / switching, and recovery from ERROR.
        cli_up = bool(self.status_info and self.status_info.is_connected)
        if (
            not self.machine.can_disconnect
            and self.machine.state is not VpnState.CONNECTED
            and not cli_up
        ):
            self._emit("notice", message="VPN is not connected.")
            return

        if self.machine.can_cancel:
            self._cancel_requested.set()
            self._set_state(VpnState.DISCONNECTING)
            self._set_progress("Cancelling…")
            return

        def work() -> None:
            info = self.service.disconnect(progress=self._set_progress)
            self.status_info = info
            self._set_state(VpnState.DISCONNECTED, force=True)
            self._emit("status", info=info)
            self._refresh_ip_silent()
            self._set_progress("Disconnected")

        if not self._run_bg(work, name="disconnect"):
            self._emit("notice", message="Please wait for the current operation to finish.")
            return
        self._set_state(VpnState.DISCONNECTING)
        self._set_progress("Disconnecting…")

    def switch_location(self, location: Location, credentials: Credentials | None = None) -> None:
        if self.machine.busy or self.is_busy():
            self._emit("notice", message="Please wait for the current operation to finish.")
            return
        creds = credentials or self.secret_store.load()
        if creds is None or not creds.is_complete():
            self._emit("need_credentials")
            return
        self.selected = location

        def work() -> None:
            info = self.service.switch_location(location, creds, progress=self._set_progress)
            if self._cancel_requested.is_set():
                try:
                    info = self.service.disconnect(progress=self._set_progress, settle_seconds=0.5)
                except AppError:
                    info = self.service.refresh_status()
                self.status_info = info
                self._set_state(info.state, force=True)
                self._emit("status", info=info)
                self._set_progress("Cancelled")
                return
            self.status_info = info
            self.settings.remember_location(location.code)
            self.settings_repo.save(self.settings)
            self._set_state(VpnState.CONNECTED, force=True)
            self._emit("status", info=info)
            self._emit("selection", location=location)
            self._refresh_ip_silent()
            self._set_progress("Connected")

        if not self._run_bg(work, name="switch_location"):
            return
        self._set_state(VpnState.SWITCHING_LOCATION)
        self._set_progress("Changing location…")

    def refresh_locations(self) -> None:
        if self.machine.busy or self.is_busy():
            self._emit("notice", message="Please wait for the current operation to finish.")
            return
        self._set_progress("Loading locations…")

        def work() -> None:
            try:
                self.locations = self.service.list_locations()
                self._emit("locations", locations=list(self.locations))
                self._set_progress(self.machine.display_label)
            except AppError as exc:
                # Never corrupt Connected/Disconnected into Error for a list failure.
                self._emit("locations_error", message=exc.user_message, technical=exc.technical)
                self._set_progress(self.machine.display_label)

        self._run_bg(work, name="refresh_locations")

    def refresh_status(self) -> None:
        if self.machine.busy or self.is_busy():
            self._emit("notice", message="Please wait for the current operation to finish.")
            return

        def work() -> None:
            info = self.service.refresh_status()
            self.status_info = info
            self._set_state(info.state, force=True)
            self._emit("status", info=info)
            self._refresh_ip_silent()
            self._set_progress(self.machine.display_label)

        self._run_bg(work, name="refresh_status")

    def _refresh_ip_silent(self) -> None:
        def work() -> None:
            try:
                self.public_ip = self.service.lookup_ip()
                self._emit("ip", info=self.public_ip)
            except Exception as exc:  # noqa: BLE001
                logger.debug("IP refresh failed: %s", exc)
                self._emit("ip", info=None)

        threading.Thread(target=work, name="ip-refresh", daemon=True).start()

    def save_credentials(self, credentials: Credentials) -> None:
        self.secret_store.save(credentials)

    def load_credentials(self) -> Credentials | None:
        return self.secret_store.load()

    def shutdown(self) -> None:
        """Close controller. VPN stays connected by default (documented behavior)."""
        self._closed = True
        self._cancel_requested.set()
        self.settings_repo.save(self.settings)
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=1.0)
