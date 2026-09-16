"""ANSI text rendering with simple and incremental Chalk APIs."""

from __future__ import annotations

import os
import sys
from enum import Enum, IntEnum
from functools import partial
from typing import Iterable, TextIO

__all__ = (
    'Color',
    'TextStyle',
    'ColorMode',
    'Chalk',
    'BlackChalk',
    'RedChalk',
    'GreenChalk',
    'YellowChalk',
    'BlueChalk',
    'MagentaChalk',
    'CyanChalk',
    'WhiteChalk',
    'BoldChalk',
    'BrightBlackChalk',
    'BrightRedChalk',
    'BrightGreenChalk',
    'BrightYellowChalk',
    'BrightBlueChalk',
    'BrightMagentaChalk',
    'BrightCyanChalk',
    'BrightWhiteChalk',
    'color_enabled',
    'render',
    'enable_windows_ansi',
)

_RESET = '\033[0m'
_windows_ansi_enabled = False


class Color(IntEnum):
    """Standard and bright ANSI foreground colors."""

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    BRIGHT_BLACK = 90
    BRIGHT_RED = 91
    BRIGHT_GREEN = 92
    BRIGHT_YELLOW = 93
    BRIGHT_BLUE = 94
    BRIGHT_MAGENTA = 95
    BRIGHT_CYAN = 96
    BRIGHT_WHITE = 97


class TextStyle(IntEnum):
    """ANSI text styles supported by the renderer."""

    BOLD = 1
    DIM = 2
    ITALIC = 3
    UNDERLINE = 4
    REVERSE = 7
    STRIKETHROUGH = 9


class ColorMode(str, Enum):
    """Policy used to decide whether ANSI sequences are emitted."""

    AUTO = 'auto'
    ALWAYS = 'always'
    NEVER = 'never'


def color_enabled(*, mode: ColorMode = ColorMode.AUTO, stream: TextIO | None = None) -> bool:
    """Return whether the selected mode permits ANSI output for *stream*.

    ``AUTO`` requires a TTY and a terminal other than ``dumb``. ``ALWAYS`` and
    ``NEVER`` are explicit overrides; only ``AUTO`` consults the destination.
    ``NO_COLOR`` is handled by :func:`render` because it suppresses colors but
    intentionally preserves requested text styles.
    """
    if mode is ColorMode.ALWAYS:
        return True
    if mode is ColorMode.NEVER:
        return False
    if os.environ.get('TERM') == 'dumb':
        return False

    output = sys.stdout if stream is None else stream
    return bool(getattr(output, 'isatty', lambda: False)())


def enable_windows_ansi() -> None:
    """Enable Windows virtual-terminal handling once, without import-time setup."""
    global _windows_ansi_enabled

    if os.name != 'nt' or _windows_ansi_enabled:
        return

    from colorama import just_fix_windows_console

    just_fix_windows_console()
    _windows_ansi_enabled = True


def render(
    text: object,
    *,
    fg: Color | None = None,
    bg: Color | None = None,
    styles: Iterable[TextStyle] = (),
    mode: ColorMode = ColorMode.AUTO,
    stream: TextIO | None = None,
) -> str:
    """Render *text* with one combined ANSI opener and one full reset.

    ``AUTO`` emits ANSI only to non-``dumb`` TTY streams. A non-empty
    ``NO_COLOR`` suppresses foreground and background colors in that mode but
    leaves requested styles intact. ``ALWAYS`` and ``NEVER`` override every
    automatic policy. The renderer supports the standard 16 ANSI colors;
    non-basic styles remain terminal-dependent.
    """
    rendered = str(text)
    selected_styles = tuple(styles)
    if not color_enabled(mode=mode, stream=stream):
        return rendered

    include_colors = not (mode is ColorMode.AUTO and os.environ.get('NO_COLOR'))
    attributes = [
        *([fg.value] if include_colors and fg is not None else []),
        *([bg.value + 10] if include_colors and bg is not None else []),
        *(style.value for style in selected_styles),
    ]
    if not attributes:
        return rendered

    enable_windows_ansi()
    return f"\033[{';'.join(map(str, attributes))}m{rendered}{_RESET}"


class Chalk:
    """Incrementally write independently styled ANSI text segments.

    The active foreground color, background color, and styles apply to the
    next :meth:`write`. Each write snapshots them into its own segment, so a
    later color or style change cannot alter text already written. Methods
    mutate and return this builder to support natural chains such as
    ``Chalk().red('error').bold().write(': retry').green(' recovered')``.
    """

    def __init__(
        self,
        text: object | None = None,
        fgc: Color | None = None,
        bgc: Color | None = None,
        styles: Iterable[TextStyle] = (),
        mode: ColorMode = ColorMode.AUTO,
        *,
        fg: Color | None = None,
        bg: Color | None = None,
    ) -> None:
        if fgc is not None and fg is not None:
            raise TypeError('pass only one of fgc or fg')
        if bgc is not None and bg is not None:
            raise TypeError('pass only one of bgc or bg')

        self._fg = fgc if fg is None else fg
        self._bg = bgc if bg is None else bg
        self._styles = tuple(styles)
        self._mode = mode
        self._segments: list[tuple[str, Color | None, Color | None, tuple[TextStyle, ...]]] = []
        if text is not None:
            self.write(text)

    @property
    def raw(self) -> str:
        """Return all written text without ANSI sequences."""
        return ''.join(text for text, _, _, _ in self._segments)

    def __len__(self) -> int:
        return len(self.raw)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.raw!r})'

    def __add__(self, other: object) -> str:
        return f'{self}{other}'

    def __radd__(self, other: object) -> str:
        return f'{other}{self}'

    def write(self, text: object) -> Chalk:
        """Write *text* using the currently selected chalk attributes."""
        self._segments.append((str(text), self._fg, self._bg, self._styles))
        return self

    def text(self, text: object) -> Chalk:
        """Compatibility name for :meth:`write`."""
        return self.write(text)

    def use(
        self,
        *styles: TextStyle,
        fg_color: Color | None = None,
        bg_color: Color | None = None,
    ) -> Chalk:
        """Add styles or select colors for subsequent writes."""
        if fg_color is not None:
            self.color(fg_color)
        if bg_color is not None:
            self.background(bg_color)
        for style in styles:
            self._add_style(style)
        return self

    def color(self, color: Color | None) -> Chalk:
        """Select the foreground color used by subsequent writes."""
        self._fg = color
        return self

    def background(self, color: Color | None) -> Chalk:
        """Select the background color used by subsequent writes."""
        self._bg = color
        return self

    def style(self, *styles: TextStyle) -> Chalk:
        """Replace the styles used by subsequent writes; no argument clears them."""
        self._styles = tuple(styles)
        return self

    def reset(self) -> Chalk:
        """Clear the active color, background, and styles for future writes."""
        self._fg = None
        self._bg = None
        self._styles = ()
        return self

    def _add_style(self, style: TextStyle, text: object | None = None) -> Chalk:
        if style not in self._styles:
            self._styles = (*self._styles, style)
        if text is not None:
            self.write(text)
        return self

    def bold(self, text: object | None = None) -> Chalk:
        """Add bold styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.BOLD, text)

    def dim(self, text: object | None = None) -> Chalk:
        """Add dim styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.DIM, text)

    def italic(self, text: object | None = None) -> Chalk:
        """Add italic styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.ITALIC, text)

    def underline(self, text: object | None = None) -> Chalk:
        """Add underline styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.UNDERLINE, text)

    def reverse(self, text: object | None = None) -> Chalk:
        """Add reverse-video styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.REVERSE, text)

    def strikethrough(self, text: object | None = None) -> Chalk:
        """Add strikethrough styling, optionally writing *text* immediately."""
        return self._add_style(TextStyle.STRIKETHROUGH, text)

    def _use_color(self, color: Color, text: object | None = None) -> Chalk:
        self.color(color)
        if text is not None:
            self.write(text)
        return self

    def black(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.BLACK, text)

    def red(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.RED, text)

    def green(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.GREEN, text)

    def yellow(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.YELLOW, text)

    def blue(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.BLUE, text)

    def magenta(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.MAGENTA, text)

    def cyan(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.CYAN, text)

    def white(self, text: object | None = None) -> Chalk:
        return self._use_color(Color.WHITE, text)

    def render(self, *, stream: TextIO | None = None, mode: ColorMode | None = None) -> str:
        """Render all written segments using this builder's policy or an override."""
        selected_mode = self._mode if mode is None else mode
        return ''.join(
            render(text, fg=fg, bg=bg, styles=styles, mode=selected_mode, stream=stream)
            for text, fg, bg, styles in self._segments
        )


# Compatibility factories retain the established `RedChalk('text')` call shape.
BlackChalk = partial(Chalk, fgc=Color.BLACK)
RedChalk = partial(Chalk, fgc=Color.RED)
GreenChalk = partial(Chalk, fgc=Color.GREEN)
YellowChalk = partial(Chalk, fgc=Color.YELLOW)
BlueChalk = partial(Chalk, fgc=Color.BLUE)
MagentaChalk = partial(Chalk, fgc=Color.MAGENTA)
CyanChalk = partial(Chalk, fgc=Color.CYAN)
WhiteChalk = partial(Chalk, fgc=Color.WHITE)
BoldChalk = partial(Chalk, styles=(TextStyle.BOLD,))
BrightBlackChalk = partial(Chalk, fgc=Color.BRIGHT_BLACK)
BrightRedChalk = partial(Chalk, fgc=Color.BRIGHT_RED)
BrightGreenChalk = partial(Chalk, fgc=Color.BRIGHT_GREEN)
BrightYellowChalk = partial(Chalk, fgc=Color.BRIGHT_YELLOW)
BrightBlueChalk = partial(Chalk, fgc=Color.BRIGHT_BLUE)
BrightMagentaChalk = partial(Chalk, fgc=Color.BRIGHT_MAGENTA)
BrightCyanChalk = partial(Chalk, fgc=Color.BRIGHT_CYAN)
BrightWhiteChalk = partial(Chalk, fgc=Color.BRIGHT_WHITE)
