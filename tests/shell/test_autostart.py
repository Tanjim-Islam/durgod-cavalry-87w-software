from engine.shell.autostart import RUN_KEY, VALUE, Autostart


class FakeReg:
    HKEY_CURRENT_USER, KEY_SET_VALUE, KEY_READ, REG_SZ = 1, 2, 4, 1

    def __init__(self):
        self.values = {}

    class _K:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def OpenKey(self, root, path, reserved=0, access=0):
        assert path == RUN_KEY
        return self._K()

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError
        return self.values[name], 1

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError
        del self.values[name]


def test_toggle():
    reg = FakeReg()
    a = Autostart('"C:\\app\\Cavalry87.exe" --tray', reg=reg)
    assert a.enabled() is False
    a.set(True)
    assert reg.values[VALUE] == '"C:\\app\\Cavalry87.exe" --tray' and a.enabled() is True
    a.set(False)
    a.set(False)
    assert a.enabled() is False
