import os
import sys
from enum import IntEnum
from typing import Any, List, Optional, Tuple, Union

from colorama import init
from jcramda import first, join, partial, zip_

from jcutil.core import c_write, nl_print

__all__ = (
    "Color",
    "FontFormat",
    "Chalk",
    "EndFlag",
    "RedChalk",
    "GreenChalk",
    "BlackChalk",
    "BlueChalk",
    "MagentaChalk",
    "WhiteChalk",
    "YellowChalk",
    "CyanChalk",
    "show_menu",
    "select",
    "BoldChalk",
    "BrightRedChalk",
    "BrightBlueChalk",
    "BrightCyanChalk",
    "BrightBlackChalk",
    "BrightGreenChalk",
    "BrightWhiteChalk",
    "BrightYellowChalk",
    "BrightMagentaChalk",
)


__CHALK_TMPL__ = "\033[{}m"
__RESET__ = "\033[0m"

# 在Windows系统上初始化colorama
if os.name == "nt":
    init(convert=True, strip=False)


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
    def bgcolor(self) -> int:
        """获取对应的背景色值"""
        return self.value + 10

    @property
    def echo(self):
        """获取带有当前颜色的Chalk函数"""
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


def _gen_raw(
    fgc: Optional[Color] = None, bgc: Optional[Color] = None, *styles: FontFormat
) -> str:
    """生成ANSI转义序列

    Args:
        fgc: 前景色
        bgc: 背景色
        styles: 字体样式

    Returns:
        ANSI转义序列字符串
    """
    # 过滤None值，确保join函数收到的是有效值
    raw = [
        value
        for value in (
            fgc.value if fgc else None,
            bgc.bgcolor if bgc else None,
            *[ff.value for ff in styles if ff is not None],
        )
        if value is not None
    ]

    if not raw:
        return __RESET__

    return __CHALK_TMPL__.format(join(";")(raw))


class Chalk:
    """控制台彩色文本工具类"""

    def __init__(
        self,
        text: Optional[str] = None,
        fgc: Optional[Color] = None,
        bgc: Optional[Color] = None,
        styles: Tuple[FontFormat, ...] = (),
    ):
        """初始化Chalk实例

        Args:
            text: 要设置样式的文本
            fgc: 前景色
            bgc: 背景色
            styles: 字体样式
        """
        self.__chains__: List[str] = [_gen_raw(fgc, bgc, *styles)]
        self.__buffer__: List[str] = []
        if text:
            self.text(text)

    def use(self, *args: FontFormat, **kwargs) -> "Chalk":
        """使用指定样式

        Args:
            *args: 字体样式
            **kwargs: 关键字参数
                fg_color: 前景色
                bg_color: 背景色

        Returns:
            Chalk实例
        """
        self.__chains__.append(
            _gen_raw(kwargs.get("fg_color"), kwargs.get("bg_color"), *args)
        )
        return self

    def end(self, *flag: EndFlag) -> "Chalk":
        """结束当前样式

        Args:
            *flag: 结束标志

        Returns:
            Chalk实例
        """
        if len(flag) > 0:
            self.__chains__.append(_gen_raw(None, None, *flag))
        else:
            self.__chains__.append(__RESET__)
        return self

    def _text(self, text: str) -> str:
        """处理文本，替换重置符号

        Args:
            text: 待处理文本

        Returns:
            处理后的文本
        """
        if not text:
            return ""
        return str(text).replace(__RESET__, first(self.__chains__) or "")

    def text(self, text: str) -> "Chalk":
        """添加文本

        Args:
            text: 要添加的文本

        Returns:
            Chalk实例
        """
        self.__buffer__.append(self._text(text))
        return self

    def format(self, text: str, *style: FontFormat) -> None:
        """格式化文本

        Args:
            text: 文本内容
            *style: 样式
        """
        self.use(*style).text(text).end(EndFlag.ALL_END)

    def bold(self, text: str) -> "Chalk":
        """添加粗体文本

        Args:
            text: 文本内容

        Returns:
            Chalk实例
        """
        self.use(FontFormat.BOLD).text(text)
        return self

    def italic(self, text: str) -> "Chalk":
        """添加斜体文本

        Args:
            text: 文本内容

        Returns:
            Chalk实例
        """
        self.use(FontFormat.ITALIC).text(text)
        return self

    def underline(self, text: str) -> "Chalk":
        """添加下划线文本

        Args:
            text: 文本内容

        Returns:
            Chalk实例
        """
        self.use(FontFormat.UNDER_LINE).text(text)
        return self

    def expandtabs(self) -> str:
        """展开制表符

        Returns:
            展开制表符后的文本
        """
        return str(self).expandtabs()

    @property
    def raw(self) -> str:
        """获取原始文本（不含样式）

        Returns:
            原始文本
        """
        return "".join(self.__buffer__)

    def __str__(self) -> str:
        """获取完整的彩色文本

        Returns:
            带有ANSI控制序列的文本
        """
        # 使用zip_来配对chains和buffer
        data = zip_("", self.__chains__, self.__buffer__)
        return "".join([f"{c}{t}" for c, t in data]) + __RESET__

    def __len__(self) -> int:
        """获取文本长度

        Returns:
            文本长度（不含样式）
        """
        return len(self.raw)

    def __add__(self, other: Union[str, "Chalk"]) -> Union[str, "Chalk"]:
        """连接两个Chalk对象或Chalk与字符串

        Args:
            other: 另一个Chalk对象或字符串

        Returns:
            连接后的对象
        """
        if isinstance(other, str):
            return str(self) + other

        new_chalk = Chalk()
        new_chalk.__chains__ = self.__chains__ + [__RESET__] + other.__chains__
        new_chalk.__buffer__ = self.__buffer__ + [""] + other.__buffer__
        return new_chalk

    def __radd__(self, other: str) -> str:
        """实现右侧加法

        Args:
            other: 字符串

        Returns:
            连接后的字符串
        """
        if isinstance(other, str):
            return other + str(self)
        return NotImplemented

    def __repr__(self) -> str:
        """获取对象的字符串表示

        Returns:
            对象的调试表示
        """
        return f"Chalk<buff:{self.__buffer__}, chain:{self.__chains__}>"

    def __call__(self, *args, **kwargs) -> str:
        """调用对象时返回字符串表示

        Returns:
            字符串表示
        """
        return str(self)

    def __mod__(self, args) -> str:
        """支持字符串格式化

        Args:
            args: 格式化参数

        Returns:
            格式化后的字符串
        """
        return str(self) % args


# 预定义的Chalk实例
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


def show_menu(
    items: List[tuple], is_submenu: bool = False, title: Union[str, Chalk] = "命令菜单"
) -> Any:
    """显示菜单并获取用户选择

    Args:
        items: 菜单项列表，每项为(标题, 函数)的元组
        is_submenu: 是否为子菜单
        title: 菜单标题

    Returns:
        所选菜单项的函数结果
    """
    if not items:
        return None

    items_copy = items.copy()
    index = 1

    # 显示标题
    if isinstance(title, Chalk):
        c_write(title, end="\n\n")
    else:
        c_write(GreenChalk(title, styles=(FontFormat.BOLD,)), end="\n\n")

    # 添加返回和退出选项
    if is_submenu:
        items_copy.append(("返回", lambda: ""))
    items_copy.append(("退出", sys.exit))

    # 显示菜单项
    for item_title, _ in items_copy:
        sys.stdout.write(
            YellowChalk(f"{index}. {item_title}", styles=(FontFormat.BOLD,))() + "\n"
        )
        index += 1

    nl_print("\n")

    # 获取用户选择并执行
    try:
        choice = select()
        if 1 <= choice <= len(items_copy):
            return items_copy[choice - 1][1]()
        else:
            print(RedChalk("无效选择，请重试。").bold("!"))
            return show_menu(items, is_submenu, title)
    except ValueError:
        print(RedChalk("请输入有效数字").bold("!"))
        return show_menu(items, is_submenu, title)


def select() -> int:
    """等待用户输入并返回所选数字

    Returns:
        用户选择的数字
    """
    c_write(GreenChalk("选择功能：")())
    sys.stdout.flush()
    try:
        # 支持更大的菜单项数量
        user_input = sys.stdin.readline().strip()
        return int(user_input)
    except ValueError:
        return 0  # 返回无效值，让调用者处理
