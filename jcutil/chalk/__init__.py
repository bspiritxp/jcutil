import os
from colorama import init
from enum import IntEnum
from typing import Tuple
from jcramda import compose, partial, join, if_else, ilen_gt, always, nth, curry
from jcutil.core import nl_print, c_write


__all__ = (
    'Color',
    'FontFormat',
    'Chalk',
    'EndFlag',
    'RedChalk',
    'GreenChalk',
    'BlackChalk',
    'BlueChalk',
    'MagentaChalk',
    'WhiteChalk',
    'YellowChalk',
    'CyanChalk',
    'show_menu',
    'select'
)


__CHALK_TMPL__ = '\033[{}m'


class Color(IntEnum):
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    RESET = 39
    BRIGHT_BLACK = 90
    BRIGHT_RED = 91
    BRIGHT_GREEN = 92
    BRIGHT_YELLOW = 93
    BRIGHT_BLUE = 94
    BRIGHT_MAGENTA = 95
    BRIGHT_CYAN = 96
    BRIGHT_WHITE = 97

    @property
    def bgcolor(self):
        return self.value + 10

    @property
    def echo(self):
        return partial(Chalk, fgc=self)


class FontFormat(IntEnum):
    BOLD = 1
    LIGHT = 2
    ITALIC = 3
    UNDER_LINE = 4
    BLINK = 5
    RESERVE = 7
    DELETE = 9


class EndFlag(IntEnum):
    ALL_END = 0
    B_END = 22
    I_END = 23
    UL_END = 24
    BL_END = 25
    R_END = 27
    D_END = 29


def __gen_raw__(fgc: Color = None, bgc: Color = None, *styles: FontFormat):
    raw = (fgc.value if fgc else None,
           bgc.bgcolor if bgc else None,
           *[ff.value for ff in styles if ff is not None])
    return __CHALK_TMPL__.format(join(';')(raw))


end_all = partial(__gen_raw__, None, None, EndFlag.ALL_END)


class Chalk(object):
    def __init__(self, text = None,
                 fgc: Color = None,
                 bgc: Color = None,
                 styles: Tuple[FontFormat] = ()):
        self.__buffer__ = [str(text)] if text else []
        self.__chains__ = [partial(__gen_raw__, fgc, bgc, *styles)]
        if os.name == 'nt':
            init()

    def use(self, *args, **kwargs):
        """
        Parameters
        -----------
        *args : FontFormat
        **kwargs
            * fg_color: 字体颜色
            * bg_color: 背景色

        Returns
        -------
        Chalk
        """
        self.__chains__.append(partial(__gen_raw__,
                                       kwargs.get('fg_color', None),
                                       kwargs.get('bg_color', None), *args))
        return self

    def end(self, *flag: EndFlag):
        if len(flag) > 0:
            self.__chains__.append(partial(__gen_raw__, None, None, *flag))
        else:
            self.__chains__.append(end_all)
        return self

    def text(self, text: str):
        self.__buffer__.append(text)
        return self

    def format(self, text: str, *style: FontFormat):
        self.use(*style).text(text).end(EndFlag.ALL_END)

    def bold(self, text: str):
        self.use(FontFormat.BOLD).text(text)

    def expandtabs(self):
        return str(self).expandtabs()

    def __str__(self):
        styles = self.__chains__.copy()
        texts = self.__buffer__.copy()
        r = ''
        while len(styles) > 0:
            r += styles.pop(0)() + if_else(ilen_gt(0), lambda x: x.pop(0), always(''))(texts)
        return '{}\033[0m'.format(r)

    def __len__(self):
        return len(self.__buffer__)

    def __add__(self, other):
        """

        Parameters
        ----------
        other : Chalk
        """
        if isinstance(other, str):
            self.__buffer__.append(other)
            return self
        new_chalk = Chalk()
        new_chalk.__chains__ = self.__chains__ + [end_all] + other.__chains__
        new_chalk.__buffer__ = self.__buffer__ + [' '] + other.__buffer__
        return new_chalk

    def __repr__(self):
        return rf'Chalk<buffSize={len(self.__buffer__)}, chainSize={len(self.__chains__)}>'

    def __call__(self, *args, **kwargs):
        return str(self)


RedChalk = partial(Chalk, fgc=Color.RED)
GreenChalk = partial(Chalk, fgc=Color.GREEN)
BlueChalk = partial(Chalk, fgc=Color.BLUE)
YellowChalk = partial(Chalk, fgc=Color.YELLOW)
MagentaChalk = partial(Chalk, fgc=Color.MAGENTA)
CyanChalk = partial(Chalk, fgc=Color.CYAN)
WhiteChalk = partial(Chalk, fgc=Color.WHITE)
BlackChalk = partial(Chalk, fgc=Color.BLACK)
BoldChalk = partial(Chalk, styles=(FontFormat.BOLD,))

BrightBlackChalk = partial(Chalk, fgc=Color.BRIGHT_BLACK)
BrightBlueChalk = partial(Chalk, fgc=Color.BRIGHT_BLUE)
BrightCyanChalk = partial(Chalk, fgc=Color.BRIGHT_CYAN)
BrightGreenChalk = partial(Chalk, fgc=Color.BRIGHT_GREEN)
BrightMagentaChalk = partial(Chalk, fgc=Color.BRIGHT_MAGENTA)
BrightRedChalk = partial(Chalk, fgc=Color.BRIGHT_RED)
BrightYellowChalk = partial(Chalk, fgc=Color.BRIGHT_YELLOW)
BrightWhiteChalk = partial(Chalk, fgc=Color.BRIGHT_WHITE)


def show_menu(_items: list, is_submenu=False, title='命令菜单'):
    items = _items.copy()
    i = 1
    c_write(GreenChalk(title, styles=(FontFormat.BOLD,) if not isinstance(title, Chalk) else title),
            end='\n\n')
    if is_submenu:
        items.append(('返回', lambda: ''))
    items.append(('退出', sys.exit))
    for title, _ in items:
        sys.stdout.write(
            YellowChalk(f'{i}. {title}', styles=(FontFormat.BOLD,))() + '\n')
        i += 1
    nl_print('\n')
    return compose(
        nth(1),
        nth(select() - 1),
    )(items)


def select():
    """
    wait a input from stdin then return selected number
    Returns
    -------
    int
    """
    c_write(GreenChalk('选择功能：')())
    sys.stdout.flush()
    return int(sys.stdin.read(2))
