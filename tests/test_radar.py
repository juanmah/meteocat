from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from pathlib import Path

import pytest

from meteocat.radar import current_radar_date, fetch_radar


class FakeCanvas:
    def __init__(self) -> None:
        self.saved: Path | None = None

    def save(self, path: Path) -> None:
        self.saved = Path(path)


_fixed_now: datetime = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class _FakeDateTime:
    @classmethod
    def now(cls, _tz: tzinfo | None = None) -> datetime:
        return _fixed_now


def _install_fake_datetime(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    global _fixed_now
    _fixed_now = fixed
    monkeypatch.setattr('meteocat.radar.datetime', _FakeDateTime)


def _install_fake_radar_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download_radar_tile(args: tuple[int, int, str, str]) -> None:
        x, y, temp_dir, _date = args
        dest = Path(temp_dir) / f'radar-{abs(y - 80)}-{x - 63}.png'
        dest.write_bytes(b'fake')

    monkeypatch.setattr('meteocat.radar._download_radar_tile', fake_download_radar_tile)


def test_current_radar_date(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 20, 0, tzinfo=UTC))
    # now - 15 min = 12:05; minute 5 -> 5 // 6 * 6 = 0
    assert current_radar_date() == '2026/01/01/12/00'


def test_fetch_radar_default_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    canvas = FakeCanvas()
    cols: list[int] = []

    def fake_assemble(_tiles: list[Path], columns: int) -> FakeCanvas:
        cols.append(columns)
        return canvas

    _install_fake_radar_download(monkeypatch)
    monkeypatch.setattr('meteocat.radar._assemble_tiles', fake_assemble)
    radar_path = tmp_path / 'radar.png'
    monkeypatch.setattr('meteocat.radar._RADAR', radar_path)

    result = fetch_radar()

    assert result == radar_path
    assert canvas.saved == radar_path
    assert cols == [3]


def test_fetch_radar_provided_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    canvas = FakeCanvas()
    _install_fake_radar_download(monkeypatch)
    monkeypatch.setattr('meteocat.radar._assemble_tiles', lambda _tiles, **_kwargs: canvas)
    radar_path = tmp_path / 'radar.png'
    monkeypatch.setattr('meteocat.radar._RADAR', radar_path)

    result = fetch_radar('2026/01/01/12/00')

    assert result == radar_path
    assert canvas.saved == radar_path


def test_fetch_radar_wrong_tile_count_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    monkeypatch.setattr('meteocat.radar._download_radar_tile', lambda *_: None)
    monkeypatch.setattr('meteocat.radar._assemble_tiles', lambda _tiles, _columns: FakeCanvas())
    radar_path = tmp_path / 'radar.png'
    monkeypatch.setattr('meteocat.radar._RADAR', radar_path)

    with pytest.raises(SystemExit):
        fetch_radar()
