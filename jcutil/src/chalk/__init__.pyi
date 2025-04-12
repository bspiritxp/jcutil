from enum import IntEnum
from typing import Tuple, List, Callable, ClassVar, NoReturn, Sized
from functools import partial


Color: IntEnum

FontFormat: IntEnum

EndFlag: IntEnum

class Chalk(Sized, Callable):
    def __len__(self) -> int: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    def __call__(self, *args, **kwargs) -> str: ...
    def __add__(self, other: Chalk) -> Chalk: ...

    __buffer__: List[str]
    __chains__: List[str]
    def __init__(self, text: str = ..., fgc: Color = ..., bgc: Color = ...,
                 styles: Tuple[FontFormat] = ...): ...
    def use(self, *args, **kwargs) -> Chalk: ...
    def text(self, text: str) -> Chalk: ...
    def format(self, text: str, *style: FontFormat) -> Chalk: ...
    def bold(self, text: str) -> Chalk: ...
    def end(self, *flag: EndFlag) -> Chalk: ...
    def expandtabs(self) -> str: ...
    @property
    def raw(self) -> str: ...


RedChalk: partial[Chalk]
GreenChalk: partial[Chalk]
BlueChalk: partial[Chalk]
YellowChalk: partial[Chalk]
MagentaChalk: partial[Chalk]
CyanChalk: partial[Chalk]
WhiteChalk: partial[Chalk]
BlackChalk: partial[Chalk]
BoldChalk: partial[Chalk]

BrightBlackChalk: partial[Chalk]
BrightBlueChalk = partial[Chalk]
BrightCyanChalk = partial[Chalk]
BrightGreenChalk = partial[Chalk]
BrightMagentaChalk = partial[Chalk]
BrightRedChalk = partial[Chalk]
BrightYellowChalk = partial[Chalk]
BrightWhiteChalk = partial[Chalk]


def show_menu(_items: list, is_submenu: bool = ..., title: str = ...) -> NoReturn: ...
def select() -> int: ...
