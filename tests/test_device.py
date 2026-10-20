import time
from pathlib import Path

import pytest

from engine.codec.config import Config
from engine.codec.snapshot import SnapshotError
from engine.device import DeviceManager, NotReady, VerifyError
from engine.links.base import LinkError
from engine.links.radio import RadioLink
from engine.links.wired import WiredLink
from engine.store import Store
from tests.fakes import FakeKeyboard


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path, fixture_blocks):
    kb = FakeKeyboard(fixture_blocks)
    st = Store(tmp_path)
    clock = Clock()
    state = {"kind": "wired"}
    opener = lambda k: WiredLink(kb.feature_device()) if k == "wired" else RadioLink(
        kb.packet_device(), timeout_ms=1)
    dm = DeviceManager(st, detect=lambda: state["kind"], open_link=opener, clock=clock)
    events = []
    dm.subscribe(lambda n, p: events.append(n))
    return kb, st, clock, state, dm, events


def connect(dm, clock):
    dm.poll()
    clock.t += 5.1
    dm.poll()


def set_sleep(v):
    def m(s):
        c = Config(s.config); c.sleep = v; s.config = c.to_bytes(); return s
    return m


def test_stability_gate(env):
    kb, st, clock, state, dm, ev = env
    dm.poll()
    assert dm.link is None
    with pytest.raises(NotReady):
        dm.apply(set_sleep(0))
    clock.t += 5.1
    dm.poll()
    assert dm.link is not None and "state" in ev


def test_factory_snapshot_once(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    assert st.has_factory()
    assert st.load_backup("factory").to_json() == kb.state.to_json()


def test_apply_backs_up_writes_verifies(env, fixture_blocks):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    before = len(st.list_backups())
    new = dm.apply(set_sleep(0))
    assert Config(kb.state.config).sleep == 0
    assert Config(new.config).sleep == 0
    assert len(st.list_backups()) == before + 1
    assert st.load_mirror().to_json() == kb.state.to_json()
    writes = [p for p in kb.sent if p[1] < 0x80]
    assert [p[1] for p in writes] == [0x04]       # only the changed block was written


def test_noop_apply_writes_nothing(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    n = len(kb.sent)
    dm.apply(lambda s: s)
    assert all(p[1] >= 0x80 for p in kb.sent[n:])


def test_radio_uses_mirror_and_partial(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)                       # wired first: mirror exists
    state["kind"] = "radio"
    connect(dm, clock)
    assert dm.kind == "radio" and dm.partial is False
    dm.apply(lambda s: (setattr(s, "palette", bytes(483)) or s))
    assert kb.state.palette == bytes(483)


def test_radio_without_mirror_is_partial(env):
    kb, st, clock, state, dm, ev = env
    state["kind"] = "radio"
    connect(dm, clock)
    assert dm.partial is True and dm.radio_config == kb.state.config
    with pytest.raises(NotReady, match=r"Fn \+ PrtSc"):
        dm.apply(lambda s: (setattr(s, "palette", bytes([1]) * 483) or s))
    before = kb.state.palette, list(kb.state.layers), kb.state.macros
    dm.apply(set_sleep(0))                   # config-only edits work over 2.4G before any cable read
    assert Config(kb.state.config).sleep == 0
    assert (kb.state.palette, list(kb.state.layers), kb.state.macros) == before
    assert Config(dm.radio_config).sleep == 0 and dm.snapshot is None
    assert not st.has_factory() and st.load_mirror_or_none() is None


def test_disconnect_mid_batch_marks_pending_then_reapplies(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_sleep(0))
    assert dm.pending is not None and dm.link is None
    kb.fail_on_write = False
    clock.t += 5.1
    dm.poll()
    assert Config(kb.state.config).sleep == 0 and dm.pending is None


def test_wrong_model_refused(env):
    kb, st, clock, state, dm, ev = env
    kb.identity = bytes.fromhex("030000000099")
    connect(dm, clock)
    assert dm.link is None and "error" in ev


def test_no_write_without_backup(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(st, "save_backup", boom)
    n = len(kb.sent)
    with pytest.raises(OSError):
        dm.apply(set_sleep(0))
    assert all(p[1] >= 0x80 for p in kb.sent[n:])
    assert dm.pending is None


def test_replay_adds_no_second_backup(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_sleep(0))
    kb.fail_on_write = False
    before = len(st.list_backups())
    clock.t += 5.1
    dm.poll()
    assert len(st.list_backups()) == before


def set_palette(s):
    s.palette = bytes(483)
    return s


def test_replay_writes_only_batch_blocks(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    assert kb.state.palette != bytes(483)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_palette)
    kb.fail_on_write = False
    c = Config(kb.state.config)               # changed on the keyboard while disconnected
    c.sleep = 7
    kb.state.config = c.to_bytes()
    n = len(kb.sent)
    clock.t += 5.1
    dm.poll()
    assert kb.state.palette == bytes(483)
    assert Config(kb.state.config).sleep == 7
    assert [p[1] for p in kb.sent[n:] if p[1] < 0x80] == [0x0A]
    assert Config(dm.snapshot.config).sleep == 7 and dm.snapshot.palette == bytes(483)
    assert dm.pending is None


def test_replay_runs_once(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_palette)
    assert ev.count("error") == 0              # apply failures are raised, not evented
    clock.t += 5.1
    dm.poll()                                  # replay fails too
    assert dm.pending is None and dm.link is None and ev.count("error") == 1
    kb.fail_on_write = False
    n = len(kb.sent)
    clock.t += 5.1
    dm.poll()
    assert dm.link is not None and ev.count("error") == 1
    assert all(p[1] >= 0x80 for p in kb.sent[n:])
    assert kb.state.palette != bytes(483)


def test_read_failure_on_connect_leaves_no_half_open_link(env):
    kb, st, clock, state, dm, ev = env
    real, closed = dm._open, []

    def bad(k):
        link = real(k)
        link.read_all = lambda: (_ for _ in ()).throw(SnapshotError("garbled"))
        orig = link.close
        link.close = lambda: (closed.append(1), orig())[1]
        return link
    dm._open = bad
    connect(dm, clock)
    assert dm.link is None and ev.count("error") == 1 and closed
    dm._open = real
    clock.t += 5.1
    dm.poll()
    assert dm.link is not None and dm.snapshot is not None


def test_verify_mismatch_keeps_link_and_no_pending(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    monkeypatch.setattr(dm.link, "read_block", lambda name: b"wrong")
    with pytest.raises(VerifyError):
        dm.apply(set_sleep(0))
    assert dm.link is not None and dm.pending is None and ev.count("error") == 0


def test_bad_subscriber_cannot_break_manager(env):
    from engine.device import Worker
    kb, st, clock, state, dm, ev = env
    dm.subscribe(lambda n, p: 1 / 0)
    connect(dm, clock)
    dm.apply(set_sleep(0))
    assert Config(kb.state.config).sleep == 0
    w = Worker(dm, poll_s=0.05)
    w.start()
    try:
        assert Config(w.call(dm.apply, set_sleep(1)).result(timeout=5).config).sleep == 1
    finally:
        w.stop()


def test_worker_runs_calls(env):
    from engine.device import Worker
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    w = Worker(dm, poll_s=0.05)
    w.start()
    try:
        out = w.call(dm.apply, set_sleep(0)).result(timeout=5)
        assert Config(out.config).sleep == 0
    finally:
        w.stop()


# ---------- final fix wave

def payloads(dm):
    got = []
    dm.subscribe(lambda n, p: got.append((n, p)))
    return got


def reconnect(dm, clock, state, kind="wired"):
    state["kind"] = None
    dm.poll()
    state["kind"] = kind
    connect(dm, clock)


def test_corrupt_mirror_at_startup_is_set_aside(tmp_path):
    (tmp_path / "mirror.json").write_text('{"config": "5a')
    dm = DeviceManager(Store(tmp_path), detect=lambda: None, open_link=None)
    assert dm.snapshot is None
    assert list(tmp_path.glob("mirror.corrupt-*.json"))


def test_radio_connect_with_corrupt_mirror_is_partial(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    (st.root / "mirror.json").write_text("garbage")
    state["kind"] = "radio"
    connect(dm, clock)
    assert dm.link is not None and dm.partial is True
    assert list(st.root.glob("mirror.corrupt-*.json"))


def test_corrupt_factory_is_retaken_on_next_wired_connect(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    (st.root / "backups" / "factory.json").write_text("{")
    reconnect(dm, clock, state)
    assert st.has_factory()
    assert st.load_backup("factory") == kb.state


def test_poll_mirror_save_failure_reported_once(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)

    def boom(s):
        raise OSError("disk full")
    monkeypatch.setattr(st, "save_mirror", boom)
    for v in (3, 4, 5):
        kb.state.config = set_sleep(v)(kb.state.copy()).config
        dm.poll()
        dm.poll()
    assert ev.count("error") == 1
    assert Config(dm.snapshot.config).sleep == 5


def go_radio(kb, dm, clock, state):
    kb.link_byte = 1
    kb.state.config = kb._own_link_byte(kb.state.config)
    state["kind"] = "radio"
    connect(dm, clock)


def test_restore_wired_snapshot_over_radio_keeps_link_byte(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    wired = dm.snapshot.copy()
    assert wired.config[0x0E] == 0
    go_radio(kb, dm, clock, state)
    n = len(kb.sent)
    dm.apply(lambda _: wired.copy())             # only the link byte differs: nothing to write
    assert all(p[1] == 0x44 for p in kb.sent[n:])
    changed = wired.copy()
    changed.config = set_sleep(9)(wired.copy()).config
    out = dm.apply(lambda _: changed.copy())     # verify reads back 0x0E = 1
    assert kb.state.config[0x0E] == 1 and out.config[0x0E] == 1
    assert Config(kb.state.config).sleep == 9


def flaky_reads(dm, mutate):
    real = dm._open

    def opener(k):
        link = real(k)
        orig = link.read_all

        def read_all():
            s = orig()
            mutate(s)
            return s
        link.read_all = read_all
        return link
    dm._open = opener
    return real


def test_factory_needs_two_identical_reads(env):
    kb, st, clock, state, dm, ev = env
    n = iter(range(1000))
    real = flaky_reads(dm, lambda s: setattr(s, "palette", bytes([next(n) % 256]) * 483))
    connect(dm, clock)
    assert dm.link is not None and not st.has_factory() and ev.count("error") == 1
    with pytest.raises(NotReady):
        dm.apply(set_sleep(0))                   # never write without a factory snapshot
    assert Config(kb.state.config).sleep != 0
    dm._open = real
    reconnect(dm, clock, state)
    assert st.has_factory() and st.load_backup("factory") == kb.state


def test_apply_takes_missing_factory_first(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    (st.root / "backups" / "factory.json").unlink()
    before = kb.state.copy()
    dm.apply(set_sleep(0))
    assert st.load_backup("factory") == before


def test_asleep_radio_keyboard_is_quiet(env):
    kb, st, clock, state, dm, ev = env
    got = payloads(dm)
    connect(dm, clock)                           # wired once: mirror exists
    kb.asleep = True
    state["kind"] = "radio"
    for _ in range(3):
        connect(dm, clock)
    assert dm.link is None and "error" not in ev
    assert got.count(("link", {"kind": "radio", "online": False})) == 1
    kb.asleep = False
    clock.t += 5.1
    dm.poll()
    assert dm.link is not None and dm.asleep is False


def test_radio_keyboard_falling_asleep_drops_quietly(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    state["kind"] = "radio"
    connect(dm, clock)
    assert dm.link is not None
    got = payloads(dm)
    kb.asleep = True
    n = len(kb.sent)
    dm.poll()
    assert [p[1] for p in kb.sent[n:]] == [0x07]   # one probe, no full config read
    assert dm.link is None and "error" not in ev
    assert ("link", {"kind": "radio", "online": False}) in got and ("state", {}) in got


def remap(s):
    s.layers[0] = bytes(504)
    return s


def set_brightness(v):
    def m(s):
        c = Config(s.config)
        c.set_brightness(v)
        s.config = c.to_bytes()
        return s
    return m


def rolling(st):
    return [i for i in st.list_backups() if not i.factory]


def test_config_tweaks_do_not_push_out_the_keymap_backup(tmp_path, fixture_blocks):
    kb = FakeKeyboard(fixture_blocks)
    st, clock = Store(tmp_path, keep=20), Clock()
    dm = DeviceManager(st, detect=lambda: "wired",
                       open_link=lambda k: WiredLink(kb.feature_device()), clock=clock)
    connect(dm, clock)
    pre_keymap = kb.state.copy()
    dm.apply(remap)
    for i in range(25):
        clock.t += 2
        dm.apply(set_brightness(i % 4 + 1 if i % 2 else 0))
    assert len(rolling(st)) == 2
    assert any(st.load_backup(i.name) == pre_keymap for i in rolling(st))
    clock.t += 61
    dm.apply(set_brightness(2))
    assert len(rolling(st)) == 3


def test_block_changes_always_back_up(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    dm.apply(remap)
    dm.apply(set_palette)
    assert len(rolling(st)) == 2


def test_no_duplicate_backup_when_base_unchanged(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    orig_layer = kb.state.layers[0]
    with monkeypatch.context() as mp:
        mp.setattr(dm.link, "read_block", lambda name: b"wrong")
        with pytest.raises(VerifyError):
            dm.apply(remap)
    kb.state.layers[0] = orig_layer              # the keyboard did not keep the write
    dm.apply(remap)
    assert len(rolling(st)) == 1


def test_wired_connect_reports_mirror_mismatch(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    got = payloads(dm)
    kb.state.layers[2] = bytes([0, 0, 0, 4]) * 126  # changed by another app while we were away
    kb.state.config = set_sleep(1)(kb.state.copy()).config
    reconnect(dm, clock, state)
    names = [n for n, _ in got]
    assert ("mirror_mismatch", {"blocks": ["layer2"]}) in got
    assert names.index("mirror_mismatch") < len(names) - 1 - names[::-1].index("state")
    assert st.load_mirror() == kb.state


def test_no_mismatch_event_when_only_config_differs(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.state.config = set_sleep(1)(kb.state.copy()).config
    reconnect(dm, clock, state)
    assert "mirror_mismatch" not in ev


def test_state_event_on_drop(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    ev.clear()
    kb.connected = False
    dm.poll()
    assert dm.link is None and "state" in ev
    kb.connected = True
    clock.t += 5.1
    dm.poll()
    assert dm.link is not None
    ev.clear()
    state["kind"] = None
    dm.poll()
    assert "state" in ev


def test_apply_failures_raise_without_error_events(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    with monkeypatch.context() as mp:
        mp.setattr(dm.link, "read_block", lambda name: b"wrong")
        with pytest.raises(VerifyError):
            dm.apply(set_sleep(0))
    kb.fail_on_write = True
    with pytest.raises(LinkError, match="retry"):
        dm.apply(set_sleep(1))
    assert "error" not in ev and "state" in ev  # the drop is still announced


def test_failed_replay_emits_state(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_palette)
    ev.clear()
    clock.t += 5.1
    dm.poll()
    assert dm.link is None and ev.count("error") == 1 and ev[-1] == "state"


def test_mirror_save_failure_after_write_is_a_warning(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)

    def boom(s):
        raise OSError("disk full")
    monkeypatch.setattr(st, "save_mirror", boom)
    out = dm.apply(set_sleep(0))
    assert Config(out.config).sleep == 0 and Config(dm.snapshot.config).sleep == 0
    assert "local copy" in dm.last_warning
    assert "error" not in ev
    monkeypatch.undo()
    dm.apply(set_sleep(2))
    assert dm.last_warning is None


def test_mirror_save_failure_after_replay_is_one_error(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(LinkError):
        dm.apply(set_palette)
    kb.fail_on_write = False
    got = payloads(dm)
    real = st.save_mirror
    calls = []

    def save(s):
        calls.append(1)
        if len(calls) > 1:                       # connect saves fine, the replay save fails
            raise OSError("disk full")
        real(s)
    monkeypatch.setattr(st, "save_mirror", save)
    clock.t += 5.1
    dm.poll()
    assert kb.state.palette == bytes(483) and dm.snapshot.palette == bytes(483)
    errors = [p["message"] for n, p in got if n == "error"]
    assert errors == ["Saved to keyboard, but the local copy couldn't be saved"]
    assert dm.link is not None


def test_worker_logs_poll_tracebacks(env, caplog):
    import time
    from engine.device import Worker
    kb, st, clock, state, dm, ev = env

    def bad_poll():
        raise RuntimeError("bug")
    dm.poll = bad_poll
    w = Worker(dm, poll_s=0.01)
    with caplog.at_level("ERROR", logger="cavalry"):
        w.start()
        try:
            deadline = time.monotonic() + 5
            while not caplog.records and time.monotonic() < deadline:
                time.sleep(0.01)
        finally:
            w.stop()
    rec = [r for r in caplog.records if r.name == "cavalry"]
    assert rec and rec[0].exc_info and "error" in ev


def fail_reads(monkeypatch, filename, times=1):
    real = Path.read_text
    left = [times]

    def flaky(self, *a, **k):
        if self.name == filename and left[0]:
            left[0] -= 1
            raise PermissionError("sharing violation")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky)


def test_transient_factory_read_error_never_recaptures_factory(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    fpath = st.root / "backups" / "factory.json"
    original = fpath.read_text()
    kb.state = remap(kb.state.copy())             # user-modified state
    fail_reads(monkeypatch, "factory.json", times=3)
    reconnect(dm, clock, state)
    dm.apply(set_sleep(0))
    assert fpath.read_text() == original
    assert not list(fpath.parent.glob("factory.corrupt-*.json"))


def test_transient_mirror_read_error_on_radio_connect_keeps_mirror(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    mirror = st.root / "mirror.json"
    original = mirror.read_text()
    fail_reads(monkeypatch, "mirror.json")
    state["kind"] = "radio"
    connect(dm, clock)
    assert dm.link is None and "error" in ev
    assert mirror.read_text() == original
    assert not list(st.root.glob("mirror.corrupt-*.json"))
    clock.t += 5.1
    dm.poll()                                     # retries later and succeeds
    assert dm.link is not None and dm.partial is False


def test_transient_mirror_read_error_on_wired_connect_keeps_mirror(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    mirror = st.root / "mirror.json"
    original = mirror.read_text()
    state["kind"] = None
    dm.poll()
    fail_reads(monkeypatch, "mirror.json")
    state["kind"] = "wired"
    connect(dm, clock)
    assert dm.link is None and "error" in ev
    assert mirror.read_text() == original
    assert not list(st.root.glob("mirror.corrupt-*.json"))


def test_transient_mirror_read_error_at_startup_keeps_file(tmp_path, fixture_blocks, monkeypatch):
    kb = FakeKeyboard(fixture_blocks)
    st = Store(tmp_path)
    st.save_mirror(kb.state)
    fail_reads(monkeypatch, "mirror.json")
    dm = DeviceManager(st, detect=lambda: None, open_link=None)
    assert dm.snapshot is None
    assert (tmp_path / "mirror.json").exists()
    assert not list(tmp_path.glob("mirror.corrupt-*.json"))


def test_failed_backup_does_not_suppress_next_config_backup(env, monkeypatch):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    real = st.save_backup

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(st, "save_backup", boom)
    before = kb.state.copy()
    with pytest.raises(OSError):
        dm.apply(set_brightness(1))
    assert kb.state == before                     # nothing written
    clock.t += 5
    with pytest.raises(OSError):
        dm.apply(set_brightness(2))               # still tries a backup, still refuses to write
    assert kb.state == before
    monkeypatch.setattr(st, "save_backup", real)
    clock.t += 5
    dm.apply(set_brightness(3))
    assert len(rolling(st)) == 1


# ---------- shutdown drain

class _IdleManager:
    def __init__(self):
        self.polls = 0

    def poll(self):
        self.polls += 1

    def _emit(self, name, payload=None):
        pass


def _slow(gate, done, tag, secs=0.3):
    def job():
        gate.set()
        time.sleep(secs)
        done.append(tag)
        return tag
    return job


def test_worker_stop_waits_for_the_running_and_queued_jobs():
    import threading
    from engine.device import Worker
    w = Worker(_IdleManager(), poll_s=10)
    w.start()
    started, done = threading.Event(), []
    first = w.call(_slow(started, done, "running"))
    assert started.wait(5)
    second = w.call(_slow(threading.Event(), done, "queued", 0.1))
    w.stop()
    assert done == ["running", "queued"]
    assert first.result(timeout=0) == "running" and second.result(timeout=0) == "queued"


def test_worker_rejects_calls_after_stop_promptly():
    from engine.device import Worker, ShuttingDown
    w = Worker(_IdleManager(), poll_s=10)
    w.start()
    w.stop()
    t0 = time.monotonic()
    with pytest.raises(ShuttingDown):
        w.call(lambda: 1).result(timeout=5)
    assert time.monotonic() - t0 < 0.5


def test_worker_close_rejects_new_calls_but_finishes_queued_ones():
    import threading
    from engine.device import Worker, ShuttingDown
    w = Worker(_IdleManager(), poll_s=10)
    w.start()
    started, done = threading.Event(), []
    running = w.call(_slow(started, done, "running"))
    assert started.wait(5)
    w.close()
    with pytest.raises(ShuttingDown):
        w.call(lambda: 1).result(timeout=1)
    w.stop()
    assert running.result(timeout=0) == "running" and done == ["running"]


def test_worker_drain_timeout_covers_an_api_call_and_is_logged(caplog):
    import threading
    from engine.api import Api
    from engine.device import DRAIN_TIMEOUT_S, Worker
    assert DRAIN_TIMEOUT_S >= Api.TIMEOUT_S
    w = Worker(_IdleManager(), poll_s=10)
    w.start()
    gate, started = threading.Event(), threading.Event()
    w.call(lambda: (started.set(), gate.wait(5)))
    assert started.wait(5)
    with caplog.at_level("WARNING", logger="cavalry"):
        w.stop(timeout=0.2)
    gate.set()
    assert any("still writing" in r.getMessage() for r in caplog.records)
