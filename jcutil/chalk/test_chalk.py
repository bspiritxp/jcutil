from jcutil.chalk import *


def test_chalk_init():
    red = Chalk('hello', Color.RED)
    assert len(red.__chains__) > 0
    print(red)
    assert len(red) > 0
    green = GreenChalk('oh, it is a ').use(FontFormat.BOLD).text('green').end(EndFlag.B_END).text(' chalk.')
    print(repr(green))
    print(green)
    merge = red + green
    print(repr(merge))
    print(merge)


def test_add():
    red = RedChalk('hello')
    r = red + ' world'
    assert len(red.__buffer__) == 2 
    assert str(r) == '\033[31mhello world\033[0m'
    print(r)

def test_mod():
    red = RedChalk('hello %s')
    print(red())
    r = red % 'world'
    assert r == '\033[31mhello world\033[0m'
    print(r)
    print(red % 111)
