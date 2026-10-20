import json
from pathlib import Path

import pytest

from engine.codec.snapshot import Snapshot
from engine.store import Settings, Store, StoreError


@pytest.fixture
def snap(fixture_blocks):
    b = fixture_blocks
    return Snapshot(b["config"], list(b["layers"]), b["macros"], b["key_colors"], b["palette"])


def test_mirror(tmp_path, snap):
    st = Store(tmp_path)
    assert st.load_mirror() is None
    st.save_mirror(snap)
    assert st.load_mirror().to_json() == snap.to_json()


def test_backups_rolling_and_factory(tmp_path, snap):
    st = Store(tmp_path, keep=3)
    f = st.save_backup(snap, factory=True)
    names = [st.save_backup(snap, label=f"b{i}") for i in range(5)]
    infos = st.list_backups()
    assert st.has_factory()
    assert [i.label for i in infos if not i.factory] == ["b4", "b3", "b2"]
    assert any(i.factory and i.name == f for i in infos)
    assert st.load_backup(names[-1]).to_json() == snap.to_json()
    with pytest.raises(StoreError):
        st.save_backup(snap, factory=True)


def test_profiles(tmp_path, snap):
    st = Store(tmp_path)
    st.save_profile("Gaming", snap)
    assert st.list_profiles() == ["Gaming"]
    out = tmp_path / "x.cavalry.json"
    st.export_profile("Gaming", out)
    st.delete_profile("Gaming")
    assert st.list_profiles() == []
    assert st.import_profile(out) == "Gaming"
    assert st.load_profile("Gaming").to_json() == snap.to_json()
    with pytest.raises(StoreError):
        st.save_profile("../evil", snap)


def test_settings(tmp_path):
    st = Store(tmp_path)
    assert st.load_settings() == Settings()
    st.save_settings(Settings(theme="light", autostart=True))
    assert st.load_settings().theme == "light"


BAD_NAMES = ["../evil", "..\\evil", "a/b", "a\\b", "", " ", ".", "..", "CON", "con", "NUL", "aux",
             "PRN", "COM1", "lpt9", "CON.txt", "name.", "name ", " name", "a:b", "a" * 41,
             "ok\n", "C:\\x"]


@pytest.mark.parametrize("bad", BAD_NAMES)
def test_profile_names_rejected_everywhere(tmp_path, snap, bad):
    st = Store(tmp_path)
    st.save_profile("Real", snap)
    with pytest.raises(StoreError):
        st.save_profile(bad, snap)
    with pytest.raises(StoreError):
        st.load_profile(bad)
    with pytest.raises(StoreError):
        st.delete_profile(bad)
    with pytest.raises(StoreError):
        st.export_profile(bad, tmp_path / "o.json")
    assert st.list_profiles() == ["Real"]


@pytest.mark.parametrize("bad", ["../mirror", "..\\settings", "a/b", "", "CON", "nope", "x.json",
                                 "20250101-000000-000000 ", "factory.json", "mirror"])
def test_load_backup_rejects_bad_names(tmp_path, snap, bad):
    (tmp_path / "mirror.json").write_text(json.dumps(snap.to_json()))
    st = Store(tmp_path)
    with pytest.raises(StoreError):
        st.load_backup(bad)


def test_load_backup_missing(tmp_path):
    with pytest.raises(StoreError):
        Store(tmp_path).load_backup("20250101-000000-000000")


def test_import_profile_bad_name_in_file(tmp_path, snap):
    st = Store(tmp_path)
    for name in ["../evil", 5, None, "CON"]:
        p = tmp_path / "in.json"
        p.write_text(json.dumps({"name": name, "snapshot": snap.to_json()}))
        with pytest.raises(StoreError):
            st.import_profile(p)
    assert st.list_profiles() == []


def test_import_profile_defaults_name_to_stem(tmp_path, snap):
    st = Store(tmp_path)
    p = tmp_path / "Stem.json"
    p.write_text(json.dumps({"snapshot": snap.to_json()}))
    assert st.import_profile(p) == "Stem"


CORRUPT = [
    "not json",
    "[]",
    "5",
    "{}",
    '{"snapshot": 5}',
    '{"snapshot": {}}',
    '{"snapshot": {"config": "zz", "layers": [], "macros": "", "key_colors": "", "palette": ""}}',
    '{"snapshot": {"config": "00", "layers": "x", "macros": "", "key_colors": "", "palette": ""}}',
]


@pytest.mark.parametrize("text", CORRUPT)
def test_corrupt_files_raise_store_error(tmp_path, snap, text):
    st = Store(tmp_path)
    st.save_profile("P", snap)
    (tmp_path / "profiles" / "P.json").write_text(text)
    (tmp_path / "mirror.json").write_text(text)
    (tmp_path / "backups" / "20250101-000000-000000.json").write_text(text)
    imp = tmp_path / "imp.json"
    imp.write_text(text)
    with pytest.raises(StoreError):
        st.load_profile("P")
    with pytest.raises(StoreError):
        st.import_profile(imp)
    with pytest.raises(StoreError):
        st.load_backup("20250101-000000-000000")
    with pytest.raises(StoreError):
        st.load_mirror()


def test_export_of_corrupt_profile_fails(tmp_path, snap):
    st = Store(tmp_path)
    st.save_profile("P", snap)
    (tmp_path / "profiles" / "P.json").write_text("not json")
    with pytest.raises(StoreError):
        st.export_profile("P", tmp_path / "o.json")
    assert not (tmp_path / "o.json").exists()


def test_corrupt_settings(tmp_path):
    st = Store(tmp_path)
    for text in ['{"theme": "neon"}', '{"autostart": "maybe"}', "[]", "nope"]:
        (tmp_path / "settings.json").write_text(text)
        with pytest.raises(StoreError):
            st.load_settings()


def test_non_utf8_file_is_store_error(tmp_path):
    st = Store(tmp_path)
    (tmp_path / "settings.json").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(StoreError):
        st.load_settings()


def test_tampered_snapshot_in_backup(tmp_path, snap):
    st = Store(tmp_path)
    bad = snap.to_json()
    bad["config"] = bad["config"][:-2]
    name = st.save_backup(snap)
    (tmp_path / "backups" / f"{name}.json").write_text(
        json.dumps({"created": "2025-01-01T00:00:00", "factory": False, "snapshot": bad}))
    with pytest.raises(StoreError):
        st.load_backup(name)


def test_list_backups_skips_corrupt_and_save_still_works(tmp_path, snap):
    st = Store(tmp_path, keep=2)
    (tmp_path / "backups" / "20240101-000000-000001.json").write_text("not json")
    (tmp_path / "backups" / "20240101-000000-000002.json").write_text('{"created": "yesterday", "factory": false}')
    (tmp_path / "backups" / "20240101-000000-000003.json").write_text('{"factory": false}')
    st.save_backup(snap, label="a")
    st.save_backup(snap, label="b")
    st.save_backup(snap, label="c")
    assert [i.label for i in st.list_backups()] == ["c", "b"]


def test_factory_survives_cleanup_and_tampered_metadata(tmp_path, snap):
    st = Store(tmp_path, keep=1)
    st.save_backup(snap, factory=True)
    p = tmp_path / "backups" / "factory.json"
    d = json.loads(p.read_text())
    d["factory"] = False
    p.write_text(json.dumps(d))
    for i in range(4):
        st.save_backup(snap, label=str(i))
    assert p.exists()
    assert st.has_factory()
    with pytest.raises(StoreError):
        st.save_backup(snap, factory=True)


def test_factory_survives_older_than_keep_window(tmp_path, snap):
    st = Store(tmp_path, keep=1)
    st.save_backup(snap, factory=True)
    for i in range(3):
        st.save_backup(snap, label=str(i))
    infos = st.list_backups()
    assert sum(i.factory for i in infos) == 1
    assert len(infos) == 2


def test_backup_names_unique(tmp_path, snap):
    st = Store(tmp_path, keep=50)
    names = {st.save_backup(snap) for _ in range(30)}
    assert len(names) == 30


def test_atomic_write_leaves_no_tmp_and_keeps_old_on_failure(tmp_path, snap, monkeypatch):
    st = Store(tmp_path)
    st.save_mirror(snap)
    assert not list(tmp_path.rglob("*.tmp"))
    before = (tmp_path / "mirror.json").read_text()

    def boom(self, target):
        raise OSError("disk")

    monkeypatch.setattr("pathlib.Path.replace", boom)
    with pytest.raises(OSError):
        st.save_mirror(snap)
    monkeypatch.undo()
    assert (tmp_path / "mirror.json").read_text() == before
    assert not list(tmp_path.rglob("*.tmp"))


def test_invalid_snapshot_not_saved(tmp_path, snap):
    st = Store(tmp_path)
    bad = snap.copy()
    bad.macros = b"\x00"
    with pytest.raises(ValueError):
        st.save_mirror(bad)
    with pytest.raises(ValueError):
        st.save_backup(bad)
    with pytest.raises(ValueError):
        st.save_profile("P", bad)
    assert st.load_mirror() is None and st.list_backups() == [] and st.list_profiles() == []


def test_keep_must_be_positive(tmp_path):
    with pytest.raises(StoreError):
        Store(tmp_path, keep=0)


def test_write_fsyncs_tmp_before_replace(tmp_path, snap, monkeypatch):
    import engine.store as store_mod
    calls = []
    real_fsync, real_replace = store_mod.os.fsync, store_mod.Path.replace
    monkeypatch.setattr(store_mod.os, "fsync", lambda fd: (calls.append("fsync"), real_fsync(fd)))
    monkeypatch.setattr(store_mod.Path, "replace",
                        lambda self, t: (calls.append("replace"), real_replace(self, t))[1])
    Store(tmp_path).save_mirror(snap)
    assert calls == ["fsync", "replace"]


def test_corrupt_mirror_is_set_aside(tmp_path, snap):
    st = Store(tmp_path)
    (tmp_path / "mirror.json").write_text("{trunc")
    assert st.load_mirror_or_none() is None
    assert not (tmp_path / "mirror.json").exists()
    aside = list(tmp_path.glob("mirror.corrupt-*.json"))
    assert len(aside) == 1 and aside[0].read_text() == "{trunc"
    st.save_mirror(snap)
    assert st.load_mirror_or_none().to_json() == snap.to_json()


def test_corrupt_factory_is_set_aside_so_a_new_one_can_be_taken(tmp_path, snap):
    st = Store(tmp_path)
    st.save_backup(snap, factory=True)
    (tmp_path / "backups" / "factory.json").write_text("")
    assert st.has_factory() is False
    assert list((tmp_path / "backups").glob("factory.corrupt-*.json"))
    assert all(not i.factory for i in st.list_backups())
    st.save_backup(snap, factory=True)
    assert st.has_factory() and st.load_backup("factory").to_json() == snap.to_json()


def test_rolling_cleanup_failure_does_not_abort_backup(tmp_path, snap, monkeypatch):
    st = Store(tmp_path, keep=1)
    st.save_backup(snap, label="old")

    def boom(self, missing_ok=False):
        raise PermissionError("locked")
    monkeypatch.setattr("pathlib.Path.unlink", boom)
    name = st.save_backup(snap, label="new")
    monkeypatch.undo()
    assert st.load_backup(name).to_json() == snap.to_json()


def test_latest_backup(tmp_path, snap):
    st = Store(tmp_path)
    assert st.latest_backup() is None
    st.save_backup(snap, factory=True)
    assert st.latest_backup() is None
    other = snap.copy()
    other.palette = bytes(483)
    st.save_backup(snap)
    st.save_backup(other)
    assert st.latest_backup() == other


def _profile_file(tmp_path, snap, name="Imp"):
    p = tmp_path / "in.json"
    p.write_text(json.dumps({"name": name, "snapshot": snap.to_json()}))
    return p


def test_import_profile_refuses_existing_name_unless_overwrite(tmp_path, snap):
    st = Store(tmp_path)
    st.save_profile("Imp", snap)
    other = snap.copy()
    other.palette = bytes(483)
    p = _profile_file(tmp_path, other)
    with pytest.raises(StoreError, match="exists"):
        st.import_profile(p)
    assert st.load_profile("Imp") == snap
    assert st.import_profile(p, overwrite=True) == "Imp"
    assert st.load_profile("Imp") == other


def test_import_profile_rejects_undecodable_macros(tmp_path, snap):
    st = Store(tmp_path)
    bad = snap.copy()
    bad.macros = bytes([6, 0]) + bytes(4094)
    with pytest.raises(StoreError):
        st.import_profile(_profile_file(tmp_path, bad))
    assert st.list_profiles() == []


def _fail_reads_once(monkeypatch, filename):
    real = Path.read_text
    left = [1]

    def flaky(self, *a, **k):
        if self.name == filename and left[0]:
            left[0] -= 1
            raise PermissionError("sharing violation")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky)


def test_transient_read_error_on_factory_is_not_corruption(tmp_path, snap, monkeypatch):
    st = Store(tmp_path)
    st.save_backup(snap, factory=True)
    _fail_reads_once(monkeypatch, "factory.json")
    assert st.has_factory() is True
    assert (tmp_path / "backups" / "factory.json").exists()
    assert not list((tmp_path / "backups").glob("factory.corrupt-*.json"))
    assert st.load_backup("factory").to_json() == snap.to_json()


def test_factory_never_replaced_while_unreadable(tmp_path, snap, monkeypatch):
    st = Store(tmp_path)
    st.save_backup(snap, factory=True)
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError("locked")))
    with pytest.raises(StoreError, match="already exists"):
        st.save_backup(snap, factory=True)
    with pytest.raises(StoreError, match="cannot read"):
        st.load_backup("factory")


def test_transient_read_error_on_mirror_raises_and_keeps_file(tmp_path, snap, monkeypatch):
    st = Store(tmp_path)
    st.save_mirror(snap)
    _fail_reads_once(monkeypatch, "mirror.json")
    with pytest.raises(StoreError, match="cannot read"):
        st.load_mirror_or_none()
    assert (tmp_path / "mirror.json").exists()
    assert not list(tmp_path.glob("mirror.corrupt-*.json"))
    assert st.load_mirror_or_none().to_json() == snap.to_json()
