import inspect
import logging
from types import SimpleNamespace

import pytest

from engine.shell import app
from engine.shell.app import (EXPOSED, ShortApiErrors, build_engine, exposed_functions, fix_fragment,
                              flyout_origin, ui_url)
from engine.shell.bridge import API_METHODS, Bridge


def test_build_engine_uses_store_root(tmp_path):
    store, manager, worker, api = build_engine(tmp_path)
    assert store.root == tmp_path
    assert api.get_state()["connected"] is False


def test_ui_url(tmp_path, monkeypatch):
    assert ui_url(dev=True) == "http://localhost:5173"
    monkeypatch.setattr("engine.shell.app.DIST", tmp_path / "missing" / "index.html")
    with pytest.raises(FileNotFoundError, match="pnpm -C ui build"):
        ui_url(dev=False)
    (tmp_path / "index.html").write_text("<html></html>")
    monkeypatch.setattr("engine.shell.app.DIST", tmp_path / "index.html")
    assert ui_url(dev=False) == str(tmp_path / "index.html")


class _Api:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **k: self.calls.append((name, a)) or name

    def subscribe(self, cb):
        pass


class _Host:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a: self.calls.append(name)


def test_exposed_names_are_exactly_the_js_surface():
    api, host = _Api(), _Host()
    fns = exposed_functions(Bridge(api, host, autostart=None))
    names = [f.__name__ for f in fns]
    assert len(names) == len(set(names))
    assert set(names) == set(API_METHODS) | {"set_app_settings", "export_profile_dialog",
                                             "import_profile_dialog", "show_main", "hide_main", "hide_flyout",
                                             "minimize", "toggle_maximize", "open_logs", "quit", "record_macro_start",
                                             "record_macro_stop"}
    assert set(names) == set(EXPOSED)
    assert all(inspect.isfunction(f) and not hasattr(f, "__self__") for f in fns)
    assert not {"start", "stop", "push", "_api", "_host", "_autostart"} & set(names)


def test_exposed_functions_route_to_the_bridge():
    api, host = _Api(), _Host()
    fns = {f.__name__: f for f in exposed_functions(Bridge(api, host, autostart=None))}
    assert fns["get_state"]() == "get_state"
    fns["set_lighting"](3, 50)
    assert ("set_lighting", (3, 50)) in api.calls
    fns["hide_flyout"]()
    assert host.calls == ["hide_flyout"]


def test_fix_fragment_restores_forward_slashes():
    assert fix_fragment("http://127.0.0.1:42001/index.html#\\flyout") == "http://127.0.0.1:42001/index.html#/flyout"
    assert fix_fragment("http://localhost:5173#/flyout") == "http://localhost:5173#/flyout"
    assert fix_fragment("http://127.0.0.1:42001/index.html") == "http://127.0.0.1:42001/index.html"


def test_flyout_origin_converts_physical_to_logical():
    # 150% system DPI: 320x470 logical -> 480x705 physical, placed above a bottom taskbar
    x, y = flyout_origin(cursor=(1500, 1590), work=(0, 0, 2560, 1560), scale=1.5, size=(320, 470))
    assert (x, y) == (round((1500 - 240) / 1.5), round((1560 - 12 - 705) / 1.5))
    # 100%: identity
    assert flyout_origin((1500, 1050), (0, 0, 1920, 1032), 1.0, (320, 470)) == (1340, 1032 - 12 - 470)


class _Event(list):
    def __iadd__(self, fn):
        self.append(fn)
        return self

    def fire(self):
        return [fn() for fn in self]


class _Window:
    def __init__(self, title, url, **kw):
        self.title, self.url, self.kw, self.calls = title, url, kw, []
        self.events = SimpleNamespace(closing=_Event(), initialized=_Event(), before_show=_Event(),
                                      maximized=_Event(), restored=_Event())
        self.dialog_result = None

    def __getattr__(self, name):
        return lambda *a, **k: self.calls.append((name, a))

    def create_file_dialog(self, *a, **k):
        return self.dialog_result


@pytest.fixture
def wins(monkeypatch):
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    monkeypatch.setattr(app.win32api, "GetSystemMetrics", lambda i: 0)
    return app.Windows("C:/ui/index.html", start_hidden=False)


def test_main_close_hides_unless_quitting(wins):
    assert wins.main.events.closing.fire() == [False]
    assert ("hide", ()) in wins.main.calls
    wins.quit()
    assert wins.main.events.closing.fire() == [True]
    assert ("destroy", ()) in wins.main.calls and ("destroy", ()) in wins.flyout.calls


def test_main_close_ends_a_recording_but_quit_and_session_end_do_not(monkeypatch):
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    monkeypatch.setattr(app.win32api, "GetSystemMetrics", lambda i: 0)
    hidden = []
    w = app.Windows("C:/ui/index.html", start_hidden=False, on_hide=lambda: hidden.append(1))
    w.main.events.closing.fire()
    assert hidden == [1]
    w.minimize()                        # minimizing is not a close: recording goes on
    assert hidden == [1]
    w.quit()
    w.main.events.closing.fire()
    assert hidden == [1]


def test_main_close_survives_a_failing_hide_hook(monkeypatch):
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    monkeypatch.setattr(app.win32api, "GetSystemMetrics", lambda i: 0)

    def boom(): raise RuntimeError("x")
    w = app.Windows("C:/ui/index.html", start_hidden=False, on_hide=boom)
    assert w.main.events.closing.fire() == [False]
    assert ("hide", ()) in w.main.calls


def test_flyout_close_hides_unless_quitting(wins):
    assert wins.flyout.events.closing.fire() == [False]
    assert ("hide", ()) in wins.flyout.calls
    wins._quitting = True
    assert wins.flyout.events.closing.fire() == [True]


def test_flyout_url_fragment_is_fixed_after_resolve(wins):
    assert wins.flyout.url == "C:/ui/index.html#/flyout"
    wins.flyout.real_url = "http://127.0.0.1:5000/index.html#\\flyout"
    wins.flyout.events.initialized.fire()
    assert wins.flyout.real_url == "http://127.0.0.1:5000/index.html#/flyout"


@pytest.mark.parametrize("result,expected", [(("C:/a.json",), "C:/a.json"), (None, None), ((), None),
                                             ("C:/b.json", "C:/b.json")])
def test_dialogs_unwrap_to_str_or_none(wins, result, expected):
    wins.main.dialog_result = result
    assert wins.save_dialog("p") == expected
    assert wins.open_dialog() == expected


def test_show_flyout_resizes_then_moves_then_shows(wins, monkeypatch):
    monkeypatch.setattr(app.win32api, "MonitorFromPoint", lambda p, f: 1)
    monkeypatch.setattr(app.win32api, "GetMonitorInfo", lambda m: {"Work": (0, 0, 1920, 1032)})
    monkeypatch.setattr(app, "_window_scale", lambda w: 1.0)
    wins.show_flyout((1500, 1050))
    assert [c for c in wins.flyout.calls if c[0] in ("resize", "move", "show")] == [
        ("resize", (320, 470)), ("move", (1340, 550)), ("show", ())]


def _record(msg, name="pywebview", level=logging.ERROR):
    return logging.LogRecord(name, level, __file__, 1, msg, None, None)


def test_short_api_errors_shortens_user_facing_tracebacks():
    f = ShortApiErrors()
    tb = ('Traceback (most recent call last):\n  File "x.py", line 1, in call\n'
          '    raise Exception(str(e)) from None\nException: Unknown lighting effect 99\n')
    r = _record(tb)
    assert f.filter(r) is True
    assert r.getMessage() == "UI call failed: Unknown lighting effect 99"
    assert r.levelno == logging.WARNING
    crash = 'Traceback (most recent call last):\n  File "x.py", line 1, in f\nKeyError: 3\n'
    r2 = _record(crash)
    assert f.filter(r2) is True and r2.getMessage() == crash and r2.levelno == logging.ERROR
    other = _record(tb, name="cavalry")
    assert f.filter(other) is True and other.getMessage() == tb


def test_quit_refuses_new_device_calls_before_closing_windows(monkeypatch):
    order = []
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    w = app.Windows("C:/ui/index.html", start_hidden=False, on_quit=lambda: order.append("close worker"))
    w.main.destroy = lambda: order.append("destroy main")
    w.flyout.destroy = lambda: order.append("destroy flyout")
    w.quit()
    assert order == ["close worker", "destroy flyout", "destroy main"]


def test_quit_still_closes_main_when_the_flyout_is_already_gone(wins):
    def gone(): raise RuntimeError("disposed")
    wins.flyout.destroy = gone
    wins.quit()
    assert ("destroy", ()) in wins.main.calls


def test_session_ending_lets_both_windows_close(wins):
    wins.session("ending")
    assert wins.main.events.closing.fire() == [True]
    assert wins.flyout.events.closing.fire() == [True]
    wins.session("cancelled")
    assert wins.main.events.closing.fire() == [False]


def test_session_end_drains_the_worker_before_returning(monkeypatch):
    order = []
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    monkeypatch.setattr(app.win32api, "GetSystemMetrics", lambda i: 0)
    w = app.Windows("C:/ui/index.html", start_hidden=False, on_quit=lambda: order.append("close"),
                    on_session_end=lambda: order.append("drain"))
    w.session("end")
    assert order == ["close", "drain"]
    assert w.main.events.closing.fire() == [True]


def test_eval_all_delivers_to_ready_windows_without_waiting_on_a_hung_one(wins):
    import threading
    import time
    gate, got = threading.Event(), []
    for w in (wins.main, wins.flyout):
        w.events._pywebviewready = threading.Event()
        w.events._pywebviewready.set()
    wins.main.evaluate_js = lambda js: gate.wait(10)
    wins.flyout.evaluate_js = got.append
    wins._courier.timeout = 0.2
    t0 = time.monotonic()
    wins.eval_all("a")
    wins.eval_all("b")
    assert got == ["a", "b"] and time.monotonic() - t0 < 1.0
    gate.set()


def test_title_bar_buttons_and_window_state(monkeypatch):
    monkeypatch.setattr(app.webview, "create_window", lambda title, url, **kw: _Window(title, url, **kw))
    monkeypatch.setattr(app.win32api, "GetSystemMetrics", lambda i: 0)
    hidden, states = [], []
    w = app.Windows("C:/ui/index.html", start_hidden=False, on_hide=lambda: hidden.append(1),
                    on_window=states.append)
    w.hide_main()                       # the bar's close button behaves like the window's close
    assert hidden == [1] and ("hide", ()) in w.main.calls
    w.toggle_maximize()
    assert ("maximize", ()) in w.main.calls
    w.main.events.maximized.fire(); w.main.events.restored.fire()
    assert states == [True, False]
    w.main.events.before_show.fire()    # no native handle in tests: keeps the Windows bar, no crash
    assert w._caption is None


def test_caption_client_top():
    from engine.shell.chrome import client_top
    assert client_top(100, 50, 58, zoomed=False) == 100     # caption gone, sides keep their frame
    assert client_top(-8, -8, 0, zoomed=True) == 0          # maximized: frame hangs off-screen


def test_restore_guard_pins_only_the_first_quick_resize():
    from engine.shell.chrome import SWP_NOSIZE, WINDOWPOS, keep_size
    wp = WINDOWPOS(cx=1180, cy=791, flags=0x16)
    assert keep_size(wp, (1180, 760, 10.0), now=10.1) is None and (wp.cx, wp.cy) == (1180, 760)
    late = WINDOWPOS(cx=1180, cy=791, flags=0x16)
    assert keep_size(late, (1180, 760, 10.0), now=11.0) is None and late.cy == 791
    move = WINDOWPOS(cx=0, cy=0, flags=SWP_NOSIZE)
    assert keep_size(move, (1180, 760, 10.0), now=10.1) == (1180, 760, 10.0)   # moves don't use up the guard
    assert keep_size(WINDOWPOS(cx=5, cy=5), None, now=1.0) is None
