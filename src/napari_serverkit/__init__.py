from ._version import version as __version__
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from napari_serverkit._widget import ServerKitWidget