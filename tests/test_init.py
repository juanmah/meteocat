import meteocat


def test_version_is_str_nonempty() -> None:
    assert isinstance(meteocat.__version__, str)
    assert meteocat.__version__ != ''


def test_all_equals_version_only() -> None:
    assert meteocat.__all__ == ['__version__']
