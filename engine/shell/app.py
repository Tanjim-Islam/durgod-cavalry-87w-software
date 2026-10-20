"""Wires the engine, the two windows, the tray and the device worker together."""
from __future__ import annotations

import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import webview
import win32api
import win32con
import win32gui

from ..api import Api
from ..device import DeviceManager, Worker
from ..links.detect import detect_link_kind, open_link
from ..store import Store, default_root
from . import single
from .autostart import Autostart
from .bridge import API_METHODS, Bridge
from .flyout import place
from .tray import Tray

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DIST = ROOT / "ui" / "dist" / "index.html"
ICON = Path(__file__).with_name("icon.ico")
TITLE = "Cavalry 87W"
FLYOUT_SIZE = (320, 470)
SM_SHUTTINGDOWN = 0x2000
EXPOSED = API_METHODS + ("set_app_settings", "export_profile_dialog", "import_profile_dialog",
                         "show_main", "hide_flyout", "minimize", "quit")
log = logging.getLogger("cavalry")


def build_engine(root: Path):
    store = Store(root)
    manager = DeviceManager(store, detect=detect_link_kind, open_link=open_link)
    worker = Worker(manager)
    return store, manager, worker, Api(manager, worker, store)


def ui_url(dev: bool) -> str:
    if dev:
        return "http://localhost:5173"
    if not DIST.exists():
        raise FileNotFoundError(f"{DIST} not found. Run pnpm -C ui build first.")
    return str(DIST)


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" -m engine --tray'


def exposed_functions(bridge: Bridge) -> list:
    """Plain functions named after the JS surface, so pywebview can't walk into the Bridge."""
    def make(name: str, target):
        def call(*args):
            return target(*args)
        call.__name__ = call.__qualname__ = name
        return call
    return [make(n, getattr(bridge, n)) for n in EXPOSED]


def fix_fragment(url: str) -> str:
    """pywebview builds served URLs with os.path.relpath, which turns '#/flyout' into '#\\flyout'."""
    base, sep, frag = url.partition("#")
    return base + sep + frag.replace("\\", "/")


def flyout_origin(cursor, work, scale: float, size) -> tuple[int, int]:
    """Place in physical pixels, then return the logical point pywebview's move() scales back up."""
    x, y = place(cursor, work, (round(size[0] * scale), round(size[1] * scale)))
    return round(x / scale), round(y / scale)


_user32 = ctypes.windll.user32
_user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]


def _dpi_aware() -> None:
    """The same system-aware model pywebview sets, but before the tray thread reads any coordinates."""
    try:
        _user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        log.warning("could not make the process DPI aware")


def _window_scale(window) -> float:
    """The scale pywebview's move()/resize() multiply by: the window's DPI (system DPI when system aware)."""
    hwnd = _hwnd(window)
    dpi = _user32.GetDpiForWindow(hwnd) if hwnd else 0
    return (dpi or _user32.GetDpiForSystem() or 96) / 96


def _hwnd(window) -> int | None:
    try:
        return window.native.Handle.ToInt32()
    except Exception:
        return None


class ShortApiErrors(logging.Filter):
    """pywebview logs a full traceback for every failed JS call; user-facing errors need one line."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "pywebview" and record.levelno >= logging.ERROR:
            msg = record.getMessage()
            last = msg.rstrip().splitlines()[-1] if msg.startswith("Traceback") else ""
            if last.startswith("Exception: "):
                record.msg, record.args = f"UI call failed: {last[len('Exception: '):]}", ()
                record.levelno, record.levelname = logging.WARNING, "WARNING"
        return True


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    handlers[0].setLevel(logging.INFO)  # pywebview logs at DEBUG in --dev; keep that out of the file
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    pv = logging.getLogger("pywebview")
    for h in list(pv.handlers):
        pv.removeHandler(h)
    pv.addFilter(ShortApiErrors())


class Windows:
    def __init__(self, url: str, start_hidden: bool, on_quit=lambda: None, on_session_end=lambda: None):
        self.main = webview.create_window(TITLE, url, width=1180, height=760, min_size=(980, 640),
                                          hidden=start_hidden, background_color="#1a1a1a")
        self.flyout = webview.create_window("Cavalry flyout", url + "#/flyout", width=FLYOUT_SIZE[0],
                                            height=FLYOUT_SIZE[1], frameless=True, on_top=True, hidden=True,
                                            resizable=False, background_color="#1a1a1a", easy_drag=False)
        self._quitting = False
        self._on_quit, self._on_session_end = on_quit, on_session_end
        self.main.events.closing += self._on_close
        self.flyout.events.closing += self._on_flyout_close
        self.flyout.events.initialized += self._fix_flyout_url

    def _fix_flyout_url(self):
        if self.flyout.real_url:
            self.flyout.real_url = fix_fragment(self.flyout.real_url)

    def _on_close(self):
        if self._quitting or win32api.GetSystemMetrics(SM_SHUTTINGDOWN):
            return True
        self.main.hide()
        return False

    def _on_flyout_close(self):
        if self._quitting or win32api.GetSystemMetrics(SM_SHUTTINGDOWN):
            return True
        self.flyout.hide()
        return False

    def show_main(self) -> None:
        self.flyout.hide()
        self.main.show()
        hwnd = _hwnd(self.main)
        if hwnd and win32gui.IsIconic(hwnd):
            self.main.restore()

    def show_flyout(self, cursor) -> None:
        mon = win32api.MonitorFromPoint(cursor, win32con.MONITOR_DEFAULTTONEAREST)
        work = win32api.GetMonitorInfo(mon)["Work"]
        # The frameless form loses its border after sizing, so set the outer size again before placing.
        self.flyout.resize(*FLYOUT_SIZE)
        self.flyout.move(*flyout_origin(cursor, work, _window_scale(self.flyout), FLYOUT_SIZE))
        self.flyout.show()

    def hide_flyout(self) -> None:
        self.flyout.hide()

    def minimize(self) -> None:
        self.main.minimize()

    def quit(self) -> None:
        self._quitting = True
        _quietly(self._on_quit)
        for w in (self.flyout, self.main):
            _quietly(w.destroy)

    def session(self, action: str) -> None:
        """Called on the tray thread for WM_QUERYENDSESSION / WM_ENDSESSION."""
        if action == "cancelled":
            self._quitting = False
            return
        self._quitting = True
        if action == "end":
            # Windows may end the process once this returns, so finish keyboard writes now.
            _quietly(self._on_quit)
            _quietly(self._on_session_end)

    def eval_all(self, js: str) -> None:
        # A page that isn't ready yet fetches state on load; don't stall the event thread waiting for it.
        for w in (self.main, self.flyout):
            if w.events._pywebviewready.is_set():
                try:
                    w.evaluate_js(js)
                except Exception:
                    log.exception("could not deliver an event to %s", w.title)

    def save_dialog(self, name: str) -> str | None:
        r = self.main.create_file_dialog(webview.FileDialog.SAVE, save_filename=f"{name}.cavalry.json",
                                         file_types=("Cavalry profile (*.json)",))
        return r if isinstance(r, str) else (r[0] if r else None)

    def open_dialog(self) -> str | None:
        r = self.main.create_file_dialog(webview.FileDialog.OPEN, file_types=("Cavalry profile (*.json)",))
        return r if isinstance(r, str) else (r[0] if r else None)


def _quietly(fn) -> None:
    try:
        fn()
    except Exception:
        log.exception("shutdown step failed")


def main(argv: list[str]) -> int:
    _dpi_aware()
    dev, tray_only = "--dev" in argv, "--tray" in argv
    if not single.acquire():
        single.focus_existing(TITLE)
        return 0
    root = default_root()
    setup_logging(root / "logs")
    try:
        store, manager, worker, api = build_engine(root)
        windows = Windows(ui_url(dev), start_hidden=tray_only, on_quit=worker.close, on_session_end=worker.stop)
        bridge = Bridge(api, windows, Autostart(launch_command()))
        fns = exposed_functions(bridge)
        for w in (windows.main, windows.flyout):
            w.expose(*fns)
        tray = Tray(str(ICON), TITLE, windows.show_main, windows.show_flyout, on_session=windows.session)
    except Exception:
        log.exception("could not start %s", TITLE)
        raise
    try:
        bridge.start()
        worker.start()
        tray.start()
        webview.start(debug=dev, http_server=not dev, private_mode=True,
                      storage_path=str(root / "webview"), icon=str(ICON))
    finally:
        for step in (bridge.stop, tray.stop, worker.stop):
            _quietly(step)
    return 0
