from enum import Enum, IntEnum
from functools import partial
from typing import Iterable, TextIO

class Color(IntEnum):
    BLACK: Color
    RED: Color
    GREEN: Color
    YELLOW: Color
    BLUE: Color
    MAGENTA: Color
    CYAN: Color
    WHITE: Color
    BRIGHT_BLACK: Color
    BRIGHT_RED: Color
    BRIGHT_GREEN: Color
    BRIGHT_YELLOW: Color
    BRIGHT_BLUE: Color
    BRIGHT_MAGENTA: Color
    BRIGHT_CYAN: Color
    BRIGHT_WHITE: Color

class TextStyle(IntEnum):
    BOLD: TextStyle
    DIM: TextStyle
    ITALIC: TextStyle
    UNDERLINE: TextStyle
    REVERSE: TextStyle
    STRIKETHROUGH: TextStyle

class ColorMode(str, Enum):
    AUTO: ColorMode
    ALWAYS: ColorMode
    NEVER: ColorMode

class Chalk:
    def __init__(
        self,
        text: object | None = ...,
        fgc: Color | None = ...,
        bgc: Color | None = ...,
        styles: Iterable[TextStyle] = ...,
        mode: ColorMode = ...,
        *,
        fg: Color | None = ...,
        bg: Color | None = ...,
    ) -> None: ...
    @property
    def raw(self) -> str: ...
    def __len__(self) -> int: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...
    def __add__(self, other: object) -> str: ...
    def __radd__(self, other: object) -> str: ...
    def write(self, text: object) -> Chalk: ...
    def text(self, text: object) -> Chalk: ...
    def use(
        self,
        *styles: TextStyle,
        fg_color: Color | None = ...,
        bg_color: Color | None = ...,
    ) -> Chalk: ...
    def color(self, color: Color | None) -> Chalk: ...
    def background(self, color: Color | None) -> Chalk: ...
    def style(self, *styles: TextStyle) -> Chalk: ...
    def reset(self) -> Chalk: ...
    def bold(self, text: object | None = ...) -> Chalk: ...
    def dim(self, text: object | None = ...) -> Chalk: ...
    def italic(self, text: object | None = ...) -> Chalk: ...
    def underline(self, text: object | None = ...) -> Chalk: ...
    def reverse(self, text: object | None = ...) -> Chalk: ...
    def strikethrough(self, text: object | None = ...) -> Chalk: ...
    def black(self, text: object | None = ...) -> Chalk: ...
    def red(self, text: object | None = ...) -> Chalk: ...
    def green(self, text: object | None = ...) -> Chalk: ...
    def yellow(self, text: object | None = ...) -> Chalk: ...
    def blue(self, text: object | None = ...) -> Chalk: ...
    def magenta(self, text: object | None = ...) -> Chalk: ...
    def cyan(self, text: object | None = ...) -> Chalk: ...
    def white(self, text: object | None = ...) -> Chalk: ...
    def render(self, *, stream: TextIO | None = ..., mode: ColorMode | None = ...) -> str: ...

BlackChalk: partial[Chalk]
RedChalk: partial[Chalk]
GreenChalk: partial[Chalk]
YellowChalk: partial[Chalk]
BlueChalk: partial[Chalk]
MagentaChalk: partial[Chalk]
CyanChalk: partial[Chalk]
WhiteChalk: partial[Chalk]
BoldChalk: partial[Chalk]
BrightBlackChalk: partial[Chalk]
BrightRedChalk: partial[Chalk]
BrightGreenChalk: partial[Chalk]
BrightYellowChalk: partial[Chalk]
BrightBlueChalk: partial[Chalk]
BrightMagentaChalk: partial[Chalk]
BrightCyanChalk: partial[Chalk]
BrightWhiteChalk: partial[Chalk]

def color_enabled(*, mode: ColorMode = ..., stream: TextIO | None = ...) -> bool: ...
def render(
    text: object,
    *,
    fg: Color | None = ...,
    bg: Color | None = ...,
    styles: Iterable[TextStyle] = ...,
    mode: ColorMode = ...,
    stream: TextIO | None = ...,
) -> str: ...
def enable_windows_ansi() -> None: ...
