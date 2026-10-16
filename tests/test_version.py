from __future__ import annotations

import importlib
import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

METEOCAT_VERSION_MODULE = 'meteocat._version'


def test_version_is_str() -> None:
    import meteocat._version as version_module

    assert isinstance(version_module.__version__, str)


def test_version_falls_back_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.metadata as metadata_module

    def fake_version(_distribution: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(metadata_module, 'version', fake_version)

    module = importlib.import_module(METEOCAT_VERSION_MODULE)
    importlib.reload(module)

    assert module.__version__ == 'unknown'
