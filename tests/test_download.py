from pathlib import Path

import pytest
import requests

from meteocat.download import (
    _MAX_RETRIES,
    _download_background_tile,
    _download_radar_tile,
    _download_tile,
)


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b'') -> None:
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        raise requests.HTTPError


def test_download_tile_success_first_attempt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / 'out.png'
    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> FakeResponse:
        calls.append(url)
        return FakeResponse(200, b'data')

    monkeypatch.setattr('meteocat.download.requests.get', fake_get)
    monkeypatch.setattr('meteocat.download.sleep', lambda *_a: None)
    monkeypatch.setattr('meteocat.download.uniform', lambda _a, _b: 0)

    _download_tile('http://example.com/x.png', dest)

    assert dest.read_bytes() == b'data'
    assert len(calls) == 1


def test_download_tile_retry_then_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / 'out.png'
    states = [{'code': 500}, {'code': 200}]

    def fake_get(_url: str, **_kwargs: object) -> FakeResponse:
        state = states.pop(0)
        return FakeResponse(state['code'], b'data' if state['code'] == 200 else b'')

    monkeypatch.setattr('meteocat.download.requests.get', fake_get)
    monkeypatch.setattr('meteocat.download.sleep', lambda *_a: None)
    monkeypatch.setattr('meteocat.download.uniform', lambda _a, _b: 0)

    _download_tile('http://example.com/x.png', dest)

    assert dest.read_bytes() == b'data'


def test_download_tile_all_retries_with_response(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / 'out.png'
    calls: list[str] = []
    sleep_calls: list[int] = []

    def fake_get(url: str, **_kwargs: object) -> FakeResponse:
        calls.append(url)
        return FakeResponse(500, b'')

    monkeypatch.setattr('meteocat.download.requests.get', fake_get)
    monkeypatch.setattr('meteocat.download.sleep', lambda cap: sleep_calls.append(cap))
    monkeypatch.setattr('meteocat.download.uniform', lambda _a, _b: 0)

    with pytest.raises(requests.HTTPError):
        _download_tile('http://example.com/x.png', dest)

    assert len(calls) == _MAX_RETRIES
    assert len(sleep_calls) == _MAX_RETRIES


def test_download_tile_request_exception_then_runtime_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dest = tmp_path / 'out.png'

    def fake_get(_url: str, **_kwargs: object) -> FakeResponse:
        msg = 'boom'
        raise requests.RequestException(msg)

    monkeypatch.setattr('meteocat.download.requests.get', fake_get)
    monkeypatch.setattr('meteocat.download.sleep', lambda *_a: None)
    monkeypatch.setattr('meteocat.download.uniform', lambda _a, _b: 0)

    with pytest.raises(RuntimeError):
        _download_tile('http://example.com/x.png', dest)


def test_download_background_tile_url_and_dest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_download_tile(url: str, dest: Path) -> None:
        captured['url'] = url
        captured['dest'] = dest

    monkeypatch.setattr('meteocat.download._download_tile', fake_download_tile)

    _download_background_tile((510, 638, str(tmp_path)))

    assert 'GoogleMapsCompatible/10/' in captured['url']
    assert captured['dest'].name == 'background-09-00.png'


def test_download_radar_tile_url_and_dest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_download_tile(url: str, dest: Path) -> None:
        captured['url'] = url
        captured['dest'] = dest

    monkeypatch.setattr('meteocat.download._download_tile', fake_download_tile)

    _download_radar_tile((63, 79, str(tmp_path), '2026/01/01/12/00'))

    assert 'tiles/radar/2026/01/01/12/00/07/' in captured['url']
    assert captured['dest'].name == 'radar-1-0.png'
