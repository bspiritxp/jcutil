import importlib.util
import io
import sys
from types import SimpleNamespace

import jcutil.chalk as chalk
from jcutil.chalk import (
    BoldChalk,
    BrightGreenChalk,
    Chalk,
    Color,
    ColorMode,
    GreenChalk,
    RedChalk,
    TextStyle,
    color_enabled,
    render,
)


class TerminalStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class RedirectedStream(io.StringIO):
    def isatty(self) -> bool:
        return False


class StringifiedOnce:
    def __init__(self) -> None:
        self.calls = 0

    def __str__(self) -> str:
        self.calls += 1
        return 'value'


def test_render_combines_requested_sgr_attributes_before_text() -> None:
    assert render(
        'message',
        fg=Color.RED,
        bg=Color.BLUE,
        styles=(
            TextStyle.BOLD,
            TextStyle.ITALIC,
            TextStyle.UNDERLINE,
            TextStyle.REVERSE,
            TextStyle.STRIKETHROUGH,
        ),
        mode=ColorMode.ALWAYS,
    ) == '\033[31;44;1;3;4;7;9mmessage\033[0m'


def test_render_preserves_falsy_and_unstyled_values() -> None:
    assert render('', fg=Color.RED, mode=ColorMode.ALWAYS) == '\033[31m\033[0m'
    assert render(0) == '0'
    assert render(False, mode=ColorMode.ALWAYS) == 'False'
    assert render('plain', mode=ColorMode.ALWAYS) == 'plain'

    value = StringifiedOnce()
    assert render(value, fg=Color.GREEN, mode=ColorMode.ALWAYS) == '\033[32mvalue\033[0m'
    assert value.calls == 1


def test_auto_mode_respects_terminal_environment(monkeypatch) -> None:
    terminal = TerminalStream()
    redirected = RedirectedStream()
    monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.delenv('TERM', raising=False)

    assert color_enabled(stream=terminal)
    assert render('tty', fg=Color.GREEN, styles=(TextStyle.BOLD,), stream=terminal) == (
        '\033[32;1mtty\033[0m'
    )
    assert not color_enabled(stream=redirected)
    assert render('redirected', fg=Color.GREEN, styles=(TextStyle.BOLD,), stream=redirected) == 'redirected'

    monkeypatch.setenv('TERM', 'dumb')
    assert not color_enabled(stream=terminal)
    assert render('dumb', fg=Color.GREEN, styles=(TextStyle.BOLD,), stream=terminal) == 'dumb'

    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('NO_COLOR', '1')
    assert render(
        'no color',
        fg=Color.GREEN,
        bg=Color.BLUE,
        styles=(TextStyle.BOLD,),
        stream=terminal,
    ) == '\033[1mno color\033[0m'


def test_explicit_modes_override_auto_policy(monkeypatch) -> None:
    redirected = RedirectedStream()
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setenv('TERM', 'dumb')

    assert color_enabled(mode=ColorMode.ALWAYS, stream=redirected)
    assert render(
        'forced',
        fg=Color.GREEN,
        bg=Color.BLUE,
        styles=(TextStyle.BOLD,),
        mode=ColorMode.ALWAYS,
        stream=redirected,
    ) == '\033[32;44;1mforced\033[0m'
    assert not color_enabled(mode=ColorMode.NEVER, stream=TerminalStream())
    assert render(
        'disabled',
        fg=Color.GREEN,
        bg=Color.BLUE,
        styles=(TextStyle.BOLD,),
        mode=ColorMode.NEVER,
        stream=TerminalStream(),
    ) == 'disabled'


def test_import_does_not_initialize_windows_colorama(monkeypatch) -> None:
    calls: list[None] = []
    fake_colorama = SimpleNamespace(just_fix_windows_console=lambda: calls.append(None))
    monkeypatch.setattr(chalk.os, 'name', 'nt')
    monkeypatch.setitem(sys.modules, 'colorama', fake_colorama)

    spec = importlib.util.spec_from_file_location('chalk_import_probe', chalk.__file__)
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    assert calls == []


def test_windows_ansi_setup_is_lazy_and_idempotent(monkeypatch) -> None:
    calls: list[None] = []
    fake_colorama = SimpleNamespace(just_fix_windows_console=lambda: calls.append(None))
    monkeypatch.setattr(chalk.os, 'name', 'nt')
    monkeypatch.setattr(chalk, '_windows_ansi_enabled', False)
    monkeypatch.setitem(sys.modules, 'colorama', fake_colorama)

    assert render('plain', fg=Color.GREEN, mode=ColorMode.NEVER) == 'plain'
    assert calls == []

    assert render('first', fg=Color.GREEN, mode=ColorMode.ALWAYS) == '\033[32mfirst\033[0m'
    assert render('second', fg=Color.GREEN, mode=ColorMode.ALWAYS) == '\033[32msecond\033[0m'
    assert calls == [None]


def test_chalk_builder_snapshots_each_written_segment() -> None:
    chalk_builder = Chalk(mode=ColorMode.ALWAYS)

    assert (
        chalk_builder.color(Color.RED)
        .write('error')
        .bold()
        .write(': urgent')
        .color(Color.GREEN)
        .style()
        .write(' resolved')
    ) is chalk_builder
    assert str(chalk_builder) == (
        '\033[31merror\033[0m'
        '\033[31;1m: urgent\033[0m'
        '\033[32m resolved\033[0m'
    )
    assert chalk_builder.raw == 'error: urgent resolved'


def test_chalk_builder_supports_named_chalks_and_stream_policy() -> None:
    chalk_builder = Chalk().red('alert').underline().write(' attention').green().style().write(' done')

    assert chalk_builder.render(stream=RedirectedStream()) == 'alert attention done'


def test_chalk_preserves_constructor_and_text_writing_habits() -> None:
    chalk_builder = Chalk('first', Color.RED, styles=(TextStyle.BOLD,), mode=ColorMode.ALWAYS)

    assert (
        chalk_builder.text(' second')
        .use(TextStyle.UNDERLINE, fg_color=Color.GREEN, bg_color=Color.BLUE)
        .text(' third')
    ) is chalk_builder
    assert str(chalk_builder) == (
        '\033[31;1mfirst\033[0m'
        '\033[31;1m second\033[0m'
        '\033[32;44;1;4m third\033[0m'
    )


def test_legacy_chalk_color_factories_preserve_builder_behavior() -> None:
    assert str(RedChalk('error', mode=ColorMode.ALWAYS)) == '\033[31merror\033[0m'
    assert str(GreenChalk(mode=ColorMode.ALWAYS).bold('ready')) == '\033[32;1mready\033[0m'
    assert str(BrightGreenChalk('go', mode=ColorMode.ALWAYS)) == '\033[92mgo\033[0m'
    assert str(BoldChalk('important', mode=ColorMode.ALWAYS)) == '\033[1mimportant\033[0m'
