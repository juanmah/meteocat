from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

import meteocat.progress as progress_module
from meteocat.progress import PROGRESS_COLUMNS, progress_console


def test_progress_console_is_console_stderr() -> None:
    from rich.console import Console

    assert isinstance(progress_console, Console)
    assert progress_console.stderr is True


def test_progress_columns_types() -> None:
    from rich.progress import (
        BarColumn,
        ProgressColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    assert isinstance(PROGRESS_COLUMNS, tuple)
    expected = [TextColumn, BarColumn, TextColumn, TaskProgressColumn, TimeRemainingColumn]
    assert len(PROGRESS_COLUMNS) == len(expected)
    for column, expected_type in zip(PROGRESS_COLUMNS, expected, strict=True):
        assert isinstance(column, ProgressColumn)
        assert isinstance(column, expected_type)


def test_progress_disable_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('sys.stderr.isatty', lambda: True)
    importlib.reload(progress_module)
    assert progress_module.progress_disable is False


def test_progress_disable_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('sys.stderr.isatty', lambda: False)
    importlib.reload(progress_module)
    assert progress_module.progress_disable is True
