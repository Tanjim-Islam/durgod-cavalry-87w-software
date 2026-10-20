from engine.shell.flyout import place

WORK = (0, 0, 1920, 1032)  # taskbar at the bottom


def test_above_taskbar_near_cursor():
    x, y = place((1800, 1060), WORK, (320, 460))
    assert (x, y) == (1920 - 12 - 320, 1032 - 12 - 460)


def test_clamped_left():
    x, y = place((10, 1060), WORK, (320, 460))
    assert x == 12


def test_taskbar_on_top():
    x, y = place((900, 5), (0, 48, 1920, 1080), (320, 460))
    assert y == 48 + 12
