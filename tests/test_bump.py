import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'bump.py'


def _load_bump() -> ModuleType:
    spec = importlib.util.spec_from_file_location('meteocat_bump_tests', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bump = _load_bump()


def _write_version(tmp_path: Path, version: str) -> None:
    (tmp_path / 'pyproject.toml').write_text(f'version = "{version}"\n')


def test_bumps_constant() -> None:
    assert {'patch', 'minor', 'major'} == bump.BUMPS


def test_default_patch_bump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_version(tmp_path, '1.1.2')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump'])
    bump.main()
    out = capsys.readouterr()
    assert out.out == 'Bumped version: 1.1.2 -> 1.1.3\n'
    assert out.err == ''
    assert (tmp_path / 'pyproject.toml').read_text() == 'version = "1.1.3"\n'


def test_explicit_patch_bump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_version(tmp_path, '0.9.0')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump', 'patch'])
    bump.main()
    out = capsys.readouterr()
    assert out.out == 'Bumped version: 0.9.0 -> 0.9.1\n'
    assert (tmp_path / 'pyproject.toml').read_text() == 'version = "0.9.1"\n'


def test_minor_bump_resets_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_version(tmp_path, '1.2.3')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump', 'minor'])
    bump.main()
    out = capsys.readouterr()
    assert out.out == 'Bumped version: 1.2.3 -> 1.3.0\n'
    assert (tmp_path / 'pyproject.toml').read_text() == 'version = "1.3.0"\n'


def test_major_bump_resets_minor_and_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_version(tmp_path, '1.2.3')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump', 'major'])
    bump.main()
    out = capsys.readouterr()
    assert out.out == 'Bumped version: 1.2.3 -> 2.0.0\n'
    assert (tmp_path / 'pyproject.toml').read_text() == 'version = "2.0.0"\n'


def test_invalid_bump_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_version(tmp_path, '1.0.0')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump', 'foo'])
    with pytest.raises(SystemExit) as exc:
        bump.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Invalid BUMP: foo (expected one of ['major', 'minor', 'patch'])" in err


def test_missing_version_line_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['bump'])
    with pytest.raises(SystemExit) as exc:
        bump.main()
    assert exc.value.code == 1
    assert 'Could not find version in pyproject.toml' in capsys.readouterr().err
