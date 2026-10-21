from engine.shell import preflight, single


def test_webview2_version_reads_the_registry(monkeypatch):
    class Key:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    values = iter([OSError(), ("0.0.0.0", 1), ("155.0.1.2", 1)])

    def open_key(hive, path):
        return Key()

    def query(k, name):
        v = next(values)
        if isinstance(v, Exception):
            raise v
        return v
    monkeypatch.setattr(preflight.winreg, "OpenKey", open_key)
    monkeypatch.setattr(preflight.winreg, "QueryValueEx", query)
    assert preflight.webview2_version() == "155.0.1.2"     # skips missing keys and the "0.0.0.0" placeholder


def test_webview2_missing(monkeypatch):
    def missing(*a):
        raise OSError("no key")
    monkeypatch.setattr(preflight.winreg, "OpenKey", missing)
    assert preflight.webview2_version() is None


def test_fatal_opens_the_link_only_on_yes(monkeypatch):
    opened = []
    monkeypatch.setattr(preflight.os, "startfile", opened.append)
    monkeypatch.setattr(preflight.win32api, "MessageBox", lambda *a: preflight.win32con.IDNO)
    preflight.fatal("T", "msg", "https://example.com")
    monkeypatch.setattr(preflight.win32api, "MessageBox", lambda *a: preflight.win32con.IDYES)
    preflight.fatal("T", "msg", "https://example.com")
    assert opened == ["https://example.com"]


def test_second_launch_asks_the_running_copy(monkeypatch):
    posted = []
    monkeypatch.setattr(single.win32gui, "FindWindow", lambda c, t: 42 if t == single.TRAY_WINDOW else 0)
    monkeypatch.setattr(single.win32process, "GetWindowThreadProcessId", lambda h: (1, 999))
    monkeypatch.setattr(single.win32gui, "PostMessage", lambda h, m, w, l: posted.append((h, m)))
    assert single.focus_existing() is True and posted and posted[0][0] == 42
    monkeypatch.setattr(single.win32gui, "FindWindow", lambda c, t: 0)
    assert single.focus_existing() is False
