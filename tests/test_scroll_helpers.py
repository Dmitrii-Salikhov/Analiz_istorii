from types import SimpleNamespace

from gui.widgets import wheel_steps


def test_wheel_steps_windows_style():
    assert wheel_steps(SimpleNamespace(delta=120)) == -1
    assert wheel_steps(SimpleNamespace(delta=-240)) == 2


def test_wheel_steps_linux_buttons():
    assert wheel_steps(SimpleNamespace(num=4, delta=0)) == -1
    assert wheel_steps(SimpleNamespace(num=5, delta=0)) == 1
