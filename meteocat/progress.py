import sys

from rich.console import Console
from rich.progress import (
    BarColumn,
    ProgressColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

progress_console = Console(stderr=True)
progress_disable = not sys.stderr.isatty()

PROGRESS_COLUMNS: tuple[ProgressColumn, ...] = (
    TextColumn('[progress.description]{task.description}'),
    BarColumn(),
    TextColumn('{task.completed}/{task.total}'),
    TaskProgressColumn(),
    TimeRemainingColumn(),
)
