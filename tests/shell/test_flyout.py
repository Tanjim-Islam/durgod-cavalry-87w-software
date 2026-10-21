from engine.shell.flyout import MARGIN, edge, place

WORK = (0, 0, 1920, 1032)            # taskbar at the bottom
SIZE = (320, 470)


def test_above_a_taskbar_icon_and_centered_on_it():
    icon = (1500, 1040, 1532, 1080)
    x, y, dx, dy = place(icon, WORK, SIZE)
    assert (x, y) == (1516 - 160, 1032 - MARGIN - 470)
    assert (dx, dy) == (0, 14)                   # rises out of the taskbar


def test_clamped_inside_the_screen():
    x, _, _, _ = place((1890, 1040, 1920, 1080), WORK, SIZE)
    assert x == 1920 - MARGIN - 320
    x, _, _, _ = place((0, 1040, 30, 1080), WORK, SIZE)
    assert x == MARGIN


def test_icon_in_the_hidden_icons_popup_opens_above_that_icon():
    icon = (1701, 855, 1741, 895)
    assert edge(icon, WORK) == "inside"
    x, y, dx, dy = place(icon, WORK, SIZE)
    assert y == 855 - MARGIN - 470 and x == 1721 - 160 and dy > 0


def test_popup_icon_near_the_top_opens_below_it():
    _, y, _, dy = place((900, 60, 940, 100), WORK, SIZE)
    assert y == 100 + MARGIN and dy < 0


def test_taskbar_on_top_left_and_right():
    assert place((900, 5, 940, 40), (0, 48, 1920, 1080), SIZE)[1] == 48 + MARGIN
    x, _, dx, _ = place((1890, 500, 1920, 540), (0, 0, 1872, 1080), SIZE)
    assert x == 1872 - MARGIN - 320 and dx > 0
    x, _, dx, _ = place((0, 500, 40, 540), (48, 0, 1920, 1080), SIZE)
    assert x == 48 + MARGIN and dx < 0


def test_animation_frames_ease_out_and_land_on_target():
    from engine.shell.animate import frames
    f = list(frames((0, 114), (0, 100), 0, 255, 0.18))
    assert len(f) == 11 and f[-1] == (0, 100, 255)
    ys = [y for _, y, _ in f]
    assert ys == sorted(ys, reverse=True)                       # moves one way only
    assert (ys[0] - ys[1]) > (ys[-2] - ys[-1])                  # fast start, gentle stop
