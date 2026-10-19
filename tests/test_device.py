import pytest

from engine.codec.config import Config
from engine.device import DeviceManager, NotReady
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
    assert dm.partial is True
    with pytest.raises(NotReady):
        dm.apply(lambda s: s)


def test_disconnect_mid_batch_marks_pending_then_reapplies(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(Exception):
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


def test_pending_replay_is_backed_up(env):
    kb, st, clock, state, dm, ev = env
    connect(dm, clock)
    kb.fail_on_write = True
    with pytest.raises(Exception):
        dm.apply(set_sleep(0))
    kb.fail_on_write = False
    before = len(st.list_backups())
    clock.t += 5.1
    dm.poll()
    assert len(st.list_backups()) == before + 1


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
