import json
from concurrent.futures import Future

import pytest

from engine.api import Api, ApiError
from engine.codec.config import OFF_EFFECT, Config
from engine.codec.keymap import Consumer, Key, MacroRef, NoAction, decode_layer, encode_layer
from engine.codec.macro import decode_macros
from engine.device import DeviceManager
from engine.links.wired import WiredLink
from engine.store import Store
from tests.fakes import FakeKeyboard


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class InlineWorker:
    def call(self, fn, *a):
        f = Future()
        try:
            f.set_result(fn(*a))
        except Exception as e:
            f.set_exception(e)
        return f


class StuckWorker:
    def call(self, fn, *a):
        return Future()


def make(tmp_path, fixture_blocks, detect=lambda: "wired"):
    kb = FakeKeyboard(fixture_blocks)
    clock = Clock()
    st = Store(tmp_path)
    dm = DeviceManager(st, detect=detect,
                       open_link=lambda k: WiredLink(kb.feature_device()), clock=clock)
    dm.poll()
    clock.t += 5.1
    dm.poll()
    return Api(dm, InlineWorker(), st), kb


@pytest.fixture
def api(tmp_path, fixture_blocks):
    return make(tmp_path, fixture_blocks)


def tap(code):
    return [{"kind": "key", "code": code, "release": False, "delay_ms": 16},
            {"kind": "key", "code": code, "release": True, "delay_ms": 16}]


def test_state_shape(api):
    a, kb = api
    s = a.get_state()
    assert s["connected"] is True and s["link"] == "wired"
    assert s["lighting"]["effect"] == 1 and len(s["effects"]) == 17
    assert len(s["layers"]) == 4 and len(s["layers"][0]) == 126
    assert s["key_names"]["45"] == "J"
    json.dumps(s)


def test_lighting_and_keep_on(api):
    a, kb = api
    a.set_lighting(effect=0x0B, brightness=2)
    c = Config(kb.state.config)
    assert c.effect == 0x0B and c.brightness(0x0B) == 2
    a.set_keep_lights_on(True)
    assert Config(kb.state.config).sleep == 0


def test_keep_lights_off_restores_factory_sleep(api):
    a, kb = api
    factory_sleep = Config(a.store.load_backup("factory").config).sleep
    a.set_keep_lights_on(True)
    a.set_keep_lights_on(False)
    assert Config(kb.state.config).sleep == (factory_sleep or 0x0C)


def test_remap_and_reset(api):
    a, kb = api
    a.remap_key(1, 45, {"type": "consumer", "usage": 0x192})
    assert decode_layer(kb.state.layers[1])[45] == Consumer(0x192)
    a.reset_key(1, 45)
    assert kb.state.layers[1][180:184] == bytes(4)
    res = a.remap_key(0, 45, {"type": "key", "hid": 0x73})   # F24: works on 2.4G only
    assert "cable" in res["warning"]
    with pytest.raises(ApiError):
        a.remap_key(0, 200, {"type": "key", "hid": 0x04})


def test_high_hid_is_a_warning_not_a_refusal(api):
    a, kb = api
    res = a.remap_key(0, 45, {"type": "key", "hid": 0x73})
    assert decode_layer(kb.state.layers[0])[45] == Key(0x73)
    assert res["warning"]
    res = a.remap_key(0, 45, {"type": "key", "hid": 0x70})
    assert "warning" not in res
    r = a.save_macro(None, {"name": "F24", "events": tap(0x73)})
    assert r["warning"] and decode_macros(kb.state.macros)[0].name == "F24"


def test_reset_layer(api):
    a, kb = api
    orig = kb.state.layers[2]
    a.remap_key(2, 45, {"type": "consumer", "usage": 0x192})
    assert kb.state.layers[2] != orig
    a.reset_layer(2)
    assert kb.state.layers[2] == orig


def test_reset_without_factory_is_an_error(api):
    a, kb = api
    (a.store.root / "backups" / "factory.json").unlink()
    with pytest.raises(ApiError):
        a.reset_key(1, 45)
    with pytest.raises(ApiError):
        a.reset_layer(1)


def test_macros(api):
    a, kb = api
    r = a.save_macro(None, {"name": "Hi", "events": [
        {"kind": "key", "code": 0x0B, "release": False, "delay_ms": 16},
        {"kind": "key", "code": 0x0B, "release": True, "delay_ms": 16}]})
    assert r == {"index": 0, "warning": None}
    assert a.get_state()["macros"][0]["name"] == "Hi"
    a.delete_macro(0)
    assert a.get_state()["macros"] == []


def test_macro_replace_and_delete_fixes_references(api):
    a, kb = api
    a.save_macro(None, {"name": "A", "events": tap(4)})
    a.save_macro(None, {"name": "B", "events": tap(5)})
    assert a.save_macro(1, {"name": "B2", "events": tap(6)})["index"] == 1
    a.remap_key(0, 10, {"type": "macro", "index": 0})
    a.remap_key(0, 11, {"type": "macro", "index": 1})
    a.delete_macro(0)
    acts = decode_layer(kb.state.layers[0])
    assert acts[10] == NoAction() and acts[11] == MacroRef(0)
    assert [m.name for m in decode_macros(kb.state.macros)] == ["B2"]


def test_profiles_and_restore(api):
    a, kb = api
    a.save_profile("Default")
    a.set_lighting(brightness=1)
    a.apply_profile("Default")
    assert Config(kb.state.config).brightness() == 4
    assert any(b["factory"] for b in a.list_backups())


def test_profile_export_import_and_restore(api, tmp_path):
    a, kb = api
    assert a.save_profile("One") == ["One"]
    out = tmp_path / "one.json"
    a.export_profile("One", str(out))
    a.delete_profile("One")
    assert a.list_profiles() == []
    assert a.import_profile(str(out)) == "One"
    a.set_lighting(brightness=1)
    a.restore_backup("factory")
    assert Config(kb.state.config).brightness() == 4
    json.dumps(a.list_backups())


def test_shortcuts(api):
    a, kb = api
    rows = a.get_shortcuts()
    mute = next(r for r in rows if r["keys"] == "Fn + F1")
    assert mute["current"] == "Mute" and mute["changed"] is False
    a.remap_key(1, 12, {"type": "consumer", "usage": 0x192})
    mute = next(r for r in a.get_shortcuts() if r["keys"] == "Fn + F1")
    assert mute["changed"] is True and mute["current"] == "Calculator"


def test_colors(api):
    a, kb = api
    a.set_key_colors([(1, 2, 3)] * 126)
    a.set_palette(5, [[9, 8, 7]] * 7)
    s = a.get_state()
    assert tuple(s["key_colors"][0]) == (1, 2, 3)
    assert tuple(s["palette"][5][0]) == (9, 8, 7)


def test_app_settings(api):
    a, kb = api
    assert a.get_app_settings() == {"theme": "dark", "autostart": False}
    assert a.set_app_settings(theme="light") == {"theme": "light", "autostart": False}
    assert a.set_app_settings(autostart=True) == {"theme": "light", "autostart": True}


# ---------- failures are always ApiError

BAD_ACTION = {"type": "key", "hid": 0x04}
EV = {"kind": "key", "code": 1}


@pytest.mark.parametrize("call", [
    lambda a: a.remap_key(4, 0, BAD_ACTION),
    lambda a: a.remap_key(-1, 0, BAD_ACTION),
    lambda a: a.remap_key(0, 126, BAD_ACTION),
    lambda a: a.remap_key(0, -1, BAD_ACTION),
    lambda a: a.remap_key("0", 0, BAD_ACTION),
    lambda a: a.remap_key(True, 0, BAD_ACTION),
    lambda a: a.remap_key(0, 0, {"type": "nope"}),
    lambda a: a.remap_key(0, 0, {"type": "key", "hid": 999}),
    lambda a: a.remap_key(0, 0, {"type": "key"}),
    lambda a: a.remap_key(0, 0, "key"),
    lambda a: a.remap_key(0, 0, None),
    lambda a: a.remap_key(0, 0, {"type": "macro", "index": 0}),
    lambda a: a.reset_key(0, 126),
    lambda a: a.reset_key(9, 0),
    lambda a: a.reset_layer(4),
    lambda a: a.reset_layer(-1),
    lambda a: a.save_macro(None, {"name": "x"}),
    lambda a: a.save_macro(None, {"name": 5, "events": []}),
    lambda a: a.save_macro(None, {"name": "x", "events": [{"kind": "zzz", "code": 1}]}),
    lambda a: a.save_macro(None, {"name": "x", "events": [{"kind": "key", "code": "a"}]}),
    lambda a: a.save_macro(None, {"name": "x", "events": [{**EV, "delay_ms": 1.5}]}),
    lambda a: a.save_macro(None, {"name": "x" * 31, "events": []}),
    lambda a: a.save_macro(None, {"name": "big", "events": tap(4) * 600}),
    lambda a: a.save_macro(None, None),
    lambda a: a.save_macro(0, {"name": "x", "events": []}),
    lambda a: a.save_macro(-1, {"name": "x", "events": []}),
    lambda a: a.save_macro("0", {"name": "x", "events": []}),
    lambda a: a.delete_macro(0),
    lambda a: a.delete_macro(-1),
    lambda a: a.delete_macro("a"),
    lambda a: a.set_palette(23, [[0, 0, 0]] * 7),
    lambda a: a.set_palette(-1, [[0, 0, 0]] * 7),
    lambda a: a.set_palette(0, [[0, 0, 0]] * 6),
    lambda a: a.set_palette(0, [[0, 0, 256]] * 7),
    lambda a: a.set_palette(0, [5] * 7),
    lambda a: a.set_palette(0, None),
    lambda a: a.set_key_colors([[0, 0, 0]] * 125),
    lambda a: a.set_key_colors([[0, 0, 300]] * 126),
    lambda a: a.set_key_colors(None),
    lambda a: a.set_lighting(effect=0x0E),
    lambda a: a.set_lighting(effect="1"),
    lambda a: a.set_lighting(brightness=5),
    lambda a: a.set_lighting(speed="fast"),
    lambda a: a.set_lighting(color=8),
    lambda a: a.set_lighting(direction="yes"),
    lambda a: a.set_settings(win_mac="linux"),
    lambda a: a.set_settings(sleep=256),
    lambda a: a.set_settings(debounce=5),
    lambda a: a.set_keep_lights_on("yes"),
    lambda a: a.save_profile("../evil"),
    lambda a: a.save_profile("CON"),
    lambda a: a.save_profile(None),
    lambda a: a.apply_profile("missing"),
    lambda a: a.apply_profile("../evil"),
    lambda a: a.delete_profile("../evil"),
    lambda a: a.export_profile("missing", "x.json"),
    lambda a: a.export_profile("../evil", "x.json"),
    lambda a: a.import_profile("no/such/file.json"),
    lambda a: a.restore_backup("nope"),
    lambda a: a.restore_backup("../factory"),
    lambda a: a.restore_backup(None),
    lambda a: a.set_app_settings(theme="pink"),
    lambda a: a.set_app_settings(autostart="yes"),
])
def test_bad_arguments_raise_api_error(api, call):
    a, kb = api
    before = kb.state.config, list(kb.state.layers), kb.state.macros, kb.state.palette
    with pytest.raises(ApiError) as ei:
        call(a)
    assert str(ei.value)
    assert (kb.state.config, list(kb.state.layers), kb.state.macros, kb.state.palette) == before


def test_export_to_unwritable_path(api, tmp_path):
    a, kb = api
    a.save_profile("One")
    with pytest.raises(ApiError):
        a.export_profile("One", str(tmp_path / "missing_dir" / "x.json"))


def test_import_garbage_file(api, tmp_path):
    a, kb = api
    p = tmp_path / "junk.json"
    p.write_text("[1, 2")
    with pytest.raises(ApiError):
        a.import_profile(str(p))
    p.write_text('{"name": "ok", "snapshot": {"config": "zz"}}')
    with pytest.raises(ApiError):
        a.import_profile(str(p))


def test_corrupt_settings_file(api):
    a, kb = api
    (a.store.root / "settings.json").write_text("{nope")
    with pytest.raises(ApiError):
        a.get_app_settings()
    with pytest.raises(ApiError):
        a.set_app_settings(theme="light")


def test_disconnected(tmp_path, fixture_blocks):
    a, kb = make(tmp_path, fixture_blocks, detect=lambda: None)
    s = a.get_state()
    assert s["connected"] is False and "layers" not in s
    with pytest.raises(ApiError):
        a.remap_key(0, 0, BAD_ACTION)
    with pytest.raises(ApiError):
        a.set_lighting(brightness=1)
    with pytest.raises(ApiError):
        a.save_profile("x")
    with pytest.raises(ApiError):
        a.get_shortcuts()


def test_link_error_becomes_api_error(api):
    a, kb = api
    kb.fail_on_write = True
    with pytest.raises(ApiError) as ei:
        a.remap_key(0, 0, BAD_ACTION)
    assert "unplugged" in str(ei.value)


def test_verify_error_becomes_api_error(api, monkeypatch):
    a, kb = api
    monkeypatch.setattr(a.m.link, "read_block", lambda name: b"\0")
    with pytest.raises(ApiError):
        a.remap_key(0, 0, BAD_ACTION)


def test_timeout_becomes_api_error(tmp_path, fixture_blocks):
    a, kb = make(tmp_path, fixture_blocks)
    a.w = StuckWorker()
    a.TIMEOUT_S = 0.01
    with pytest.raises(ApiError) as ei:
        a.set_lighting(brightness=1)
    assert "busy" in str(ei.value) and "Refresh" in str(ei.value)


def test_unknown_effect_byte(api):
    a, kb = api
    raw = bytearray(kb.state.config)
    raw[OFF_EFFECT] = 0x0E
    kb.state.config = bytes(raw)
    a.m.poll()
    s = a.get_state()
    assert s["lighting"]["effect"] == 0x0E
    assert all(s["lighting"][k] is None for k in ("brightness", "speed", "color", "direction"))
    assert s["settings"]["debounce"] is not None
    json.dumps(s)
    with pytest.raises(ApiError):
        a.set_lighting(brightness=1)
    a.set_lighting(effect=1, brightness=1)
    assert a.get_state()["lighting"]["brightness"] == 1


# ---------- final fix wave

BAD_MACROS = bytes([6, 0]) + bytes(4094)


def test_state_sections_fail_independently(api):
    a, kb = api
    a.m.snapshot.macros = BAD_MACROS
    s = a.get_state()
    assert s["macros"] is None and s["macros_error"]
    assert len(s["layers"]) == 4 and s["lighting"]["effect"] == 1 and len(s["palette"]) == 23
    assert "layers_error" not in s
    json.dumps(s)


def test_successful_write_is_not_reported_as_failed(api, monkeypatch):
    a, kb = api

    def broken():
        raise ApiError("view broke")
    monkeypatch.setattr(a, "get_state", broken)
    res = a.set_lighting(brightness=1)
    assert Config(kb.state.config).brightness() == 1
    assert "view broke" in res["warning"]


def test_undecodable_macros_point_to_clear_macros(api):
    a, kb = api
    acts = decode_layer(kb.state.layers[0])
    acts[10] = MacroRef(0)
    kb.state.layers[0] = encode_layer(acts)
    kb.state.macros = BAD_MACROS
    with pytest.raises(ApiError, match="Clear all macros"):
        a.save_macro(None, {"name": "x", "events": tap(4)})
    with pytest.raises(ApiError, match="Clear all macros"):
        a.delete_macro(0)
    s = a.clear_macros()
    assert s["macros"] == [] and decode_macros(kb.state.macros) == []
    assert decode_layer(kb.state.layers[0])[10] == NoAction()
    assert a.save_macro(None, {"name": "x", "events": tap(4)})["index"] == 0


def test_remap_to_missing_macro_is_refused(api):
    a, kb = api
    before = list(kb.state.layers)
    with pytest.raises(ApiError, match="macro"):
        a.remap_key(0, 10, {"type": "macro", "index": 0})
    a.save_macro(None, {"name": "A", "events": tap(4)})
    with pytest.raises(ApiError):
        a.remap_key(0, 10, {"type": "macro", "index": 1})
    assert kb.state.layers == before
    a.remap_key(0, 10, {"type": "macro", "index": 0})
    assert decode_layer(kb.state.layers[0])[10] == MacroRef(0)


def test_import_profile_overwrite(api, tmp_path):
    a, kb = api
    a.save_profile("One")
    out = tmp_path / "one.json"
    a.export_profile("One", str(out))
    with pytest.raises(ApiError, match="already exists"):
        a.import_profile(str(out))
    assert a.import_profile(str(out), overwrite=True) == "One"


def test_subscribe_forwards_manager_events(api):
    a, kb = api
    got = []
    a.subscribe(lambda n, p: got.append((n, p)))
    kb.connected = False
    a.m.poll()
    assert ("state", {}) in got and any(n == "error" for n, _ in got)
    assert a.get_state()["connected"] is False


def test_api_write_failure_raises_and_sends_no_error_event(api):
    a, kb = api
    got = []
    a.subscribe(lambda n, p: got.append(n))
    kb.fail_on_write = True
    with pytest.raises(ApiError, match="retry"):
        a.set_lighting(brightness=1)
    assert "error" not in got


def test_mirror_save_failure_still_returns_state_with_warning(api, monkeypatch):
    a, kb = api

    def boom(s):
        raise OSError("disk full")
    monkeypatch.setattr(a.store, "save_mirror", boom)
    s = a.set_lighting(brightness=1)
    assert s["lighting"]["brightness"] == 1 and "local copy" in s["warning"]
    r = a.remap_key(0, 45, {"type": "key", "hid": 0x73})
    assert "local copy" in r["warning"] and "cable" in r["warning"]
    m = a.save_macro(None, {"name": "x", "events": tap(4)})
    assert "local copy" in m["warning"]


def test_unexpected_errors_are_logged_with_traceback(api, monkeypatch, caplog):
    a, kb = api

    def bug(mutator):
        raise RuntimeError("boom")
    monkeypatch.setattr(a.m, "apply", bug)
    with caplog.at_level("ERROR", logger="cavalry"):
        with pytest.raises(ApiError, match="Unexpected"):
            a.set_lighting(brightness=1)
        with pytest.raises(ApiError):
            a.set_lighting(brightness=9)          # expected: not logged
    rec = [r for r in caplog.records if r.name == "cavalry"]
    assert len(rec) == 1 and rec[0].exc_info


def test_event_contract_is_documented():
    import engine.api
    for name in ("state", "link", "error", "mirror_mismatch", "online"):
        assert name in engine.api.__doc__
