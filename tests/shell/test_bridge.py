import json

import pytest

from engine.api import ApiError
from engine.shell.bridge import Bridge


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
    return Bridge(FakeApi(), FakeHost(), FakeAutostart())


def test_passthrough_and_errors(b):
    assert b.get_state() == {"connected": True}
    assert b.set_lighting(11, None, None, None, None)["effect"] == 11
    with pytest.raises(Exception) as e:
        b.set_lighting(99)
    assert str(e.value) == "Unknown lighting effect 99"
    assert not isinstance(e.value, ApiError)


def test_events_are_pushed_as_js(b):
    b.api.subs[0]("state", {})
    b.api.subs[0]("error", {"message": "x\"</script>"})
    assert b.host.js[0] == 'window.__cavalryEmit && window.__cavalryEmit({"name": "state", "payload": {}})'
    payload = b.host.js[1].split("__cavalryEmit(", 1)[1].rstrip(")")
    assert json.loads(payload)["payload"]["message"] == 'x"</script>'


def test_push_never_raises(b):
    def boom(js): raise RuntimeError("window closed")
    b.host.eval_all = boom
    b.push("state", {})


def test_window_controls_and_dialogs(b):
    b.show_main(); b.hide_flyout(); b.quit()
    assert b.host.calls == ["show_main", "hide_flyout", "quit"]
    assert b.export_profile_dialog("Gaming") == "C:/x/Gaming.cavalry.json"
    assert b.api.exported == ("Gaming", "C:/x/Gaming.cavalry.json")
    assert b.import_profile_dialog() == "Imported"


def test_autostart_follows_settings(b):
    out = b.set_app_settings(None, True)
    assert out["autostart"] is True and b.autostart.on is True


def test_every_api_method_is_exposed(b):
    from engine.shell.bridge import API_METHODS
    assert all(callable(getattr(b, n)) for n in API_METHODS)
