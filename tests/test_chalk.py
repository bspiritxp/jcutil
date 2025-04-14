"""
测试Chalk模块 - 用于控制台彩色输出

这个测试文件验证jcutil.chalk模块的功能是否正常工作，包括颜色输出、样式设置、文本操作等。
"""

import io
import sys

import pytest

from jcutil.chalk import (
    BlueChalk,
    Chalk,
    Color,
    EndFlag,
    FontFormat,
    GreenChalk,
    RedChalk,
    YellowChalk,
)


@pytest.fixture
def capture_stdout():
    """捕获标准输出的fixture"""
    captured_output = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured_output

    yield captured_output

    # 恢复标准输出
    sys.stdout = old_stdout
    # 打印捕获的输出，方便调试
    print(captured_output.getvalue())


def test_chalk_init(capture_stdout):
    """测试Chalk初始化和链式调用"""
    red = Chalk("hello", Color.RED)
    assert len(red.__chains__) > 0
    print(red)
    assert len(red) > 0

    green = (
        GreenChalk("oh, it is a ")
        .use(FontFormat.BOLD)
        .text("green")
        .end(EndFlag.B_END)
        .text(" chalk.")
    )
    print(repr(green))
    print(green)

    merge = red + green
    print(repr(merge))
    print(merge)


def test_add(capture_stdout):
    """测试加法操作符重载"""
    red = RedChalk("hello")
    r = red + " world"
    assert isinstance(r, str), "return a str when add a str"
    assert r == "\033[31mhello\033[0m world"
    print(r)

    r = red + GreenChalk("|Mo")
    assert str(r) == "\033[31mhello\033[0m\033[32m|Mo\033[0m"
    print(r)


def test_mod(capture_stdout):
    """测试格式化操作符重载"""
    red = RedChalk("hello %s")
    print(red)
    r = red % "world"
    assert r == "\033[31mhello world\033[0m"
    print(r)
    print(red % 111)


def test_wrapper(capture_stdout):
    """测试嵌套使用功能"""
    red = RedChalk("[wappered]")
    r = GreenChalk(f"a {red} b")
    print(repr(r))
    print(r)

    br = YellowChalk().bold("bold string")
    print(repr(br), br)


def test_new_features(capture_stdout):
    """测试新增的功能"""
    # 测试italic方法
    italic_text = RedChalk().italic("This is italic text")
    print(italic_text)
    assert "\033[3m" in str(italic_text), "斜体标记应存在"

    # 测试underline方法
    underline_text = BlueChalk().underline("This is underlined text")
    print(underline_text)
    assert "\033[4m" in str(underline_text), "下划线标记应存在"

    # 测试__radd__方法
    text_with_chalk = "Plain text with " + GreenChalk("green text")
    print(text_with_chalk)
    assert text_with_chalk.endswith("\033[0m"), "应以重置颜色标记结尾"
    assert text_with_chalk.startswith("Plain text with "), "应以普通文本开始"

    # 测试raw属性
    colored_text = RedChalk("Hello").bold(" World")
    print(colored_text)
    assert colored_text.raw == "Hello World"


if __name__ == "__main__":
    print(YellowChalk().bold("=== 开始测试Chalk模块 ===").expandtabs())
    pytest.main(["-xvs", __file__])
