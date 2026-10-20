import win32con

from engine.shell.tray import (WM_CONTEXTMENU, WM_LBUTTONUP, WM_MOUSEMOVE, WM_RBUTTONUP, Tray, click_action,
                               session_action)


def test_click_mapping():
    assert click_action(WM_LBUTTONUP) == "main"
    assert click_action(WM_RBUTTONUP) == "flyout"
    assert click_action(WM_CONTEXTMENU) == "flyout"
    assert click_action(WM_MOUSEMOVE) is None


def test_session_mapping():
    assert session_action(win32con.WM_QUERYENDSESSION, 0) == "ending"
    assert session_action(win32con.WM_ENDSESSION, 1) == "end"
    assert session_action(win32con.WM_ENDSESSION, 0) == "cancelled"
    assert session_action(win32con.WM_CLOSE, 1) is None


def test_tray_window_never_blocks_the_session_from_ending():
    seen = []
    t = Tray("x.ico", "tip", lambda: None, lambda p: None, on_session=seen.append)
    assert t._proc(0, win32con.WM_QUERYENDSESSION, 0, 0) == 1
    assert t._proc(0, win32con.WM_ENDSESSION, 1, 0) == 0
    assert seen == ["ending", "end"]


def test_a_failing_session_callback_still_lets_the_session_end():
    def boom(action): raise RuntimeError("x")
    t = Tray("x.ico", "tip", lambda: None, lambda p: None, on_session=boom)
    assert t._proc(0, win32con.WM_QUERYENDSESSION, 0, 0) == 1
