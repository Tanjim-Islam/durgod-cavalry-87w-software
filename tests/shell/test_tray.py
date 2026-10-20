from engine.shell.tray import WM_CONTEXTMENU, WM_LBUTTONUP, WM_MOUSEMOVE, WM_RBUTTONUP, click_action


def test_click_mapping():
    assert click_action(WM_LBUTTONUP) == "main"
    assert click_action(WM_RBUTTONUP) == "flyout"
    assert click_action(WM_CONTEXTMENU) == "flyout"
    assert click_action(WM_MOUSEMOVE) is None
