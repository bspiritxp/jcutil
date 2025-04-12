import io
import sys
import unittest

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


class TestChalk(unittest.TestCase):
    def setUp(self):
        # 捕获标准输出
        self.capturedOutput = io.StringIO()
        sys.stdout = self.capturedOutput

    def tearDown(self):
        # 恢复标准输出
        sys.stdout = sys.__stdout__
        print(self.capturedOutput.getvalue())

    def test_chalk_init(self):
        red = Chalk('hello', Color.RED)
        self.assertTrue(len(red.__chains__) > 0)
        print(red)
        self.assertTrue(len(red) > 0)

        green = GreenChalk('oh, it is a ').use(FontFormat.BOLD).text('green').end(EndFlag.B_END).text(' chalk.')
        print(repr(green))
        print(green)

        merge = red + green
        print(repr(merge))
        print(merge)

    def test_add(self):
        red = RedChalk('hello')
        r = red + ' world'
        self.assertIsInstance(r, str, 'return a str when add a str')
        self.assertEqual(r, '\033[31mhello\033[0m world')
        print(r)

        r = red + GreenChalk('|Mo')
        self.assertEqual(str(r), '\033[31mhello\033[0m\033[32m|Mo\033[0m')
        print(r)

    def test_mod(self):
        red = RedChalk('hello %s')
        print(red)
        r = red % 'world'
        self.assertEqual(r, '\033[31mhello world\033[0m')
        print(r)
        print(red % 111)

    def test_wrapper(self):
        red = RedChalk('[wappered]')
        r = GreenChalk(f'a {red} b')
        print(repr(r))
        print(r)

        br = YellowChalk().bold('bold string')
        print(repr(br), br)

    def test_new_features(self):
        """测试新增的功能"""
        # 测试italic方法
        italic_text = RedChalk().italic("This is italic text")
        print(italic_text)
        self.assertIn('\033[3m', str(italic_text))  # 3是斜体的ANSI代码

        # 测试underline方法
        underline_text = BlueChalk().underline("This is underlined text")
        print(underline_text)
        self.assertIn('\033[4m', str(underline_text))  # 4是下划线的ANSI代码

        # 测试__radd__方法
        text_with_chalk = "Plain text with " + GreenChalk("green text")
        print(text_with_chalk)
        self.assertTrue(text_with_chalk.endswith('\033[0m'))
        self.assertTrue(text_with_chalk.startswith('Plain text with '))

        # 测试raw属性
        colored_text = RedChalk("Hello").bold(" World")
        print(colored_text)
        self.assertEqual(colored_text.raw, "Hello World")


if __name__ == "__main__":
    print(YellowChalk().bold("=== 开始测试Chalk模块 ===").expandtabs())
    unittest.main(verbosity=2)
