from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from rich.logging import RichHandler

from meteocat.logger import logger, setup


def _reset_handlers() -> None:
    logger.handlers.clear()


def test_logger_is_named_meteocat() -> None:
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'meteocat'


def test_setup_sets_level() -> None:
    _reset_handlers()
    setup(logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_setup_idempotent_when_handlers_present() -> None:
    _reset_handlers()
    setup(logging.INFO)
    count = len(logger.handlers)
    setup(logging.WARNING)
    assert len(logger.handlers) == count


def test_setup_tty_adds_rich_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_handlers()
    monkeypatch.setattr('sys.stderr.isatty', lambda: True)
    setup(logging.INFO)
    assert any(isinstance(h, RichHandler) for h in logger.handlers)


def test_setup_non_tty_adds_stream_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_handlers()
    monkeypatch.setattr('sys.stderr.isatty', lambda: False)
    setup(logging.INFO)
    from logging import StreamHandler

    assert any(isinstance(h, StreamHandler) and not isinstance(h, RichHandler) for h in logger.handlers)


def test_setup_debug_logs_command_and_cwd(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _reset_handlers()
    monkeypatch.setattr('sys.stderr.isatty', lambda: False)
    monkeypatch.setattr('sys.argv', ['meteocat', 'wallpaper'])
    with caplog.at_level(logging.DEBUG):
        setup(logging.DEBUG)
    assert 'Command:' in caplog.text
    assert 'Working directory:' in caplog.text
