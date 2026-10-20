import inspect
import logging

import pytest

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
                                             "import_profile_dialog", "show_main", "hide_flyout",
                                             "minimize", "quit"}
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
    # 150% monitor: 320x470 logical -> 480x705 physical, placed above a bottom taskbar
    x, y = flyout_origin(cursor=(1500, 1590), work=(0, 0, 2560, 1560), monitor_scale=1.5,
                         window_scale=1.5, size=(320, 470))
    assert (x, y) == (round((1500 - 240) / 1.5), round((1560 - 12 - 705) / 1.5))
    # 100%: identity
    assert flyout_origin((1500, 1050), (0, 0, 1920, 1032), 1.0, 1.0, (320, 470)) == (1340, 1032 - 12 - 470)


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
