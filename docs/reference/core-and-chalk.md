# 核心与终端 API

以下内容由源码解析生成。使用指南和限制见[核心、JSON 与并发](../guides/core.md)。

## `jcutil.core`

::: jcutil.core

## `jcutil.chalk`

`jcutil.chalk` 同时提供单段 `render()` 和增量式 `Chalk` builder。`Chalk` 按调用顺序记录每一段 `write()` 时的前景色、背景色与样式，因此后续换色或换样式不会重写已写文本。

```python
from jcutil.chalk import Chalk, ColorMode

status = Chalk(mode=ColorMode.ALWAYS).green('ready').bold().write(' now').red('!')
print(f'status: {status}')
```

`Chalk` 的 `color()`、`background()`、`style()`、`reset()` 与 `write()` 都返回当前 builder；`red()`、`green()` 等颜色快捷方法和 `bold()`、`italic()` 等样式快捷方法可以直接写入文本。`render()` 保留用于一次性文本。

为兼容既有调用，`RedChalk`、`GreenChalk`、所有基础/明亮色 `*Chalk` 工厂和 `BoldChalk` 仍会构造 `Chalk`；例如 `RedChalk('error')` 可继续 `.bold()`、`.write()`。

默认 `ColorMode.AUTO` 仅向非 `dumb` 的 TTY 输出 ANSI；重定向输出保持纯文本。非空 `NO_COLOR` 在 `AUTO` 下禁用前景和背景色，但保留请求的样式。`ColorMode.ALWAYS` 和 `ColorMode.NEVER` 明确覆盖该策略。模块支持标准和明亮的 16 个 ANSI 颜色；终端对斜体、删除线等非基础样式的显示是尽力而为，不承诺 256 色或真彩色支持。

::: jcutil.chalk
