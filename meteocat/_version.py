from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('meteocat')
except PackageNotFoundError:
    __version__ = 'unknown'
