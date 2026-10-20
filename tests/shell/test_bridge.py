import json
import re
import threading
import time
from types import SimpleNamespace

import pytest

from engine.api import ApiError
from engine.device import DeviceManager, Worker
from engine.shell.bridge import API_METHODS, Bridge
from engine.store import Store


class FakeApi:
    def __init__(self):
        self.subs = []

    def __getattr__(self, name):
        return lambda *a, **k: None

    def subscribe(self, cb):
        self.subs.append(cb)

    def get_state(self):
        return {"connected": True}

    def set_lighting(self, effect=None, brightness=None, speed=None, color=None, direction=None):
        if effect == 99:
            raise ApiError("Unknown lighting effect 99")
        return {"connected": True, "effect": effect}

    def set_app_settings(self, theme=None, autostart=None):
        return {"theme": theme or "dark", "autostart": bool(autostart)}

    def export_profile(self, name, path):
        self.exported = (name, path)

    def import_profile(self, path, overwrite=False):
        return "Imported"


class FakeHost:
    def __init__(self):
        self.js, self.calls = [], []

    def eval_all(self, js):
        self.js.append(js)

    def show_main(self): self.calls.append("show_main")
    def hide_flyout(self): self.calls.append("hide_flyout")
    def minimize(self): self.calls.append("minimize")
    def quit(self): self.calls.append("quit")
    def save_dialog(self, name): return f"C:/x/{name}.cavalry.json"
    def open_dialog(self): return "C:/x/in.cavalry.json"


class FakeAutostart:
    on = False

    def enabled(self): return self.on
    def set(self, on): self.on = on


@pytest.fixture
def b():
    bridge = Bridge(FakeApi(), FakeHost(), FakeAutostart())
    yield bridge
    bridge.stop()


def test_passthrough_and_errors(b):
    assert b.get_state() == {"connected": True}
    assert b.set_lighting(11, None, None, None, None)["effect"] == 11
    with pytest.raises(Exception) as e:
        b.set_lighting(99)
    assert str(e.value) == "Unknown lighting effect 99"
    assert not isinstance(e.value, ApiError)


def test_events_are_pushed_as_js(b):
    b._api.subs[0]("state", {})
    b._api.subs[0]("error", {"message": "x\"</script>"})
    b.stop()
    assert b._host.js[0] == 'window.__cavalryEmit && window.__cavalryEmit({"name": "state", "payload": {}})'
    payload = b._host.js[1].split("__cavalryEmit(", 1)[1].rstrip(")")
    assert json.loads(payload)["payload"]["message"] == 'x"</script>'


def test_push_never_raises(b):
    def boom(js): raise RuntimeError("window closed")
    b._host.eval_all = boom
    b.push("state", {})
    b.push(object(), {"x": object()})


def test_window_controls_and_dialogs(b):
    b.show_main(); b.hide_flyout(); b.quit()
    assert b._host.calls == ["show_main", "hide_flyout", "quit"]
    assert b.export_profile_dialog("Gaming") == "C:/x/Gaming.cavalry.json"
    assert b._api.exported == ("Gaming", "C:/x/Gaming.cavalry.json")
    assert b.import_profile_dialog() == "Imported"


def test_autostart_follows_settings(b):
    out = b.set_app_settings(None, True)
    assert out["autostart"] is True and b._autostart.on is True


def test_push_returns_fast_while_the_page_is_blocked(b):
    gate = threading.Event()
    b._host.eval_all = lambda js: gate.wait(10)
    t0 = time.monotonic()
    for _ in range(5):
        b.push("state", {})
    assert time.monotonic() - t0 < 0.5
    gate.set()


def test_events_arrive_in_order(b):
    for i in range(20):
        b.push("state", {"i": i})
    b.stop()
    got = [int(re.search(r'"i": (\d+)', js).group(1)) for js in b._host.js]
    assert got == list(range(20))


def test_dispatcher_survives_a_failing_delivery(b):
    seen = []

    def flaky(js):
        seen.append(js)
        if len(seen) == 1:
            raise RuntimeError("page not ready")

    b._host.eval_all = flaky
    b.push("state", {"n": 1})
    b.push("state", {"n": 2})
    b.stop()
    assert len(seen) == 2


def test_import_dialog_passes_overwrite(b):
    seen = []
    b._api.import_profile = lambda path, overwrite=False: seen.append((path, overwrite)) or "Imported"
    b.import_profile_dialog(True)
    b.import_profile_dialog()
    assert seen == [("C:/x/in.cavalry.json", True), ("C:/x/in.cavalry.json", False)]


def test_autostart_failure_keeps_settings_unchanged(b):
    saved = []
    b._api.set_app_settings = lambda theme=None, autostart=None: saved.append(autostart)

    def fail(on): raise PermissionError("denied")

    b._autostart.set = fail
    with pytest.raises(Exception, match="Start with Windows"):
        b.set_app_settings(None, True)
    assert saved == []


def test_autostart_rolls_back_when_settings_are_rejected(b):
    def reject(theme=None, autostart=None): raise ApiError("theme must be one of dark, light, system")

    b._api.set_app_settings = reject
    with pytest.raises(Exception, match="theme must be"):
        b.set_app_settings("pink", True)
    assert b._autostart.on is False


def test_every_public_api_method_is_handled():
    from engine.api import Api
    public = {n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))}
    special = {"subscribe", "set_app_settings", "export_profile", "import_profile"}
    assert public == set(API_METHODS) | special


def _pywebview_functions(js_api) -> set[str]:
    """Run pywebview's own injection and read back which functions it would expose to the page."""
    from webview import util
    ev = SimpleNamespace(set=lambda: None)
    window = SimpleNamespace(
        uid="t", js_api_endpoint="", text_select=False, zoomable=False, draggable=False, easy_drag=False,
        frameless=False, state={}, _js_api=js_api, _functions={}, _expose_lock=threading.Lock(),
        events=SimpleNamespace(before_load=ev, _pywebviewready=ev, loaded=ev), scripts=[])
    scripts = []
    done = threading.Event()

    def run_js(code):
        scripts.append(code)
        if "_createApi" in code:
            done.set()

    window.run_js = run_js
    util.inject_pywebview("edgechromium", window)
    assert done.wait(10)
    listing = re.search(r"_createApi\(JSON.parse\('(.*?)'\)\)", scripts[-1], re.S).group(1)
    return {f["func"] for f in json.loads(listing)}


def test_page_sees_only_the_intended_surface(tmp_path):
    store = Store(tmp_path)
    dm = DeviceManager(store, detect=lambda: None, open_link=lambda k: None)
    from engine.api import Api
    bridge = Bridge(Api(dm, Worker(dm), store), FakeHost(), FakeAutostart())
    try:
        assert _pywebview_functions(bridge) == set(API_METHODS) | {
            "set_app_settings", "export_profile_dialog", "import_profile_dialog",
            "show_main", "hide_flyout", "minimize", "quit", "record_macro_start", "record_macro_stop"}
    finally:
        bridge.stop()


def test_one_hung_window_does_not_stop_events_for_the_other(caplog):
    from engine.shell.bridge import Courier
    gate, got = threading.Event(), []
    courier = Courier(timeout=0.2)
    targets = {"main": lambda js: gate.wait(10), "flyout": got.append}
    t0 = time.monotonic()
    with caplog.at_level("WARNING", logger="cavalry"):
        for i in range(3):
            courier.send(targets, f"e{i}")
    assert got == ["e0", "e1", "e2"]
    assert time.monotonic() - t0 < 1.0
    assert any("main" in r.getMessage() for r in caplog.records)
    gate.set()


def test_courier_resumes_a_window_once_it_answers_again():
    from engine.shell.bridge import Courier
    gate, got = threading.Event(), []

    def slow(js):
        if js == "e0":
            gate.wait(10)
        got.append(js)

    courier = Courier(timeout=0.1)
    courier.send({"main": slow}, "e0")
    courier.send({"main": slow}, "skipped")
    gate.set()
    deadline = time.monotonic() + 5
    while got != ["e0"] and time.monotonic() < deadline:
        time.sleep(0.01)
    courier.send({"main": slow}, "e2")
    assert got == ["e0", "e2"]


def test_courier_logs_a_failing_window_and_still_delivers_to_the_rest():
    from engine.shell.bridge import Courier
    got = []

    def boom(js): raise RuntimeError("page gone")

    Courier(timeout=1).send({"main": boom, "flyout": got.append}, "e")
    assert got == ["e"]


def test_replace_after_a_name_clash_reuses_the_picked_file(b):
    from engine.store import ProfileExists
    picks, seen = [], []
    b._host.open_dialog = lambda: picks.append(1) or f"C:/x/{len(picks)}.cavalry.json"

    def imp(path, overwrite=False):
        seen.append((path, overwrite))
        if not overwrite:
            try:
                raise ProfileExists("a profile named 'Gaming' already exists")
            except ProfileExists as e:
                raise ApiError(f"Not imported: {e}. Import again with overwrite to replace it.") from e
        return "Gaming"

    b._api.import_profile = imp
    with pytest.raises(Exception, match="already exists"):
        b.import_profile_dialog()
    assert b.import_profile_dialog(True) == "Gaming"
    assert len(picks) == 1
    assert seen == [("C:/x/1.cavalry.json", False), ("C:/x/1.cavalry.json", True)]
    b.import_profile_dialog(True)
    assert len(picks) == 2


def test_recorder_methods(b, monkeypatch):
    calls = []

    class FakeHook:
        def __init__(self, cb): calls.append("init"); self.cb = cb
        def start(self): calls.append("start")
        def stop(self): calls.append("stop")
    monkeypatch.setattr("engine.shell.bridge.KeyboardHook", FakeHook)
    b.record_macro_start()
    out = b.record_macro_stop()
    assert out == {"events": [], "truncated": False} and calls == ["init", "start", "stop"]
    with pytest.raises(Exception):
        b.record_macro_stop()


def test_stop_ends_an_active_recording(b, monkeypatch):
    calls = []

    class FakeHook:
        def __init__(self, cb): pass
        def start(self): pass
        def stop(self): calls.append("stop")
    monkeypatch.setattr("engine.shell.bridge.KeyboardHook", FakeHook)
    b.record_macro_start()
    with pytest.raises(Exception):
        b.record_macro_start()
    b.stop()
    assert calls == ["stop"]
