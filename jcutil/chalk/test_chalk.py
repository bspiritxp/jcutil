from . import *


def test_chalk_init():
    red = Chalk('hello', Color.RED)
    assert len(red.__chains__) > 0
    print(red)
    assert len(red) > 0
    green = GreenChalk('oh, it is a ').use(FontFormat.BOLD).write('green').end(EndFlag.B_END).write(' chalk.')
    print(green)
    merge = red + green
    print(merge)